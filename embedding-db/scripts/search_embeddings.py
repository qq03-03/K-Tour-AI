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

def resolve_candidate_k(
    top_k: int,
    candidate_k: int | None,
) -> int:
    """candidate_k 기본값과 입력값을 검증한다."""
    validated_top_k = validate_top_k(top_k)

    if candidate_k is None:
        return max(validated_top_k * 5, 50)

    if not isinstance(candidate_k, int) or candidate_k < 1:
        raise ValueError(
            "candidate-k must be an integer greater than or equal to 1."
        )

    return candidate_k

def normalize_filter_values(values) -> list[str]:
    """필터 입력을 중복 없는 문자열 리스트로 정리한다."""
    if values is None:
        return []

    if isinstance(values, str):
        values = [values]

    if not isinstance(values, (list, tuple, set)):
        return []

    result = []
    seen = set()

    for value in values:
        if not isinstance(value, str):
            continue

        cleaned = value.strip()

        if not cleaned:
            continue

        key = cleaned.lower()

        if key not in seen:
            seen.add(key)
            result.append(cleaned)

    return result

def build_filter_clause(
    filters: dict | None,
) -> tuple[str, list, dict]:
    """하드 필터를 안전한 SQL WHERE 조건으로 변환한다."""
    allowed_fields = {
        "place_id": "vs.place_id",
        "drama_title": "vs.drama_title",
        "region": "vs.region",
        "city": "vs.city",
        "season": "vs.season",
        "time_of_day": "vs.time_of_day",
    }

    filters = filters or {}

    clauses = []
    params = []
    applied_filters = {}

    for field, column in allowed_fields.items():
        values = normalize_filter_values(
            filters.get(field)
        )

        if not values:
            continue

        clauses.append(
            f"{column} = ANY(%s)"
        )
        params.append(values)
        applied_filters[field] = values

    if not clauses:
        return "", [], {}

    return (
        " AND " + " AND ".join(clauses),
        params,
        applied_filters,
    )

def search_text_candidates(
    cursor,
    query_vector,
    candidate_k: int,
    filters: dict | None = None,
) -> list[dict]:
    """필터 적용 후 text embedding 기준 후보 SCENE을 검색한다."""
    vector = validate_query_vector(query_vector)
    limit = resolve_candidate_k(1, candidate_k)

    filter_clause, filter_params, _ = build_filter_clause(
        filters
    )

    query = f"""
        SELECT
            vs.source_segment_id,
            vs.segment_id,
            sk.keyframe_id,
            sk.keyframe_path,
            vs.place_id,
            vs.place_name,
            vs.region,
            vs.city,
            vs.drama_title,
            vs.season,
            vs.time_of_day,
            sk.description,
            sk.mood,
            sk.activity,
            sk.scene_elements,
            sk.k_culture_elements,
            vs.start_time,
            vs.end_time,
            se.text_embedding <=> %s AS text_distance
        FROM video_segments AS vs

        JOIN segment_embeddings AS se
            ON se.segment_id = vs.segment_id

        LEFT JOIN segment_keyframes AS sk
            ON sk.segment_id = vs.segment_id

        WHERE se.text_embedding IS NOT NULL
        {filter_clause}

        ORDER BY text_distance ASC
        LIMIT %s
    """

    params = [
        vector,
        *filter_params,
        limit,
    ]

    cursor.execute(
        query,
        params,
    )

    rows = cursor.fetchall()
    results = []

    for rank, row in enumerate(rows, start=1):
        results.append(
            {
                "source_segment_id": row[0],
                "segment_id": row[1],
                "keyframe_id": row[2],
                "keyframe_path": row[3],
                "place_id": row[4],
                "place_name": row[5],
                "region": row[6],
                "city": row[7],
                "drama_title": row[8],
                "season": row[9],
                "time_of_day": row[10],
                "description": row[11],
                "mood": row[12],
                "activity": row[13],
                "scene_elements": row[14],
                "k_culture_elements": row[15],
                "start_time": row[16],
                "end_time": row[17],
                "text_score": distance_to_similarity(
                    row[18]
                ),
                "text_rank": rank,
                "image_score": None,
                "image_rank": None,
            }
        )

    return results

