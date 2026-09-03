"""검수 완료 테마 매핑을 source_segment_id 하드 필터로 적용한다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


THEME_ALIASES: Mapping[str, str] = {
    "night-view": "night_view",
    "night_view": "night_view",
    "drive": "drive",
    "cherry-blossom": "flower",
    "flower": "flower",
    "autumn-leaves": "autumn_leaves",
    "autumn_leaves": "autumn_leaves",
    "beach": "sea",
    "sea": "sea",
    "traditional": "traditional",
    "field": "field",
    "hiking": "hiking",
    "forest": "forest",
}

THEME_SEARCH_TEXT: Mapping[str, str] = {
    "night_view": "야경 밤 조명 관광지",
    "drive": "드라이브 도로 풍경 관광지",
    "flower": "꽃 벚꽃 꽃길 관광지",
    "autumn_leaves": "가을 단풍 관광지",
    "sea": "바다 바닷가 해안 관광지",
    "traditional": "전통 한옥 궁궐 문화유산 관광지",
    "field": "들판 초원 평야 관광지",
    "hiking": "등산 산행 산 관광지",
    "forest": "숲 수목원 자연휴양림 관광지",
}


def normalize_themes(values: str | Sequence[str] | None) -> list[str]:
    if values is None:
        return []
    raw_values: Sequence[str] = [values] if isinstance(values, str) else values
    if isinstance(raw_values, (str, bytes)) or not isinstance(raw_values, Sequence):
        raise TypeError("theme은 문자열 또는 문자열 목록이어야 합니다.")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        if not isinstance(raw, str) or not raw.strip():
            continue
        key = raw.strip().casefold()
        canonical = THEME_ALIASES.get(key)
        if canonical is None:
            raise ValueError(f"지원하지 않는 theme입니다: {raw}")
        if canonical not in seen:
            seen.add(canonical)
            normalized.append(canonical)
    return normalized


def build_theme_index(payload: Mapping[str, Any] | None) -> dict[str, set[str]]:
    """검수 완료 entries를 theme -> source_segment_id 집합으로 변환한다."""

    index = {theme: set() for theme in set(THEME_ALIASES.values())}
    if payload is None:
        return index
    entries = payload.get("entries")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise ValueError("theme mapping은 entries 배열을 가져야 합니다.")
    seen_sources: set[str] = set()
    for position, item in enumerate(entries):
        if not isinstance(item, Mapping):
            raise ValueError(f"theme mapping entries[{position}]는 객체여야 합니다.")
        source_id = item.get("source_segment_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError(f"theme mapping entries[{position}].source_segment_id가 비었습니다.")
        source_id = source_id.strip()
        if source_id in seen_sources:
            raise ValueError(f"theme mapping source_segment_id 중복: {source_id}")
        seen_sources.add(source_id)
        for theme in normalize_themes(item.get("themes")):
            index[theme].add(source_id)
    return index


def filter_by_themes(
    segments: Sequence[Mapping[str, Any]],
    themes: str | Sequence[str] | None,
    *,
    theme_index: Mapping[str, set[str]],
) -> list[dict[str, Any]]:
    """같은 필드의 여러 theme은 OR로 적용한다."""

    normalized = normalize_themes(themes)
    if not normalized:
        return [dict(item) for item in segments]
    allowed_sources: set[str] = set()
    for theme in normalized:
        allowed_sources.update(theme_index.get(theme, set()))
    return [
        dict(item)
        for item in segments
        if _source_segment_id(item) in allowed_sources
    ]


def theme_search_text(themes: str | Sequence[str] | None) -> str:
    return " ".join(THEME_SEARCH_TEXT[item] for item in normalize_themes(themes))


def _source_segment_id(item: Mapping[str, Any]) -> str:
    explicit = item.get("source_segment_id")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    segment_id = item.get("segment_id")
    if not isinstance(segment_id, str):
        return ""
    parent, marker, number = segment_id.rpartition("_SCENE_")
    return parent if marker and number.isdigit() else segment_id
