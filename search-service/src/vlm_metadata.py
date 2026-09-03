"""VLM 메타데이터와 영상 전처리 결과의 연결을 검증한다."""

from __future__ import annotations

import json
from collections import Counter
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

    raw_segments = _extract_vlm_segments(payload)

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

    raw_segments = _extract_preprocessing_segments(payload)
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


def load_preprocessing_segments(path: str | Path) -> list[dict[str, Any]]:
    """구형 단일 객체와 신형 영상별 배열 전처리 결과를 모두 읽는다."""

    data_path = Path(path)
    try:
        with data_path.open("r", encoding="utf-8-sig") as file:
            payload = json.load(file)
    except json.JSONDecodeError as error:
        raise VLMMetadataError(f"전처리 결과 JSON 문법 오류: {error}") from error

    raw_segments = _extract_preprocessing_segments(payload)

    segments: list[dict[str, Any]] = []
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
        segment = dict(item)
        segment["segment_id"] = segment_id
        start_time = _number(segment.get("start_time"), "start_time", segment_id)
        end_time = _number(segment.get("end_time"), "end_time", segment_id)
        if start_time >= end_time:
            raise VLMMetadataError(f"{segment_id}의 시작·종료 시간을 확인하세요.")
        segment["start_time"] = start_time
        segment["end_time"] = end_time
        segment["keyframe_path"] = _nonempty_text(
            segment.get("keyframe_path"),
            "keyframe_path",
            segment_id,
        )
        segments.append(segment)

    return segments


def build_alignment_report(
    metadata_path: str | Path,
    preprocessing_path: str | Path,
    *,
    keyframe_root: str | Path | None = None,
) -> dict[str, Any]:
    """VLM과 전처리 결과의 ID·시간·키프레임 연결을 전수 비교한다."""

    metadata_path = Path(metadata_path)
    preprocessing_path = Path(preprocessing_path)
    resolved_keyframe_root = (
        Path(keyframe_root) if keyframe_root is not None else preprocessing_path.parent
    )
    try:
        metadata_payload = json.loads(
            metadata_path.read_text(encoding="utf-8-sig")
        )
    except json.JSONDecodeError as error:
        raise VLMMetadataError(f"VLM 결과 JSON 문법 오류: {error}") from error

    raw_vlm_segments = _extract_vlm_segments(metadata_payload)
    preprocessing_segments = load_preprocessing_segments(preprocessing_path)
    expected_by_id = {
        segment["segment_id"]: segment for segment in preprocessing_segments
    }
    expected_by_keyframe = {
        _normalized_path(segment["keyframe_path"]): segment
        for segment in preprocessing_segments
    }

    issues: list[str] = []
    actual_ids: list[str] = []
    linked_expected_ids: set[str] = set()

    for index, raw_segment in enumerate(raw_vlm_segments):
        if not isinstance(raw_segment, Mapping):
            issues.append(f"VLM segments[{index}]는 객체가 아닙니다.")
            continue
        segment = dict(raw_segment)
        context = f"VLM segments[{index}]"
        raw_segment_id = segment.get("scene_id", segment.get("segment_id"))
        segment_id = str(raw_segment_id or "").strip()
        if segment_id:
            actual_ids.append(segment_id)
            context = segment_id
        else:
            issues.append(f"{context}: segment_id가 없습니다.")

        keyframe_path = str(segment.get("keyframe_path") or "").strip()
        expected = expected_by_keyframe.get(_normalized_path(keyframe_path))
        if expected is None and segment_id:
            expected = expected_by_id.get(segment_id)
        if expected is None:
            issues.append(f"{context}: 연결되는 전처리 장면을 찾을 수 없습니다.")
            continue

        expected_id = expected["segment_id"]
        linked_expected_ids.add(expected_id)
        if segment_id != expected_id:
            issues.append(
                f"{expected_id}: segment_id 불일치 "
                f"(VLM={segment_id or '없음'}, 전처리={expected_id})"
            )

        expected_source_id = str(expected.get("source_segment_id") or "").strip()
        actual_source_id = str(segment.get("source_segment_id") or "").strip()
        if expected_source_id and actual_source_id != expected_source_id:
            issues.append(
                f"{expected_id}: source_segment_id 불일치 "
                f"(VLM={actual_source_id or '없음'}, 전처리={expected_source_id})"
            )

        for field_name in ("start_time", "end_time"):
            actual_value = segment.get(field_name)
            expected_value = expected[field_name]
            if not _same_number(actual_value, expected_value):
                issues.append(
                    f"{expected_id}: {field_name} 불일치 "
                    f"(VLM={actual_value!r}, 전처리={expected_value})"
                )

        if not keyframe_path:
            issues.append(f"{expected_id}: keyframe_path가 없습니다.")
        else:
            keyframe_file = resolved_keyframe_root / Path(
                keyframe_path.replace("/", "\\")
            )
            if not keyframe_file.is_file():
                issues.append(
                    f"{expected_id}: 키프레임 파일이 없습니다: {keyframe_path}"
                )

        season = segment.get("season")
        if isinstance(season, str) and "," in season:
            issues.append(f"{expected_id}: season에 여러 값이 들어 있습니다: {season}")

    duplicate_ids = sorted(
        segment_id
        for segment_id, count in Counter(actual_ids).items()
        if count > 1
    )
    for segment_id in duplicate_ids:
        issues.append(
            f"VLM segment_id 중복: {segment_id} ({actual_ids.count(segment_id)}건)"
        )

    missing_ids = sorted(set(expected_by_id) - linked_expected_ids)
    for segment_id in missing_ids:
        issues.append(f"VLM 결과 누락: {segment_id}")

    return {
        "is_valid": not issues,
        "preprocessing_segment_count": len(preprocessing_segments),
        "vlm_segment_count": len(raw_vlm_segments),
        "linked_segment_count": len(linked_expected_ids),
        "duplicate_segment_ids": duplicate_ids,
        "missing_segment_ids": missing_ids,
        "issues": issues,
    }