def search_image_candidates(
    cursor,
    query_vector,
    candidate_k: int,
    filters: dict | None = None,
) -> list[dict]:
    """필터 적용 후 image embedding 기준 후보 SCENE을 검색한다."""
    vector = validate_query_vector(query_vector)
    limit = resolve_candidate_k(1, candidate_k)

    filter_clause, filter_params, _ = build_filter_clause(
        filters
    )

    query = f"""
        SELECT
            vs.source_segment_id,
            vs.segment_id,
            sk.keyframe_id,
            sk.keyframe_path,
            vs.place_id,
            vs.place_name,
            vs.region,
            vs.city,
            vs.drama_title,
            vs.season,
            vs.time_of_day,
            sk.description,
            sk.mood,
            sk.activity,
            sk.scene_elements,
            sk.k_culture_elements,
            vs.start_time,
            vs.end_time,
            ke.image_embedding <=> %s AS image_distance
        FROM video_segments AS vs

        JOIN segment_keyframes AS sk
            ON sk.segment_id = vs.segment_id

        JOIN keyframe_embeddings AS ke
            ON ke.keyframe_id = sk.keyframe_id

        WHERE ke.image_embedding IS NOT NULL
        {filter_clause}

        ORDER BY image_distance ASC
        LIMIT %s
    """

    params = [
        vector,
        *filter_params,
        limit,
    ]

    cursor.execute(
        query,
        params,
    )

    rows = cursor.fetchall()
    results = []

    for rank, row in enumerate(rows, start=1):
        results.append(
            {
                "source_segment_id": row[0],
                "segment_id": row[1],
                "keyframe_id": row[2],
                "keyframe_path": row[3],
                "place_id": row[4],
                "place_name": row[5],
                "region": row[6],
                "city": row[7],
                "drama_title": row[8],
                "season": row[9],
                "time_of_day": row[10],
                "description": row[11],
                "mood": row[12],
                "activity": row[13],
                "scene_elements": row[14],
                "k_culture_elements": row[15],
                "start_time": row[16],
                "end_time": row[17],
                "text_score": None,
                "text_rank": None,
                "image_score": distance_to_similarity(
                    row[18]
                ),
                "image_rank": rank,
            }
        )

    return results

