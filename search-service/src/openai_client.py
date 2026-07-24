"""OpenAI Responses API를 기존 StructuredLLMClient 규격에 연결한다."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field


DEFAULT_QUERY_MODEL = "gpt-5.6-luna"


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
        client: Any | None = None,
    ) -> None:
        self.model = model or os.getenv("OPENAI_QUERY_MODEL", DEFAULT_QUERY_MODEL)
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
