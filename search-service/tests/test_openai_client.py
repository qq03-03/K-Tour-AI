"""OpenAI Responses API 어댑터의 구조화 출력 테스트."""

from __future__ import annotations

from types import SimpleNamespace

from src.openai_client import OpenAIStructuredClient, QueryParserResponse


class FakeResponses:
    def __init__(self) -> None:
        self.arguments = None

    def parse(self, **kwargs):
        self.arguments = kwargs
        return SimpleNamespace(
            output_parsed=QueryParserResponse(
                search_text="a peaceful hydrangea path on Nami Island",
                filters={"season": ["여름"]},
                soft_hints={"mood": ["평화로운"]},
            )
        )


def test_openai_client_uses_responses_structured_output() -> None:
    responses = FakeResponses()
    sdk = SimpleNamespace(responses=responses)
    client = OpenAIStructuredClient(model="test-model", client=sdk)

    payload = client.generate_json(
        system_prompt="system",
        user_prompt="여름의 평화로운 남이섬 수국길",
        response_schema={"type": "object"},
    )

    assert payload == {
        "search_text": "a peaceful hydrangea path on Nami Island",
        "filters": {"season": ["여름"]},
        "soft_hints": {"mood": ["평화로운"]},
    }
    assert responses.arguments["model"] == "test-model"
    assert responses.arguments["text_format"] is QueryParserResponse
    assert responses.arguments["reasoning"] == {"effort": "none"}
    assert responses.arguments["text"] == {"verbosity": "low"}
    assert responses.arguments["prompt_cache_key"] == "k-tour-query-parser-v1"


def test_openai_client_accepts_explicit_latency_options() -> None:
    responses = FakeResponses()
    sdk = SimpleNamespace(responses=responses)
    client = OpenAIStructuredClient(
        model="test-model",
        reasoning_effort="low",
        verbosity="medium",
        prompt_cache_key="custom-query-parser",
        client=sdk,
    )

    client.generate_json(
        system_prompt="system",
        user_prompt="query",
        response_schema={"type": "object"},
    )

    assert responses.arguments["reasoning"] == {"effort": "low"}
    assert responses.arguments["text"] == {"verbosity": "medium"}
    assert responses.arguments["prompt_cache_key"] == "custom-query-parser"


def test_openai_client_rejects_invalid_reasoning_effort() -> None:
    sdk = SimpleNamespace(responses=FakeResponses())

    try:
        OpenAIStructuredClient(reasoning_effort="fastest", client=sdk)
    except ValueError as error:
        assert "reasoning_effort" in str(error)
    else:
        raise AssertionError("지원하지 않는 reasoning effort를 거부해야 합니다.")


def test_openai_client_rejects_missing_parsed_output() -> None:
    sdk = SimpleNamespace(
        responses=SimpleNamespace(
            parse=lambda **kwargs: SimpleNamespace(output_parsed=None)
        )
    )
    client = OpenAIStructuredClient(client=sdk)

    try:
        client.generate_json(
            system_prompt="system",
            user_prompt="query",
            response_schema={"type": "object"},
        )
    except ValueError as error:
        assert "구조화된" in str(error)
    else:
        raise AssertionError("구조화 출력 누락을 거부해야 합니다.")
