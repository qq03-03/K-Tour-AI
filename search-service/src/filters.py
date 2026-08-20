"""영상 구간에 지역·계절·감성 구조화 필터를 적용한다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal


MatchMode = Literal["all", "any"]


def filter_segments(
    segments: Sequence[Mapping[str, Any]],
    *,
    regions: str | Sequence[str] | None = None,
    seasons: str | Sequence[str] | None = None,
    times_of_day: str | Sequence[str] | None = None,
    moods: str | Sequence[str] | None = None,
    activities: str | Sequence[str] | None = None,
    landscapes: str | Sequence[str] | None = None,
    categories: str | Sequence[str] | None = None,
    mood_match: MatchMode = "all",
    activity_match: MatchMode = "all",
    landscape_match: MatchMode = "all",
    category_match: MatchMode = "all",
) -> list[Mapping[str, Any]]:
    """구조화 조건을 만족하는 영상 구간을 원래 순서대로 반환한다.

    지역·계절·시간대는 지정한 값 중 하나가 일치하면 통과한다.
    감성·활동·풍경·카테고리는 각각의 ``*_match`` 값이 ``"all"``이면
    모든 값, ``"any"``이면 하나 이상의 값이 포함되어야 한다.
    """

    _validate_match_mode(mood_match, "mood_match")
    _validate_match_mode(activity_match, "activity_match")
    _validate_match_mode(landscape_match, "landscape_match")
    _validate_match_mode(category_match, "category_match")

    normalized_regions = _normalize_filter_values(regions, "regions")
    normalized_seasons = _normalize_filter_values(seasons, "seasons")
    normalized_times = _normalize_filter_values(times_of_day, "times_of_day")
    normalized_moods = _normalize_filter_values(moods, "moods")
    normalized_activities = _normalize_filter_values(activities, "activities")
    normalized_landscapes = _normalize_filter_values(landscapes, "landscapes")
    normalized_categories = _normalize_filter_values(categories, "categories")

    if not any(
        (
            normalized_regions,
            normalized_seasons,
            normalized_times,
            normalized_moods,
            normalized_activities,
            normalized_landscapes,
            normalized_categories,
        )
    ):
        return list(segments)

    filtered: list[Mapping[str, Any]] = []
    for segment in segments:
        if normalized_regions:
            region = _normalize_scalar_field(segment, "region")
            if region not in normalized_regions:
                continue

        if normalized_seasons:
            season = _normalize_scalar_field(segment, "season")
            if season not in normalized_seasons:
                continue

        if normalized_times:
            time_of_day = _normalize_scalar_field(segment, "time_of_day")
            if time_of_day not in normalized_times:
                continue

        list_filters = (
            ("mood", normalized_moods, mood_match),
            ("activity", normalized_activities, activity_match),
            ("scene_elements", normalized_landscapes, landscape_match),
            ("category", normalized_categories, category_match),
        )
        if any(
            requested
            and not _matches_list_filter(segment, field_name, requested, match_mode)
            for field_name, requested, match_mode in list_filters
        ):
            continue

        filtered.append(segment)

    return filtered


def _validate_match_mode(value: str, field_name: str) -> None:
    if value not in ("all", "any"):
        raise ValueError(f"{field_name}는 'all' 또는 'any'여야 합니다.")


def _matches_list_filter(
    segment: Mapping[str, Any],
    field_name: str,
    requested: set[str],
    match_mode: MatchMode,
) -> bool:
    segment_values = _normalize_list_field(segment, field_name)
    if match_mode == "all":
        return requested.issubset(segment_values)
    return not requested.isdisjoint(segment_values)


def _normalize_filter_values(
    values: str | Sequence[str] | None,
    field_name: str,
) -> set[str]:
    if values is None:
        return set()

    if isinstance(values, str):
        items: Sequence[str] = [values]
    elif isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        items = values
    else:
        raise TypeError(f"{field_name}는 문자열 또는 문자열 목록이어야 합니다.")

    normalized: set[str] = set()
    for value in items:
        if not isinstance(value, str):
            raise TypeError(f"{field_name}의 모든 값은 문자열이어야 합니다.")
        cleaned = value.strip().casefold()
        if not cleaned:
            raise ValueError(f"{field_name}에는 빈 문자열을 사용할 수 없습니다.")
        normalized.add(cleaned)
    return normalized


def _normalize_scalar_field(segment: Mapping[str, Any], field_name: str) -> str:
    value = segment.get(field_name)
    if not isinstance(value, str) or not value.strip():
        segment_id = segment.get("segment_id", "(알 수 없음)")
        raise TypeError(
            f"{segment_id} 구간의 {field_name}은 빈 문자열이 아닌 문자열이어야 합니다."
        )
    return value.strip().casefold()


def _normalize_list_field(
    segment: Mapping[str, Any], field_name: str
) -> set[str]:
    values = segment.get(field_name)
    segment_id = segment.get("segment_id", "(알 수 없음)")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{segment_id} 구간의 {field_name}은 문자열 목록이어야 합니다.")

    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise TypeError(
                f"{segment_id} 구간의 {field_name} 값은 빈 문자열이 아닌 문자열이어야 합니다."
            )
        normalized.add(value.strip().casefold())
    return normalized
