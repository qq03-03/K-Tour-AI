"""통합 구간 JSON 로더와 남이섬 샘플 데이터 검증."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.data_loader import SegmentDataError, load_segments, validate_segments


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "nami_segments.json"


@pytest.fixture()
def payload() -> dict[str, object]:
    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def test_nami_sample_has_nine_valid_segments() -> None:
    segments = load_segments(DATA_PATH)

    assert len(segments) == 9
    assert len({segment["segment_id"] for segment in segments}) == 9
    assert {segment["place_id"] for segment in segments} == {"PLC_NAMI_001"}


def test_loader_adds_existing_search_field_aliases() -> None:
    segment = load_segments(DATA_PATH)[0]

    assert segment["start_sec"] == segment["start_time"] == 0.0
    assert segment["end_sec"] == segment["end_time"] == 18.0
    assert segment["location_name"] == segment["place_name"] == "남이섬"
    assert segment["landscape"] == segment["scene_elements"]
    assert "남이섬 입구 및 얼음 구조물" in segment["metadata_text"]


def test_missing_required_field_is_rejected(payload: dict[str, object]) -> None:
    changed = copy.deepcopy(payload)
    del changed["segments"][0]["place_id"]  # type: ignore[index]

    with pytest.raises(SegmentDataError, match="필수 항목.*place_id"):
        validate_segments(changed)


def test_duplicate_segment_id_is_rejected(payload: dict[str, object]) -> None:
    changed = copy.deepcopy(payload)
    changed["segments"][1]["segment_id"] = changed["segments"][0]["segment_id"]  # type: ignore[index]

    with pytest.raises(SegmentDataError, match="segment_id가 중복"):
        validate_segments(changed)


@pytest.mark.parametrize(
    ("start_time", "end_time"),
    [(-1, 10), (10, 10), (11, 10), (False, 10)],
)
def test_invalid_time_values_are_rejected(
    payload: dict[str, object],
    start_time: object,
    end_time: object,
) -> None:
    changed = copy.deepcopy(payload)
    changed["segments"][0]["start_time"] = start_time  # type: ignore[index]
    changed["segments"][0]["end_time"] = end_time  # type: ignore[index]

    with pytest.raises(SegmentDataError):
        validate_segments(changed)


def test_duplicate_tag_is_rejected(payload: dict[str, object]) -> None:
    changed = copy.deepcopy(payload)
    changed["segments"][0]["mood"] = ["고요한", " 고요한 "]  # type: ignore[index]

    with pytest.raises(SegmentDataError, match="중복 태그"):
        validate_segments(changed)


def test_keyframes_can_be_required_after_images_arrive() -> None:
    with pytest.raises(SegmentDataError, match="keyframe_path가 필요"):
        load_segments(DATA_PATH, require_keyframes=True)
