from __future__ import annotations

import importlib.util
from pathlib import Path


TOOL_PATH = Path(__file__).resolve().parents[2] / "tools" / "lookup_kakao_coordinates.py"
SPEC = importlib.util.spec_from_file_location("lookup_kakao_coordinates", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def review_row(place_id: str, latitude: str = "", longitude: str = "") -> dict[str, str]:
    return {
        "place_id": place_id,
        "source_segment_id": f"{place_id}_SEG",
        "video_id": f"{place_id}_VIDEO",
        "source_url": "https://example.test/video",
        "current_place_candidates": "화성행궁",
        "region": "경기도",
        "city": "수원시",
        "latitude": latitude,
        "longitude": longitude,
    }


def test_coordinate_query_skips_places_with_existing_coordinates() -> None:
    units = MODULE.build_query_units(
        [
            review_row("P001", latitude="37.2", longitude="127.0"),
            review_row("P002"),
        ]
    )

    assert len(units) == 1
    assert units[0]["place_id"] == "P002"
    assert units[0]["query"] == "화성행궁 수원시"


def test_kakao_response_maps_y_to_latitude_and_x_to_longitude() -> None:
    unit = MODULE.build_query_units([review_row("P001")])[0]
    rows = MODULE.result_rows(
        unit,
        [
            {
                "place_name": "화성행궁",
                "category_name": "관광명소",
                "address_name": "경기 수원시 팔달구",
                "road_address_name": "경기 수원시 팔달구 정조로 825",
                "y": "37.2827",
                "x": "127.0141",
                "place_url": "https://place.map.kakao.com/example",
            }
        ],
    )

    assert rows[0]["latitude"] == "37.2827"
    assert rows[0]["longitude"] == "127.0141"
    assert rows[0]["selection_status"] == "미검수"


def test_empty_kakao_response_is_kept_for_manual_review() -> None:
    unit = MODULE.build_query_units([review_row("P001")])[0]

    rows = MODULE.result_rows(unit, [])

    assert rows[0]["selection_status"] == "검색 결과 없음"
