from __future__ import annotations

from ktour_search_automation.coordinates import validate_coordinate_alignment


def test_coordinate_alignment_reports_near_but_does_not_merge() -> None:
    metadata = [
        {"place_id": "P001", "place_name": "장소1", "region": "서울", "city": "서울"},
        {"place_id": "P002", "place_name": "장소2", "region": "서울", "city": "서울"},
    ]
    coordinates = {
        "records": [
            {"place_id": "P001", "place_name": "장소1", "region": "서울", "city": "서울", "latitude": 37.0, "longitude": 127.0},
            {"place_id": "P002", "place_name": "장소2", "region": "서울", "city": "서울", "latitude": 37.0, "longitude": 127.0},
        ]
    }

    report = validate_coordinate_alignment(metadata, coordinates)

    assert report["is_valid"] is True
    assert report["duplicate_or_near_candidates"][0]["exact_same_coordinate"] is True
    assert report["coordinate_count"] == 2


def test_coordinate_outside_korea_bounds_is_blocking() -> None:
    metadata = [
        {"place_id": "P001", "place_name": "장소1", "region": "서울", "city": "서울"}
    ]
    coordinates = {
        "records": [
            {
                "place_id": "P001",
                "place_name": "장소1",
                "region": "서울",
                "city": "서울",
                "latitude": 0.0,
                "longitude": 0.0,
            }
        ]
    }

    report = validate_coordinate_alignment(metadata, coordinates)

    assert report["is_valid"] is False
    assert any(
        issue["code"] == "COORDINATE_OUTSIDE_KOREA_BOUNDS"
        for issue in report["issues"]
    )
