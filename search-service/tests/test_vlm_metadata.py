import json

import pytest

from src.vlm_metadata import (
    VLMMetadataError,
    load_expected_segment_ids,
    load_vlm_metadata,
    validate_vlm_metadata,
)


def make_segment(segment_id: str = "SEG_NAMI_01_01") -> dict:
    return {
        "segment_id": segment_id,
        "season": "여름",
        "time_of_day": "낮",
        "mood": ["평화로운"],
        "scene_elements": ["수국", "숲"],
        "activity": ["산책"],
        "description": "흰색 수국이 보이는 여름 숲길",
    }


def make_payload(*segments: dict) -> dict:
    return {
        "schema_version": "1.0",
        "segments": list(segments) or [make_segment()],
    }


def test_valid_metadata_is_normalized() -> None:
    segment = make_segment()
    segment["description"] = "  흰색 수국이 보이는 장면  "

    result = validate_vlm_metadata(make_payload(segment))

    assert result[0]["description"] == "흰색 수국이 보이는 장면"
    assert result[0]["metadata_source"] == "vlm"


def test_missing_required_field_is_rejected() -> None:
    segment = make_segment()
    del segment["season"]

    with pytest.raises(VLMMetadataError, match="필수 항목"):
        validate_vlm_metadata(make_payload(segment))


def test_duplicate_segment_id_is_rejected() -> None:
    with pytest.raises(VLMMetadataError, match="중복"):
        validate_vlm_metadata(make_payload(make_segment(), make_segment()))


def test_non_list_tags_are_rejected() -> None:
    segment = make_segment()
    segment["mood"] = "평화로운"

    with pytest.raises(VLMMetadataError, match="문자열 목록"):
        validate_vlm_metadata(make_payload(segment))


def test_duplicate_tags_are_rejected_case_insensitively() -> None:
    segment = make_segment()
    segment["scene_elements"] = ["Hanok", "hanok"]

    with pytest.raises(VLMMetadataError, match="중복 태그"):
        validate_vlm_metadata(make_payload(segment))


def test_expected_ids_report_missing_and_extra() -> None:
    payload = make_payload(make_segment("SEG_001"), make_segment("SEG_999"))

    with pytest.raises(VLMMetadataError) as error:
        validate_vlm_metadata(
            payload,
            expected_segment_ids=["SEG_001", "SEG_002"],
        )

    message = str(error.value)
    assert "누락: SEG_002" in message
    assert "추가: SEG_999" in message


def test_load_expected_segment_ids(tmp_path) -> None:
    path = tmp_path / "preprocessing.json"
    path.write_text(
        json.dumps(
            {
                "segments": [
                    {"segment_id": "SEG_001"},
                    {"segment_id": "SEG_002"},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_expected_segment_ids(path) == ["SEG_001", "SEG_002"]


def test_load_vlm_metadata_checks_preprocessing_ids(tmp_path) -> None:
    path = tmp_path / "vlm.json"
    path.write_text(
        json.dumps(make_payload(make_segment("SEG_001")), ensure_ascii=False),
        encoding="utf-8",
    )

    result = load_vlm_metadata(path, expected_segment_ids=["SEG_001"])

    assert [item["segment_id"] for item in result] == ["SEG_001"]


def test_load_vlm_metadata_accepts_utf8_bom(tmp_path) -> None:
    path = tmp_path / "vlm-with-bom.json"
    path.write_text(
        json.dumps(make_payload(), ensure_ascii=False),
        encoding="utf-8-sig",
    )

    result = load_vlm_metadata(path)

    assert result[0]["segment_id"] == "SEG_NAMI_01_01"
