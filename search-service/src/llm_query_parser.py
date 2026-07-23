"""구체적인 모델이나 실행 프로그램에 의존하지 않는 LLM QueryParser."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from .interfaces import StructuredLLMClient
from .query_parser import ParsedQuery, _validate_query_text


FILTER_ARRAY_SCHEMA: dict[str, object] = {
    "type": "array",
    "items": {"type": "string", "minLength": 1},
    "uniqueItems": True,
}

FILTERS_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "region": FILTER_ARRAY_SCHEMA,
        "season": FILTER_ARRAY_SCHEMA,
        "time_of_day": FILTER_ARRAY_SCHEMA,
        "mood": FILTER_ARRAY_SCHEMA,
        "activity": FILTER_ARRAY_SCHEMA,
        "scene_elements": FILTER_ARRAY_SCHEMA,
    },
}

QUERY_PARSER_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "search_text": {"type": "string", "minLength": 1},
        "filters": FILTERS_SCHEMA,
        "soft_hints": FILTERS_SCHEMA,
    },
    "required": ["search_text", "filters", "soft_hints"],
}

QUERY_PARSER_SYSTEM_PROMPT = """당신은 관광 영상 검색어 구조화기입니다.
답변을 작성하지 말고 제공된 JSON 스키마에 맞는 검색 조건만 반환하세요.

규칙:
1. search_text에는 작품명과 장소명을 포함한 사용자의 핵심 검색 의도를 유지합니다.
2. 원문에서 명확하게 지정된 객관적 조건만 filters에 넣습니다.
3. 감성·분위기 표현은 검색 후보를 제거하지 않도록 filters가 아니라 soft_hints.mood에 넣습니다.
4. 애매하거나 문맥에서 추론한 조건도 filters가 아니라 soft_hints에 넣습니다.
5. 작품 제목에 포함된 단어를 계절·지역·시간 조건으로 오해하지 않습니다.
   예: '겨울연가', 'Winter Sonata', '冬のソナタ', '冬季恋歌' 안의 겨울 표현은 계절 필터가 아닙니다.
6. 작품명 밖에서 계절을 명시한 경우에는 계절 필터를 사용합니다.
   예: '겨울에 겨울연가 촬영지'의 작품명 밖 '겨울에'는 계절 필터입니다.
7. 확신할 수 없는 필드는 빈 목록이 아니라 해당 키 자체를 생략합니다.
8. 계절은 봄/여름/가을/겨울, 시간대는 새벽/아침/낮/해질녘/밤으로 정규화합니다.
9. 지역과 감성은 가능한 경우 한국어 표준 표현으로 정규화합니다.
10. 사용자가 말하지 않은 장소·계절·감성을 새로 만들지 않습니다.
"""


class LLMQueryParser:
    """주입된 구조화 LLM 클라이언트를 이용해 질문을 분석한다."""

    def __init__(self, client: StructuredLLMClient) -> None:
        self._client = client

    def parse(self, query: str) -> ParsedQuery:
        original_query = _validate_query_text(query)
        payload = self._client.generate_json(
            system_prompt=QUERY_PARSER_SYSTEM_PROMPT,
            user_prompt=original_query,
            response_schema=QUERY_PARSER_RESPONSE_SCHEMA,
        )
        if not isinstance(payload, Mapping):
            raise TypeError("LLM 클라이언트는 JSON 객체를 반환해야 합니다.")

        search_text = payload.get("search_text")
        filters = payload.get("filters", {})
        soft_hints = payload.get("soft_hints", {})
        if not isinstance(search_text, str):
            raise TypeError("LLM 결과의 search_text는 문자열이어야 합니다.")
        if not isinstance(filters, Mapping):
            raise TypeError("LLM 결과의 filters는 객체여야 합니다.")
        if not isinstance(soft_hints, Mapping):
            raise TypeError("LLM 결과의 soft_hints는 객체여야 합니다.")

        # 값의 세부 형식과 허용 필드는 parse_query_safely()가 공통 검증한다.
        return ParsedQuery(
            original_query=original_query,
            search_text=search_text,
            filters=cast(dict[str, list[str]], dict(filters)),
            soft_hints=cast(dict[str, list[str]], dict(soft_hints)),
        )
