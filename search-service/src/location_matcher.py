"""프로젝트 카탈로그로 질의의 행정 지역과 관광지명을 구분한다."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "location_alias_catalog.json"


@dataclass(frozen=True)
class MatchedPlace:
    place_id: str
    place_name: str
    matched_alias: str


@dataclass(frozen=True)
class LocationMatch:
    region_filters: tuple[str, ...] = ()
    places: tuple[MatchedPlace, ...] = ()


@dataclass(frozen=True)
class _RegionEntry:
    canonical: str
    alias: str


@dataclass(frozen=True)
class _PlaceEntry:
    place_id: str
    place_name: str
    explicit_region_filter: str | None
    alias: str


@dataclass(frozen=True)
class _Span:
    start: int
    end: int

    def overlaps(self, other: "_Span") -> bool:
        return self.start < other.end and self.end > other.start


@lru_cache(maxsize=1)
def _catalog_entries() -> tuple[tuple[_RegionEntry, ...], tuple[_PlaceEntry, ...]]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    raw_regions = payload.get("region_aliases")
    raw_places = payload.get("place_aliases")
    if not isinstance(raw_regions, list) or not raw_regions:
        raise ValueError("location_alias_catalog.json의 region_aliases가 비어 있습니다.")
    if not isinstance(raw_places, list):
        raise ValueError("location_alias_catalog.json의 place_aliases는 배열이어야 합니다.")

    regions: list[_RegionEntry] = []
    places: list[_PlaceEntry] = []
    seen_aliases: dict[str, str] = {}

    for index, item in enumerate(raw_regions):
        if not isinstance(item, dict):
            raise ValueError(f"region_aliases[{index}]는 객체여야 합니다.")
        canonical = _required_text(item.get("canonical"), f"region_aliases[{index}].canonical")
        for alias in _flatten_aliases(item.get("aliases"), f"region_aliases[{index}].aliases"):
            _register_alias(seen_aliases, alias, f"region:{canonical}")
            regions.append(_RegionEntry(canonical, alias))

    for index, item in enumerate(raw_places):
        if not isinstance(item, dict):
            raise ValueError(f"place_aliases[{index}]는 객체여야 합니다.")
        place_id = _required_text(item.get("place_id"), f"place_aliases[{index}].place_id")
        place_name = _required_text(item.get("place_name"), f"place_aliases[{index}].place_name")
        explicit = item.get("explicit_region_filter")
        if explicit is not None:
            explicit = _required_text(explicit, f"place_aliases[{index}].explicit_region_filter")
        for alias in _flatten_aliases(item.get("aliases"), f"place_aliases[{index}].aliases"):
            _register_alias(seen_aliases, alias, f"place:{place_id}")
            places.append(_PlaceEntry(place_id, place_name, explicit, alias))

    regions.sort(key=lambda entry: len(entry.alias), reverse=True)
    places.sort(key=lambda entry: len(entry.alias), reverse=True)
    return tuple(regions), tuple(places)


def analyze_locations(query: str) -> LocationMatch:
    """질문에 직접 등장한 지역과 프로젝트 관광지를 반환한다."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("query는 빈 문자열이 아니어야 합니다.")
    region_entries, place_entries = _catalog_entries()

    place_spans: list[_Span] = []
    matched_places: list[MatchedPlace] = []
    implied_regions: list[str] = []
    seen_places: set[str] = set()
    for entry in place_entries:
        for span in _find_spans(query, entry.alias):
            if any(span.overlaps(existing) for existing in place_spans):
                continue
            place_spans.append(span)
            if entry.place_id not in seen_places:
                seen_places.add(entry.place_id)
                matched_places.append(
                    MatchedPlace(entry.place_id, entry.place_name, query[span.start:span.end])
                )
            if entry.explicit_region_filter:
                implied_regions.append(entry.explicit_region_filter)

    explicit_regions: list[str] = [*implied_regions]
    for entry in region_entries:
        spans = _find_spans(query, entry.alias)
        if any(not any(span.overlaps(place_span) for place_span in place_spans) for span in spans):
            explicit_regions.append(entry.canonical)

    return LocationMatch(
        region_filters=tuple(_deduplicate(explicit_regions)),
        places=tuple(matched_places),
    )


def first_known_location_start(query: str) -> int | None:
    """질문에서 처음 등장한 프로젝트 지역·관광지 별칭의 시작 위치를 반환한다."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("query는 빈 문자열이 아니어야 합니다.")
    region_entries, place_entries = _catalog_entries()
    starts = [
        span.start
        for entry in (*region_entries, *place_entries)
        for span in _find_spans(query, entry.alias)
    ]
    return min(starts) if starts else None


def _find_spans(query: str, alias: str) -> list[_Span]:
    escaped = re.escape(alias).replace(r"\ ", r"[\s\-–—_:：,，.。'’‘\"“”]*")
    if alias.isascii() and alias[0].isalnum() and alias[-1].isalnum():
        escaped = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    return [_Span(match.start(), match.end()) for match in re.finditer(escaped, query, re.IGNORECASE)]


def _flatten_aliases(value: object, field_name: str) -> list[str]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{field_name}는 언어별 별칭 객체여야 합니다.")
    result: list[str] = []
    for language, aliases in value.items():
        if not isinstance(language, str) or not language.strip():
            raise ValueError(f"{field_name}의 언어 키가 비어 있습니다.")
        if not isinstance(aliases, list) or not aliases:
            raise ValueError(f"{field_name}.{language}는 비어 있지 않은 배열이어야 합니다.")
        result.extend(_required_text(alias, f"{field_name}.{language}") for alias in aliases)
    return result


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}은 빈 문자열이 아니어야 합니다.")
    return value.strip()


def _register_alias(seen: dict[str, str], alias: str, owner: str) -> None:
    key = re.sub(r"[\s\-–—_:：,，.。'’‘\"“”]+", "", alias.casefold())
    previous = seen.get(key)
    if previous is not None and previous != owner:
        raise ValueError(f"서로 다른 위치가 같은 별칭을 사용합니다: {alias}")
    seen[key] = owner


def _deduplicate(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result
