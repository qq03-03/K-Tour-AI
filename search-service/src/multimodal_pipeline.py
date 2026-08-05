"""OpenAI QueryParser, CLIP, pgvector, 필터와 검색 결합의 실제 통합 흐름."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from numbers import Real
from time import perf_counter
from typing import Any, Literal

from .clip_backend import ClipRuntime, PgVectorRepository
from .filters import filter_segments
from .fusion import normalized_score_fusion, reciprocal_rank_fusion
from .interfaces import QueryParser
from .metadata_reranker import rerank_with_metadata
from .query_parser import ParsedQuery, parse_query_safely, to_filter_arguments


FusionMethod = Literal["rrf", "normalized"]
SUPPORTED_FUSION_METHODS: tuple[FusionMethod, ...] = ("rrf", "normalized")

class MultimodalSearchPipeline:
    """모델과 메타데이터를 캐시해 반복 검색의 초기화 비용을 제거한다."""

    def __init__(
        self,
        *,
        runtime: ClipRuntime,
        repository: PgVectorRepository,
        metadata_rerank_enabled: bool = False,
    ) -> None:
        if not isinstance(metadata_rerank_enabled, bool):
            raise TypeError("metadata_rerank_enabled는 bool이어야 합니다.")
        self.runtime = runtime
        self.repository = repository
        self.metadata_rerank_enabled = metadata_rerank_enabled
        self._segments: list[dict[str, Any]] | None = None

    def warmup(self) -> None:
        self.runtime.warmup()
        self._load_segments()

    def refresh_metadata(self) -> None:
        self._segments = None

    def search(
        self,
        query: str,
        *,
        parser: QueryParser,
        top_k: int = 5,
        search_depth: int = 50,
        methods: Sequence[FusionMethod] = SUPPORTED_FUSION_METHODS,
        weights: Mapping[str, float] | None = None,
        rrf_k: float = 60.0,
    ) -> dict[str, Any]:
        if top_k < 1 or search_depth < 1:
            raise ValueError("top_k와 search_depth는 1 이상이어야 합니다.")
        unknown_methods = set(methods) - set(SUPPORTED_FUSION_METHODS)
        if unknown_methods:
            raise ValueError(f"지원하지 않는 결합 방식입니다: {sorted(unknown_methods)}")

        total_started = perf_counter()

        parser_started = perf_counter()
        parsed = parse_query_safely(query, parser)
        parser_latency_ms = _elapsed_ms(parser_started)

        if parsed.title_match_status == "not_found":
            return {
                "original_query": parsed.original_query,
                "search_text": parsed.search_text,
                "query_status": "not_found",
                "message": "프로젝트에 등록되지 않은 작품입니다.",
                "matched_drama_titles": [],
                "possible_title": parsed.possible_title,
                "filters": parsed.filters,
                "soft_hints": parsed.soft_hints,
                "filter_arguments": to_filter_arguments(parsed.filters),
                "fallback_used": parsed.fallback_used,
                "fallback_reason": parsed.fallback_reason,
                "candidate_count": 0,
                "source_results": {"text": [], "image": []},
                "results_by_method": {method: [] for method in methods},
                "runtime": {
                    "embedding_model": self.runtime.model_name,
                    "device": self.runtime.device,
                    "model_load_count": self.runtime.load_count,
                    "model_load_latency_ms": round(self.runtime.load_latency_ms, 3),
                    "metadata_rerank_enabled": self.metadata_rerank_enabled,
                },
                "latency_ms": {
                    "parser": round(parser_latency_ms, 3),
                    "metadata_and_filter": 0.0,
                    "query_embedding": 0.0,
                    "vector_search": 0.0,
                    "fusion": 0.0,
                    "total": round(_elapsed_ms(total_started), 3),
                },
            }

        metadata_started = perf_counter()
        segments = self._load_segments()
        title_scoped_segments = _filter_by_drama_titles(
            segments,
            parsed.matched_drama_titles,
        )
        filter_arguments = to_filter_arguments(parsed.filters)
        candidates = filter_segments(title_scoped_segments, **filter_arguments)
        if parsed.filters and not candidates:
            parsed = replace(
                parsed,
                filters={},
                fallback_used=True,
                fallback_reason=(
                    "구조화 필터 결과가 없어 작품 범위만 유지해 다시 검색했습니다."
                    if parsed.matched_drama_titles
                    else "필터 결과가 없어 필터 없이 다시 검색했습니다."
                ),
            )
            filter_arguments = {}
            candidates = list(title_scoped_segments)
        metadata_latency_ms = _elapsed_ms(metadata_started)

        candidate_ids = [str(segment["segment_id"]) for segment in candidates]
        depth = min(search_depth, len(candidate_ids))

        encoder_started = perf_counter()
        query_vector = self.runtime.encode_text(parsed.search_text)
        encoder_latency_ms = _elapsed_ms(encoder_started)

        vector_started = perf_counter()
        text_results = collapse_source_results(
            self.repository.search(
                query_vector,
                "text",
                candidate_ids=candidate_ids,
                top_k=depth,
            ),
            source="text",
        )
        image_results = collapse_source_results(
            self.repository.search(
                query_vector,
                "image",
                candidate_ids=candidate_ids,
                top_k=depth,
            ),
            source="image",
        )
        vector_search_latency_ms = _elapsed_ms(vector_started)

        fusion_started = perf_counter()
        fused = self._fuse(
            text_results,
            image_results,
            methods=methods,
            weights=weights,
            rrf_k=rrf_k,
            top_k=depth,
        )
        segment_by_id = {
            str(segment["segment_id"]): dict(segment) for segment in candidates
        }
        reranked = {
            method: rerank_with_metadata(
                results,
                segment_by_id=segment_by_id,
                soft_hints=parsed.soft_hints,
                top_k=top_k,
                enabled=self.metadata_rerank_enabled,
            )
            for method, results in fused.items()
        }
        enriched = {
            method: self._enrich(
                results,
                segment_by_id=segment_by_id,
                text_results=text_results,
                image_results=image_results,
            )
            for method, results in reranked.items()
        }
        fusion_latency_ms = _elapsed_ms(fusion_started)

        return {
            "original_query": parsed.original_query,
            "search_text": parsed.search_text,
            "query_status": parsed.title_match_status,
            "matched_drama_titles": parsed.matched_drama_titles,
            "possible_title": parsed.possible_title,
            "filters": parsed.filters,
            "soft_hints": parsed.soft_hints,
            "filter_arguments": filter_arguments,
            "fallback_used": parsed.fallback_used,
            "fallback_reason": parsed.fallback_reason,
            "candidate_count": len(candidates),
            "source_results": {
                "text": text_results,
                "image": image_results,
            },
            "results_by_method": enriched,
            "runtime": {
                "embedding_model": self.runtime.model_name,
                "device": self.runtime.device,
                "model_load_count": self.runtime.load_count,
                "model_load_latency_ms": round(self.runtime.load_latency_ms, 3),
                "metadata_rerank_enabled": self.metadata_rerank_enabled,
            },
            "latency_ms": {
                "parser": round(parser_latency_ms, 3),
                "metadata_and_filter": round(metadata_latency_ms, 3),
                "query_embedding": round(encoder_latency_ms, 3),
                "vector_search": round(vector_search_latency_ms, 3),
                "fusion": round(fusion_latency_ms, 3),
                "total": round(_elapsed_ms(total_started), 3),
            },
        }

    def _load_segments(self) -> list[dict[str, Any]]:
        if self._segments is None:
            self._segments = self.repository.list_segments()
        return list(self._segments)

    @staticmethod
    def _fuse(
        text_results: Sequence[Mapping[str, Any]],
        image_results: Sequence[Mapping[str, Any]],
        *,
        methods: Sequence[FusionMethod],
        weights: Mapping[str, float] | None,
        rrf_k: float,
        top_k: int,
    ) -> dict[str, list[dict[str, Any]]]:
        rankings = {
            "text": [str(item["segment_id"]) for item in text_results],
            "image": [str(item["segment_id"]) for item in image_results],
        }
        source_scores = {
            "text": list(text_results),
            "image": list(image_results),
        }
        output: dict[str, list[dict[str, Any]]] = {}
        if "rrf" in methods:
            output["rrf"] = reciprocal_rank_fusion(
                rankings,
                weights=weights,
                rrf_k=rrf_k,
                top_k=top_k,
            )
        if "normalized" in methods:
            output["normalized"] = normalized_score_fusion(
                source_scores,
                weights=weights,
                top_k=top_k,
            )
        return output

    @staticmethod
    def _enrich(
        fused_results: Sequence[Mapping[str, Any]],
        *,
        segment_by_id: Mapping[str, Mapping[str, Any]],
        text_results: Sequence[Mapping[str, Any]],
        image_results: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        text_by_id = {str(item["segment_id"]): item for item in text_results}
        image_by_id = {str(item["segment_id"]): item for item in image_results}
        enriched: list[dict[str, Any]] = []
        for fused in fused_results:
            segment_id = str(fused["segment_id"])
            segment = dict(segment_by_id[segment_id])
            representative = dict(
                image_by_id.get(segment_id)
                or text_by_id.get(segment_id)
                or {}
            )
            text_score = _optional_score(
                text_by_id.get(segment_id),
                "text_score",
                fallback="score",
            )
            image_score = _optional_score(
                image_by_id.get(segment_id),
                "image_score",
                fallback="score",
            )
            enriched.append(
                {
                    **segment,
                    **representative,
                    **dict(fused),
                    "text_score": text_score,
                    "image_score": image_score,
                }
            )
        return enriched


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000.0


def _filter_by_drama_titles(
    segments: Sequence[Mapping[str, Any]],
    matched_titles: Sequence[str],
) -> list[dict[str, Any]]:
    """질문에 등록 작품명이 명시되면 재검색에서도 작품 범위를 유지한다."""

    if not matched_titles:
        return [dict(segment) for segment in segments]
    normalized_titles = {
        title.strip().casefold()
        for title in matched_titles
        if isinstance(title, str) and title.strip()
    }
    return [
        dict(segment)
        for segment in segments
        if isinstance(segment.get("drama_title"), str)
        and str(segment["drama_title"]).strip().casefold() in normalized_titles
    ]


def collapse_source_results(
    results: Sequence[Mapping[str, Any]],
    *,
    source: Literal["text", "image"],
) -> list[dict[str, Any]]:
    """keyframe 행을 segment 단위로 묶고 대표 keyframe과 검색 점수를 보존한다."""

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for index, item in enumerate(results):
        if not isinstance(item, Mapping):
            raise TypeError(f"{source} 검색 결과 {index}는 객체여야 합니다.")
        segment_id = item.get("segment_id")
        if not isinstance(segment_id, str) or not segment_id.strip():
            raise ValueError(f"{source} 검색 결과의 segment_id가 올바르지 않습니다.")
        grouped.setdefault(segment_id.strip(), []).append(item)

    collapsed: list[dict[str, Any]] = []
    for segment_id, rows in grouped.items():
        source_scores = [_source_score(row, source) for row in rows]
        image_scores = [
            _optional_score(row, "image_score", fallback=None)
            for row in rows
        ]
        representative_index = max(
            range(len(rows)),
            key=lambda index: (
                image_scores[index]
                if image_scores[index] is not None
                else source_scores[index] if source == "image" else -math.inf,
                -index,
            ),
        )
        representative = dict(rows[representative_index])
        representative["segment_id"] = segment_id
        representative["score"] = max(source_scores)

        text_scores = [
            value
            for row in rows
            if (value := _optional_score(row, "text_score", fallback=None))
            is not None
        ]
        valid_image_scores = [value for value in image_scores if value is not None]
        if text_scores:
            representative["text_score"] = max(text_scores)
        elif source == "text":
            representative["text_score"] = max(source_scores)
        if valid_image_scores:
            representative["image_score"] = max(valid_image_scores)
        elif source == "image":
            representative["image_score"] = max(source_scores)
        collapsed.append(representative)

    return sorted(
        collapsed,
        key=lambda item: (-float(item["score"]), str(item["segment_id"])),
    )


def _source_score(item: Mapping[str, Any], source: str) -> float:
    value = _optional_score(item, "score", fallback=f"{source}_score")
    if value is None:
        raise ValueError(f"{source} 검색 결과에 score 또는 {source}_score가 필요합니다.")
    return value


def _optional_score(
    item: Mapping[str, Any] | None,
    field_name: str,
    *,
    fallback: str | None,
) -> float | None:
    if item is None:
        return None
    value = item.get(field_name)
    if value is None and fallback is not None:
        value = item.get(fallback)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name}는 숫자여야 합니다.")
    score = float(value)
    if not math.isfinite(score):
        raise ValueError(f"{field_name}는 유한한 숫자여야 합니다.")
    return score
