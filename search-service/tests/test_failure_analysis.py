"""검색 실패 분류와 실제 평가셋 분석 테스트."""

from __future__ import annotations

import json
from pathlib import Path

from src.dummy_embedder import DummyTextEmbedder
from src.failure_analysis import analyze_failures, classify_failure


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_successful_top_rank_has_no_failure_label() -> None:
    labels = classify_failure(["A"], ["A", "B"], ["autumn"], k=5)

    assert labels == []


def test_relevant_result_below_first_is_wrong_top_rank() -> None:
    labels = classify_failure(["A"], ["B", "A"], ["forest"], k=5)

    assert labels == ["wrong_top_rank"]


def test_relevant_result_outside_k_is_missed() -> None:
    labels = classify_failure(["A"], ["B", "C", "A"], ["forest"], k=2)

    assert labels == ["missed_at_k"]


def test_unknown_query_without_results_has_three_failure_labels() -> None:
    labels = classify_failure(["A"], [], [], k=5)

    assert labels == ["vocabulary_gap", "no_results", "missed_at_k"]


def test_actual_eval_set_identifies_expected_failure_queries() -> None:
    with (PROJECT_ROOT / "data" / "dummy_segments.json").open(
        "r", encoding="utf-8"
    ) as file:
        segments = json.load(file)["segments"]
    with (PROJECT_ROOT / "data" / "eval_queries.json").open(
        "r", encoding="utf-8"
    ) as file:
        queries = json.load(file)["queries"]

    report = analyze_failures(queries, segments, DummyTextEmbedder(), k=5)
    cases = {case["query_id"]: case for case in report["cases"]}

    assert report["summary"]["failure_queries"] == 2
    assert set(cases) == {"Q009", "Q010"}
    assert "wrong_top_rank" in cases["Q009"]["failure_types"]
    assert "feature_collision" in cases["Q009"]["failure_types"]
    assert "vocabulary_gap" in cases["Q010"]["failure_types"]
    assert "missed_at_k" in cases["Q010"]["failure_types"]
