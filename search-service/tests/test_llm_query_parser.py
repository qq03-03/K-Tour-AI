"""모델 독립적인 LLM QueryParser 연결 구조 테스트."""

from __future__ import annotations

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
    assert client.last_user_prompt == parsed.original_query
    assert client.last_schema == QUERY_PARSER_RESPONSE_SCHEMA
    assert "겨울연가" in (client.last_system_prompt or "")
    assert "Winter Sonata" in (client.last_system_prompt or "")
    assert "冬のソナタ" in (client.last_system_prompt or "")
    assert "冬季恋歌" in (client.last_system_prompt or "")
    assert "soft_hints.mood" in (client.last_system_prompt or "")


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
