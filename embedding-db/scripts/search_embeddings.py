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
    if search_mode not in {"text", "image"}:
        raise ValueError(
            f"지원하지 않는 검색 모드입니다: {search_mode}"
        )

    vector = validate_query_vector(query_vector)
    limit = validate_top_k(top_k)
    connection_string = build_connection_string()

    order_column = (
        "text_distance"
        if search_mode == "text"
        else "image_distance"
    )

    query = f"""
        SELECT
            vs.segment_id,
            best_keyframe.keyframe_id,
            best_keyframe.keyframe_path,
            vs.place_id,
            vs.region,
            vs.spot_name,
            vs.drama_title,

            best_keyframe.description,
            best_keyframe.time_of_day,
            best_keyframe.mood,
            best_keyframe.activity,
            best_keyframe.scene_elements,

            vs.video_id,
            vs.start_time,
            vs.end_time,

            se.text_embedding <=> %s
                AS text_distance,

            best_keyframe.image_distance,

            vs.summary

        FROM video_segments AS vs

        JOIN segment_embeddings AS se
            ON se.segment_id = vs.segment_id

        JOIN LATERAL (
            SELECT
                sk.keyframe_id,
                sk.keyframe_path,
                sk.description,
                sk.time_of_day,
                sk.mood,
                sk.activity,
                sk.scene_elements,

                ke.image_embedding <=> %s
                    AS image_distance

            FROM segment_keyframes AS sk

            JOIN keyframe_embeddings AS ke
                ON ke.keyframe_id = sk.keyframe_id

            WHERE sk.segment_id = vs.segment_id
              AND ke.image_embedding IS NOT NULL

            ORDER BY image_distance
            LIMIT 1

        ) AS best_keyframe
            ON TRUE

        WHERE se.text_embedding IS NOT NULL

        ORDER BY {order_column}
        LIMIT %s
    """

    with psycopg.connect(connection_string) as connection:
        register_vector(connection)

        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    vector,
                    vector,
                    limit,
                ),
            )

            rows = cursor.fetchall()

    results = []

    for row in rows:
        text_score = distance_to_similarity(
            float(row[15])
        )

        image_score = distance_to_similarity(
            float(row[16])
        )

        similarity = (
            text_score
            if search_mode == "text"
            else image_score
        )

        results.append(
            {
                "segment_id": row[0],
                "keyframe_id": row[1],
                "keyframe_path": row[2],

                "place_id": row[3],
                "region": row[4],
                "spot_name": row[5],
                "drama_title": row[6],

                "description": row[7],
                "time_of_day": row[8],
                "mood": row[9],
                "activity": row[10],
                "scene_elements": row[11],

                "video_id": row[12],
                "start_time": row[13],
                "end_time": row[14],

                "text_score": text_score,
                "image_score": image_score,
                "similarity": similarity,

                "summary": row[17],
            }
        )

    return results

def print_results(results: list[dict]) -> None:
    if not results:
        print("검색 결과가 없습니다.")
        return

    print()
    print("=" * 70)
    print(f"Search results: {len(results)}")
    print("=" * 70)

    for index, item in enumerate(
        results,
        start=1,
    ):
        print(f"[{index}]")

        print(
            f"segment_id    : "
            f"{item['segment_id']}"
        )

        print(
            f"keyframe_id   : "
            f"{item.get('keyframe_id')}"
        )

        print(
            f"place_id      : "
            f"{item.get('place_id')}"
        )

        print(
            f"region        : "
            f"{item.get('region')}"
        )

        print(
            f"spot_name     : "
            f"{item.get('spot_name')}"
        )

        print(f"drama_title   : {item.get('drama_title')}")
        print(f"description   : {item.get('description')}")
        print(f"time_of_day   : {item.get('time_of_day')}")
        print(f"mood          : {item.get('mood')}")
        print(f"activity      : {item.get('activity')}")
        print(f"scene_elements: {item.get('scene_elements')}")

        print(
            f"video_id      : "
            f"{item.get('video_id')}"
        )

        print(
            "time           : "
            f"{item.get('start_time', 0.0):.2f}s "
            "~ "
            f"{item.get('end_time', 0.0):.2f}s"
        )

        print(
            f"text_score     : "
            f"{item.get('text_score', 0.0):.4f}"
        )

        print(
            f"image_score    : "
            f"{item.get('image_score', 0.0):.4f}"
        )

        print(
            f"similarity     : "
            f"{item.get('similarity', 0.0):.4f}"
        )

        print(
            f"keyframe_path : "
            f"{item.get('keyframe_path')}"
        )

        print(
            f"summary        : "
            f"{item.get('summary')}"
        )

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