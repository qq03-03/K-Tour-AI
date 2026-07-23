"""Ollama 로컬 API를 공통 구조화 LLM 인터페이스에 연결한다."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class OllamaStructuredClient:
    """Ollama ``/api/chat``에서 JSON 스키마 응답을 생성한다."""

    def __init__(
        self,
        *,
        model: str = "llama3.1",
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 120.0,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Ollama model은 빈 문자열이 아니어야 합니다.")
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("Ollama base_url은 빈 문자열이 아니어야 합니다.")
        parsed_url = urlparse(base_url.strip())
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("Ollama base_url은 http 또는 https URL이어야 합니다.")
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 0보다 커야 합니다.")

        self.model = model.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self._opener = opener

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Ollama에 구조화 출력을 요청하고 JSON 객체를 반환한다."""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": dict(response_schema),
            "options": {"temperature": 0},
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )

        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                raw_response = response.read().decode("utf-8")
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace").strip()
            raise ConnectionError(
                f"Ollama HTTP 오류 {error.code}: {details or error.reason}"
            ) from error
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError(
                    f"Ollama 응답 시간이 {self.timeout_seconds}초를 초과했습니다."
                ) from error
            raise ConnectionError(f"Ollama에 연결할 수 없습니다: {error.reason}") from error
        except TimeoutError as error:
            raise TimeoutError(
                f"Ollama 응답 시간이 {self.timeout_seconds}초를 초과했습니다."
            ) from error

        try:
            response_payload = json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise ValueError("Ollama API 응답이 올바른 JSON이 아닙니다.") from error

        if not isinstance(response_payload, Mapping):
            raise TypeError("Ollama API 응답 최상위 값은 객체여야 합니다.")
        message = response_payload.get("message")
        if not isinstance(message, Mapping):
            raise ValueError("Ollama API 응답에 message 객체가 없습니다.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama API 응답의 message.content가 비어 있습니다.")

        try:
            generated = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("Ollama 모델이 올바른 JSON을 생성하지 않았습니다.") from error
        if not isinstance(generated, Mapping):
            raise TypeError("Ollama 모델의 구조화 결과는 JSON 객체여야 합니다.")
        return dict(generated)
