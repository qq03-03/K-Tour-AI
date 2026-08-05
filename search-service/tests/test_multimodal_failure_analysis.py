from __future__ import annotations

from src.multimodal_failure_analysis import analyze_multimodal_report


def test_missed_and_wrong_top_rank_are_classified() -> None:
    payload = {
        "cases": [
            {
                "query_id": "Q1",
                "language": "ko",
                "query": "눈길",
                "relevant_segment_ids": ["RIGHT"],
                "candidate_count": 2,
                "fallback_used": False,
                "methods": {
                    "rrf": {"retrieved_segment_ids": ["WRONG"]},
                    "normalized": {"retrieved_segment_ids": ["WRONG", "RIGHT"]},
                },
            }
        ]
    }

    report = analyze_multimodal_report(payload)

    by_method = {item["method"]: item for item in report["cases"]}
    assert by_method["rrf"]["failure_types"] == ["missed_at_k"]
    assert by_method["normalized"]["failure_types"] == ["wrong_top_rank"]


def test_fallback_is_recorded_even_when_rank_is_correct() -> None:
    payload = {
        "cases": [
            {
                "query_id": "Q1",
                "language": "ko",
                "query": "궁궐",
                "relevant_segment_ids": ["RIGHT"],
                "candidate_count": 3,
                "fallback_used": True,
                "fallback_reason": "필터 결과 없음",
                "methods": {"rrf": {"retrieved_segment_ids": ["RIGHT"]}},
            }
        ]
    }

    report = analyze_multimodal_report(payload)

    assert report["cases"][0]["failure_types"] == ["parser_fallback"]


def test_successful_report_has_no_failure_cases() -> None:
    payload = {
        "cases": [
            {
                "query_id": "Q1",
                "language": "ko",
                "query": "궁궐",
                "relevant_segment_ids": ["RIGHT"],
                "candidate_count": 3,
                "fallback_used": False,
                "methods": {"rrf": {"retrieved_segment_ids": ["RIGHT"]}},
            }
        ]
    }

    report = analyze_multimodal_report(payload)

    assert report["summary"]["failure_record_count"] == 0
    assert report["cases"] == []


def test_parser_branch_and_representative_failures_are_distinguished() -> None:
    payload = {
        "cases": [
            {
                "query_id": "Q1",
                "language": "ko",
                "query": "전주 궁궐",
                "relevant_segment_ids": ["RIGHT"],
                "candidate_count": 3,
                "fallback_used": False,
                "expected_filters": {"region": ["전주"]},
                "filters": {"region": ["전북"]},
                "expected_soft_hints": {"mood": ["고요한"]},
                "soft_hints": {},
                "source_anchors": {"keyframe_paths": ["keyframes/right.jpg"]},
                "source_results": {
                    "text": [{"segment_id": "WRONG"}],
                    "image": [{"segment_id": "RIGHT"}],
                },
                "methods": {
                    "rrf": {
                        "retrieved_segment_ids": ["RIGHT"],
                        "retrieved_results": [
                            {
                                "segment_id": "RIGHT",
                                "keyframe_path": "keyframes/wrong.jpg",
                            }
                        ],
                    }
                },
            }
        ]
    }

    report = analyze_multimodal_report(payload)

    assert report["cases"][0]["failure_types"] == [
        "filter_mismatch",
        "soft_hint_mismatch",
        "text_branch_miss",
        "wrong_representative_keyframe",
    ]
