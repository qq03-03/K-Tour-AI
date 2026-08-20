"""검색어 분석·필터·텍스트 검색을 안전하게 연결하는 통합 흐름."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .filters import filter_segments
from .interfaces import QueryParser, TextEmbedder
from .query_parser import parse_query_safely, to_filter_arguments, without_filters
from .search import search_segments


def run_search_pipeline(
    query: str,
    segments: Sequence[Mapping[str, Any]],
    *,
    parser: QueryParser,
    embedder: TextEmbedder,
    top_k: int = 5,
) -> dict[str, Any]:
    """질문을 구조화하고 필터링한 뒤 텍스트 유사도 검색을 실행한다."""

    parsed = parse_query_safely(query, parser)
    filter_arguments = to_filter_arguments(parsed.filters)
    candidates = filter_segments(segments, **filter_arguments)

    if parsed.filters and not candidates:
        parsed = without_filters(parsed, "필터 결과가 없어 원문 질문으로 다시 검색했습니다.")
        filter_arguments = {}
        candidates = list(segments)

    results = search_segments(
        parsed.search_text,
        candidates,
        embedder,
        top_k=min(top_k, len(candidates)) if candidates else top_k,
    )
    return {
        "original_query": parsed.original_query,
        "search_text": parsed.search_text,
        "filters": parsed.filters,
        "soft_hints": parsed.soft_hints,
        "filter_arguments": filter_arguments,
        "fallback_used": parsed.fallback_used,
        "fallback_reason": parsed.fallback_reason,
        "candidate_count": len(candidates),
        "results": results,
    }
