"""모델 독립적인 LLM QueryParser 연결 구조 테스트."""

from __future__ import annotations

import json
from collections.abc import Mapping

from src.interfaces import QueryParser, StructuredLLMClient
from src.llm_query_parser import LLMQueryParser, QUERY_PARSER_RESPONSE_SCHEMA
from src.query_parser import ParsedQuery, parse_query_safely


class FakeStructuredClient:
    def __init__(self, response: Mapping[str, object]) -> None:
        self.response = response
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None
        self.last_schema: Mapping[str, object] | None = None

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        self.last_schema = response_schema
        return self.response


def test_llm_parser_uses_common_client_and_schema() -> None:
    client = FakeStructuredClient(
        {
            "search_text": "남이섬 숲길",
            "filters": {"season": ["여름"]},
            "soft_hints": {"mood": ["평화로운"]},
        }
    )
    parser = LLMQueryParser(client)

    parsed = parse_query_safely("여름의 평화로운 남이섬 숲길", parser)

    assert parsed.original_query == "여름의 평화로운 남이섬 숲길"
    assert parsed.search_text == "남이섬 숲길"
    assert parsed.filters == {"season": ["여름"]}
    assert parsed.soft_hints == {"mood": ["평화로운"]}
    user_payload = json.loads(client.last_user_prompt or "{}")
    assert user_payload["query"] == parsed.original_query
    assert user_payload["title_match_status"] == "none"
    assert user_payload["registered_titles"] == []
    assert user_payload["explicit_region_filters"] == []
    assert user_payload["matched_places"] == []
    assert client.last_schema == QUERY_PARSER_RESPONSE_SCHEMA
    assert "registered_titles" in (client.last_system_prompt or "")
    assert "not_found" in (client.last_system_prompt or "")
    assert "soft_hints.mood" in (client.last_system_prompt or "")


def test_llm_receives_only_catalog_matched_title_as_authority() -> None:
    client = FakeStructuredClient(
        {"search_text": "Our Beloved Summer location", "filters": {}, "soft_hints": {}}
    )

    parsed = parse_query_safely("Our Beloved Summer 촬영지", LLMQueryParser(client))
    payload = json.loads(client.last_user_prompt or "{}")

    assert parsed.title_match_status == "matched"
    assert parsed.matched_drama_titles == ["그 해 우리는"]
    assert payload["registered_titles"] == ["그 해 우리는"]
    assert payload["protected_title_texts"] == ["Our Beloved Summer"]


def test_fake_client_and_llm_parser_satisfy_protocols() -> None:
    client = FakeStructuredClient(
        {"search_text": "질문", "filters": {}, "soft_hints": {}}
    )

    assert isinstance(client, StructuredLLMClient)
    assert isinstance(LLMQueryParser(client), QueryParser)


class FailingClient:
    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        raise TimeoutError("로컬 LLM 시간 초과")


def test_client_error_uses_original_query_fallback() -> None:
    parsed = parse_query_safely("조용한 남이섬", LLMQueryParser(FailingClient()))

    assert parsed == ParsedQuery(
        original_query="조용한 남이섬",
        search_text="조용한 남이섬",
        fallback_used=True,
        fallback_reason="TimeoutError: 로컬 LLM 시간 초과",
    )


def test_invalid_filter_from_llm_is_rejected_by_common_validation() -> None:
    client = FakeStructuredClient(
        {
            "search_text": "남이섬",
            "filters": {"unknown_filter": ["값"]},
            "soft_hints": {},
        }
    )

    parsed = parse_query_safely("남이섬", LLMQueryParser(client))

    assert parsed.filters == {}
    assert parsed.fallback_used is True
    assert "지원하지 않는 필터" in (parsed.fallback_reason or "")


def test_activity_and_scene_filters_become_soft_hints() -> None:
    client = FakeStructuredClient(
        {
            "search_text": "a rabbit eating leaves",
            "filters": {
                "activity": ["eating"],
                "scene_elements": ["rabbit"],
            },
            "soft_hints": {},
        }
    )

    parsed = parse_query_safely(
        "a rabbit eating leaves",
        LLMQueryParser(client),
    )

    assert parsed.filters == {}
    assert parsed.soft_hints == {
        "activity": ["eating"],
        "scene_elements": ["rabbit"],
    }


def test_local_location_catalog_corrects_place_name_as_region() -> None:
    client = FakeStructuredClient(
        {
            "search_text": "Jeonju Hanok Village in spring",
            "filters": {
                "region": ["Jeonju Hanok Village"],
                "season": ["spring"],
            },
            "soft_hints": {},
        }
    )

    parsed = parse_query_safely(
        "Show me Jeonju Hanok Village in spring",
        LLMQueryParser(client),
    )
    payload = json.loads(client.last_user_prompt or "{}")

    assert parsed.filters == {"region": ["전주"], "season": ["봄"]}
    assert payload["explicit_region_filters"] == ["전주"]
    assert payload["matched_places"][0]["place_id"] == "P005"


def test_local_location_catalog_adds_missing_multilingual_region() -> None:
    client = FakeStructuredClient(
        {
            "search_text": "winter Woljeongsa in Pyeongchang",
            "filters": {"season": ["winter"]},
            "soft_hints": {},
        }
    )

    parsed = parse_query_safely(
        "冬の平昌にある月精寺の撮影地",
        LLMQueryParser(client),
    )

    assert parsed.filters == {"region": ["평창"], "season": ["겨울"]}


def test_known_place_without_explicit_region_removes_llm_region_guess() -> None:
    client = FakeStructuredClient(
        {
            "search_text": "Woljeongsa filming location",
            "filters": {"region": ["월정사"]},
            "soft_hints": {},
        }
    )

    parsed = parse_query_safely("월정사 촬영 장면", LLMQueryParser(client))

    assert parsed.filters == {}


def test_local_scalar_alias_adds_missing_english_daytime() -> None:
    client = FakeStructuredClient(
        {
            "search_text": "Jeonju Hanok Village in spring during the day",
            "filters": {"season": ["spring"]},
            "soft_hints": {},
        }
    )

    parsed = parse_query_safely(
        "Show me Jeonju Hanok Village in spring during the day",
        LLMQueryParser(client),
    )

    assert parsed.filters == {
        "region": ["전주"],
        "season": ["봄"],
        "time_of_day": ["낮"],
    }


def test_generic_filming_words_are_not_scene_or_activity_hints() -> None:
    client = FakeStructuredClient(
        {
            "search_text": "winter Woljeongsa in Pyeongchang",
            "filters": {"season": ["winter"]},
            "soft_hints": {
                "activity": ["filming locations"],
                "scene_elements": ["촬영 장면"],
            },
        }
    )

    parsed = parse_query_safely(
        "A winter filming location at Woljeongsa in Pyeongchang",
        LLMQueryParser(client),
    )

    assert parsed.filters == {"region": ["평창"], "season": ["겨울"]}
    assert parsed.soft_hints == {}
