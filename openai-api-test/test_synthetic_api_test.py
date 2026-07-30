from __future__ import annotations

from types import SimpleNamespace

from run_synthetic_api_test import (
    PING_PROMPT,
    STRUCTURED_USER_PROMPT,
    SyntheticQuery,
    run_ping,
    run_structured,
)


class FakeResponses:
    def __init__(self) -> None:
        self.created_input = None
        self.parsed_input = None

    def create(self, *, model: str, input: str) -> SimpleNamespace:
        self.created_input = (model, input)
        return SimpleNamespace(output_text="OK")

    def parse(
        self,
        *,
        model: str,
        input: list[dict[str, str]],
        text_format: type[SyntheticQuery],
    ) -> SimpleNamespace:
        self.parsed_input = (model, input, text_format)
        return SimpleNamespace(
            output_parsed=SyntheticQuery(
                search_text="A calm spring morning garden walk",
                season=["spring"],
                time_of_day=["morning"],
                mood=["calm"],
                activity=["walking"],
                scene_elements=["flower garden"],
            )
        )


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def test_ping_sends_only_fixed_synthetic_text() -> None:
    client = FakeClient()

    result = run_ping(client, "test-model")

    assert result["status"] == "passed"
    assert result["answer"] == "OK"
    assert client.responses.created_input == ("test-model", PING_PROMPT)


def test_structured_test_sends_only_fixed_fictional_text() -> None:
    client = FakeClient()

    result = run_structured(client, "test-model")

    assert result["status"] == "passed"
    assert result["sent_text"] == STRUCTURED_USER_PROMPT
    assert result["parsed"]["season"] == ["spring"]
    assert result["parsed"]["activity"] == ["walking"]
