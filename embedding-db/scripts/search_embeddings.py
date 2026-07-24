import argparse
import os
import sys
from pathlib import Path

import numpy as np
import psycopg
import torch
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


EXPECTED_DIMENSION = 512
MODEL_NAME = "openai/clip-vit-base-patch32"


def validate_top_k(top_k: int) -> int:
    if not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top-k must be an integer greater than or equal to 1.")
    return top_k


def validate_query_vector(vector) -> np.ndarray:
    array = np.asarray(vector, dtype=np.float32)

    if array.ndim != 1:
        raise ValueError("Query vector must be one-dimensional.")

    if array.shape[0] != EXPECTED_DIMENSION:
        raise ValueError(
            f"Query vector must have 512 dimensions: "
            f"received {array.shape[0]}"
        )

    if not np.isfinite(array).all():
        raise ValueError(
            "Query vector contains NaN or infinity values."
        )

    return array


def distance_to_similarity(distance: float) -> float:
    return 1.0 - float(distance)


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(
        description="CLIP embedding based video segment search"
    )

    search_group = parser.add_mutually_exclusive_group(
        required=True
    )

    search_group.add_argument(
        "--text",
        type=str,
        help="Natural-language search query",
    )

    search_group.add_argument(
        "--image",
        type=str,
        help="Image file path",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to return",
    )

    args = parser.parse_args(argv)
    args.top_k = validate_top_k(args.top_k)
    return args


def build_connection_string() -> str:
    required_variables = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ]

    missing = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing:
        raise ValueError(
            "Missing DB environment variables: "
            + ", ".join(missing)
        )

    return (
        f"host={os.environ['POSTGRES_HOST']} "
        f"port={os.environ['POSTGRES_PORT']} "
        f"user={os.environ['POSTGRES_USER']} "
        f"password={os.environ['POSTGRES_PASSWORD']} "
        f"dbname={os.environ['POSTGRES_DB']}"
    )


def normalize_vector(vector) -> np.ndarray:
    array = np.asarray(vector, dtype=np.float32)
    norm = np.linalg.norm(array)

    if norm == 0:
        raise ValueError("0 \ubca1\ud130\ub294 \uc815\uaddc\ud654\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.")

    return (array / norm).astype(np.float32)


def validate_image_path(image_path: str) -> Path:
    path = Path(image_path)

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(
            f"\uc774\ubbf8\uc9c0 \ud30c\uc77c\uc744 \ucc3e\uc744 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4: {path}"
        )

    return path


def extract_clip_features(features, projection):
    if not hasattr(features, "pooler_output"):
        return features

    pooled = features.pooler_output

    if pooled.shape[-1] == EXPECTED_DIMENSION:
        return pooled

    if projection is None:
        raise ValueError(
            "Projection layer is required for non-512-dimensional features."
        )

    return projection(pooled)


def encode_text(
    text: str,
    model,
    processor,
    device: str,
) -> np.ndarray:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Search text must not be empty.")

    inputs = processor(
        text=[text],
        return_tensors="pt",
        padding=True,
        truncation=True,
    )

    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        features = model.get_text_features(**inputs)
        features = extract_clip_features(
            features,
            getattr(model, "text_projection", None),
        )

    vector = features.detach().cpu().numpy()[0]
    vector = normalize_vector(vector)

    return validate_query_vector(vector)


def encode_image(
    image_path,
    model,
    processor,
    device: str,
) -> np.ndarray:
    path = validate_image_path(str(image_path))

    with Image.open(path) as image:
        rgb_image = image.convert("RGB")

        inputs = processor(
            images=rgb_image,
            return_tensors="pt",
        )

    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        features = model.get_image_features(**inputs)
        features = extract_clip_features(
            features,
            getattr(model, "visual_projection", None),
        )

    vector = features.detach().cpu().numpy()[0]
    vector = normalize_vector(vector)

    return validate_query_vector(vector)


