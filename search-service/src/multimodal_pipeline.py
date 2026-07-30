"""OpenAI QueryParser, CLIP, pgvector, 필터와 검색 결합의 실제 통합 흐름."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
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

        metadata_started = perf_counter()
        segments = self._load_segments()
        filter_arguments = to_filter_arguments(parsed.filters)
        candidates = filter_segments(segments, **filter_arguments)
        if parsed.filters and not candidates:
            parsed = replace(
                parsed,
                filters={},
                fallback_used=True,
                fallback_reason="필터 결과가 없어 필터 없이 다시 검색했습니다.",
            )
            filter_arguments = {}
            candidates = list(segments)
        metadata_latency_ms = _elapsed_ms(metadata_started)

        candidate_ids = [str(segment["segment_id"]) for segment in candidates]
        depth = min(search_depth, len(candidate_ids))

        encoder_started = perf_counter()
        query_vector = self.runtime.encode_text(parsed.search_text)
        encoder_latency_ms = _elapsed_ms(encoder_started)

        vector_started = perf_counter()
        text_results = self.repository.search(
            query_vector,
            "text",
            candidate_ids=candidate_ids,
            top_k=depth,
        )
        image_results = self.repository.search(
            query_vector,
            "image",
            candidate_ids=candidate_ids,
            top_k=depth,
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
            )
            for method, results in reranked.items()
        }
        fusion_latency_ms = _elapsed_ms(fusion_started)

        return {
            "original_query": parsed.original_query,
            "search_text": parsed.search_text,
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
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for fused in fused_results:
            segment_id = str(fused["segment_id"])
            segment = dict(segment_by_id[segment_id])
            enriched.append(
                {
                    **segment,
                    **dict(fused),
                }
            )
        return enriched


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000.0
