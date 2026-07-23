"""통합 영상 구간 JSON을 검증하고 기존 검색 형식으로 변환한다."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = frozenset(
    {
        "segment_id",
        "video_id",
        "place_id",
        "place_name",
        "region",
        "start_time",
        "end_time",
        "keyframe_path",
        "season",
        "time_of_day",
        "mood",
        "scene_elements",
        "activity",
        "description",
    }
)
ID_FIELDS = ("segment_id", "video_id", "place_id")
TEXT_FIELDS = ("place_name", "region", "season", "time_of_day", "description")
LIST_FIELDS = ("mood", "scene_elements", "activity")
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
LEGACY_REQUIRED_FIELDS = frozenset(
    {"segment_id", "video_id", "start_sec", "end_sec", "location_name", "metadata_text"}
)


class SegmentDataError(ValueError):
    """구간 데이터가 통합 규격을 만족하지 않을 때 발생한다."""


def load_segments(
    path: str | Path,
    *,
    require_keyframes: bool = False,
    keyframe_root: str | Path | None = None,
    require_contiguous: bool = False,
) -> list[dict[str, Any]]:
    """통합 JSON을 읽고 기존 검색 함수에서 사용할 수 있는 구간 목록을 반환한다.

    통합 규격의 ``start_time``·``place_name``·``description``을 기존 검색 코드의
    ``start_sec``·``location_name``·``metadata_text`` 별칭으로 함께 제공한다.
    """

    data_path = Path(path)
    with data_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if _looks_like_legacy_payload(payload):
        return _validate_legacy_payload(payload)

    root = Path(keyframe_root) if keyframe_root is not None else data_path.parent.parent
    return validate_segments(
        payload,
        require_keyframes=require_keyframes,
        keyframe_root=root,
        require_contiguous=require_contiguous,
    )


def validate_segments(
    payload: object,
    *,
    require_keyframes: bool = False,
    keyframe_root: str | Path | None = None,
    require_contiguous: bool = False,
    time_tolerance: float = 1e-6,
) -> list[dict[str, Any]]:
    """이미 읽은 통합 데이터의 규격을 검사하고 검색용 별칭을 추가한다."""

    if not isinstance(payload, Mapping):
        raise SegmentDataError("JSON 최상위 값은 객체여야 합니다.")
    _validate_schema_version(payload.get("schema_version"))
    if (
        isinstance(time_tolerance, bool)
        or not isinstance(time_tolerance, (int, float))
        or not math.isfinite(float(time_tolerance))
        or time_tolerance < 0
    ):
        raise SegmentDataError("time_tolerance은 0 이상의 유한한 숫자여야 합니다.")

    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise SegmentDataError("segments는 하나 이상의 구간을 가진 목록이어야 합니다.")

    root = Path(keyframe_root) if keyframe_root is not None else Path.cwd()
    loaded: list[dict[str, Any]] = []
    seen_segment_ids: set[str] = set()

    for index, raw_segment in enumerate(raw_segments):
        segment = _validate_segment(
            raw_segment,
            index=index,
            keyframe_root=root,
            require_keyframe=require_keyframes,
        )
        segment_id = segment["segment_id"]
        if segment_id in seen_segment_ids:
            raise SegmentDataError(f"segment_id가 중복되었습니다: {segment_id}")
        seen_segment_ids.add(segment_id)
        loaded.append(_add_search_aliases(segment))

    _validate_timeline(
        loaded,
        require_contiguous=require_contiguous,
        tolerance=float(time_tolerance),
    )
    return loaded


def _validate_segment(
    raw_segment: object,
    *,
    index: int,
    keyframe_root: Path,
    require_keyframe: bool,
) -> dict[str, Any]:
    if not isinstance(raw_segment, Mapping):
        raise SegmentDataError(f"segments[{index}]는 객체여야 합니다.")

    missing = sorted(REQUIRED_FIELDS - raw_segment.keys())
    if missing:
        raise SegmentDataError(
            f"segments[{index}]에 필수 항목이 없습니다: {', '.join(missing)}"
        )

    segment = dict(raw_segment)
    context = str(segment.get("segment_id") or f"segments[{index}]")

    for field_name in ID_FIELDS + TEXT_FIELDS:
        segment[field_name] = _nonempty_text(segment[field_name], field_name, context)

    start_time = _number(segment["start_time"], "start_time", context)
    end_time = _number(segment["end_time"], "end_time", context)
    if start_time < 0:
        raise SegmentDataError(f"{context}의 start_time은 0 이상이어야 합니다.")
    if end_time <= start_time:
        raise SegmentDataError(f"{context}의 end_time은 start_time보다 커야 합니다.")
    segment["start_time"] = start_time
    segment["end_time"] = end_time

    if "representative_frame_time" in segment:
        frame_time = _number(
            segment["representative_frame_time"],
            "representative_frame_time",
            context,
        )
        if not start_time <= frame_time <= end_time:
            raise SegmentDataError(
                f"{context}의 representative_frame_time은 구간 안에 있어야 합니다."
            )
        segment["representative_frame_time"] = frame_time

    for field_name in LIST_FIELDS:
        segment[field_name] = _string_list(segment[field_name], field_name, context)
    if "category" in segment:
        segment["category"] = _string_list(segment["category"], "category", context)

    segment["keyframe_path"] = _keyframe_path(
        segment["keyframe_path"],
        context=context,
        keyframe_root=keyframe_root,
        required=require_keyframe,
    )
    return segment


def _nonempty_text(value: object, field_name: str, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SegmentDataError(f"{context}의 {field_name}은 빈 문자열이 아니어야 합니다.")
    return value.strip()


def _number(value: object, field_name: str, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SegmentDataError(f"{context}의 {field_name}은 숫자여야 합니다.")
    number = float(value)
    if not math.isfinite(number):
        raise SegmentDataError(f"{context}의 {field_name}은 유한한 숫자여야 합니다.")
    return number


def _string_list(value: object, field_name: str, context: str) -> list[str]:
    if not isinstance(value, list):
        raise SegmentDataError(f"{context}의 {field_name}은 문자열 목록이어야 합니다.")

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise SegmentDataError(
                f"{context}의 {field_name}에는 빈 문자열을 사용할 수 없습니다."
            )
        normalized = item.strip()
        key = normalized.casefold()
        if key in seen:
            raise SegmentDataError(f"{context}의 {field_name}에 중복 태그가 있습니다: {normalized}")
        seen.add(key)
        cleaned.append(normalized)
    return cleaned


def _keyframe_path(
    value: object,
    *,
    context: str,
    keyframe_root: Path,
    required: bool,
) -> str | None:
    if value is None:
        if required:
            raise SegmentDataError(f"{context}에 keyframe_path가 필요합니다.")
        return None
    if not isinstance(value, str) or not value.strip():
        raise SegmentDataError(f"{context}의 keyframe_path는 경로 문자열 또는 null이어야 합니다.")

    cleaned = value.strip()
    frame_path = Path(cleaned)
    if frame_path.suffix.casefold() not in IMAGE_SUFFIXES:
        raise SegmentDataError(f"{context}의 대표 프레임 확장자를 확인하세요: {cleaned}")

    resolved = frame_path if frame_path.is_absolute() else keyframe_root / frame_path
    if not frame_path.is_absolute():
        try:
            resolved.resolve().relative_to(keyframe_root.resolve())
        except ValueError as error:
            raise SegmentDataError(
                f"{context}의 대표 프레임 경로가 허용된 폴더 밖을 가리킵니다: {cleaned}"
            ) from error
    if not resolved.is_file():
        raise SegmentDataError(f"{context}의 대표 프레임 파일이 없습니다: {resolved}")
    return cleaned


def _add_search_aliases(segment: dict[str, Any]) -> dict[str, Any]:
    result = dict(segment)
    result["start_sec"] = segment["start_time"]
    result["end_sec"] = segment["end_time"]
    result["location_name"] = segment["place_name"]
    result["landscape"] = list(segment["scene_elements"])
    result.setdefault("category", [])

    text_parts = [
        segment["place_name"],
        str(segment.get("spot_name", "")),
        segment["description"],
    ]
    result["metadata_text"] = " ".join(part for part in text_parts if part)
    return result


def _validate_schema_version(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SegmentDataError("schema_version은 빈 문자열이 아닌 문자열이어야 합니다.")
    return value.strip()


def _validate_timeline(
    segments: list[dict[str, Any]],
    *,
    require_contiguous: bool,
    tolerance: float,
) -> None:
    by_video: dict[str, list[dict[str, Any]]] = {}
    for segment in segments:
        by_video.setdefault(segment["video_id"], []).append(segment)

    for video_id, video_segments in by_video.items():
        ordered = sorted(video_segments, key=lambda item: (item["start_time"], item["segment_id"]))
        for previous, current in zip(ordered, ordered[1:]):
            difference = current["start_time"] - previous["end_time"]
            if difference < -tolerance:
                raise SegmentDataError(
                    f"{video_id}의 {previous['segment_id']}와 {current['segment_id']} 시간이 겹칩니다."
                )
            if require_contiguous and abs(difference) > tolerance:
                raise SegmentDataError(
                    f"{video_id}의 {previous['segment_id']}와 {current['segment_id']} 사이 시간이 연속적이지 않습니다."
                )


def _looks_like_legacy_payload(payload: object) -> bool:
    if not isinstance(payload, Mapping):
        return False
    segments = payload.get("segments")
    return bool(
        isinstance(segments, list)
        and segments
        and isinstance(segments[0], Mapping)
        and "start_sec" in segments[0]
        and "start_time" not in segments[0]
    )


def _validate_legacy_payload(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise SegmentDataError("JSON 최상위 값은 객체여야 합니다.")
    _validate_schema_version(payload.get("schema_version"))
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise SegmentDataError("segments는 하나 이상의 구간을 가진 목록이어야 합니다.")

    loaded: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_segment in enumerate(raw_segments):
        if not isinstance(raw_segment, Mapping):
            raise SegmentDataError(f"segments[{index}]는 객체여야 합니다.")
        missing = sorted(LEGACY_REQUIRED_FIELDS - raw_segment.keys())
        if missing:
            raise SegmentDataError(
                f"segments[{index}]에 필수 항목이 없습니다: {', '.join(missing)}"
            )
        segment = dict(raw_segment)
        segment_id = _nonempty_text(segment["segment_id"], "segment_id", f"segments[{index}]")
        if segment_id in seen_ids:
            raise SegmentDataError(f"segment_id가 중복되었습니다: {segment_id}")
        seen_ids.add(segment_id)
        start = _number(segment["start_sec"], "start_sec", segment_id)
        end = _number(segment["end_sec"], "end_sec", segment_id)
        if start < 0 or end <= start:
            raise SegmentDataError(f"{segment_id}의 시간 범위를 확인하세요.")
        segment["segment_id"] = segment_id
        segment["start_sec"] = start
        segment["end_sec"] = end
        loaded.append(segment)
    return loaded
