"""P001~P030 다국어 위치 별칭 카탈로그의 완전성과 검색 연결을 검증한다."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.location_matcher import analyze_locations


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "location_alias_catalog.json"
REQUIRED_LANGUAGES = {"ko", "en", "ja", "zh"}
EXPECTED_PLACE_IDS = {f"P{index:03d}" for index in range(1, 31)}


def _catalog() -> dict[str, object]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_catalog_contains_exactly_p001_through_p030() -> None:
    places = _catalog()["place_aliases"]
    assert isinstance(places, list)

    actual_ids = [place["place_id"] for place in places]
    assert len(actual_ids) == 30
    assert len(set(actual_ids)) == 30
    assert set(actual_ids) == EXPECTED_PLACE_IDS


def test_every_place_has_all_four_nonempty_language_aliases() -> None:
    places = _catalog()["place_aliases"]
    assert isinstance(places, list)

    for place in places:
        aliases = place["aliases"]
        assert set(aliases) == REQUIRED_LANGUAGES, place["place_id"]
        for language in REQUIRED_LANGUAGES:
            assert aliases[language], f"{place['place_id']}.{language}"
            assert all(alias.strip() for alias in aliases[language])


@pytest.mark.parametrize("language", ["ko", "en", "ja", "zh"])
def test_first_alias_of_every_place_resolves_to_its_place_id(language: str) -> None:
    places = _catalog()["place_aliases"]
    assert isinstance(places, list)

    for place in places:
        alias = place["aliases"][language][0]
        result = analyze_locations(f"{alias} 촬영 장면")
        assert [matched.place_id for matched in result.places] == [place["place_id"]], (
            place["place_id"],
            language,
            alias,
        )
