from __future__ import annotations

import pytest

from src.drama_title_matcher import analyze_drama_titles, load_title_catalog


@pytest.mark.parametrize(
    "query",
    [
        "A winter filming location at Woljeongsa in Pyeongchang",
        "冬の平昌にある月精寺の撮影地",
        "冬天平昌月精寺的拍摄地",
        "秋天早晨水原大学的拍摄地",
    ],
)
def test_multilingual_filter_and_known_place_are_not_unknown_title(query: str) -> None:
    result = analyze_drama_titles(query)

    assert result.status == "none"


def test_project_catalog_contains_thirteen_canonical_titles() -> None:
    titles = {str(item["canonical_title"]) for item in load_title_catalog()}

    assert len(titles) == 13
    assert "호텔 델루나" in titles
    assert "호텔델루나" not in titles


@pytest.mark.parametrize(
    ("query", "canonical"),
    [
        ("Hometown Cha-Cha-Cha filming locations", "갯마을 차차차"),
        ("愛の不時着のロケ地", "사랑의 불시착"),
        ("海岸村恰恰恰拍攝地", "갯마을 차차차"),
        ("Lovely Runner 촬영지", "선재 업고 튀어"),
    ],
)
def test_multilingual_registered_aliases_match_project_titles(
    query: str,
    canonical: str,
) -> None:
    match = analyze_drama_titles(query)

    assert match.status == "matched"
    assert match.matched_titles == (canonical,)


def test_unregistered_title_with_filming_intent_is_not_found() -> None:
    match = analyze_drama_titles("서울의 봄 촬영지")

    assert match.status == "not_found"
    assert match.possible_title == "서울의 봄"


def test_general_query_is_not_forced_into_a_drama_title() -> None:
    match = analyze_drama_titles("서울의 봄 낮 경복궁 입구")

    assert match.status == "none"
    assert match.protected_spans == ()


def test_generic_english_title_requires_work_context() -> None:
    assert analyze_drama_titles("an ancient kingdom in autumn").status == "none"
    matched = analyze_drama_titles("Kingdom filming locations")
    assert matched.status == "matched"
    assert matched.matched_titles == ("킹덤",)


def test_quoted_unknown_title_is_ambiguous_without_work_intent() -> None:
    match = analyze_drama_titles('"봄날의 기억"과 비슷한 장소')

    assert match.status == "ambiguous"
    assert match.possible_title == "봄날의 기억"
