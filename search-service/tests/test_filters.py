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
        raw_segments = json.load(file)["segments"]

    # 실제 프로덕션 DB(segment_row.segment_from_row)가 만드는 구간 딕셔너리는
    # "landscape"가 아니라 "scene_elements" 키를 사용한다. 더미 픽스처 파일은
    # 다른(레거시) 파이프라인 테스트들과 공유되므로 파일 자체는 그대로 두고,
    # 여기서만 filters.py가 실제로 받는 필드명으로 맞춰준다.
    for segment in raw_segments:
        segment["scene_elements"] = segment.pop("landscape")
    return raw_segments


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


def test_landscapes_filter_matches_scene_elements_field() -> None:
    """실제 DB 구간 딕셔너리(segment_row.segment_from_row)처럼 'landscape' 키가
    없고 'scene_elements' 키만 있는 구간도 landscapes= 필터로 매칭돼야 한다.

    회귀 방지: filter_segments가 내부적으로 segment.get("landscape")를 조회하면
    이런 구간은 항상 걸러지고, 실사용 시 TypeError까지 발생한다.
    """

    segments = [
        {
            "segment_id": "SEG_REAL_1",
            "scene_elements": ["한옥", "단풍", "마당"],
        },
        {
            "segment_id": "SEG_REAL_2",
            "scene_elements": ["바다", "노을"],
        },
    ]

    results = filter_segments(
        segments,
        landscapes=["한옥", "단풍"],
        landscape_match="all",
    )

    assert segment_ids(results) == ["SEG_REAL_1"]


def _ui_filter_segments() -> list[dict[str, object]]:
    """UI 하드 필터 3종(place_id·city·drama_title)을 가진 실제 DB 형태의 구간."""

    return [
        {
            "segment_id": "SEG_UI_1",
            "place_id": "P031",
            "city": "충주시",
            "region": "충청북도",
            "drama_title": "사랑의 불시착",
        },
        {
            "segment_id": "SEG_UI_2",
            "place_id": "P031",
            "city": "충주시",
            "region": "충청북도",
            "drama_title": "겨울연가",
        },
        {
            "segment_id": "SEG_UI_3",
            "place_id": "P042",
            "city": "춘천시",
            "region": "강원특별자치도",
            "drama_title": "겨울연가",
        },
    ]


def test_place_id_filter_matches_exactly() -> None:
    results = filter_segments(_ui_filter_segments(), place_ids="P031")

    assert segment_ids(results) == ["SEG_UI_1", "SEG_UI_2"]


def test_city_filter_matches_after_normalization() -> None:
    results = filter_segments(_ui_filter_segments(), cities=" 춘천시 ")

    assert segment_ids(results) == ["SEG_UI_3"]


def test_drama_title_filter_matches_normalized_title() -> None:
    results = filter_segments(_ui_filter_segments(), drama_titles="겨울연가")

    assert segment_ids(results) == ["SEG_UI_2", "SEG_UI_3"]


def test_place_id_filter_ignores_case_and_surrounding_spaces() -> None:
    results = filter_segments(_ui_filter_segments(), place_ids=[" p031 "])

    assert segment_ids(results) == ["SEG_UI_1", "SEG_UI_2"]


def test_multiple_drama_titles_use_or_condition() -> None:
    results = filter_segments(
        _ui_filter_segments(),
        drama_titles=["사랑의 불시착", "겨울연가"],
    )

    assert segment_ids(results) == ["SEG_UI_1", "SEG_UI_2", "SEG_UI_3"]


def test_multiple_place_ids_use_or_condition() -> None:
    results = filter_segments(_ui_filter_segments(), place_ids=["P031", "P042"])

    assert segment_ids(results) == ["SEG_UI_1", "SEG_UI_2", "SEG_UI_3"]


def test_ui_hard_filters_from_different_fields_use_and_condition() -> None:
    """같은 필드 여러 값은 OR, 서로 다른 필드는 AND로 결합된다."""

    results = filter_segments(
        _ui_filter_segments(),
        place_ids=["P031", "P042"],
        drama_titles=["겨울연가"],
        cities=["충주시"],
    )

    assert segment_ids(results) == ["SEG_UI_2"]


def test_ui_hard_filters_combine_with_existing_scalar_filters() -> None:
    results = filter_segments(
        _ui_filter_segments(),
        regions="충청북도",
        drama_titles="겨울연가",
    )

    assert segment_ids(results) == ["SEG_UI_2"]


def test_no_matching_ui_hard_filter_returns_empty_list() -> None:
    assert filter_segments(_ui_filter_segments(), place_ids="P999") == []


@pytest.mark.parametrize("keyword", ["place_ids", "cities", "drama_titles"])
def test_ui_hard_filter_is_not_applied_when_omitted(keyword: str) -> None:
    """None을 전달하면 해당 필드 필터는 적용되지 않는다."""

    segments = _ui_filter_segments()

    results = filter_segments(segments, **{keyword: None})  # type: ignore[arg-type]

    assert segment_ids(results) == segment_ids(segments)


@pytest.mark.parametrize("field_name", ["place_id", "city", "drama_title"])
def test_invalid_segment_ui_hard_filter_field_raises_error(field_name: str) -> None:
    segment = {"segment_id": "SEG_BAD", field_name: None}
    keyword = {"place_id": "place_ids", "city": "cities", "drama_title": "drama_titles"}[
        field_name
    ]

    with pytest.raises(TypeError, match=f"SEG_BAD.*{field_name}"):
        filter_segments([segment], **{keyword: "값"})  # type: ignore[arg-type]


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
