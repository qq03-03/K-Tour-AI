"""프로젝트 위치 별칭의 다국어 정규화 테스트."""

from __future__ import annotations

import pytest

from src.location_matcher import analyze_locations


@pytest.mark.parametrize(
    "query",
    [
        "봄 낮에 전주 한옥마을을 보여줘",
        "Show me Jeonju Hanok Village in spring during the day",
        "春の昼に全州韓屋村を見せて",
        "请展示春天白天的全州韩屋村",
    ],
)
def test_jeonju_hanok_village_maps_to_jeonju_without_place_pollution(query: str) -> None:
    result = analyze_locations(query)

    assert result.region_filters == ("전주",)
    assert [place.place_id for place in result.places] == ["P005"]


@pytest.mark.parametrize(
    "query",
    [
        "겨울 평창 월정사 촬영 장면",
        "A winter filming location at Woljeongsa in Pyeongchang",
        "冬の平昌にある月精寺の撮影地",
        "冬天平昌月精寺的拍摄地",
    ],
)
def test_pyeongchang_and_woljeongsa_are_separated(query: str) -> None:
    result = analyze_locations(query)

    assert result.region_filters == ("평창",)
    assert [place.place_id for place in result.places] == ["P014"]


def test_place_name_alone_does_not_infer_region() -> None:
    result = analyze_locations("월정사 촬영 장면")

    assert result.region_filters == ()
    assert [place.place_id for place in result.places] == ["P014"]
