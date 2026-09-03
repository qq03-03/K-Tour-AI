"""실데이터 평가 전에 DB 적재 완전성과 stale 데이터를 검사한다."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import psycopg


REQUIRED_TABLES = {
    "video_segments",
    "segment_embeddings",
    "segment_keyframes",
    "keyframe_embeddings",
}


def collect_db_snapshot(connection_string: str) -> dict[str, Any]:
    """pgvector DB에서 검증에 필요한 ID·경로·벡터 차원만 읽는다."""

    with psycopg.connect(connection_string) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            )
            tables = {str(row[0]) for row in cursor.fetchall()}
            snapshot: dict[str, Any] = {"tables": sorted(tables)}
            if not REQUIRED_TABLES.issubset(tables):
                return snapshot

            cursor.execute(
                "SELECT segment_id, place_id FROM video_segments ORDER BY segment_id"
            )
            segment_rows = cursor.fetchall()
            snapshot["segment_ids"] = [str(row[0]) for row in segment_rows]
            snapshot["p030_segment_ids"] = [
                str(row[0]) for row in segment_rows if str(row[1]) == "P030"
            ]

            cursor.execute(
                """
                SELECT segment_id, vector_dims(text_embedding)
                FROM segment_embeddings
                WHERE text_embedding IS NOT NULL
                ORDER BY segment_id
                """
            )
            text_rows = cursor.fetchall()
            snapshot["text_embedding_segment_ids"] = [
                str(row[0]) for row in text_rows
            ]
            snapshot["text_vector_dimensions"] = [int(row[1]) for row in text_rows]

            cursor.execute(
                """
                SELECT keyframe_id, keyframe_path
                FROM segment_keyframes
                ORDER BY keyframe_id
                """
            )
            keyframe_rows = cursor.fetchall()
            snapshot["keyframe_ids"] = [str(row[0]) for row in keyframe_rows]
            snapshot["keyframe_paths"] = [str(row[1]) for row in keyframe_rows]

            cursor.execute(
                """
                SELECT sk.keyframe_path, vector_dims(ke.image_embedding)
                FROM keyframe_embeddings AS ke
                JOIN segment_keyframes AS sk ON sk.keyframe_id = ke.keyframe_id
                WHERE ke.image_embedding IS NOT NULL
                ORDER BY sk.keyframe_path
                """
            )
            image_rows = cursor.fetchall()
            snapshot["image_embedding_keyframe_paths"] = [
                str(row[0]) for row in image_rows
            ]
            snapshot["image_vector_dimensions"] = [int(row[1]) for row in image_rows]
    return snapshot


def build_dry_run_snapshot(metadata_records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """DB 연결 없이 점검기 자체를 검증하는 이상적인 합성 snapshot을 만든다."""

    segment_ids = [str(item["segment_id"]) for item in metadata_records]
    keyframe_paths = [str(item["keyframe_path"]) for item in metadata_records]
    return {
        "tables": sorted(REQUIRED_TABLES),
        "segment_ids": segment_ids,
        "p030_segment_ids": [
            str(item["segment_id"])
            for item in metadata_records
            if str(item.get("place_id")) == "P030"
        ],
        "text_embedding_segment_ids": segment_ids,
        "text_vector_dimensions": [768] * len(segment_ids),
        "keyframe_ids": [f"DRY__{index:03d}" for index in range(len(keyframe_paths))],
        "keyframe_paths": keyframe_paths,
        "image_embedding_keyframe_paths": keyframe_paths,
        "image_vector_dimensions": [768] * len(keyframe_paths),
    }


def analyze_db_snapshot(
    snapshot: Mapping[str, Any],
    metadata_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected_segments = {str(item["segment_id"]) for item in metadata_records}
    expected_keyframes = {
        _normalize_path(item["keyframe_path"]) for item in metadata_records
    }
    expected_p030 = {
        str(item["segment_id"])
        for item in metadata_records
        if str(item.get("place_id")) == "P030"
    }
    checks: list[dict[str, Any]] = []

    actual_tables = {str(value) for value in snapshot.get("tables", [])}
    _add_check(
        checks,
        "required_tables",
        REQUIRED_TABLES.issubset(actual_tables),
        missing=sorted(REQUIRED_TABLES - actual_tables),
    )
    if not REQUIRED_TABLES.issubset(actual_tables):
        return _report(checks, snapshot)

    _check_id_set(
        checks,
        "segments",
        snapshot.get("segment_ids", []),
        expected_segments,
    )
    _check_id_set(
        checks,
        "text_embeddings",
        snapshot.get("text_embedding_segment_ids", []),
        expected_segments,
    )
    _check_path_set(
        checks,
        "keyframes",
        snapshot.get("keyframe_paths", []),
        expected_keyframes,
    )
    _check_path_set(
        checks,
        "image_embeddings",
        snapshot.get("image_embedding_keyframe_paths", []),
        expected_keyframes,
    )
    _check_vector_dimensions(
        checks,
        "text_vector_dimensions",
        snapshot.get("text_vector_dimensions", []),
        len(expected_segments),
    )
    _check_vector_dimensions(
        checks,
        "image_vector_dimensions",
        snapshot.get("image_vector_dimensions", []),
        len(expected_keyframes),
    )
    actual_p030 = {str(value) for value in snapshot.get("p030_segment_ids", [])}
    _add_check(
        checks,
        "p030_changgyeonggung",
        actual_p030 == expected_p030 and bool(expected_p030),
        expected=sorted(expected_p030),
        actual=sorted(actual_p030),
    )
    return _report(checks, snapshot)


def _check_id_set(
    checks: list[dict[str, Any]],
    name: str,
    actual_values: object,
    expected: set[str],
) -> None:
    actual_list = [str(value) for value in _sequence(actual_values)]
    counts = Counter(actual_list)
    actual = set(actual_list)
    _add_check(
        checks,
        name,
        actual == expected and len(actual_list) == len(expected),
        expected_count=len(expected),
        actual_count=len(actual_list),
        missing=sorted(expected - actual),
        stale=sorted(actual - expected),
        duplicates=sorted(value for value, count in counts.items() if count > 1),
    )


def _check_path_set(
    checks: list[dict[str, Any]],
    name: str,
    actual_values: object,
    expected: set[str],
) -> None:
    normalized = [_normalize_path(value) for value in _sequence(actual_values)]
    _check_id_set(checks, name, normalized, expected)


def _check_vector_dimensions(
    checks: list[dict[str, Any]],
    name: str,
    raw_dimensions: object,
    expected_count: int,
) -> None:
    dimensions = [int(value) for value in _sequence(raw_dimensions)]
    unique = sorted(set(dimensions))
    _add_check(
        checks,
        name,
        len(dimensions) == expected_count and len(unique) == 1 and unique[0] > 0,
        expected_count=expected_count,
        actual_count=len(dimensions),
        dimensions=unique,
    )


def _add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    **details: Any,
) -> None:
    checks.append({"name": name, "status": "pass" if passed else "fail", **details})


def _report(checks: list[dict[str, Any]], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    failed = [item["name"] for item in checks if item["status"] == "fail"]
    return {
        "summary": {
            "status": "pass" if not failed else "fail",
            "check_count": len(checks),
            "failed_checks": failed,
        },
        "checks": checks,
        "snapshot_counts": {
            key: len(value)
            for key, value in snapshot.items()
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        },
    }


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return []


def _normalize_path(value: object) -> str:
    return str(value).strip().replace("\\", "/").casefold()
