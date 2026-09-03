"""실제 멀티모달 평가 보고서에서 실패 질문과 원인을 분류한다."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any


FAILURE_EXPLANATIONS = {
    "no_candidates": "구조화 필터 적용 후 검색 후보가 남지 않았습니다.",
    "parser_fallback": "질문 분석이 실패하거나 필터 없는 재검색이 사용됐습니다.",
    "filter_mismatch": "QueryParser 필터가 평가셋의 예상 필터와 다릅니다.",
    "soft_hint_mismatch": "QueryParser 소프트 힌트가 평가셋의 예상값과 다릅니다.",
    "text_branch_miss": "텍스트 Top-K에 정답 세그먼트가 없습니다.",
    "image_branch_miss": "이미지 Top-K에 정답 세그먼트가 없습니다.",
    "missed_at_k": "정답 세그먼트가 상위 K 결과에 포함되지 않았습니다.",
    "wrong_top_rank": "정답이 상위 K에는 있지만 1위가 아닙니다.",
    "wrong_representative_keyframe": "정답 세그먼트의 대표 keyframe이 평가 앵커와 다릅니다.",
}


def analyze_multimodal_report(payload: object) -> dict[str, Any]:
    """`evaluate_multimodal_search` 결과를 방식별 실패 보고서로 변환한다."""

    if not isinstance(payload, Mapping):
        raise ValueError("멀티모달 평가 보고서는 JSON 객체여야 합니다.")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("멀티모달 평가 보고서에 cases 배열이 필요합니다.")

    failures: list[dict[str, Any]] = []
    is_dry_run = str(payload.get("execution_mode", "")).startswith("dry_run")
    for case in raw_cases:
        if not isinstance(case, Mapping):
            raise ValueError("평가 cases의 각 항목은 객체여야 합니다.")
        methods = case.get("methods")
        if not isinstance(methods, Mapping):
            raise ValueError("평가 case에 methods 객체가 필요합니다.")
        shared: list[str] = []
        if int(case.get("candidate_count", 0)) == 0:
            shared.append("no_candidates")
        if bool(case.get("fallback_used")):
            shared.append("parser_fallback")
        if _normalized_mapping(case.get("filters")) != _normalized_mapping(
            case.get("expected_filters")
        ):
            shared.append("filter_mismatch")
        if _normalized_mapping(case.get("soft_hints")) != _normalized_mapping(
            case.get("expected_soft_hints")
        ):
            shared.append("soft_hint_mismatch")

        relevant = [str(value) for value in case.get("relevant_segment_ids", [])]
        source_results = case.get("source_results", {})
        if isinstance(source_results, Mapping):
            text_ids = _source_segment_ids(source_results.get("text"))
            image_ids = _source_segment_ids(source_results.get("image"))
            if text_ids and _first_relevant_rank(relevant, text_ids) is None:
                shared.append("text_branch_miss")
            if image_ids and _first_relevant_rank(relevant, image_ids) is None:
                shared.append("image_branch_miss")

        for method, metrics in methods.items():
            if not isinstance(metrics, Mapping):
                raise ValueError("methods의 각 값은 지표 객체여야 합니다.")
            labels = list(shared)
            retrieved = [str(value) for value in metrics.get("retrieved_segment_ids", [])]
            first_rank = _first_relevant_rank(relevant, retrieved)
            if first_rank is None:
                labels.append("missed_at_k")
            elif first_rank > 1:
                labels.append("wrong_top_rank")
            if not is_dry_run and _wrong_representative_keyframe(case, metrics):
                labels.append("wrong_representative_keyframe")
            if not labels:
                continue
            failures.append(
                {
                    "query_id": case.get("query_id"),
                    "language": case.get("language"),
                    "query": case.get("query"),
                    "method": method,
                    "failure_types": labels,
                    "explanations": [FAILURE_EXPLANATIONS[label] for label in labels],
                    "relevant_segment_ids": relevant,
                    "retrieved_segment_ids": retrieved,
                    "first_relevant_rank": first_rank,
                    "filters": case.get("filters", {}),
                    "soft_hints": case.get("soft_hints", {}),
                    "fallback_reason": case.get("fallback_reason"),
                }
            )

    counts = Counter(label for item in failures for label in item["failure_types"])
    methods = sorted({str(item["method"]) for item in failures})
    return {
        "summary": {
            "evaluation_query_count": len(raw_cases),
            "failure_record_count": len(failures),
            "failure_type_counts": dict(sorted(counts.items())),
            "failure_records_by_method": {
                method: sum(item["method"] == method for item in failures)
                for method in methods
            },
        },
        "cases": failures,
    }


def _first_relevant_rank(relevant: list[str], retrieved: list[str]) -> int | None:
    relevant_set = set(relevant)
    for rank, segment_id in enumerate(retrieved, 1):
        if segment_id in relevant_set:
            return rank
    return None


def _normalized_mapping(value: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, tuple[str, ...]] = {}
    for key, raw_values in value.items():
        if isinstance(raw_values, str):
            values = [raw_values]
        elif isinstance(raw_values, list):
            values = raw_values
        else:
            values = []
        normalized[str(key)] = tuple(
            sorted(
                str(item).strip().casefold()
                for item in values
                if str(item).strip()
            )
        )
    return normalized


def _source_segment_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item.get("segment_id"))
        for item in value
        if isinstance(item, Mapping) and item.get("segment_id")
    ]


def _wrong_representative_keyframe(
    case: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> bool:
    anchors = case.get("source_anchors")
    if not isinstance(anchors, Mapping):
        return False
    expected_paths = {
        _normalize_path(value) for value in anchors.get("keyframe_paths", [])
    }
    if not expected_paths:
        return False
    relevant = {str(value) for value in case.get("relevant_segment_ids", [])}
    results = metrics.get("retrieved_results")
    if not isinstance(results, list):
        return False
    for result in results:
        if not isinstance(result, Mapping):
            continue
        if str(result.get("segment_id")) not in relevant:
            continue
        keyframe_path = result.get("keyframe_path")
        if keyframe_path and _normalize_path(keyframe_path) not in expected_paths:
            return True
    return False


def _normalize_path(value: object) -> str:
    return str(value).strip().replace("\\", "/").casefold()
