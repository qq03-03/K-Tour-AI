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


def validate_vector(
    vector,
    segment_id: str,
    field_name: str,
) -> list[float]:
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

    return array.astype(float).tolist()
def prepare_records(
    metadata_list: list[dict],
    segment_embedding_list: list[dict],
    keyframe_embedding_list: list[dict],
) -> dict[str, list[dict]]:
    """DB 적재용 segment/keyframe 레코드를 준비한다."""

    metadata_by_segment = {}

    for item in metadata_list:
        segment_id = item["segment_id"]

        metadata_by_segment.setdefault(
            segment_id,
            [],
        ).append(item)

    segment_embeddings_by_id = {
        item["segment_id"]: item
        for item in segment_embedding_list
    }

    metadata_segment_ids = set(metadata_by_segment)
    embedding_segment_ids = set(
        segment_embeddings_by_id
    )

    if metadata_segment_ids != embedding_segment_ids:
        missing_embeddings = sorted(
            metadata_segment_ids
            - embedding_segment_ids
        )

        missing_metadata = sorted(
            embedding_segment_ids
            - metadata_segment_ids
        )

        raise ValueError(
            "segment metadata와 embedding이 "
            "일치하지 않습니다. "
            f"embedding 누락={missing_embeddings}, "
            f"metadata 누락={missing_metadata}"
        )

    metadata_by_keyframe_path = {
        item["keyframe_path"]: item
        for item in metadata_list
    }

    keyframe_embeddings_by_path = {
        item["keyframe_path"]: item
        for item in keyframe_embedding_list
    }

    metadata_keyframe_paths = set(
        metadata_by_keyframe_path
    )

    embedding_keyframe_paths = set(
        keyframe_embeddings_by_path
    )

    if (
        metadata_keyframe_paths
        != embedding_keyframe_paths
    ):
        missing_embeddings = sorted(
            metadata_keyframe_paths
            - embedding_keyframe_paths
        )

        missing_metadata = sorted(
            embedding_keyframe_paths
            - metadata_keyframe_paths
        )

        raise ValueError(
            "keyframe metadata와 embedding이 "
            "일치하지 않습니다. "
            f"embedding 누락={missing_embeddings}, "
            f"metadata 누락={missing_metadata}"
        )

    segments = []

    for segment_id in sorted(
        metadata_segment_ids
    ):
        items = metadata_by_segment[segment_id]
        first_item = items[0]

        embedding = segment_embeddings_by_id[
            segment_id
        ]

        text_embedding = validate_vector(
            embedding.get("text_embedding"),
            segment_id,
            "text_embedding",
        )

        segments.append(
            {
                "segment_id": segment_id,
                "video_id": first_item["video_id"],
                "place_id": optional_text(
                    first_item.get("place_id")
                ),
                "place_name": optional_text(
                    first_item.get("place_name")
                ),
                "spot_name": optional_text(
                    first_item.get("spot_name")
                ),
                "region": optional_text(
                    first_item.get("region")
                ),
                "drama_title": optional_text(
                    first_item.get("drama_title")
                ),
                "start_time": first_item.get(
                    "start_time"
                ),
                "end_time": first_item.get(
                    "end_time"
                ),
                "search_text": optional_text(
                    embedding.get("search_text")
                ),
                "text_embedding": text_embedding,
                "metadata": items,
            }
        )

    keyframes = []

    for keyframe_path in sorted(
        metadata_keyframe_paths
    ):
        metadata = metadata_by_keyframe_path[
            keyframe_path
        ]

        embedding = keyframe_embeddings_by_path[
            keyframe_path
        ]

        segment_id = metadata["segment_id"]

        if (
            embedding.get("segment_id")
            != segment_id
        ):
            raise ValueError(
                "keyframe의 segment_id가 "
                "일치하지 않습니다: "
                f"{keyframe_path}"
            )

        image_embedding = validate_vector(
            embedding.get("image_embedding"),
            segment_id,
            "image_embedding",
        )

        keyframes.append(
    {
        "keyframe_id": embedding[
            "keyframe_id"
        ],
        "segment_id": segment_id,
        "keyframe_path": keyframe_path,
        "description": metadata.get(
            "description"
        ),
        "time_of_day": metadata.get(
            "time_of_day"
        ),
        "mood": metadata.get(
            "mood",
            [],
        ),
        "activity": metadata.get(
            "activity",
            [],
        ),
        "scene_elements": metadata.get(
            "scene_elements",
            [],
        ),
        "image_embedding": image_embedding,
        "metadata": metadata,
    }
)

    return {
        "segments": segments,
        "keyframes": keyframes,
    }