def search_database(
    query_vector,
    search_mode: str,
    top_k: int,
) -> list[dict]:
    if search_mode == "text":
        embedding_column = "text_embedding"
    elif search_mode == "image":
        embedding_column = "image_embedding"
    else:
        raise ValueError(
            f"\uc9c0\uc6d0\ud558\uc9c0 \uc54a\ub294 \uac80\uc0c9 \ubaa8\ub4dc\uc785\ub2c8\ub2e4: {search_mode}"
        )

    vector = validate_query_vector(query_vector)
    limit = validate_top_k(top_k)
    connection_string = build_connection_string()

    query = f"""
        SELECT
            vs.segment_id,
            vs.spot_name,
            vs.video_id,
            vs.start_time,
            vs.end_time,
            se.{embedding_column} <=> %s AS cosine_distance,
            vs.keyframe_path,
            vs.summary
        FROM segment_embeddings AS se
        JOIN video_segments AS vs
            ON vs.segment_id = se.segment_id
        WHERE se.{embedding_column} IS NOT NULL
        ORDER BY se.{embedding_column} <=> %s
        LIMIT %s
    """

    with psycopg.connect(connection_string) as connection:
        register_vector(connection)

        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (vector, vector, limit),
            )
            rows = cursor.fetchall()

    results = []

    for row in rows:
        results.append(
            {
                "segment_id": row[0],
                "spot_name": row[1],
                "video_id": row[2],
                "start_time": row[3],
                "end_time": row[4],
                "similarity": distance_to_similarity(
                    float(row[5])
                ),
                "keyframe_path": row[6],
                "summary": row[7],
            }
        )

    return results


def print_results(results: list[dict]) -> None:
    if not results:
        print(
            "\uac80\uc0c9 \uacb0\uacfc\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."
        )
        return

    print()
    print("=" * 70)
    print(f"Search results: {len(results)}")
    print("=" * 70)

    for rank, result in enumerate(results, start=1):
        similarity = float(result["similarity"])

        print(f"[{rank}]")
        print(f"segment_id   : {result['segment_id']}")
        print(f"spot_name    : {result['spot_name'] or '-'}")
        print(f"video_id     : {result['video_id']}")
        print(
            f"time          : "
            f"{result['start_time']:.2f}s ~ "
            f"{result['end_time']:.2f}s"
        )
        print(f"similarity    : {similarity:.4f}")
        print(
            f"keyframe_path: "
            f"{result['keyframe_path'] or '-'}"
        )
        print(f"summary       : {result['summary'] or '-'}")
        print("-" * 70)


def load_clip_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = CLIPModel.from_pretrained(MODEL_NAME)
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)

    model = model.to(device)
    model.eval()

    return model, processor, device


def main(argv=None) -> None:
    embedding_root = Path(__file__).resolve().parent.parent
    env_path = embedding_root / ".env"

    load_dotenv(env_path)

    args = parse_arguments(argv)

    print("Loading CLIP model...")
    model, processor, device = load_clip_model()
    print(f"Device: {device}")

    if args.text is not None:
        search_mode = "text"
        print(f'Text query: "{args.text}"')

        query_vector = encode_text(
            args.text,
            model,
            processor,
            device,
        )
    else:
        search_mode = "image"
        image_path = validate_image_path(args.image)
        print(f"Image query: {image_path}")

        query_vector = encode_image(
            image_path,
            model,
            processor,
            device,
        )

    print(f"Query vector dimension: {query_vector.shape[0]}")
    print(f"Searching top {args.top_k} results...")

    results = search_database(
        query_vector,
        search_mode,
        args.top_k,
    )

    print_results(results)


if __name__ == "__main__":
    try:
        main()
    except (
        FileNotFoundError,
        ValueError,
        psycopg.Error,
    ) as error:
        print(f"[Execution failed] {error}")
        sys.exit(1)