def _extract_vlm_segments(payload: object) -> list[object]:
    if isinstance(payload, list):
        if not payload:
            raise VLMMetadataError("VLM 결과 목록이 비어 있습니다.")
        return payload
    if not isinstance(payload, Mapping):
        raise VLMMetadataError("VLM 결과 JSON 최상위 값은 객체 또는 목록이어야 합니다.")
    if not isinstance(payload.get("schema_version"), str) or not str(
        payload["schema_version"]
    ).strip():
        raise VLMMetadataError("schema_version은 빈 문자열이 아니어야 합니다.")
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise VLMMetadataError("segments는 하나 이상의 구간을 가진 목록이어야 합니다.")
    return raw_segments


def _extract_preprocessing_segments(payload: object) -> list[object]:
    if isinstance(payload, Mapping):
        raw_segments = payload.get("segments")
        if not isinstance(raw_segments, list) or not raw_segments:
            raise VLMMetadataError(
                "전처리 결과의 segments가 비어 있거나 목록이 아닙니다."
            )
        return raw_segments
    if not isinstance(payload, list) or not payload:
        raise VLMMetadataError(
            "전처리 결과 JSON 최상위 값은 객체 또는 영상 목록이어야 합니다."
        )

    flattened: list[object] = []
    for index, video in enumerate(payload):
        if not isinstance(video, Mapping):
            raise VLMMetadataError(f"전처리 videos[{index}]는 객체여야 합니다.")
        raw_segments = video.get("segments", [])
        if not isinstance(raw_segments, list):
            raise VLMMetadataError(
                f"전처리 videos[{index}].segments는 목록이어야 합니다."
            )
        flattened.extend(raw_segments)
    if not flattened:
        raise VLMMetadataError("전처리 결과에 장면이 없습니다.")
    return flattened


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


def _number(value: object, field_name: str, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VLMMetadataError(f"{context}의 {field_name}은 숫자여야 합니다.")
    return float(value)


def _same_number(actual: object, expected: object, *, tolerance: float = 0.001) -> bool:
    if isinstance(actual, bool) or not isinstance(actual, (int, float)):
        return False
    if isinstance(expected, bool) or not isinstance(expected, (int, float)):
        return False
    return abs(float(actual) - float(expected)) <= tolerance


def _normalized_path(value: object) -> str:
    return str(value or "").strip().replace("\\", "/").casefold()


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