def insert_prepared_records(
    cursor,
    records: dict[str, list[dict]],
) -> None:
    """준비된 segment/keyframe 레코드를 PostgreSQL에 저장한다."""

    inserted_videos = set()

    for segment in records["segments"]:
        segment_id = segment["segment_id"]
        video_id = segment["video_id"]

        metadata_items = segment.get(
            "metadata",
            [],
        )

        first_metadata = (
            metadata_items[0]
            if metadata_items
            else {}
        )

        place_name = segment.get("place_name")
        spot_name = (
            segment.get("spot_name")
            or place_name
        )

        description = optional_text(
            first_metadata.get("description")
        )

        mood_tags = unique_strings(
            first_metadata.get("mood", [])
        )

        scene_elements = unique_strings(
            first_metadata.get(
                "scene_elements",
                [],
            )
        )

        activities = unique_strings(
            first_metadata.get(
                "activity",
                [],
            )
        )

        tags = unique_strings(
            scene_elements + activities
        )

        season = optional_text(
            first_metadata.get("season")
        )

        season_tags = (
            [season]
            if season
            else []
        )

        keyframe_path = optional_text(
            first_metadata.get(
                "keyframe_path"
            )
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
                    (
                        f"{video_id}의 "
                        "VLM 기반 관광 영상"
                    ),
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
                place_id,
                start_time,
                end_time,
                caption,
                summary,
                tags,
                mood_tags,
                season_tags,
                region,
                drama_title,
                spot_name,
                keyframe_path,
                metadata
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (segment_id)
            DO UPDATE SET
                video_id = EXCLUDED.video_id,
                spot_id = EXCLUDED.spot_id,
                place_id = EXCLUDED.place_id,
                start_time = EXCLUDED.start_time,
                end_time = EXCLUDED.end_time,
                caption = EXCLUDED.caption,
                summary = EXCLUDED.summary,
                tags = EXCLUDED.tags,
                mood_tags = EXCLUDED.mood_tags,
                season_tags = EXCLUDED.season_tags,
                region = EXCLUDED.region,
                drama_title = EXCLUDED.drama_title,
                spot_name = EXCLUDED.spot_name,
                keyframe_path = EXCLUDED.keyframe_path,
                metadata = EXCLUDED.metadata
            """,
            (
                segment_id,
                video_id,
                None,
                segment.get("place_id"),
                segment.get("start_time"),
                segment.get("end_time"),
                description,
                segment.get("search_text"),
                tags,
                mood_tags,
                season_tags,
                segment.get("region"),
                segment.get("drama_title"),
                spot_name,
                keyframe_path,
                Jsonb(metadata_items),
            ),
        )

        cursor.execute(
            """
            INSERT INTO segment_embeddings (
                segment_id,
                text_embedding
            )
            VALUES (%s, %s)
            ON CONFLICT (segment_id)
            DO UPDATE SET
                text_embedding =
                    EXCLUDED.text_embedding,
                created_at =
                    CURRENT_TIMESTAMP
            """,
            (
                segment_id,
                segment["text_embedding"],
            ),
        )

    for keyframe in records["keyframes"]:
        cursor.execute(
    """
    INSERT INTO segment_keyframes (
        keyframe_id,
        segment_id,
        keyframe_path,
        description,
        time_of_day,
        mood,
        activity,
        scene_elements,
        metadata
    )
    VALUES (
        %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s
    )
    ON CONFLICT (keyframe_id)
    DO UPDATE SET
        segment_id =
            EXCLUDED.segment_id,
        keyframe_path =
            EXCLUDED.keyframe_path,
        description =
            EXCLUDED.description,
        time_of_day =
            EXCLUDED.time_of_day,
        mood =
            EXCLUDED.mood,
        activity =
            EXCLUDED.activity,
        scene_elements =
            EXCLUDED.scene_elements,
        metadata =
            EXCLUDED.metadata
    """,
    (
        keyframe["keyframe_id"],
        keyframe["segment_id"],
        keyframe["keyframe_path"],
        keyframe.get("description"),
        keyframe.get("time_of_day"),
        keyframe.get("mood", []),
        keyframe.get("activity", []),
        keyframe.get(
            "scene_elements",
            [],
        ),
        Jsonb(
            keyframe.get(
                "metadata",
                {},
            )
        ),
    ),
)

        cursor.execute(
            """
            INSERT INTO keyframe_embeddings (
                keyframe_id,
                image_embedding
            )
            VALUES (%s, %s)
            ON CONFLICT (keyframe_id)
            DO UPDATE SET
                image_embedding =
                    EXCLUDED.image_embedding,
                created_at =
                    CURRENT_TIMESTAMP
            """,
            (
                keyframe["keyframe_id"],
                keyframe["image_embedding"],
            ),
        )

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

def delete_stale_records(
    cursor,
    records: dict[str, list[dict]],
) -> None:
    """현재 records에 없는 오래된 segment/keyframe 행을 삭제한다."""

    current_segment_ids = [
        item["segment_id"]
        for item in records["segments"]
    ]

    current_keyframe_ids = [
        item["keyframe_id"]
        for item in records["keyframes"]
    ]

    cursor.execute(
        """
        DELETE FROM segment_keyframes
        WHERE NOT (
            keyframe_id = ANY(%s)
        )
        """,
        (current_keyframe_ids,),
    )

    cursor.execute(
        """
        DELETE FROM video_segments
        WHERE NOT (
            segment_id = ANY(%s)
        )
        """,
        (current_segment_ids,),
    )

def main() -> None:
    embedding_root = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )

    metadata_path = (
        embedding_root
        / "metadata"
        / "metadata.json"
    )

    segment_embeddings_path = (
        embedding_root
        / "output"
        / "embeddings"
        / "segment_embeddings.json"
    )

    keyframe_embeddings_path = (
        embedding_root
        / "output"
        / "embeddings"
        / "keyframe_embeddings.json"
    )

    env_path = (
        embedding_root
        / ".env"
    )

    load_dotenv(env_path)

    print("DB 적재 데이터 로딩 중...")

    metadata_list = load_json(
        metadata_path
    )

    segment_embedding_list = load_json(
        segment_embeddings_path
    )

    keyframe_embedding_list = load_json(
        keyframe_embeddings_path
    )

    print(
        f"metadata: "
        f"{len(metadata_list)}건"
    )

    print(
        f"segment embeddings: "
        f"{len(segment_embedding_list)}건"
    )

    print(
        f"keyframe embeddings: "
        f"{len(keyframe_embedding_list)}건"
    )

    records = prepare_records(
        metadata_list=
            metadata_list,
        segment_embedding_list=
            segment_embedding_list,
        keyframe_embedding_list=
            keyframe_embedding_list,
    )

    print("-" * 60)

    print(
        "DB 적재 준비 완료"
    )

    print(
        f"segments: "
        f"{len(records['segments'])}건"
    )

    print(
        f"keyframes: "
        f"{len(records['keyframes'])}건"
    )

    connection_string = (
        build_connection_string()
    )

    with psycopg.connect(
        connection_string
    ) as connection:

        with connection.cursor() as cursor:
            delete_stale_records(
                cursor,
                records,
            )

            insert_prepared_records(
                cursor,
                records,
            )

        connection.commit()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM videos
                """
            )

            video_count = (
                cursor.fetchone()[0]
            )

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM video_segments
                """
            )

            segment_count = (
                cursor.fetchone()[0]
            )

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM segment_embeddings
                """
            )

            segment_embedding_count = (
                cursor.fetchone()[0]
            )

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM segment_keyframes
                """
            )

            keyframe_count = (
                cursor.fetchone()[0]
            )

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM keyframe_embeddings
                """
            )

            keyframe_embedding_count = (
                cursor.fetchone()[0]
            )

    print("-" * 60)
    print("DB 적재 완료")

    print(
        f"videos 전체 건수: "
        f"{video_count}"
    )

    print(
        f"video_segments 전체 건수: "
        f"{segment_count}"
    )

    print(
        f"segment_embeddings 전체 건수: "
        f"{segment_embedding_count}"
    )

    print(
        f"segment_keyframes 전체 건수: "
        f"{keyframe_count}"
    )

    print(
        f"keyframe_embeddings 전체 건수: "
        f"{keyframe_embedding_count}"
    )

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
