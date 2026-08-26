from __future__ import annotations

from ktour_search_automation.regression import (
    build_regression_report,
    compare_regression_reports,
    evaluate_response_case,
)
from ktour_search_automation.contract import evaluate_contract_response


def test_response_metrics_and_source_deduplication_check() -> None:
    case = {
        "query_id": "E1",
        "language": "ko",
        "query": "꽃길",
        "relevant_source_segment_ids": ["SOURCE_2"],
        "expected_filters": {"season": ["봄"]},
    }
    response = {"applied_filters": {"season": ["봄"]}}
    results = [
        {
            "source_segment_id": "SOURCE_1",
            "segment_id": "SCENE_1",
            "keyframe_id": "SCENE_1",
            "place_id": "P001",
            "place_name": "장소1",
            "region": "경기",
            "city": "수원",
            "start_time": 0.0,
            "end_time": 1.0,
            "keyframe_path": "keyframes/1.jpg",
            "final_score": 0.03,
        },
        {
            "source_segment_id": "SOURCE_2",
            "segment_id": "SCENE_2",
            "keyframe_id": "SCENE_2",
            "place_id": "P002",
            "place_name": "장소2",
            "region": "경기",
            "city": "수원",
            "start_time": 1.0,
            "end_time": 2.0,
            "keyframe_path": "keyframes/2.jpg",
            "final_score": 0.02,
        },
    ]

    result = evaluate_response_case(case, response, results, top_k=5)
    assert result["hit_at_k"] == 1.0
    assert result["reciprocal_rank"] == 0.5
    assert result["filter_check"] == "passed"
    assert result["duplicate_source_segment_ids"] == []
    assert result["result_schema_issues"] == []

    result.update({"latency_ms": 100.0, "http_error": None})
    report = build_regression_report(
        [result],
        base_url="https://example.test",
        endpoint="/api/search",
        top_k=5,
        candidate_k=50,
    )
    assert report["summary"]["hit_at_k"] == 1.0
    assert report["summary"]["mrr"] == 0.5


def test_contract_checks_no_relax_and_rrf() -> None:
    request = {"query": "궁궐", "lang": "ko", "top_k": 5}
    expected = {
        "applied_filters": {"place_id": ["P016"]},
        "all_results": {"place_id": ["P016"]},
        "strict_result_contract": True,
        "no_filter_relaxation": True,
    }
    result = {
        "rank": 1,
        "source_segment_id": "SOURCE_1",
        "segment_id": "SCENE_1",
        "keyframe_id": "SCENE_1",
        "keyframe_path": "keyframes/1.jpg",
        "video_id": "VIDEO_1",
        "place_id": "P016",
        "place_name": "경복궁",
        "region": "서울특별시",
        "city": "서울특별시",
        "latitude": 37.0,
        "longitude": 127.0,
        "drama_title": "킹덤",
        "start_time": 0.0,
        "end_time": 1.0,
        "season": "여름",
        "time_of_day": "day",
        "description": "궁궐",
        "mood": [],
        "activity": [],
        "scene_elements": [],
        "k_culture_elements": [],
        "text_score": 0.7,
        "image_score": None,
        "text_rank": 1,
        "image_rank": None,
        "final_score": 1.0 / 61.0,
    }
    response = {"applied_filters": {"place_id": ["P016"]}}

    assert evaluate_contract_response(request, expected, response, [result]) == []


def test_regression_comparison_detects_new_miss() -> None:
    baseline = {
        "summary": {"hit_at_k": 1.0, "recall_at_k": 1.0, "mrr": 1.0, "ndcg_at_k": 1.0},
        "cases": [{"query_id": "Q1", "hit_at_k": 1.0, "first_relevant_rank": 1, "http_error": None}],
    }
    current = {
        "summary": {"hit_at_k": 0.0, "recall_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0},
        "cases": [{"query_id": "Q1", "hit_at_k": 0.0, "first_relevant_rank": None, "http_error": None}],
    }

    report = compare_regression_reports(current, baseline)
    assert report["new_failure_query_ids"] == ["Q1"]
    assert report["has_regression"] is True


def test_regression_comparison_detects_recall_drop_without_hit_loss() -> None:
    baseline = {
        "summary": {"hit_at_k": 1.0, "recall_at_k": 1.0, "mrr": 1.0, "ndcg_at_k": 1.0},
        "cases": [{"query_id": "Q1", "hit_at_k": 1.0, "first_relevant_rank": 1, "http_error": None}],
    }
    current = {
        "summary": {"hit_at_k": 1.0, "recall_at_k": 0.5, "mrr": 1.0, "ndcg_at_k": 0.8},
        "cases": [{"query_id": "Q1", "hit_at_k": 1.0, "first_relevant_rank": 1, "http_error": None}],
    }

    report = compare_regression_reports(current, baseline)

    assert report["new_failure_query_ids"] == []
    assert report["negative_metric_deltas"]["recall_at_k"] == -0.5
    assert report["has_regression"] is True
