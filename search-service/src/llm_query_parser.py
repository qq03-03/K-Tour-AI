"""구체적인 모델이나 실행 프로그램에 의존하지 않는 LLM QueryParser."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from .drama_title_matcher import analyze_drama_titles, mask_protected_titles
from .interfaces import StructuredLLMClient
from .location_matcher import analyze_locations
from .query_parser import (
    ParsedQuery,
    _validate_query_text,
    extract_explicit_scalar_filters,
)


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
1. search_text는 CLIP 검색에 사용할 짧고 자연스러운 영어 문장으로 작성합니다.
   작품명·장소명·대상·활동·감성을 포함한 사용자의 핵심 의도는 빠뜨리지 않습니다.
2. 원문에서 명확하게 지정된 지역·계절·시간대만 filters에 넣습니다.
3. 감성·분위기 표현은 검색 후보를 제거하지 않도록 filters가 아니라 soft_hints.mood에 넣습니다.
4. 활동과 장면 요소는 언어별 태그 표기 차이로 후보를 잘못 제거하지 않도록
   filters가 아니라 soft_hints.activity 또는 soft_hints.scene_elements에 넣습니다.
5. 애매하거나 문맥에서 추론한 조건도 filters가 아니라 soft_hints에 넣습니다.
6. 사용자 입력 JSON의 registered_titles에 있는 문자열만 프로젝트에 등록된 작품 제목입니다.
   해당 제목 문자열 안의 지역·계절·시간 표현은 filters로 해석하지 않습니다.
7. title_match_status가 not_found이면 possible_title은 미등록 작품 후보입니다.
   possible_title 안의 지역·계절·시간 표현도 filters로 해석하지 않습니다.
8. protected_title_texts 밖에서 명시한 지역·계절·시간 표현은 정상적으로 filters에 넣습니다.
9. explicit_region_filters는 프로젝트의 다국어 위치 카탈로그가 원문에서 직접 확인한 지역입니다.
   이 목록이 있으면 filters.region에는 이 값만 사용합니다.
10. matched_places는 관광지명이며 filters.region에 넣지 않습니다.
11. 확신할 수 없는 필드는 빈 목록이 아니라 해당 키 자체를 생략합니다.
12. 계절은 봄/여름/가을/겨울, 시간대는 새벽/아침/낮/해질녘/밤으로 정규화합니다.
13. 지역과 감성은 가능한 경우 한국어 표준 표현으로 정규화합니다.
14. 사용자가 말하지 않은 장소·계절·감성을 새로 만들지 않습니다.
"""


class LLMQueryParser:
    """주입된 구조화 LLM 클라이언트를 이용해 질문을 분석한다."""

    def __init__(self, client: StructuredLLMClient) -> None:
        self._client = client

    def parse(self, query: str) -> ParsedQuery:
        original_query = _validate_query_text(query)
        title_match = analyze_drama_titles(original_query)
        location_match = analyze_locations(
            mask_protected_titles(original_query, title_match)
        )
        user_payload = {
            "query": original_query,
            "title_match_status": title_match.status,
            "registered_titles": list(title_match.matched_titles),
            "possible_title": title_match.possible_title,
            "protected_title_texts": [span.text for span in title_match.protected_spans],
            "explicit_region_filters": list(location_match.region_filters),
            "matched_places": [
                {
                    "place_id": place.place_id,
                    "place_name": place.place_name,
                    "matched_alias": place.matched_alias,
                }
                for place in location_match.places
            ],
        }
        payload = self._client.generate_json(
            system_prompt=QUERY_PARSER_SYSTEM_PROMPT,
            user_prompt=json.dumps(user_payload, ensure_ascii=False),
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

        normalized_filters = cast(dict[str, list[str]], dict(filters))
        normalized_filters.update(extract_explicit_scalar_filters(original_query))
        if location_match.region_filters:
            # OpenAI가 다국어 지역을 누락하거나 관광지명 전체를 region으로 반환해도
            # 프로젝트 카탈로그에서 직접 확인한 지역값을 사용한다.
            normalized_filters["region"] = list(location_match.region_filters)
        elif location_match.places:
            # 관광지만 명시된 경우 소속 지역을 하드 필터로 추론하지 않는다.
            normalized_filters.pop("region", None)

        # 값의 세부 형식과 허용 필드는 parse_query_safely()가 공통 검증한다.
        return ParsedQuery(
            original_query=original_query,
            search_text=search_text,
            filters=normalized_filters,
            soft_hints=cast(dict[str, list[str]], dict(soft_hints)),
            title_match_status=title_match.status,
            matched_drama_titles=list(title_match.matched_titles),
            possible_title=title_match.possible_title,
        )
