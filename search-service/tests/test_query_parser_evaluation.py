"""QueryParser 평가셋 로더와 지표 계산 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.query_parser import ParsedQuery, RuleBasedQueryParser
from src.query_parser_evaluation import evaluate_query_parser, load_query_parser_cases


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_PATH = PROJECT_ROOT / "data" / "query_parser_eval.json"


def test_multilingual_evaluation_dataset_is_valid() -> None:
    cases = load_query_parser_cases(EVAL_PATH)

    assert len(cases) == 32
    assert {case["language"] for case in cases} == {"ko", "en", "ja", "zh"}
    assert {
        language: sum(case["language"] == language for case in cases)
        for language in ("ko", "en", "ja", "zh")
    } == {"ko": 8, "en": 8, "ja": 8, "zh": 8}
    assert len({case["query_id"] for case in cases}) == len(cases)
    assert {
        "title_ambiguity",
        "title_with_explicit_season",
        "emotional_soft_hint",
        "semantic_only",
        "place_not_region",
        "inferred_season_guard",
    }.issubset({case["case_type"] for case in cases})


class ExpectedParser:
    def __init__(self, expected_by_query: dict[str, dict[str, list[str]]]) -> None:
        self.expected_by_query = expected_by_query

    def parse(self, query: str) -> ParsedQuery:
        return ParsedQuery(query, query, self.expected_by_query[query])


def test_perfect_parser_gets_full_scores() -> None:
    cases = [
        {
            "query_id": "Q1",
            "language": "ko",
            "query": "여름 서울",
            "expected_filters": {"season": ["여름"], "region": ["서울"]},
        },
        {
            "query_id": "Q2",
            "language": "ko",
            "query": "연꽃",
            "expected_filters": {},
        },
    ]
    parser = ExpectedParser(
        {
            "여름 서울": {"season": ["여름"], "region": ["서울"]},
            "연꽃": {},
        }
    )

    summary = evaluate_query_parser(parser, cases)["summary"]

    assert summary["exact_match_rate"] == 1.0
    assert summary["micro_precision"] == 1.0
    assert summary["micro_recall"] == 1.0
    assert summary["micro_f1"] == 1.0
    assert summary["soft_hint_exact_match_rate"] == 1.0
    assert summary["soft_hint_micro_f1"] == 1.0
    assert summary["fallback_rate"] == 0.0
    assert summary["original_query_preservation_rate"] == 1.0
    assert summary["average_latency_ms"] >= 0.0
    assert summary["p50_latency_ms"] >= 0.0
    assert summary["p95_latency_ms"] >= 0.0


def test_missing_filters_reduce_recall() -> None:
    cases = [
        {
            "query_id": "Q1",
            "language": "ko",
            "query": "여름 서울",
            "expected_filters": {"season": ["여름"], "region": ["서울"]},
        }
    ]
    parser = ExpectedParser({"여름 서울": {"season": ["여름"]}})

    summary = evaluate_query_parser(parser, cases)["summary"]

    assert summary["exact_match_rate"] == 0.0
    assert summary["micro_precision"] == 1.0
    assert summary["micro_recall"] == 0.5
    assert summary["micro_f1"] == pytest.approx(2 / 3)


def test_rule_baseline_can_run_on_full_dataset() -> None:
    cases = load_query_parser_cases(EVAL_PATH)

    evaluation = evaluate_query_parser(RuleBasedQueryParser(), cases)

    assert evaluation["summary"]["query_count"] == 32
    assert len(evaluation["cases"]) == 32
    assert set(evaluation["by_language"]) == {"ko", "en", "ja", "zh"}
    assert all(
        summary["query_count"] == 8
        for summary in evaluation["by_language"].values()
    )
    assert 0.0 <= evaluation["summary"]["exact_match_rate"] <= 1.0


def test_emotion_as_hard_filter_is_corrected_to_soft_hint() -> None:
    cases = [
        {
            "query_id": "Q1",
            "language": "ko",
            "query": "마음이 편안해지는 장소",
            "expected_filters": {},
            "expected_soft_hints": {"mood": ["평화로운"]},
            "case_type": "emotional_soft_hint",
        }
    ]
    parser = ExpectedParser({"마음이 편안해지는 장소": {"mood": ["평화로운"]}})

    evaluation = evaluate_query_parser(parser, cases)
    summary = evaluation["summary"]

    assert summary["micro_precision"] == 1.0
    assert summary["soft_hint_micro_recall"] == 1.0
    assert evaluation["cases"][0]["exact_match"] is True
    assert evaluation["cases"][0]["soft_hint_exact_match"] is True


def test_language_summaries_keep_accuracy_and_latency_separate() -> None:
    cases = [
        {
            "query_id": "KO",
            "language": "ko",
            "query": "서울",
            "expected_filters": {"region": ["서울"]},
        },
        {
            "query_id": "EN",
            "language": "en",
            "query": "Seoul",
            "expected_filters": {"region": ["서울"]},
        },
    ]
    parser = ExpectedParser({"서울": {"region": ["서울"]}, "Seoul": {}})

    evaluation = evaluate_query_parser(parser, cases)

    assert evaluation["by_language"]["ko"]["exact_match_rate"] == 1.0
    assert evaluation["by_language"]["en"]["exact_match_rate"] == 0.0
    assert evaluation["by_language"]["ko"]["average_latency_ms"] >= 0.0
    assert evaluation["by_language"]["en"]["p95_latency_ms"] >= 0.0
