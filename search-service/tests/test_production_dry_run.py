from __future__ import annotations

from src.multimodal_evaluation import evaluate_multimodal_search
from src.multimodal_failure_analysis import analyze_multimodal_report
from src.production_dry_run import ProductionEvaluationDryRunPipeline


def test_dry_run_exercises_fusion_metrics_and_failure_report() -> None:
    cases = [
        {
            "query_id": "Q1",
            "language": "ko",
            "query": "궁궐",
            "relevant_segment_ids": ["SEG_A"],
            "expected_filters": {"region": ["서울"]},
            "expected_soft_hints": {},
        },
        {
            "query_id": "Q2",
            "language": "en",
            "query": "beach",
            "relevant_segment_ids": ["SEG_B", "SEG_C"],
            "expected_filters": {},
            "expected_soft_hints": {},
        },
    ]

    pipeline = ProductionEvaluationDryRunPipeline(cases)
    report = evaluate_multimodal_search(pipeline, object(), cases, top_k=3)
    failures = analyze_multimodal_report(report)

    assert report["summary"]["query_count"] == 2
    assert report["summary"]["methods"]["rrf"]["hit_at_k"] == 1.0
    assert report["summary"]["methods"]["normalized"]["recall_at_k"] == 1.0
    assert failures["summary"]["failure_record_count"] == 0
    for case in report["cases"]:
        for method in case["methods"].values():
            assert len(method["retrieved_segment_ids"]) == len(
                set(method["retrieved_segment_ids"])
            )
