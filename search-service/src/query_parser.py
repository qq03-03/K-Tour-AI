"""API 없이 검색어 구조화 흐름을 검증하는 안전한 기준선."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from .interfaces import QueryParser


ALLOWED_FILTER_FIELDS = frozenset(
    {
        "region",
        "season",
        "time_of_day",
        "mood",
        "activity",
        "scene_elements",
    }
)

FILTER_ARGUMENT_NAMES: Mapping[str, str] = {
    "region": "regions",
    "season": "seasons",
    "time_of_day": "times_of_day",
    "mood": "moods",
    "activity": "activities",
    "scene_elements": "landscapes",
}

_VALUE_ALIASES: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "season": {
        "봄": ("봄", "spring", "春", "春天", "春季"),
        "여름": ("여름", "summer", "夏", "夏天", "夏季"),
        "가을": ("가을", "autumn", "fall", "秋", "秋天", "秋季"),
        "겨울": ("겨울", "winter", "冬", "冬天", "冬季"),
    },
    "time_of_day": {
        "새벽": ("새벽", "dawn", "before sunrise", "明け方", "黎明"),
        "아침": ("아침", "morning", "朝", "早晨", "上午"),
        "낮": ("낮", "daytime", "昼", "白天"),
        "해질녘": ("해질녘", "sunset", "dusk", "夕暮れ", "日落", "黄昏"),
        "밤": ("밤", "night", "夜", "夜晚"),
    },
    "mood": {
        "고요한": (
            "고요한", "고요", "조용한", "조용", "잔잔한", "잔잔", "차분한", "차분",
            "calm", "quiet", "tranquil", "穏やか", "静か", "安静", "宁静",
        ),
        "평화로운": (
            "평화로운", "평화", "편안한", "편안", "마음이 편안", "peaceful",
            "at ease", "心が安らぐ", "平和", "平静", "放松",
        ),
        "낭만적인": ("낭만적인", "낭만", "로맨틱", "romantic", "ロマンチック", "浪漫"),
        "활기찬": ("활기찬", "활기", "역동적인", "역동", "lively", "vibrant", "にぎやか", "热闹"),
        "신비로운": ("신비로운", "신비", "mysterious", "神秘的", "神秘"),
        "화려한": ("화려한", "화려", "glamorous", "華やか", "华丽"),
    },
    "region": {
        "서울": ("서울", "seoul", "ソウル", "首尔", "首爾"),
        "부산": ("부산", "busan", "釜山"),
        "제주": ("제주", "제주도", "jeju", "済州", "济州", "濟州"),
        "강원": ("강원", "강원도", "gangwon", "江原"),
        "춘천": ("춘천", "chuncheon", "春川"),
        "경주": ("경주", "gyeongju", "慶州", "庆州"),
        "전주": ("전주", "jeonju", "全州"),
        "인천": ("인천", "incheon", "仁川"),
        "수원": ("수원", "suwon", "水原"),
        "강릉": ("강릉", "gangneung", "江陵"),
        "속초": ("속초", "sokcho", "束草"),
    },
}

_KNOWN_TITLE_ALIASES = ("겨울연가", "winter sonata", "冬のソナタ", "冬季恋歌")
_KNOWN_PLACE_ALIASES = frozenset({"남이섬", "nami island", "南怡島", "南怡岛"})


@dataclass
class ParsedQuery:
    """검색어 분석 결과와 안전한 재검색 상태."""

    original_query: str
    search_text: str
    filters: dict[str, list[str]] = field(default_factory=dict)
    soft_hints: dict[str, list[str]] = field(default_factory=dict)
    fallback_used: bool = False
    fallback_reason: str | None = None


class RuleBasedQueryParser:
    """명시적으로 등장한 기본 조건만 추출하는 로컬 테스트 분석기."""

    _SCALAR_KEYWORDS: Mapping[str, tuple[str, ...]] = {
        "region": (
            "서울",
            "부산",
            "제주",
            "강원",
            "춘천",
            "경주",
            "전주",
            "인천",
            "수원",
            "강릉",
            "속초",
        ),
        "season": ("봄", "여름", "가을", "겨울"),
        "time_of_day": ("새벽", "아침", "낮", "해질녘", "밤"),
    }
    _MOOD_KEYWORDS: Mapping[str, tuple[str, ...]] = {
        "고요한": ("고요", "조용", "차분"),
        "평화로운": ("평화",),
        "낭만적인": ("낭만", "로맨틱"),
        "활기찬": ("활기", "역동"),
        "신비로운": ("신비",),
        "화려한": ("화려",),
    }
    # 제목 안의 단어를 계절 조건으로 오해하지 않도록 분석용 문자열에서 제외한다.
    _KNOWN_TITLES = ("겨울연가",)

    def parse(self, query: str) -> ParsedQuery:
        original_query = _validate_query_text(query)
        filter_text = original_query.casefold()
        for title in self._KNOWN_TITLES:
            filter_text = filter_text.replace(title.casefold(), " ")

        filters: dict[str, list[str]] = {}
        for field_name, keywords in self._SCALAR_KEYWORDS.items():
            matched = [keyword for keyword in keywords if keyword.casefold() in filter_text]
            if matched:
                filters[field_name] = matched

        moods = [
            canonical
            for canonical, expressions in self._MOOD_KEYWORDS.items()
            if any(expression.casefold() in filter_text for expression in expressions)
        ]
        soft_hints: dict[str, list[str]] = {}
        if moods:
            # 감성은 해석의 여지가 크므로 기본적으로 후보를 제거하는 강제 필터가
            # 아니라 검색 순위를 보조하는 힌트로 전달한다.
            soft_hints["mood"] = moods

        # 의미 손실을 막기 위해 규칙 기반 단계에서는 검색 문장을 축약하지 않는다.
        return ParsedQuery(
            original_query=original_query,
            search_text=original_query,
            filters=filters,
            soft_hints=soft_hints,
        )


def parse_query_safely(query: str, parser: QueryParser) -> ParsedQuery:
    """분석기 오류나 잘못된 출력이 발생하면 필터 없는 검색으로 복구한다."""

    original_query = _validate_query_text(query)
    try:
        parsed = parser.parse(original_query)
        validated = _validate_parsed_query(parsed, original_query=original_query)
        return _postprocess_parsed_query(validated)
    except Exception as error:
        return ParsedQuery(
            original_query=original_query,
            search_text=original_query,
            fallback_used=True,
            fallback_reason=f"{type(error).__name__}: {error}",
        )


def without_filters(parsed: ParsedQuery, reason: str) -> ParsedQuery:
    """필터 적용 결과가 부족할 때 원본 검색문을 유지한 재검색 상태를 만든다."""

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("필터 제거 이유는 빈 문자열이 아니어야 합니다.")
    return replace(
        parsed,
        search_text=parsed.original_query,
        filters={},
        fallback_used=True,
        fallback_reason=reason.strip(),
    )


def to_filter_arguments(filters: Mapping[str, Sequence[str]]) -> dict[str, list[str]]:
    """QueryParser 필드명을 ``filter_segments``의 인자명으로 변환한다."""

    validated = _validate_filter_mapping(filters, "filters")
    return {
        FILTER_ARGUMENT_NAMES[field_name]: values
        for field_name, values in validated.items()
    }


def _validate_query_text(query: object) -> str:
    if not isinstance(query, str):
        raise TypeError("query는 문자열이어야 합니다.")
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("query는 빈 문자열이 아니어야 합니다.")
    return cleaned


def _validate_parsed_query(
    parsed: object,
    *,
    original_query: str,
) -> ParsedQuery:
    if not isinstance(parsed, ParsedQuery):
        raise TypeError("QueryParser는 ParsedQuery를 반환해야 합니다.")

    search_text = _validate_query_text(parsed.search_text)
    filters = _validate_filter_mapping(parsed.filters, "filters")
    soft_hints = _validate_filter_mapping(parsed.soft_hints, "soft_hints")
    return ParsedQuery(
        # 분석기가 원문을 바꾸더라도 호출자가 전달한 질문을 기준으로 보존한다.
        original_query=original_query,
        search_text=search_text,
        filters=filters,
        soft_hints=soft_hints,
        fallback_used=bool(parsed.fallback_used),
        fallback_reason=parsed.fallback_reason,
    )


def _validate_filter_mapping(
    values: object,
    field_name: str,
) -> dict[str, list[str]]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name}는 객체여야 합니다.")

    normalized: dict[str, list[str]] = {}
    for key, raw_items in values.items():
        if key not in ALLOWED_FILTER_FIELDS:
            raise ValueError(f"지원하지 않는 필터입니다: {key}")
        if isinstance(raw_items, (str, bytes)) or not isinstance(raw_items, Sequence):
            raise TypeError(f"{field_name}.{key}는 문자열 목록이어야 합니다.")

        cleaned_items: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            if not isinstance(item, str) or not item.strip():
                raise TypeError(f"{field_name}.{key}에는 빈 값이 아닌 문자열만 사용합니다.")
            cleaned = item.strip()
            compare_key = cleaned.casefold()
            if compare_key not in seen:
                seen.add(compare_key)
                cleaned_items.append(cleaned)
        if cleaned_items:
            normalized[key] = cleaned_items
    return normalized


def _postprocess_parsed_query(parsed: ParsedQuery) -> ParsedQuery:
    """LLM 출력의 명백한 오분류를 제거하고 감성 표현을 표준화한다."""

    masked_query = parsed.original_query.casefold()
    for title in _KNOWN_TITLE_ALIASES:
        masked_query = masked_query.replace(title.casefold(), " ")

    filters = _normalize_mapping_values(parsed.filters)
    soft_hints = _normalize_mapping_values(parsed.soft_hints)

    for field_name in ("season", "time_of_day"):
        if field_name in filters:
            evidenced = [
                value
                for value in filters[field_name]
                if _query_has_alias(masked_query, field_name, value)
            ]
            if evidenced:
                filters[field_name] = evidenced
            else:
                filters.pop(field_name)

    if "region" in filters:
        regions = [
            value
            for value in filters["region"]
            if value.casefold() not in _KNOWN_PLACE_ALIASES
            and _query_has_alias(parsed.original_query.casefold(), "region", value)
        ]
        if regions:
            filters["region"] = regions
        else:
            filters.pop("region")

    hard_moods = filters.pop("mood", [])
    mood_values = [*soft_hints.get("mood", []), *hard_moods]
    evidenced_moods = [
        value
        for value in _deduplicate(mood_values)
        if _query_has_alias(parsed.original_query.casefold(), "mood", value)
    ]
    if evidenced_moods:
        soft_hints["mood"] = evidenced_moods
    else:
        soft_hints.pop("mood", None)

    return replace(parsed, filters=filters, soft_hints=soft_hints)


def _normalize_mapping_values(
    values: Mapping[str, Sequence[str]],
) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for field_name, raw_values in values.items():
        canonical_values = [_canonical_value(field_name, value) for value in raw_values]
        kept = [value for value in canonical_values if value is not None]
        if kept:
            normalized[field_name] = _deduplicate(kept)
    return normalized


def _canonical_value(field_name: str, value: str) -> str | None:
    alias_groups = _VALUE_ALIASES.get(field_name)
    if alias_groups is None:
        return value.strip()

    compare_value = value.strip().casefold()
    for canonical, aliases in alias_groups.items():
        if compare_value == canonical.casefold() or any(
            compare_value == alias.casefold() for alias in aliases
        ):
            return canonical
    if field_name in {"season", "time_of_day"}:
        return None
    return value.strip()


def _query_has_alias(query: str, field_name: str, value: str) -> bool:
    aliases = _VALUE_ALIASES.get(field_name, {}).get(value, (value,))
    return any(alias.casefold() in query for alias in aliases)


def _deduplicate(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result
