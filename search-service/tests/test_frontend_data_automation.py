from __future__ import annotations

import copy
import json

import pytest

from src.frontend_data_automation import (
    PlaceIdentityConflict,
    build_coordinate_review_rows,
    coordinate_summary,
    extract_segment_ids,
    filter_accepted_segments,
    flatten_metadata,
    load_existing_coordinates,
    validate_segment_and_place_identity,
)


def nested_metadata() -> list[dict]:
    return [
        {
            "video_id_prefix": "V001",
            "drama_title": "작품",
            "places": [
                {
                    "place_id": "P001",
                    "place_name": "화성행궁",
                    "region": "경기",
                    "city": "수원",
                    "source_url": "https://example.test/one",
                    "segments": [
                        {
                            "segment_id": "V001_P001_S001",
                            "keyframe_path": "keyframes/one.jpg",
                        }
                    ],
                },
                {
                    "place_id": "P002",
                    "place_name": "제주도",
                    "region": "제주",
                    "source_url": "https://example.test/two",
                    "segments": [
                        {
                            "segment_id": "V001_P002_S001",
                            "keyframe_path": "keyframes/two.jpg",
                        }
                    ],
                },
            ],
        }
    ]


def test_flatten_and_filter_do_not_modify_source() -> None:
    payload = nested_metadata()
    original = copy.deepcopy(payload)

    flattened = flatten_metadata(payload)
    accepted = filter_accepted_segments(flattened, {"V001_P002_S001"})

    assert payload == original
    assert len(flattened) == 2
    assert accepted[0]["segment_id"] == "V001_P002_S001"
    assert accepted[0]["video_id"] == "V001"
    assert accepted[0]["drama_title"] == "작품"


def test_extract_segment_ids_from_nested_preprocessing_manifest() -> None:
    manifest = {
        "preprocessed_segments": [
            {"segment_id": "SEG_001"},
            {"nested": {"segment_id": "SEG_002"}},
        ]
    }

    assert extract_segment_ids(manifest) == {"SEG_001", "SEG_002"}


def test_missing_accepted_segment_is_rejected() -> None:
    records = flatten_metadata(nested_metadata())

    with pytest.raises(ValueError, match="metadata에 없습니다"):
        filter_accepted_segments(records, {"UNKNOWN_SEGMENT"})


def test_duplicate_segment_is_rejected() -> None:
    records = flatten_metadata(nested_metadata())
    records.append(dict(records[0]))

    with pytest.raises(ValueError, match="segment_id 중복"):
        validate_segment_and_place_identity(records)


def test_one_place_id_with_multiple_names_is_rejected() -> None:
    records = flatten_metadata(nested_metadata())
    conflicting = dict(records[0])
    conflicting["segment_id"] = "V001_P001_S002"
    conflicting["place_name"] = "다른 장소"
    records.append(conflicting)

    with pytest.raises(PlaceIdentityConflict, match="P001"):
        build_coordinate_review_rows(records)


def test_existing_coordinates_are_reused_and_broad_names_require_review() -> None:
    records = flatten_metadata(nested_metadata())
    rows = build_coordinate_review_rows(
        records,
        existing_coordinates={
            "P001": {
                "latitude": "37.2827",
                "longitude": "127.0141",
            }
        },
    )

    by_id = {row["place_id"]: row for row in rows}
    assert by_id["P001"]["selection_status"] == "기존 좌표 재사용"
    assert by_id["P001"]["latitude"] == "37.2827"
    assert by_id["P002"]["selection_status"] == "장소명 검토 필요"
    assert coordinate_summary(rows) == {
        "place_count": 2,
        "reused_count": 1,
        "lookup_count": 0,
        "review_count": 1,
    }


def test_existing_coordinate_loader_detects_conflicting_files(tmp_path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(
        json.dumps([{"place_id": "P001", "latitude": 1, "longitude": 2}]),
        encoding="utf-8",
    )
    second.write_text(
        json.dumps([{"place_id": "P001", "latitude": 3, "longitude": 4}]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="좌표가 충돌"):
        load_existing_coordinates([first, second])