def merge_candidate_results(
    text_results: list[dict],
    image_results: list[dict],
) -> list[dict]:
    """text/image 후보를 segment_id 기준으로 병합한다."""
    merged = {}

    for item in text_results:
        segment_id = item["segment_id"]
        merged[segment_id] = dict(item)

    for item in image_results:
        segment_id = item["segment_id"]

        if segment_id not in merged:
            merged[segment_id] = dict(item)
            continue

        merged_item = merged[segment_id]

        merged_item["image_score"] = item.get(
            "image_score"
        )
        merged_item["image_rank"] = item.get(
            "image_rank"
        )

    return list(merged.values())

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

    parser.add_argument(
    "--candidate-k",
    type=int,
    default=None,
    help="Number of candidates to retrieve per modality",
    )

    parser.add_argument(
        "--place-id",
        action="append",
        default=None,
    )

    parser.add_argument(
        "--drama-title",
        action="append",
        default=None,
    )

    parser.add_argument(
        "--region",
        action="append",
        default=None,
    )

    parser.add_argument(
        "--city",
        action="append",
        default=None,
    )

    parser.add_argument(
        "--season",
        action="append",
        default=None,
    )

    parser.add_argument(
        "--time-of-day",
        action="append",
        default=None,
    )

    args = parser.parse_args(argv)
    args.top_k = validate_top_k(args.top_k)
    args.candidate_k = resolve_candidate_k(
        args.top_k,
        args.candidate_k,
    )
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
    top_k: int = 5,
    candidate_k: int | None = None,
    filters: dict | None = None,
) -> dict:
    """text/image 후보를 각각 검색한 뒤 SCENE 단위로 병합한다."""
    vector = validate_query_vector(query_vector)

    validated_top_k = validate_top_k(top_k)

    resolved_candidate_k = resolve_candidate_k(
        validated_top_k,
        candidate_k,
    )

    _, _, applied_filters = build_filter_clause(
        filters
    )

    connection_string = build_connection_string()

    with psycopg.connect(
        connection_string
    ) as connection:
        register_vector(connection)

        with connection.cursor() as cursor:
            text_results = search_text_candidates(
                cursor=cursor,
                query_vector=vector,
                candidate_k=resolved_candidate_k,
                filters=filters,
            )

            image_results = search_image_candidates(
                cursor=cursor,
                query_vector=vector,
                candidate_k=resolved_candidate_k,
                filters=filters,
            )

    results = merge_candidate_results(
        text_results,
        image_results,
    )

    return {
        "applied_filters": applied_filters,
        "result_count": len(results),
        "candidate_k": resolved_candidate_k,
        "results": results,
    }

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
            f"keyframe_path : "
            f"{item.get('keyframe_path')}"
        )

        print(
            f"summary        : "
            f"{item.get('summary')}"
        )

        print("-" * 70)

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
                f"source_segment_id : "
                f"{item.get('source_segment_id')}"
            )

            print(
                f"segment_id        : "
                f"{item.get('segment_id')}"
            )

            print(
                f"keyframe_id       : "
                f"{item.get('keyframe_id')}"
            )

            print(
                f"keyframe_path     : "
                f"{item.get('keyframe_path')}"
            )

            print(
                f"place_id          : "
                f"{item.get('place_id')}"
            )

            print(
                f"place_name        : "
                f"{item.get('place_name')}"
            )

            print(
                f"region            : "
                f"{item.get('region')}"
            )

            print(
                f"city              : "
                f"{item.get('city')}"
            )

            print(
                f"drama_title       : "
                f"{item.get('drama_title')}"
            )

            print(
                f"season            : "
                f"{item.get('season')}"
            )

            print(
                f"time_of_day       : "
                f"{item.get('time_of_day')}"
            )

            print(
                f"description       : "
                f"{item.get('description')}"
            )

            print(
                f"mood              : "
                f"{item.get('mood')}"
            )

            print(
                f"activity          : "
                f"{item.get('activity')}"
            )

            print(
                f"scene_elements    : "
                f"{item.get('scene_elements')}"
            )

            print(
                f"k_culture_elements: "
                f"{item.get('k_culture_elements')}"
            )

            start_time = item.get("start_time")
            end_time = item.get("end_time")

            print(
                f"time              : "
                f"{start_time}s ~ {end_time}s"
            )

            text_score = item.get("text_score")
            image_score = item.get("image_score")

            print(
                f"text_score        : "
                f"{text_score if text_score is not None else None}"
            )

            print(
                f"image_score       : "
                f"{image_score if image_score is not None else None}"
            )

            print(
                f"text_rank         : "
                f"{item.get('text_rank')}"
            )

            print(
                f"image_rank        : "
                f"{item.get('image_rank')}"
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

    filters = {
        "place_id": args.place_id,
        "drama_title": args.drama_title,
        "region": args.region,
        "city": args.city,
        "season": args.season,
        "time_of_day": args.time_of_day,
    }

    response = search_database(
        query_vector=query_vector,
        top_k=args.top_k,
        candidate_k=args.candidate_k,
        filters=filters,
    )

    print(
        f"Applied filters: "
        f"{response['applied_filters']}"
    )

    print(
        f"Candidate count: "
        f"{response['result_count']}"
    )

    print(
        f"Candidate k: "
        f"{response['candidate_k']}"
    )

    print_results(
        response["results"]
    )



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