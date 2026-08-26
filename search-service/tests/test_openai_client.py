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


def test_openai_client_minimizes_reasoning_effort_and_verbosity() -> None:
    # The query parser runs on every /api/search request, so it must use
    # minimal reasoning effort and low verbosity. Without these, gpt-5.6
    # class reasoning models can take 15-35s per call instead of the
    # expected sub-second response.
    responses = FakeResponses()
    sdk = SimpleNamespace(responses=responses)
    client = OpenAIStructuredClient(model="test-model", client=sdk)

    client.generate_json(
        system_prompt="system",
        user_prompt="여름의 평화로운 남이섬 수국길",
        response_schema={"type": "object"},
    )

    assert responses.arguments["reasoning"] == {"effort": "none"}
    assert responses.arguments["verbosity"] == "low"


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
