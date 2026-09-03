from __future__ import annotations

import json

from src.multimodal_evaluation import evaluate_multimodal_search, load_multimodal_cases


class Runtime:
    model_name = "fake"
    device = "cpu"
    load_count = 1
    load_latency_ms = 0.0


class Pipeline:
    runtime = Runtime()

    def search(self, query, *, parser, top_k, methods, weights):
        results = [{"segment_id": "RIGHT_1"}, {"segment_id": "WRONG"}]
        return {
            "search_text": query,
            "filters": {},
            "soft_hints": {},
            "fallback_used": False,
            "fallback_reason": None,
            "candidate_count": 3,
            "source_results": {
                "text": [{"segment_id": "RIGHT_1", "score": 0.9}],
                "image": [{"segment_id": "RIGHT_1", "score": 0.8}],
            },
            "latency_ms": {
                "total": 10.0,
                "parser": 2.0,
                "query_embedding": 1.0,
                "vector_search": 3.0,
            },
            "results_by_method": {"rrf": results, "normalized": results},
        }


def test_multimodal_summary_includes_recall_at_k() -> None:
    cases = [
        {
            "query_id": "Q1",
            "language": "ko",
            "query": "질문",
            "relevant_segment_ids": ["RIGHT_1", "RIGHT_2"],
        }
    ]

    report = evaluate_multimodal_search(Pipeline(), object(), cases, top_k=2)

    assert report["cases"][0]["methods"]["rrf"]["recall_at_k"] == 0.5
    assert report["summary"]["methods"]["rrf"]["recall_at_k"] == 0.5


def test_multimodal_cases_accept_utf8_bom(tmp_path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "query_id": "Q1",
                        "language": "ko",
                        "query": "궁궐",
                        "relevant_segment_ids": ["SEG_A"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8-sig",
    )

    assert load_multimodal_cases(path)[0]["query_id"] == "Q1"
