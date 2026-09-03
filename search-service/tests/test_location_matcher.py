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


def test_gyeongsang_region_expands_to_five_database_regions() -> None:
    result = analyze_locations("경상도 야경 촬영지 보여줘")

    assert result.region_filters == ("부산", "대구", "울산", "경북", "경남")


def test_specific_busan_query_does_not_expand_to_gyeongsang_region() -> None:
    result = analyze_locations("부산 야경 촬영지 보여줘")

    assert result.region_filters == ("부산",)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("수도권 촬영지", ("서울", "경기", "인천")),
        ("충청도 촬영지", ("대전", "세종", "충북", "충남")),
        ("호남권 촬영지", ("광주", "전북", "전남")),
        ("영남권 촬영지", ("부산", "대구", "울산", "경북", "경남")),
    ],
)
def test_broad_region_aliases_expand_to_configured_regions(
    query: str,
    expected: tuple[str, ...],
) -> None:
    assert analyze_locations(query).region_filters == expected
