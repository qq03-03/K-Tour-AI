"""지역·계절·감성 구조화 필터 테스트."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.filters import filter_segments


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "dummy_segments.json"


@pytest.fixture(scope="module")
def segments() -> list[dict[str, object]]:
    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)["segments"]


def segment_ids(items: list[object]) -> list[str]:
    return [item["segment_id"] for item in items]  # type: ignore[index]


def test_no_filters_returns_all_segments_in_original_order(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(segments)

    assert segment_ids(results) == segment_ids(segments)


def test_region_filter(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(segments, regions="서울")

    assert segment_ids(results) == ["SEG_003", "SEG_005", "SEG_006", "SEG_007"]


def test_province_filter_accepts_short_and_official_names() -> None:
    sample = [
        {"segment_id": "SEOUL", "region": "서울특별시"},
        {"segment_id": "GANGWON", "region": "강원특별자치도"},
    ]

    assert segment_ids(filter_segments(sample, regions="서울")) == ["SEOUL"]
    assert segment_ids(filter_segments(sample, regions="강원도")) == ["GANGWON"]


def test_gyeongsang_region_values_filter_with_or_semantics() -> None:
    sample = [
        {"segment_id": "BUSAN", "region": "부산광역시"},
        {"segment_id": "DAEGU", "region": "대구광역시"},
        {"segment_id": "ULSAN", "region": "울산광역시"},
        {"segment_id": "GYEONGBUK", "region": "경상북도"},
        {"segment_id": "GYEONGNAM", "region": "경상남도"},
        {"segment_id": "SEOUL", "region": "서울특별시"},
    ]

    regions = ["부산", "대구", "울산", "경북", "경남"]

    assert segment_ids(filter_segments(sample, regions=regions)) == [
        "BUSAN",
        "DAEGU",
        "ULSAN",
        "GYEONGBUK",
        "GYEONGNAM",
    ]
    assert segment_ids(filter_segments(sample, regions="부산")) == ["BUSAN"]


def test_city_filter_does_not_expand_to_the_entire_province() -> None:
    sample = [
        {
            "segment_id": "GANGNEUNG",
            "region": "강원특별자치도",
            "city": "강릉시",
        },
        {
            "segment_id": "PYEONGCHANG",
            "region": "강원특별자치도",
            "city": "평창군",
        },
    ]

    assert segment_ids(filter_segments(sample, regions="강릉")) == ["GANGNEUNG"]


def test_city_filter_can_use_place_name_or_metadata_address() -> None:
    sample = [
        {
            "segment_id": "JUMUNJIN",
            "region": "강원특별자치도",
            "place_name": "강릉 주문진",
        },
        {
            "segment_id": "OMOKDAE",
            "region": "전북특별자치도",
            "place_name": "오목대",
            "metadata": {
                "address": "전북특별자치도 전주시 완산구 기린대로 55"
            },
        },
    ]

    assert segment_ids(filter_segments(sample, regions="강릉")) == ["JUMUNJIN"]
    assert segment_ids(filter_segments(sample, regions="전주")) == ["OMOKDAE"]


def test_city_filter_uses_place_id_fallback_before_places_table_is_connected() -> None:
    sample = [
        {
            "segment_id": "OMOKDAE",
            "place_id": "P009",
            "region": "전북특별자치도",
            "place_name": "오목대",
        },
        {
            "segment_id": "GOCHANG",
            "place_id": "P004",
            "region": "전북특별자치도",
            "place_name": "고창 학원농장",
        },
    ]

    assert segment_ids(filter_segments(sample, regions="전주")) == ["OMOKDAE"]


def test_structured_city_takes_precedence_over_place_id_fallback() -> None:
    sample = [
        {
            "segment_id": "UPDATED_CITY",
            "place_id": "P009",
            "region": "전북특별자치도",
            "city": "고창군",
            "place_name": "오목대",
        }
    ]

    assert filter_segments(sample, regions="전주") == []
    assert segment_ids(filter_segments(sample, regions="고창")) == ["UPDATED_CITY"]


def test_multiple_regions_use_or_condition(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(segments, regions=["서울", "부산"])

    assert segment_ids(results) == [
        "SEG_003",
        "SEG_005",
        "SEG_006",
        "SEG_007",
        "SEG_008",
        "SEG_009",
    ]


def test_season_filter(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(segments, seasons="겨울")

    assert segment_ids(results) == [
        "SEG_005",
        "SEG_011",
        "SEG_014",
        "SEG_019",
    ]


def test_region_and_season_use_and_condition(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(segments, regions="서울", seasons="봄")

    assert segment_ids(results) == ["SEG_003", "SEG_006"]


def test_place_city_and_drama_filters_use_or_within_and_across_fields() -> None:
    sample = [
        {
            "segment_id": "A",
            "place_id": "P001",
            "drama_title": "작품 A",
            "city": "수원시",
        },
        {
            "segment_id": "B",
            "place_id": "P002",
            "drama_title": "작품 B",
            "city": "수원시",
        },
        {
            "segment_id": "C",
            "place_id": "P003",
            "drama_title": "작품 A",
            "city": "서울특별시",
        },
    ]

    results = filter_segments(
        sample,
        place_ids=["P001", "P003"],
        drama_titles="작품 A",
        cities="수원",
    )

    assert segment_ids(results) == ["A"]


def test_multiple_times_of_day_use_or_condition(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(segments, times_of_day=["밤", "해질녘"])

    assert segment_ids(results) == [
        "SEG_004",
        "SEG_007",
        "SEG_009",
        "SEG_011",
        "SEG_018",
        "SEG_019",
    ]


def test_english_evening_and_sunset_match_korean_twilight_filter() -> None:
    sample = [
        {"segment_id": "EVENING", "time_of_day": "evening"},
        {"segment_id": "SUNSET", "time_of_day": "sunset"},
        {"segment_id": "NIGHT", "time_of_day": "night"},
    ]

    assert segment_ids(filter_segments(sample, times_of_day="해질녘")) == [
        "EVENING",
        "SUNSET",
    ]


def test_mood_all_requires_every_requested_mood(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(
        segments,
        moods=["고요한", "따뜻한"],
        mood_match="all",
    )

    assert segment_ids(results) == ["SEG_001"]


def test_mood_any_accepts_one_requested_mood(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(
        segments,
        moods=["역동적인", "신비로운"],
        mood_match="any",
    )

    assert segment_ids(results) == ["SEG_004", "SEG_011", "SEG_014", "SEG_020"]


def test_activity_all_requires_every_requested_activity(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(
        segments,
        activities=["산책", "사진촬영"],
        activity_match="all",
    )

    assert segment_ids(results) == ["SEG_001", "SEG_003", "SEG_017"]


def test_landscape_all_requires_every_requested_element(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(
        segments,
        landscapes=["한옥", "단풍"],
        landscape_match="all",
    )

    assert segment_ids(results) == ["SEG_001", "SEG_020"]


def test_category_any_accepts_one_requested_category(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(
        segments,
        categories=["궁궐", "성곽"],
        category_match="any",
    )

    assert segment_ids(results) == ["SEG_005", "SEG_006", "SEG_018"]


def test_filters_from_different_groups_use_and_condition(
    segments: list[dict[str, object]],
) -> None:
    results = filter_segments(
        segments,
        regions="서울",
        times_of_day="밤",
        moods="활기찬",
        categories="도심",
    )

    assert segment_ids(results) == ["SEG_007"]


def test_filter_values_ignore_case_and_surrounding_spaces() -> None:
    sample = [
        {
            "segment_id": "SEG_A",
            "region": " Seoul ",
            "season": "AUTUMN",
            "mood": [" Quiet ", "Traditional"],
        }
    ]

    results = filter_segments(
        sample,
        regions="seoul",
        seasons=" autumn ",
        moods=["QUIET", "traditional"],
    )

    assert segment_ids(results) == ["SEG_A"]


def test_no_matching_segment_returns_empty_list(
    segments: list[dict[str, object]],
) -> None:
    assert filter_segments(segments, regions="없는 지역") == []


@pytest.mark.parametrize(
    "keyword",
    ["mood_match", "activity_match", "landscape_match", "category_match"],
)
def test_invalid_match_mode_raises_error(keyword: str) -> None:
    with pytest.raises(ValueError, match=keyword):
        filter_segments([], **{keyword: "some"})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("keyword", "value", "error_type"),
    [
        ("regions", "  ", ValueError),
        ("seasons", ["가을", 1], TypeError),
        ("moods", 3, TypeError),
    ],
)
def test_invalid_filter_value_raises_error(
    keyword: str,
    value: object,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        filter_segments([], **{keyword: value})  # type: ignore[arg-type]


def test_invalid_segment_scalar_field_raises_error() -> None:
    segment = {"segment_id": "SEG_BAD", "region": None}

    with pytest.raises(TypeError, match="SEG_BAD.*region"):
        filter_segments([segment], regions="서울")


@pytest.mark.parametrize("bad_mood", ["quiet", None, ["quiet", 1]])
def test_invalid_segment_mood_field_raises_error(bad_mood: object) -> None:
    segment = {"segment_id": "SEG_BAD", "mood": bad_mood}

    with pytest.raises(TypeError, match="SEG_BAD.*mood"):
        filter_segments([segment], moods="quiet")
