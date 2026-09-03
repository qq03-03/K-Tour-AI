from __future__ import annotations

from src.display_translation_qa import build_qa_summary


def test_build_qa_summary_counts_failed_languages() -> None:
    records = [
        {
            "segment_id": "S1",
            "passed": True,
            "failed_languages": [],
        },
        {
            "segment_id": "S2",
            "passed": False,
            "failed_languages": ["ja", "zh"],
        },
    ]

    summary = build_qa_summary(records)

    assert summary["record_count"] == 2
    assert summary["passed_count"] == 1
    assert summary["review_count"] == 1
    assert summary["by_language_review_count"]["ja"] == 1
    assert summary["by_language_review_count"]["zh"] == 1
