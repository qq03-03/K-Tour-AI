"""OpenAI Responses API를 기존 StructuredLLMClient 규격에 연결한다."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field


DEFAULT_QUERY_MODEL = "gpt-5.6-luna"
DEFAULT_QUERY_REASONING_EFFORT = "none"
DEFAULT_QUERY_VERBOSITY = "low"
QUERY_PARSER_PROMPT_CACHE_KEY = "k-tour-query-parser-v1"

ALLOWED_REASONING_EFFORTS = frozenset({"none", "low", "medium", "high", "xhigh", "max"})
ALLOWED_VERBOSITY_LEVELS = frozenset({"low", "medium", "high"})


class QueryFilterSet(BaseModel):
    """검색 파서가 반환할 수 있는 구조화 조건."""

    model_config = ConfigDict(extra="forbid")

    region: list[str] = Field(default_factory=list)
    season: list[str] = Field(default_factory=list)
    time_of_day: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    activity: list[str] = Field(default_factory=list)
    scene_elements: list[str] = Field(default_factory=list)


class QueryParserResponse(BaseModel):
    """OpenAI Structured Outputs용 최종 응답 형식."""

    model_config = ConfigDict(extra="forbid")

    search_text: str = Field(min_length=1)
    filters: QueryFilterSet
    soft_hints: QueryFilterSet


class OpenAIStructuredClient:
    """Responses API의 구조화 출력을 Mapping으로 변환한다."""

    def __init__(
        self,
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
        verbosity: str | None = None,
        prompt_cache_key: str = QUERY_PARSER_PROMPT_CACHE_KEY,
        client: Any | None = None,
    ) -> None:
        self.model = model or os.getenv("OPENAI_QUERY_MODEL", DEFAULT_QUERY_MODEL)
        self.reasoning_effort = _validated_choice(
            reasoning_effort
            or os.getenv("OPENAI_REASONING_EFFORT", DEFAULT_QUERY_REASONING_EFFORT),
            ALLOWED_REASONING_EFFORTS,
            "reasoning_effort",
        )
        self.verbosity = _validated_choice(
            verbosity or os.getenv("OPENAI_QUERY_VERBOSITY", DEFAULT_QUERY_VERBOSITY),
            ALLOWED_VERBOSITY_LEVELS,
            "verbosity",
        )
        if not isinstance(prompt_cache_key, str) or not prompt_cache_key.strip():
            raise ValueError("prompt_cache_key는 빈 문자열이 아니어야 합니다.")
        self.prompt_cache_key = prompt_cache_key.strip()
        self._client = client or OpenAI()

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        if not isinstance(response_schema, Mapping):
            raise TypeError("response_schema는 JSON 스키마 객체여야 합니다.")

        response = self._client.responses.parse(
            model=self.model,
            reasoning={"effort": self.reasoning_effort},
            text={"verbosity": self.verbosity},
            prompt_cache_key=self.prompt_cache_key,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=QueryParserResponse,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("OpenAI 응답에 구조화된 검색 결과가 없습니다.")

        payload = parsed.model_dump(exclude_defaults=True)
        payload.setdefault("filters", {})
        payload.setdefault("soft_hints", {})
        return payload


def _validated_choice(value: str, allowed: frozenset[str], field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name}는 문자열이어야 합니다.")
    normalized = value.strip().lower()
    if normalized not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name}는 다음 중 하나여야 합니다: {choices}")
    return normalized
