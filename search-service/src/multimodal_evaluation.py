"""실제 멀티모달 검색의 언어별 품질·속도·결합 방식을 평가한다."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import fmean
from typing import Any

from .interfaces import QueryParser
from .metrics import hit_at_k, ndcg_at_k, recall_at_k, reciprocal_rank
from .multimodal_pipeline import MultimodalSearchPipeline


def load_multimodal_cases(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, Mapping):
        raise ValueError("평가 JSON 최상위 값은 객체여야 합니다.")
    raw_cases = payload.get("queries")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("queries는 하나 이상의 평가 질문 목록이어야 합니다.")

    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_cases):
        if not isinstance(raw, Mapping):
            raise ValueError(f"queries[{index}]는 객체여야 합니다.")
        required = {"query_id", "language", "query", "relevant_segment_ids"}
        missing = required - set(raw)
        if missing:
            raise ValueError(
                f"queries[{index}] 필수 항목 누락: {', '.join(sorted(missing))}"
            )
        query_id = str(raw["query_id"]).strip()
        if not query_id or query_id in seen:
            raise ValueError(f"query_id가 비었거나 중복되었습니다: {query_id}")
        seen.add(query_id)
        relevant = raw["relevant_segment_ids"]
        if (
            isinstance(relevant, (str, bytes))
            or not isinstance(relevant, Sequence)
            or not relevant
        ):
            raise ValueError(f"{query_id}.relevant_segment_ids가 올바르지 않습니다.")
        cases.append(dict(raw))
    return cases


def evaluate_multimodal_search(
    pipeline: MultimodalSearchPipeline,
    parser: QueryParser,
    cases: Sequence[Mapping[str, Any]],
    *,
    top_k: int = 5,
    weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    if not cases:
        raise ValueError("평가 질문이 하나 이상 필요합니다.")

    details: list[dict[str, Any]] = []
    for item in cases:
        output = pipeline.search(
            str(item["query"]),
            parser=parser,
            top_k=top_k,
            methods=("rrf", "normalized"),
            weights=weights,
        )
        relevant_ids = [str(value) for value in item["relevant_segment_ids"]]
        methods: dict[str, Any] = {}
        for method, results in output["results_by_method"].items():
            retrieved_ids = [str(result["segment_id"]) for result in results]
            methods[method] = {
                "retrieved_segment_ids": retrieved_ids,
                "retrieved_results": [dict(result) for result in results],
                "hit_at_k": hit_at_k(relevant_ids, retrieved_ids, top_k),
                "recall_at_k": recall_at_k(relevant_ids, retrieved_ids, top_k),
                "reciprocal_rank": reciprocal_rank(relevant_ids, retrieved_ids),
                "ndcg_at_k": ndcg_at_k(relevant_ids, retrieved_ids, top_k),
            }

        details.append(
            {
                "query_id": item["query_id"],
                "language": item["language"],
                "query": item["query"],
                "relevant_segment_ids": relevant_ids,
                "expected_filters": dict(item.get("expected_filters", {})),
                "expected_soft_hints": dict(item.get("expected_soft_hints", {})),
                "case_type": item.get("case_type", "unspecified"),
                "source_anchors": dict(item.get("source_anchors", {})),
                "search_text": output["search_text"],
                "filters": output["filters"],
                "soft_hints": output["soft_hints"],
                "fallback_used": output["fallback_used"],
                "fallback_reason": output["fallback_reason"],
                "candidate_count": output["candidate_count"],
                "source_results": {
                    source: [dict(result) for result in results]
                    for source, results in output.get("source_results", {}).items()
                },
                "latency_ms": output["latency_ms"],
                "methods": methods,
            }
        )

    languages = sorted({str(item["language"]) for item in details})
    return {
        "summary": _summarize(details),
        "by_language": {
            language: _summarize(
                [item for item in details if item["language"] == language]
            )
            for language in languages
        },
        "by_case_type": {
            case_type: _summarize(
                [item for item in details if item["case_type"] == case_type]
            )
            for case_type in sorted({str(item["case_type"]) for item in details})
        },
        "runtime": {
            "embedding_model": pipeline.runtime.model_name,
            "device": pipeline.runtime.device,
            "model_load_count": pipeline.runtime.load_count,
            "model_load_latency_ms": round(pipeline.runtime.load_latency_ms, 3),
        },
        "cases": details,
    }


def _summarize(details: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    methods = sorted(
        {
            str(method)
            for item in details
            for method in item["methods"]
        }
    )
    latencies = [float(item["latency_ms"]["total"]) for item in details]
    parser_latencies = [float(item["latency_ms"]["parser"]) for item in details]
    embedding_latencies = [
        float(item["latency_ms"].get("query_embedding", 0.0)) for item in details
    ]
    vector_latencies = [
        float(item["latency_ms"].get("vector_search", 0.0)) for item in details
    ]
    return {
        "query_count": len(details),
        "fallback_rate": fmean(
            float(bool(item["fallback_used"])) for item in details
        ),
        "latency_ms": {
            "average_total": fmean(latencies),
            "p95_total": _percentile(latencies, 0.95),
            "average_parser": fmean(parser_latencies),
            "p95_parser": _percentile(parser_latencies, 0.95),
            "average_query_embedding": fmean(embedding_latencies),
            "p95_query_embedding": _percentile(embedding_latencies, 0.95),
            "average_vector_search": fmean(vector_latencies),
            "p95_vector_search": _percentile(vector_latencies, 0.95),
        },
        "methods": {
            method: {
                "hit_at_k": fmean(
                    float(item["methods"][method]["hit_at_k"])
                    for item in details
                ),
                "recall_at_k": fmean(
                    float(item["methods"][method]["recall_at_k"])
                    for item in details
                ),
                "mrr": fmean(
                    float(item["methods"][method]["reciprocal_rank"])
                    for item in details
                ),
                "ndcg_at_k": fmean(
                    float(item["methods"][method]["ndcg_at_k"])
                    for item in details
                ),
            }
            for method in methods
        },
    }


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]
