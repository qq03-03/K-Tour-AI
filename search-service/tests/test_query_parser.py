"""로컬 검색어 구조화와 안전한 필터 제거 테스트."""

from __future__ import annotations

import pytest

from src.interfaces import QueryParser
from src.query_parser import (
    ParsedQuery,
    RuleBasedQueryParser,
    parse_query_safely,
    to_filter_arguments,
    without_filters,
)


def test_rule_parser_preserves_original_query_and_search_text() -> None:
    parser = RuleBasedQueryParser()

    parsed = parser.parse(" 여름 남이섬의 조용한 숲길 ")

    assert parsed.original_query == "여름 남이섬의 조용한 숲길"
    assert parsed.search_text == parsed.original_query


def test_rule_parser_extracts_explicit_filters() -> None:
    parser = RuleBasedQueryParser()

    parsed = parser.parse("여름 밤 강원에서 볼 수 있는 낭만적인 장면")

    assert parsed.filters == {
        "region": ["강원"],
        "season": ["여름"],
        "time_of_day": ["밤"],
    }
    assert parsed.soft_hints == {"mood": ["낭만적인"]}


def test_title_word_is_not_mistaken_for_season_filter() -> None:
    parser = RuleBasedQueryParser()

    parsed = parser.parse("겨울연가 남이섬 촬영지")

    assert "season" not in parsed.filters
    assert parsed.search_text == "겨울연가 남이섬 촬영지"


def test_explicit_season_outside_title_is_kept() -> None:
    parser = RuleBasedQueryParser()

    parsed = parser.parse("겨울에 겨울연가 남이섬 촬영지를 보여줘")

    assert parsed.filters == {"season": ["겨울"]}


def test_mood_is_a_soft_hint_instead_of_hard_filter() -> None:
    parser = RuleBasedQueryParser()

    parsed = parser.parse("평화롭고 조용한 장소")

    assert parsed.filters == {}
    assert parsed.soft_hints == {"mood": ["고요한", "평화로운"]}


def test_unknown_query_keeps_empty_filters() -> None:
    parsed = RuleBasedQueryParser().parse("연꽃 사이를 헤엄치는 오리")

    assert parsed.filters == {}


@pytest.mark.parametrize("bad_query", ["", "   "])
def test_empty_query_is_rejected(bad_query: str) -> None:
    with pytest.raises(ValueError, match="빈 문자열"):
        RuleBasedQueryParser().parse(bad_query)


def test_non_string_query_is_rejected() -> None:
    with pytest.raises(TypeError, match="문자열"):
        RuleBasedQueryParser().parse(123)  # type: ignore[arg-type]


def test_rule_parser_satisfies_query_parser_protocol() -> None:
    assert isinstance(RuleBasedQueryParser(), QueryParser)


class BrokenParser:
    def parse(self, query: str) -> ParsedQuery:
        raise RuntimeError("로컬 모델 응답 실패")


def test_parser_failure_falls_back_to_original_query_without_filters() -> None:
    parsed = parse_query_safely("조용한 남이섬", BrokenParser())

    assert parsed.original_query == "조용한 남이섬"
    assert parsed.search_text == "조용한 남이섬"
    assert parsed.filters == {}
    assert parsed.fallback_used is True
    assert "로컬 모델 응답 실패" in (parsed.fallback_reason or "")


class InvalidOutputParser:
    def parse(self, query: str) -> ParsedQuery:
        return ParsedQuery(
            original_query="변경된 질문",
            search_text=query,
            filters={"unsupported": ["value"]},
        )


def test_invalid_parser_output_also_uses_safe_fallback() -> None:
    parsed = parse_query_safely("원본 질문", InvalidOutputParser())

    assert parsed.original_query == "원본 질문"
    assert parsed.filters == {}
    assert parsed.fallback_used is True
    assert "지원하지 않는 필터" in (parsed.fallback_reason or "")


def test_without_filters_prepares_retry_with_original_query() -> None:
    parsed = ParsedQuery(
        original_query="겨울 남이섬 숲길",
        search_text="남이섬 숲길",
        filters={"season": ["겨울"]},
    )

    retry = without_filters(parsed, "필터 적용 결과가 없습니다.")

    assert retry.search_text == "겨울 남이섬 숲길"
    assert retry.filters == {}
    assert retry.fallback_used is True
    assert retry.fallback_reason == "필터 적용 결과가 없습니다."


def test_without_filters_requires_reason() -> None:
    with pytest.raises(ValueError, match="필터 제거 이유"):
        without_filters(ParsedQuery("질문", "질문"), " ")


def test_query_filter_names_are_adapted_for_filter_segments() -> None:
    assert to_filter_arguments(
        {
            "region": ["서울"],
            "season": ["봄"],
            "time_of_day": ["밤"],
            "mood": ["고요한"],
            "activity": ["산책"],
            "scene_elements": ["한옥"],
        }
    ) == {
        "regions": ["서울"],
        "seasons": ["봄"],
        "times_of_day": ["밤"],
        "moods": ["고요한"],
        "activities": ["산책"],
        "landscapes": ["한옥"],
    }


def test_ui_hard_filter_names_are_adapted_for_filter_segments() -> None:
    """UI가 명시적으로 지정하는 하드 필터 3종도 filter_segments 인자명으로 변환된다."""

    assert to_filter_arguments(
        {
            "place_id": ["P031"],
            "city": ["충주시"],
            "drama_title": ["사랑의 불시착"],
        }
    ) == {
        "place_ids": ["P031"],
        "cities": ["충주시"],
        "drama_titles": ["사랑의 불시착"],
    }


@pytest.mark.parametrize("field_name", ["place_id", "city", "drama_title"])
def test_ui_hard_filter_fields_are_allowed(field_name: str) -> None:
    """_validate_filter_mapping이 더 이상 이 세 필드를 거부하지 않는다."""

    assert to_filter_arguments({field_name: ["값"]})


class OverGeneratingParser:
    def parse(self, query: str) -> ParsedQuery:
        return ParsedQuery(
            query,
            "겨울연가 남이섬 촬영지",
            filters={
                "season": ["겨울"],
                "region": ["남이섬"],
                "time_of_day": ["새벽", "아침", "낮", "해질녘", "밤"],
                "mood": ["calm"],
            },
        )


def test_postprocessing_removes_title_and_invented_filters() -> None:
    parsed = parse_query_safely("겨울연가 남이섬 촬영지", OverGeneratingParser())

    assert parsed.filters == {}
    assert parsed.soft_hints == {}
    assert parsed.fallback_used is False


class MultilingualMoodParser:
    def parse(self, query: str) -> ParsedQuery:
        return ParsedQuery(
            query,
            query,
            filters={"mood": ["calm"]},
            soft_hints={"mood": ["peaceful", "at ease"]},
        )


def test_multilingual_moods_are_normalized_and_moved_to_soft_hints() -> None:
    parsed = parse_query_safely(
        "A calm and peaceful place that makes me feel at ease",
        MultilingualMoodParser(),
    )

    assert parsed.filters == {}
    assert parsed.soft_hints == {"mood": ["평화로운", "고요한"]}
