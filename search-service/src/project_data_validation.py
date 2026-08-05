"""실데이터 메타데이터의 검색·DB 연결 품질을 검증한다."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


REQUIRED_TEXT_FIELDS = (
    "segment_id",
    "video_id",
    "place_id",
    "place_name",
    "region",
    "drama_title",
    "keyframe_path",
    "season",
    "time_of_day",
    "description",
)
TAG_FIELDS = ("mood", "activity", "scene_elements")
ALLOWED_SEASONS = frozenset({"봄", "여름", "가을", "겨울"})
ALLOWED_TIMES_OF_DAY = frozenset(
    {"새벽", "아침", "오전", "낮", "오후", "해질녘", "저녁", "밤"}
)


def load_metadata_payload(path: str | Path) -> object:
    """UTF-8 BOM 유무와 관계없이 JSON을 읽는다."""

    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def extract_metadata_records(payload: object) -> list[Mapping[str, Any]]:
    """배열 또는 ``{"segments": [...]}`` 형식에서 레코드를 꺼낸다."""

    raw_records: object
    if isinstance(payload, Mapping):
        raw_records = payload.get("segments")
    else:
        raw_records = payload
    if (
        isinstance(raw_records, (str, bytes))
        or not isinstance(raw_records, Sequence)
        or not raw_records
    ):
        raise ValueError("메타데이터는 하나 이상의 레코드를 가진 배열이어야 합니다.")

    records: list[Mapping[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not isinstance(record, Mapping):
            raise ValueError(f"metadata[{index}]는 객체여야 합니다.")
        records.append(record)
    return records


def validate_project_metadata(
    payload: object,
    *,
    keyframe_root: str | Path | None = None,
) -> dict[str, Any]:
    """필드·시간·태그·장소 ID·키프레임 연결을 한 번에 검사한다."""

    records = extract_metadata_records(payload)
    root = Path(keyframe_root) if keyframe_root is not None else None
    issues: list[dict[str, Any]] = []
    keyframe_owner: dict[str, int] = {}
    segment_facts: dict[str, list[dict[str, object]]] = defaultdict(list)
    place_facts: dict[str, list[dict[str, str]]] = defaultdict(list)

    def add_issue(
        severity: str,
        code: str,
        index: int | None,
        segment_id: str | None,
        message: str,
    ) -> None:
        issues.append(
            {
                "severity": severity,
                "code": code,
                "record_index": index,
                "segment_id": segment_id,
                "message": message,
            }
        )

    for index, record in enumerate(records):
        segment_id = _clean_text(record.get("segment_id"))
        context = segment_id or f"metadata[{index}]"

        cleaned: dict[str, str] = {}
        for field_name in REQUIRED_TEXT_FIELDS:
            value = _clean_text(record.get(field_name))
            cleaned[field_name] = value
            if not value:
                add_issue(
                    "error",
                    "MISSING_REQUIRED_FIELD",
                    index,
                    segment_id or None,
                    f"{context}: {field_name} 값이 비어 있습니다.",
                )

        start_time = _finite_number(record.get("start_time"))
        end_time = _finite_number(record.get("end_time"))
        if start_time is None or end_time is None:
            add_issue(
                "error",
                "INVALID_TIME_TYPE",
                index,
                segment_id or None,
                f"{context}: start_time과 end_time은 유한한 숫자여야 합니다.",
            )
        elif start_time >= end_time:
            add_issue(
                "error",
                "INVALID_TIME_RANGE",
                index,
                segment_id or None,
                f"{context}: end_time은 start_time보다 커야 합니다.",
            )

        for field_name in TAG_FIELDS:
            _validate_string_array(
                record.get(field_name),
                field_name=field_name,
                index=index,
                segment_id=segment_id or None,
                add_issue=add_issue,
            )

        season = cleaned["season"]
        if season and season not in ALLOWED_SEASONS:
            add_issue(
                "error",
                "NON_CANONICAL_SEASON",
                index,
                segment_id or None,
                f"{context}: season은 한글 단일값이어야 합니다: {season}",
            )
        time_of_day = cleaned["time_of_day"]
        if time_of_day and time_of_day not in ALLOWED_TIMES_OF_DAY:
            add_issue(
                "error",
                "NON_CANONICAL_TIME_OF_DAY",
                index,
                segment_id or None,
                f"{context}: time_of_day는 한글 단일값이어야 합니다: {time_of_day}",
            )

        keyframe_path = _normalize_path(cleaned["keyframe_path"])
        if keyframe_path:
            if not keyframe_path.startswith("keyframes/"):
                add_issue(
                    "error",
                    "INVALID_KEYFRAME_PREFIX",
                    index,
                    segment_id or None,
                    f"{context}: keyframe_path는 keyframes/... 형식이어야 합니다.",
                )
            if keyframe_path in keyframe_owner:
                add_issue(
                    "error",
                    "DUPLICATE_KEYFRAME_PATH",
                    index,
                    segment_id or None,
                    f"{context}: keyframe_path가 중복되었습니다: {keyframe_path}",
                )
            else:
                keyframe_owner[keyframe_path] = index
            if root is not None and not (root / Path(keyframe_path)).is_file():
                add_issue(
                    "error",
                    "KEYFRAME_FILE_NOT_FOUND",
                    index,
                    segment_id or None,
                    f"{context}: 키프레임 파일이 없습니다: {keyframe_path}",
                )

        if segment_id:
            segment_facts[segment_id].append(
                {
                    "video_id": cleaned["video_id"],
                    "place_id": cleaned["place_id"],
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )
        place_id = cleaned["place_id"]
        if place_id:
            place_facts[place_id].append(
                {
                    "place_name": cleaned["place_name"],
                    "region": cleaned["region"],
                    "city": _clean_text(record.get("city")),
                }
            )

    for segment_id, facts in sorted(segment_facts.items()):
        for field_name in ("video_id", "place_id", "start_time", "end_time"):
            values = {fact[field_name] for fact in facts}
            if len(values) > 1:
                add_issue(
                    "error",
                    "SEGMENT_CONFLICT",
                    None,
                    segment_id,
                    f"{segment_id}: 여러 keyframe 레코드의 {field_name} 값이 다릅니다.",
                )

    for place_id, facts in sorted(place_facts.items()):
        for field_name in ("place_name", "region", "city"):
            values = {
                fact[field_name].casefold()
                for fact in facts
                if fact[field_name]
            }
            if len(values) > 1:
                add_issue(
                    "error",
                    "PLACE_ID_CONFLICT",
                    None,
                    None,
                    f"{place_id}: 하나의 place_id에 서로 다른 {field_name} 값이 연결됐습니다.",
                )
        if not any(fact["city"] for fact in facts):
            add_issue(
                "warning",
                "CITY_NOT_PROVIDED",
                None,
                None,
                f"{place_id}: city가 없어 장소 테이블에서 보완해야 합니다.",
            )

    error_count = sum(issue["severity"] == "error" for issue in issues)
    warning_count = sum(issue["severity"] == "warning" for issue in issues)
    return {
        "is_valid": error_count == 0,
        "summary": {
            "record_count": len(records),
            "unique_segment_count": len(segment_facts),
            "unique_place_id_count": len(place_facts),
            "unique_keyframe_count": len(keyframe_owner),
            "error_count": error_count,
            "warning_count": warning_count,
        },
        "issues": issues,
    }


def _clean_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip()


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _validate_string_array(
    value: object,
    *,
    field_name: str,
    index: int,
    segment_id: str | None,
    add_issue: Any,
) -> None:
    context = segment_id or f"metadata[{index}]"
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        add_issue(
            "error",
            "INVALID_ARRAY_FIELD",
            index,
            segment_id,
            f"{context}: {field_name}은 문자열 배열이어야 합니다.",
        )
        return
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            add_issue(
                "error",
                "INVALID_ARRAY_ITEM",
                index,
                segment_id,
                f"{context}: {field_name}에는 빈 값이 아닌 문자열만 허용됩니다.",
            )
            continue
        key = item.strip().casefold()
        if key in seen:
            add_issue(
                "warning",
                "DUPLICATE_ARRAY_ITEM",
                index,
                segment_id,
                f"{context}: {field_name}에 중복 값이 있습니다: {item.strip()}",
            )
        seen.add(key)
