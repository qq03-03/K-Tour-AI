"""실제 DB 도착 전 50문항 평가 체인을 검증하는 결정론적 dry-run 대역."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .multimodal_pipeline import MultimodalSearchPipeline, collapse_source_results


class DryRunRuntime:
    model_name = "dry-run-oracle"
    device = "none"
    load_count = 0
    load_latency_ms = 0.0


class ProductionEvaluationDryRunPipeline:
    """정답 ID를 합성 순위에 넣어 평가·결합·보고서 형식만 검증한다."""

    runtime = DryRunRuntime()

    def __init__(self, cases: Sequence[Mapping[str, Any]]) -> None:
        self._case_by_query = {str(case["query"]): dict(case) for case in cases}
        if len(self._case_by_query) != len(cases):
            raise ValueError("dry-run 평가 질문 문자열이 중복되었습니다.")
        self._segment_pool = sorted(
            {
                str(segment_id)
                for case in cases
                for segment_id in case["relevant_segment_ids"]
            }
        )

    def search(
        self,
        query: str,
        *,
        parser: object,
        top_k: int,
        methods: Sequence[str],
        weights: Mapping[str, float] | None,
    ) -> dict[str, Any]:
        del parser
        case = self._case_by_query[query]
        relevant = list(dict.fromkeys(str(value) for value in case["relevant_segment_ids"]))
        fillers = [value for value in self._segment_pool if value not in relevant]
        depth = min(max(top_k, len(relevant)), len(relevant) + len(fillers))
        text_ids = (relevant + fillers)[:depth]
        image_ids = (list(reversed(relevant)) + fillers)[:depth]

        text_results = collapse_source_results(
            [
                _source_row(segment_id, rank, len(text_ids), "text")
                for rank, segment_id in enumerate(text_ids, 1)
            ],
            source="text",
        )
        image_results = collapse_source_results(
            [
                _source_row(segment_id, rank, len(image_ids), "image")
                for rank, segment_id in enumerate(image_ids, 1)
            ],
            source="image",
        )
        fused = MultimodalSearchPipeline._fuse(
            text_results,
            image_results,
            methods=methods,
            weights=weights,
            rrf_k=60.0,
            top_k=top_k,
        )
        text_by_id = {str(item["segment_id"]): item for item in text_results}
        image_by_id = {str(item["segment_id"]): item for item in image_results}
        results_by_method = {
            method: [
                _enrich_fused_result(item, text_by_id, image_by_id)
                for item in items
            ]
            for method, items in fused.items()
        }
        return {
            "search_text": query,
            "filters": dict(case.get("expected_filters", {})),
            "soft_hints": dict(case.get("expected_soft_hints", {})),
            "fallback_used": False,
            "fallback_reason": None,
            "candidate_count": len(self._segment_pool),
            "source_results": {"text": text_results, "image": image_results},
            "results_by_method": results_by_method,
            "latency_ms": {
                "parser": 0.0,
                "metadata_and_filter": 0.0,
                "query_embedding": 0.0,
                "vector_search": 0.0,
                "fusion": 0.0,
                "total": 0.0,
            },
        }


def _source_row(
    segment_id: str,
    rank: int,
    count: int,
    source: str,
) -> dict[str, Any]:
    score = 1.0 - ((rank - 1) / max(count, 1))
    return {
        "segment_id": segment_id,
        "keyframe_id": f"DRY__{segment_id}",
        "keyframe_path": f"dry-run/{segment_id}.jpg",
        "description": "dry-run synthetic result",
        "mood": [],
        "activity": [],
        "scene_elements": [],
        f"{source}_score": score,
        "score": score,
    }


def _enrich_fused_result(
    fused: Mapping[str, Any],
    text_by_id: Mapping[str, Mapping[str, Any]],
    image_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    segment_id = str(fused["segment_id"])
    text = text_by_id.get(segment_id, {})
    image = image_by_id.get(segment_id, {})
    final_score = fused.get("combined_score", fused.get("rrf_score", 0.0))
    return {
        **dict(image or text),
        **dict(fused),
        "text_score": float(text.get("text_score", text.get("score", 0.0))),
        "image_score": float(image.get("image_score", image.get("score", 0.0))),
        "final_score": float(final_score),
    }
