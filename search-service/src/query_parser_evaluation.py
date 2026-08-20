"""QueryParser의 필터 정확도와 응답 시간을 평가한다."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

from .interfaces import QueryParser
from .query_parser import parse_query_safely


def load_query_parser_cases(path: str | Path) -> list[dict[str, Any]]:
    """QueryParser 평가 JSON을 읽고 최소 형식을 검사한다."""

    data_path = Path(path)
    with data_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, Mapping):
        raise ValueError("평가 JSON의 최상위 값은 객체여야 합니다.")
    raw_cases = payload.get("queries")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("queries는 하나 이상의 평가 질문 목록이어야 합니다.")

    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_cases):
        if not isinstance(item, Mapping):
            raise ValueError(f"queries[{index}]는 객체여야 합니다.")
        required = {"query_id", "language", "query", "expected_filters"}
        missing = sorted(required - item.keys())
        if missing:
            raise ValueError(f"queries[{index}] 필수 항목 누락: {', '.join(missing)}")
        query_id = item["query_id"]
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError(f"queries[{index}].query_id는 문자열이어야 합니다.")
        if query_id in seen_ids:
            raise ValueError(f"query_id가 중복되었습니다: {query_id}")
        seen_ids.add(query_id)
        if not isinstance(item["query"], str) or not item["query"].strip():
            raise ValueError(f"{query_id}.query는 빈 문자열이 아니어야 합니다.")
        if not isinstance(item["language"], str) or not item["language"].strip():
            raise ValueError(f"{query_id}.language는 빈 문자열이 아니어야 합니다.")
        if not isinstance(item["expected_filters"], Mapping):
            raise ValueError(f"{query_id}.expected_filters는 객체여야 합니다.")
        expected_soft_hints = item.get("expected_soft_hints", {})
        if not isinstance(expected_soft_hints, Mapping):
            raise ValueError(f"{query_id}.expected_soft_hints는 객체여야 합니다.")
        case_type = item.get("case_type")
        if case_type is not None and (
            not isinstance(case_type, str) or not case_type.strip()
        ):
            raise ValueError(f"{query_id}.case_type은 빈 문자열이 아니어야 합니다.")
        cases.append(dict(item))
    return cases


def evaluate_query_parser(
    parser: QueryParser,
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """질문별 결과와 전체 정확도·fallback·지연시간을 반환한다."""

    if not cases:
        raise ValueError("평가 질문이 하나 이상 필요합니다.")

    details: list[dict[str, Any]] = []

    for item in cases:
        query = str(item["query"])
        started = perf_counter()
        parsed = parse_query_safely(query, parser)
        latency_ms = (perf_counter() - started) * 1000.0
        expected_filters = _normalized_filters(item["expected_filters"])
        actual_filters = _normalized_filters(parsed.filters)
        expected_soft_hints = _normalized_filters(item.get("expected_soft_hints", {}))
        actual_soft_hints = _normalized_filters(parsed.soft_hints)

        details.append(
            {
                "query_id": item["query_id"],
                "language": item["language"],
                "case_type": item.get("case_type", "unspecified"),
                "query": query,
                "expected_filters": expected_filters,
                "actual_filters": actual_filters,
                "exact_match": actual_filters == expected_filters,
                "expected_soft_hints": expected_soft_hints,
                "actual_soft_hints": actual_soft_hints,
                "soft_hint_exact_match": actual_soft_hints == expected_soft_hints,
                "fallback_used": parsed.fallback_used,
                "fallback_reason": parsed.fallback_reason,
                "original_query_preserved": parsed.original_query == query.strip(),
                "latency_ms": round(latency_ms, 3),
            }
        )

    languages = sorted({str(item["language"]) for item in details})
    case_types = sorted({str(item["case_type"]) for item in details})
    return {
        "summary": _summarize_details(details),
        "by_language": {
            language: _summarize_details(
                [item for item in details if item["language"] == language]
            )
            for language in languages
        },
        "by_case_type": {
            case_type: _summarize_details(
                [item for item in details if item["case_type"] == case_type]
            )
            for case_type in case_types
        },
        "cases": details,
    }


def _summarize_details(details: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """질문 묶음의 강제 필터·soft hint 정확도와 지연시간을 계산한다."""

    if not details:
        raise ValueError("요약할 평가 결과가 하나 이상 필요합니다.")

    filter_scores = _pair_scores(details, "expected_filters", "actual_filters")
    soft_hint_scores = _pair_scores(
        details,
        "expected_soft_hints",
        "actual_soft_hints",
    )
    latencies_ms = [float(item["latency_ms"]) for item in details]
    sorted_latencies = sorted(latencies_ms)
    p50_index = max(0, math.ceil(len(sorted_latencies) * 0.50) - 1)
    p95_index = max(0, math.ceil(len(sorted_latencies) * 0.95) - 1)
    count = len(details)
    return {
        "query_count": count,
        "exact_match_rate": sum(bool(item["exact_match"]) for item in details)
        / count,
        "micro_precision": filter_scores["precision"],
        "micro_recall": filter_scores["recall"],
        "micro_f1": filter_scores["f1"],
        "soft_hint_exact_match_rate": sum(
            bool(item["soft_hint_exact_match"]) for item in details
        )
        / count,
        "soft_hint_micro_precision": soft_hint_scores["precision"],
        "soft_hint_micro_recall": soft_hint_scores["recall"],
        "soft_hint_micro_f1": soft_hint_scores["f1"],
        "fallback_rate": sum(bool(item["fallback_used"]) for item in details)
        / count,
        "original_query_preservation_rate": sum(
            bool(item["original_query_preserved"]) for item in details
        )
        / count,
        "average_latency_ms": sum(latencies_ms) / count,
        "p50_latency_ms": sorted_latencies[p50_index],
        "p95_latency_ms": sorted_latencies[p95_index],
    }


def _pair_scores(
    details: Sequence[Mapping[str, Any]],
    expected_key: str,
    actual_key: str,
) -> dict[str, float]:
    true_positive = 0
    predicted_total = 0
    expected_total = 0
    for item in details:
        expected_pairs = _filter_pairs(item[expected_key])
        actual_pairs = _filter_pairs(item[actual_key])
        true_positive += len(expected_pairs & actual_pairs)
        predicted_total += len(actual_pairs)
        expected_total += len(expected_pairs)

    precision = true_positive / predicted_total if predicted_total else float(expected_total == 0)
    recall = true_positive / expected_total if expected_total else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _normalized_filters(values: object) -> dict[str, list[str]]:
    if not isinstance(values, Mapping):
        raise TypeError("필터는 객체여야 합니다.")
    normalized: dict[str, list[str]] = {}
    for key, raw_items in values.items():
        if isinstance(raw_items, (str, bytes)) or not isinstance(raw_items, Sequence):
            raise TypeError(f"{key} 필터는 문자열 목록이어야 합니다.")
        normalized[str(key)] = sorted(str(item).strip() for item in raw_items)
    return normalized


def _filter_pairs(filters: Mapping[str, Sequence[str]]) -> set[tuple[str, str]]:
    return {
        (field_name, value.casefold())
        for field_name, values in filters.items()
        for value in values
    }
