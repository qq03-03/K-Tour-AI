"""영상 구간에 지역·계절·감성 구조화 필터를 적용한다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal


MatchMode = Literal["all", "any"]


_SEASON_CANONICAL = {
    "spring": "봄",
    "summer": "여름",
    "autumn": "가을",
    "fall": "가을",
    "winter": "겨울",
}
_TIME_OF_DAY_CANONICAL = {
    "dawn": "새벽",
    "morning": "아침",
    "day": "낮",
    "daytime": "낮",
    "evening": "해질녘",
    "sunset": "해질녘",
    "dusk": "해질녘",
    "night": "밤",
}
_REGION_CANONICAL = {
    "서울": "서울",
    "서울시": "서울",
    "서울특별시": "서울",
    "인천": "인천",
    "인천시": "인천",
    "인천광역시": "인천",
    "부산": "부산",
    "부산시": "부산",
    "부산광역시": "부산",
    "대구": "대구",
    "대구시": "대구",
    "대구광역시": "대구",
    "울산": "울산",
    "울산시": "울산",
    "울산광역시": "울산",
    "광주": "광주",
    "광주시": "광주",
    "광주광역시": "광주",
    "대전": "대전",
    "대전시": "대전",
    "대전광역시": "대전",
    "세종": "세종",
    "세종시": "세종",
    "세종특별자치시": "세종",
    "경기": "경기",
    "경기도": "경기",
    "강원": "강원",
    "강원도": "강원",
    "강원특별자치도": "강원",
    "전북": "전북",
    "전라북도": "전북",
    "전북특별자치도": "전북",
    "전남": "전남",
    "전라남도": "전남",
    "경북": "경북",
    "경상북도": "경북",
    "경남": "경남",
    "경상남도": "경남",
    "제주": "제주",
    "제주도": "제주",
    "제주특별자치도": "제주",
}
# places 테이블이 검색 결과에 city를 제공하기 전까지 사용하는 MVP 보정표다.
# segment 또는 metadata에 city/address가 있으면 그 구조화 값을 함께 사용한다.
_PLACE_CITY_FALLBACKS = {
    "P001": "수원시",
    "P002": "영등포구",
    "P003": "화성시",
    "P004": "고창군",
    "P005": "전주시",
    "P006": "논산시",
    "P007": "전주시",
    "P008": "전주시",
    "P009": "전주시",
    "P010": "포항시",
    "P011": "서귀포시",
    "P012": "충주시",
    "P013": "강릉시",
    "P014": "평창군",
    "P015": "동해시",
    "P016": "종로구",
    "P017": "종로구",
    "P018": "영월군",
    "P019": "상주시",
    "P020": "서천군",
    "P021": "중구",
    "P022": "중구",
    "P023": "포항시",
    "P024": "포항시",
    "P025": "제주시",
    "P026": "서귀포시",
    "P027": "제주시",
    "P028": "제주시",
    "P029": "상주시",
    "P030": "종로구",
}


def filter_segments(
    segments: Sequence[Mapping[str, Any]],
    *,
    place_ids: str | Sequence[str] | None = None,
    drama_titles: str | Sequence[str] | None = None,
    regions: str | Sequence[str] | None = None,
    cities: str | Sequence[str] | None = None,
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

    normalized_place_ids = _normalize_filter_values(place_ids, "place_ids")
    normalized_drama_titles = _normalize_filter_values(
        drama_titles,
        "drama_titles",
    )
    normalized_regions = _normalize_filter_values(regions, "regions")
    normalized_cities = _normalize_filter_values(cities, "cities")
    normalized_seasons = _normalize_filter_values(
        seasons,
        "seasons",
        aliases=_SEASON_CANONICAL,
    )
    normalized_times = _normalize_filter_values(
        times_of_day,
        "times_of_day",
        aliases=_TIME_OF_DAY_CANONICAL,
    )
    normalized_moods = _normalize_filter_values(moods, "moods")
    normalized_activities = _normalize_filter_values(activities, "activities")
    normalized_landscapes = _normalize_filter_values(landscapes, "landscapes")
    normalized_categories = _normalize_filter_values(categories, "categories")

    if not any(
        (
            normalized_place_ids,
            normalized_drama_titles,
            normalized_regions,
            normalized_cities,
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
        if normalized_place_ids and not _matches_scalar_filter(
            segment,
            "place_id",
            normalized_place_ids,
        ):
            continue

        if normalized_drama_titles and not _matches_scalar_filter(
            segment,
            "drama_title",
            normalized_drama_titles,
        ):
            continue

        if normalized_regions and not _matches_region_filter(
            segment,
            normalized_regions,
        ):
            continue

        if normalized_cities and not _matches_location_field_filter(
            segment,
            "city",
            normalized_cities,
        ):
            continue

        if normalized_seasons:
            season = _normalize_scalar_field(
                segment,
                "season",
                aliases=_SEASON_CANONICAL,
            )
            if season not in normalized_seasons:
                continue

        if normalized_times:
            time_of_day = _normalize_scalar_field(
                segment,
                "time_of_day",
                aliases=_TIME_OF_DAY_CANONICAL,
            )
            if time_of_day not in normalized_times:
                continue

        list_filters = (
            ("mood", normalized_moods, mood_match),
            ("activity", normalized_activities, activity_match),
            ("landscape", normalized_landscapes, landscape_match),
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


def _matches_scalar_filter(
    segment: Mapping[str, Any],
    field_name: str,
    requested: set[str],
) -> bool:
    value = segment.get(field_name)
    if not isinstance(value, str) or not value.strip():
        return False
    return value.strip().casefold() in requested


def _matches_location_field_filter(
    segment: Mapping[str, Any],
    field_name: str,
    requested: set[str],
) -> bool:
    value = segment.get(field_name)
    if not isinstance(value, str) or not value.strip():
        metadata = segment.get("metadata")
        value = metadata.get(field_name) if isinstance(metadata, Mapping) else None
    if not isinstance(value, str) or not value.strip():
        return False
    actual = _location_token(value)
    actual_without_suffix = (
        actual[:-1] if len(actual) > 1 and actual.endswith(("시", "군", "구")) else actual
    )
    return any(
        requested_value in {actual, actual_without_suffix}
        or _location_token(requested_value) in {actual, actual_without_suffix}
        for requested_value in requested
    )


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
    *,
    aliases: Mapping[str, str] | None = None,
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
        normalized.add(aliases.get(cleaned, cleaned) if aliases else cleaned)
    return normalized


def _normalize_scalar_field(
    segment: Mapping[str, Any],
    field_name: str,
    *,
    aliases: Mapping[str, str] | None = None,
) -> str:
    value = segment.get(field_name)
    if not isinstance(value, str) or not value.strip():
        segment_id = segment.get("segment_id", "(알 수 없음)")
        raise TypeError(
            f"{segment_id} 구간의 {field_name}은 빈 문자열이 아닌 문자열이어야 합니다."
        )
    cleaned = value.strip().casefold()
    return aliases.get(cleaned, cleaned) if aliases else cleaned


def _matches_region_filter(
    segment: Mapping[str, Any],
    requested_regions: set[str],
) -> bool:
    stored_region = _normalize_scalar_field(segment, "region")
    canonical_region = _REGION_CANONICAL.get(stored_region, stored_region)
    location_values = _segment_location_values(segment)

    for requested in requested_regions:
        canonical_requested = _REGION_CANONICAL.get(requested)
        if canonical_requested is not None:
            if canonical_region == canonical_requested:
                return True
            continue

        if _location_token(requested) in location_values:
            return True

    return False


def _segment_location_values(segment: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    has_structured_city_or_address = False
    for field_name in ("region", "city", "place_name", "spot_name", "address"):
        value = segment.get(field_name)
        _add_location_value(values, value)
        if field_name in {"city", "address"} and isinstance(value, str) and value.strip():
            has_structured_city_or_address = True

    metadata = segment.get("metadata")
    if isinstance(metadata, Mapping):
        for field_name in ("region", "city", "place_name", "spot_name", "address"):
            value = metadata.get(field_name)
            _add_location_value(values, value)
            if (
                field_name in {"city", "address"}
                and isinstance(value, str)
                and value.strip()
            ):
                has_structured_city_or_address = True

    place_id = segment.get("place_id")
    if not isinstance(place_id, str) and isinstance(metadata, Mapping):
        place_id = metadata.get("place_id")
    if isinstance(place_id, str) and not has_structured_city_or_address:
        _add_location_value(values, _PLACE_CITY_FALLBACKS.get(place_id.strip()))
    return values


def _add_location_value(values: set[str], value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        return
    normalized = _location_token(value)
    values.add(normalized)
    for token in normalized.replace(",", " ").split():
        values.add(token)
        if len(token) > 1 and token.endswith(("시", "군", "구")):
            values.add(token[:-1])


def _location_token(value: str) -> str:
    return " ".join(value.strip().casefold().split())


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
