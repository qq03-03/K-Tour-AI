import json
import os
import sys
from pathlib import Path

import numpy as np
import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb


EXPECTED_DIMENSION = 512


def load_json(path: Path) -> list[dict]:
    """UTF-8 JSON 배열을 읽는다."""
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(f"JSON 최상위 구조는 배열이어야 합니다: {path}")

    return data


def unique_strings(values) -> list[str]:
    """문자열 배열에서 빈 값, unknown, 중복을 제거한다."""
    if not isinstance(values, list):
        return []

    result = []
    seen = set()

    for value in values:
        if not isinstance(value, str):
            continue

        cleaned = value.strip()

        if not cleaned or cleaned.lower() == "unknown":
            continue

        key = cleaned.lower()

        if key not in seen:
            seen.add(key)
            result.append(cleaned)

    return result


def optional_text(value):
    """빈 문자열과 unknown을 DB의 NULL로 변환한다."""
    if not isinstance(value, str):
        return None

    cleaned = value.strip()

    if not cleaned or cleaned.lower() == "unknown":
        return None

    return cleaned


def validate_vector(vector, segment_id: str, field_name: str) -> np.ndarray:
    """벡터가 512차원이고 유한값으로 구성됐는지 확인한다."""
    array = np.asarray(vector, dtype=np.float32)

    if array.ndim != 1:
        raise ValueError(
            f"{segment_id}의 {field_name}은 1차원 배열이어야 합니다."
        )

    if len(array) != EXPECTED_DIMENSION:
        raise ValueError(
            f"{segment_id}의 {field_name} 차원 오류: "
            f"{len(array)} != {EXPECTED_DIMENSION}"
        )

    if not np.isfinite(array).all():
        raise ValueError(
            f"{segment_id}의 {field_name}에 NaN 또는 무한대가 있습니다."
        )

    return array


def build_connection_string() -> str:
    """환경변수로 PostgreSQL 접속 문자열을 만든다."""
    required_variables = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ]

    missing = [
        name
        for name in required_variables
        if not os.getenv(name)
    ]

    if missing:
        raise ValueError(
            "DB 환경변수가 없습니다: " + ", ".join(missing)
        )

    return (
        f"host={os.environ['POSTGRES_HOST']} "
        f"port={os.environ['POSTGRES_PORT']} "
        f"user={os.environ['POSTGRES_USER']} "
        f"password={os.environ['POSTGRES_PASSWORD']} "
        f"dbname={os.environ['POSTGRES_DB']}"
    )


