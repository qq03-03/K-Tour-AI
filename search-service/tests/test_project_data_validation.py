from __future__ import annotations

from src.project_data_validation import validate_project_metadata


def record(**overrides):
    value = {
        "segment_id": "SEG_01",
        "video_id": "VID_01",
        "place_id": "P001",
        "place_name": "화성행궁",
        "region": "경기도",
        "city": "수원시",
        "drama_title": "드라마",
        "start_time": 1.0,
        "end_time": 5.0,
        "keyframe_path": "keyframes/VID_01/SCENE_01.jpg",
        "season": "봄",
        "time_of_day": "낮",
        "mood": ["평화로운"],
        "activity": ["걷기"],
        "scene_elements": ["한옥"],
        "description": "한옥 앞을 걷는 장면",
    }
    value.update(overrides)
    return value


def codes(report):
    return [issue["code"] for issue in report["issues"]]


def test_multiple_keyframes_for_same_segment_are_valid() -> None:
    payload = [
        record(),
        record(keyframe_path="keyframes/VID_01/SCENE_02.jpg"),
    ]

    report = validate_project_metadata(payload)

    assert report["is_valid"] is True
    assert report["summary"]["record_count"] == 2
    assert report["summary"]["unique_segment_count"] == 1


def test_same_place_id_with_different_places_is_rejected() -> None:
    payload = [
        record(),
        record(
            segment_id="SEG_02",
            video_id="VID_02",
            keyframe_path="keyframes/VID_02/SCENE_01.jpg",
            place_name="경천섬공원",
            region="경상북도",
            city="상주시",
        ),
    ]

    report = validate_project_metadata(payload)

    assert report["is_valid"] is False
    assert "PLACE_ID_CONFLICT" in codes(report)


def test_same_segment_with_conflicting_place_id_is_rejected() -> None:
    payload = [
        record(),
        record(
            place_id="P002",
            place_name="다른 장소",
            keyframe_path="keyframes/VID_01/SCENE_02.jpg",
        ),
    ]

    report = validate_project_metadata(payload)

    assert "SEGMENT_CONFLICT" in codes(report)


def test_noncanonical_season_and_time_are_rejected() -> None:
    report = validate_project_metadata(
        [record(season="spring, summer", time_of_day="day")]
    )

    assert "NON_CANONICAL_SEASON" in codes(report)
    assert "NON_CANONICAL_TIME_OF_DAY" in codes(report)


def test_invalid_time_and_duplicate_keyframe_are_rejected() -> None:
    payload = [record(start_time=5.0, end_time=5.0), record(segment_id="SEG_02")]

    report = validate_project_metadata(payload)

    assert "INVALID_TIME_RANGE" in codes(report)
    assert "DUPLICATE_KEYFRAME_PATH" in codes(report)


def test_missing_city_is_a_warning_not_an_error() -> None:
    value = record()
    value.pop("city")

    report = validate_project_metadata([value])

    assert report["is_valid"] is True
    assert "CITY_NOT_PROVIDED" in codes(report)
