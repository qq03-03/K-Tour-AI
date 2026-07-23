"""검색 로직과 임베딩 구현체 사이의 공통 인터페이스."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import numpy as np

if TYPE_CHECKING:
    from .query_parser import ParsedQuery


@runtime_checkable
class TextEmbedder(Protocol):
    """검색에 필요한 최소 텍스트 임베딩 규약."""

    # Python의 Protocol은 명시적 상속 없이도 같은 메서드를 구현하면 호환된다.
    # 향후 BGE-M3 어댑터도 encode()만 구현하면 검색 함수에 전달할 수 있다.

    def encode(self, text: str) -> np.ndarray:
        """문자열을 1차원 숫자 벡터로 변환한다."""

        ...


@runtime_checkable
class ExplainableTextEmbedder(TextEmbedder, Protocol):
    """인식한 개념을 설명할 수 있는 분석용 임베더 규약."""

    # matched_concepts()는 규칙 기반 더미 모델의 원인 분석에만 필요하다.
    # 실제 임베딩 모델의 기본 검색 인터페이스에는 요구하지 않는다.

    def matched_concepts(self, text: str) -> list[str]:
        """텍스트에서 인식한 더미 개념 이름을 반환한다."""

        ...


@runtime_checkable
class QueryParser(Protocol):
    """자연어 질문을 검색 문장과 구조화 조건으로 나누는 공통 규약."""

    # 규칙 기반·로컬 LLM·API LLM 구현체가 같은 결과 형식을 사용한다.
    def parse(self, query: str) -> "ParsedQuery":
        """사용자 질문을 분석해 검색용 구조로 반환한다."""

        ...


@runtime_checkable
class StructuredLLMClient(Protocol):
    """로컬 또는 API LLM에 구조화된 JSON 생성을 요청하는 공통 규약."""

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        """지정된 JSON 스키마에 맞는 객체를 반환한다."""

        ...