def main() -> None:
    embedding_root = Path(__file__).resolve().parent.parent

    metadata_path = (
        embedding_root
        / "metadata"
        / "metadata.json"
    )

    embeddings_path = (
        embedding_root
        / "output"
        / "embeddings"
        / "segment_embeddings.json"
    )

    env_path = embedding_root / ".env"
    load_dotenv(env_path)

    metadata_list = load_json(metadata_path)
    embedding_list = load_json(embeddings_path)

    metadata_by_segment = {
        item["segment_id"]: item
        for item in metadata_list
    }

    embeddings_by_segment = {
        item["segment_id"]: item
        for item in embedding_list
    }

    metadata_ids = set(metadata_by_segment)
    embedding_ids = set(embeddings_by_segment)

    if metadata_ids != embedding_ids:
        missing_embeddings = sorted(metadata_ids - embedding_ids)
        missing_metadata = sorted(embedding_ids - metadata_ids)

        raise ValueError(
            "메타데이터와 임베딩의 segment_id가 일치하지 않습니다. "
            f"임베딩 누락={missing_embeddings}, "
            f"메타데이터 누락={missing_metadata}"
        )

    connection_string = build_connection_string()

    inserted_videos = set()
    processed_segments = 0

    print(f"적재 대상: {len(metadata_list)}건")
    print("PostgreSQL 연결 중...")

    with psycopg.connect(connection_string) as connection:
        register_vector(connection)

        with connection.cursor() as cursor:
            for segment_id in sorted(metadata_ids):
                metadata = metadata_by_segment[segment_id]
                embedding = embeddings_by_segment[segment_id]

                video_id = metadata["video_id"]
                spot_name = optional_text(metadata.get("spot_name"))
                region = optional_text(metadata.get("place_name"))
                description = optional_text(metadata.get("description"))

                mood_tags = unique_strings(metadata.get("mood", []))
                scene_elements = unique_strings(
                    metadata.get("scene_elements", [])
                )
                activities = unique_strings(
                    metadata.get("activity", [])
                )

                tags = unique_strings(scene_elements + activities)

                season = optional_text(metadata.get("season"))
                season_tags = [season] if season else []

                search_text = optional_text(
                    embedding.get("search_text")
                )

                text_embedding = validate_vector(
                    embedding.get("text_embedding"),
                    segment_id,
                    "text_embedding",
                )

                image_embedding = validate_vector(
                    embedding.get("image_embedding"),
                    segment_id,
                    "image_embedding",
                )

                if video_id not in inserted_videos:
                    cursor.execute(
                        """
                        INSERT INTO videos (
                            video_id,
                            title,
                            description,
                            video_path,
                            language
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (video_id)
                        DO UPDATE SET
                            title = EXCLUDED.title,
                            description = EXCLUDED.description,
                            video_path = EXCLUDED.video_path,
                            language = EXCLUDED.language
                        """,
                        (
                            video_id,
                            f"{video_id} 관광 영상",
                            f"{video_id}의 VLM 기반 관광 영상",
                            None,
                            "ko",
                        ),
                    )

                    inserted_videos.add(video_id)

                cursor.execute(
                    """
                    INSERT INTO video_segments (
                        segment_id,
                        video_id,
                        spot_id,
                        start_time,
                        end_time,
                        caption,
                        summary,
                        tags,
                        mood_tags,
                        season_tags,
                        region,
                        spot_name,
                        keyframe_path,
                        metadata
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (segment_id)
                    DO UPDATE SET
                        video_id = EXCLUDED.video_id,
                        spot_id = EXCLUDED.spot_id,
                        start_time = EXCLUDED.start_time,
                        end_time = EXCLUDED.end_time,
                        caption = EXCLUDED.caption,
                        summary = EXCLUDED.summary,
                        tags = EXCLUDED.tags,
                        mood_tags = EXCLUDED.mood_tags,
                        season_tags = EXCLUDED.season_tags,
                        region = EXCLUDED.region,
                        spot_name = EXCLUDED.spot_name,
                        keyframe_path = EXCLUDED.keyframe_path,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        segment_id,
                        video_id,
                        None,
                        metadata["start_time"],
                        metadata["end_time"],
                        description,
                        search_text,
                        tags,
                        mood_tags,
                        season_tags,
                        region,
                        spot_name,
                        metadata["keyframe_path"],
                        Jsonb(metadata),
                    ),
                )

                cursor.execute(
                    """
                    INSERT INTO segment_embeddings (
                        segment_id,
                        text_embedding,
                        image_embedding
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (segment_id)
                    DO UPDATE SET
                        text_embedding = EXCLUDED.text_embedding,
                        image_embedding = EXCLUDED.image_embedding,
                        created_at = CURRENT_TIMESTAMP
                    """,
                    (
                        segment_id,
                        text_embedding,
                        image_embedding,
                    ),
                )

                processed_segments += 1
                print(
                    f"[{processed_segments}/{len(metadata_ids)}] "
                    f"저장 완료: {segment_id}"
                )

        connection.commit()

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM videos")
            video_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM video_segments")
            segment_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM segment_embeddings")
            embedding_count = cursor.fetchone()[0]

    print("-" * 60)
    print("DB 적재 완료")
    print(f"videos 전체 건수: {video_count}")
    print(f"video_segments 전체 건수: {segment_count}")
    print(f"segment_embeddings 전체 건수: {embedding_count}")


if __name__ == "__main__":
    try:
        main()
    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
        psycopg.Error,
    ) as error:
        print(f"[실행 실패] {error}")
        sys.exit(1)
