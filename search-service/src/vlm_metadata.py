"""VLM이 생성한 구간별 메타데이터 JSON을 검증한다."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = frozenset(
    {
        "segment_id",
        "season",
        "time_of_day",
        "mood",
        "scene_elements",
        "activity",
        "description",
    }
)
TEXT_FIELDS = ("segment_id", "season", "time_of_day", "description")
LIST_FIELDS = ("mood", "scene_elements", "activity")


class VLMMetadataError(ValueError):
    """VLM 메타데이터가 합의한 입력 규격을 만족하지 않을 때 발생한다."""


def load_vlm_metadata(
    path: str | Path,
    *,
    expected_segment_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """VLM 결과 JSON을 읽고 검증된 구간 메타데이터를 반환한다."""

    data_path = Path(path)
    try:
        with data_path.open("r", encoding="utf-8-sig") as file:
            payload = json.load(file)
    except json.JSONDecodeError as error:
        raise VLMMetadataError(f"VLM 결과 JSON 문법 오류: {error}") from error

    return validate_vlm_metadata(
        payload,
        expected_segment_ids=expected_segment_ids,
    )


def validate_vlm_metadata(
    payload: object,
    *,
    expected_segment_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """VLM 결과의 필수 필드·태그·구간 ID 연결을 검증한다."""

    if not isinstance(payload, Mapping):
        raise VLMMetadataError("VLM 결과 JSON 최상위 값은 객체여야 합니다.")
    if not isinstance(payload.get("schema_version"), str) or not str(
        payload["schema_version"]
    ).strip():
        raise VLMMetadataError("schema_version은 빈 문자열이 아니어야 합니다.")

    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise VLMMetadataError("segments는 하나 이상의 구간을 가진 목록이어야 합니다.")

    validated: list[dict[str, Any]] = []
    seen_segment_ids: set[str] = set()

    for index, raw_segment in enumerate(raw_segments):
        segment = _validate_segment(raw_segment, index=index)
        segment_id = segment["segment_id"]
        if segment_id in seen_segment_ids:
            raise VLMMetadataError(f"segment_id가 중복되었습니다: {segment_id}")
        seen_segment_ids.add(segment_id)
        validated.append(segment)

    if expected_segment_ids is not None:
        _validate_expected_ids(seen_segment_ids, expected_segment_ids)

    return validated


def load_expected_segment_ids(path: str | Path) -> list[str]:
    """영상 전처리 결과 JSON에서 예상 segment_id 목록을 읽는다."""

    data_path = Path(path)
    try:
        with data_path.open("r", encoding="utf-8-sig") as file:
            payload = json.load(file)
    except json.JSONDecodeError as error:
        raise VLMMetadataError(f"전처리 결과 JSON 문법 오류: {error}") from error

    if not isinstance(payload, Mapping):
        raise VLMMetadataError("전처리 결과 JSON 최상위 값은 객체여야 합니다.")
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise VLMMetadataError("전처리 결과의 segments가 비어 있거나 목록이 아닙니다.")

    segment_ids: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_segments):
        if not isinstance(item, Mapping):
            raise VLMMetadataError(f"전처리 segments[{index}]는 객체여야 합니다.")
        segment_id = _nonempty_text(
            item.get("segment_id"),
            "segment_id",
            f"전처리 segments[{index}]",
        )
        if segment_id in seen:
            raise VLMMetadataError(f"전처리 segment_id가 중복되었습니다: {segment_id}")
        seen.add(segment_id)
        segment_ids.append(segment_id)

    return segment_ids


def _validate_segment(raw_segment: object, *, index: int) -> dict[str, Any]:
    if not isinstance(raw_segment, Mapping):
        raise VLMMetadataError(f"segments[{index}]는 객체여야 합니다.")

    missing = sorted(REQUIRED_FIELDS - raw_segment.keys())
    if missing:
        raise VLMMetadataError(
            f"segments[{index}]에 필수 항목이 없습니다: {', '.join(missing)}"
        )

    segment = dict(raw_segment)
    context = str(segment.get("segment_id") or f"segments[{index}]")

    for field_name in TEXT_FIELDS:
        segment[field_name] = _nonempty_text(
            segment[field_name],
            field_name,
            context,
        )
    for field_name in LIST_FIELDS:
        segment[field_name] = _string_list(
            segment[field_name],
            field_name,
            context,
        )

    segment.setdefault("metadata_source", "vlm")
    return segment


def _nonempty_text(value: object, field_name: str, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VLMMetadataError(
            f"{context}의 {field_name}은 빈 문자열이 아니어야 합니다."
        )
    return value.strip()


def _string_list(value: object, field_name: str, context: str) -> list[str]:
    if not isinstance(value, list):
        raise VLMMetadataError(f"{context}의 {field_name}은 문자열 목록이어야 합니다.")

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise VLMMetadataError(
                f"{context}의 {field_name}에는 빈 문자열을 사용할 수 없습니다."
            )
        normalized = item.strip()
        key = normalized.casefold()
        if key in seen:
            raise VLMMetadataError(
                f"{context}의 {field_name}에 중복 태그가 있습니다: {normalized}"
            )
        seen.add(key)
        cleaned.append(normalized)
    return cleaned


def _validate_expected_ids(
    actual_ids: set[str],
    expected_segment_ids: Iterable[str],
) -> None:
    expected_list = [str(item).strip() for item in expected_segment_ids]
    if any(not item for item in expected_list):
        raise VLMMetadataError("예상 segment_id에는 빈 값을 사용할 수 없습니다.")
    if len(expected_list) != len(set(expected_list)):
        raise VLMMetadataError("예상 segment_id 목록에 중복이 있습니다.")

    expected_ids = set(expected_list)
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)
    if not missing and not extra:
        return

    details: list[str] = []
    if missing:
        details.append(f"누락: {', '.join(missing)}")
    if extra:
        details.append(f"추가: {', '.join(extra)}")
    raise VLMMetadataError("VLM 구간 ID가 전처리 결과와 다릅니다. " + " / ".join(details))
