import json
from urllib.error import URLError

import pytest

from src.interfaces import StructuredLLMClient
from src.ollama_client import OllamaStructuredClient


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_client_sends_schema_and_parses_json_content() -> None:
    captured = {}

    def opener(request, *, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "search_text": "남이섬 숲길",
                            "filters": {"season": ["여름"]},
                            "soft_hints": {},
                        },
                        ensure_ascii=False,
                    ),
                }
            }
        )

    schema = {"type": "object", "properties": {"search_text": {"type": "string"}}}
    client = OllamaStructuredClient(
        model="llama3.1",
        timeout_seconds=30,
        opener=opener,
    )

    result = client.generate_json(
        system_prompt="검색 조건만 반환",
        user_prompt="여름 남이섬 숲길",
        response_schema=schema,
    )

    assert result["search_text"] == "남이섬 숲길"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["timeout"] == 30.0
    assert captured["payload"]["model"] == "llama3.1"
    assert captured["payload"]["format"] == schema
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"]["temperature"] == 0


def test_client_satisfies_common_protocol() -> None:
    assert isinstance(OllamaStructuredClient(), StructuredLLMClient)


def test_connection_error_has_clear_message() -> None:
    def failing_opener(request, *, timeout):
        raise URLError("connection refused")

    client = OllamaStructuredClient(opener=failing_opener)

    with pytest.raises(ConnectionError, match="Ollama에 연결할 수 없습니다"):
        client.generate_json(
            system_prompt="system",
            user_prompt="query",
            response_schema={"type": "object"},
        )


def test_invalid_model_json_is_rejected() -> None:
    def opener(request, *, timeout):
        return FakeResponse({"message": {"content": "not-json"}})

    client = OllamaStructuredClient(opener=opener)

    with pytest.raises(ValueError, match="올바른 JSON을 생성하지 않았습니다"):
        client.generate_json(
            system_prompt="system",
            user_prompt="query",
            response_schema={"type": "object"},
        )


@pytest.mark.parametrize(
    "arguments",
    [
        {"model": ""},
        {"base_url": "localhost:11434"},
        {"timeout_seconds": 0},
    ],
)
def test_invalid_settings_are_rejected(arguments) -> None:
    with pytest.raises(ValueError):
        OllamaStructuredClient(**arguments)
