"""배포된 K-Tour AI 검색 API에 고정 평가셋을 재실행한다."""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def load_evaluation_queries(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    raw: object = payload.get("queries") if isinstance(payload, Mapping) else None
    if not isinstance(raw, list) or not raw:
        raise ValueError("평가 파일에 queries 배열이 없습니다.")
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def evaluate_backend_api(
    *,
    base_url: str,
    queries: Sequence[Mapping[str, Any]],
    endpoint: str = "/api/search",
    top_k: int = 5,
    candidate_k: int = 50,
    timeout: float = 30.0,
    bearer_token: str | None = None,
) -> dict[str, Any]:
    if top_k <= 0 or candidate_k < top_k:
        raise ValueError("top_k는 양수이고 candidate_k는 top_k 이상이어야 합니다.")
    url = base_url.rstrip("/") + "/" + endpoint.strip("/")
    cases: list[dict[str, Any]] = []
    for case in queries:
        request_body = {
            "query": _required_text(case.get("query"), "query"),
            "lang": _required_text(case.get("language"), "language"),
            "top_k": top_k,
            "candidate_k": candidate_k,
        }
        started = time.perf_counter()
        try:
            response = _post_json(
                url,
                request_body,
                timeout=timeout,
                bearer_token=bearer_token,
            )
            latency_ms = (time.perf_counter() - started) * 1000
            results = _extract_results(response)
            case_result = evaluate_response_case(case, response, results, top_k=top_k)
            case_result.update(
                {
                    "request": request_body,
                    "latency_ms": round(latency_ms, 3),
                    "http_error": None,
                }
            )
        except Exception as error:
            latency_ms = (time.perf_counter() - started) * 1000
            case_result = {
                "query_id": case.get("query_id"),
                "language": case.get("language"),
                "query": case.get("query"),
                "request": request_body,
                "latency_ms": round(latency_ms, 3),
                "http_error": f"{type(error).__name__}: {error}",
                "retrieved_source_segment_ids": [],
                "hit_at_k": 0.0,
                "recall_at_k": 0.0,
                "reciprocal_rank": 0.0,
                "ndcg_at_k": 0.0,
                "duplicate_source_segment_ids": [],
                "filter_check": "not_available",
            }
        cases.append(case_result)
    return build_regression_report(
        cases,
        base_url=base_url,
        endpoint=endpoint,
        top_k=top_k,
        candidate_k=candidate_k,
    )


def evaluate_response_case(
    case: Mapping[str, Any],
    response: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
    *,
    top_k: int,
) -> dict[str, Any]:
    retrieved = [
        _result_source_id(item)
        for item in results[:top_k]
        if _result_source_id(item)
    ]
    relevant = set(_string_list(case.get("relevant_source_segment_ids")))
    if not relevant:
        relevant = set(_string_list(case.get("relevant_segment_ids")))
    counts = Counter(retrieved)
    duplicates = sorted(value for value, count in counts.items() if count > 1)
    expected_filters = _normalize_filter_mapping(case.get("expected_filters"))
    actual_filters = _extract_filters(response)
    if actual_filters is None:
        filter_check = "not_reported"
    else:
        filter_check = "passed" if actual_filters == expected_filters else "failed"
    first_rank = next(
        (rank for rank, value in enumerate(retrieved, 1) if value in relevant),
        None,
    )
    hits = len(set(retrieved) & relevant)
    return {
        "query_id": case.get("query_id"),
        "language": case.get("language"),
        "query": case.get("query"),
        "relevant_source_segment_ids": sorted(relevant),
        "retrieved_source_segment_ids": retrieved,
        "hit_at_k": float(first_rank is not None),
        "recall_at_k": hits / len(relevant) if relevant else 0.0,
        "reciprocal_rank": 1.0 / first_rank if first_rank else 0.0,
        "ndcg_at_k": _ndcg(retrieved, relevant, top_k),
        "first_relevant_rank": first_rank,
        "duplicate_source_segment_ids": duplicates,
        "expected_filters": expected_filters,
        "actual_filters": actual_filters,
        "filter_check": filter_check,
        "result_schema_issues": _result_schema_issues(results[:top_k]),
    }


def build_regression_report(
    cases: Sequence[Mapping[str, Any]],
    *,
    base_url: str,
    endpoint: str,
    top_k: int,
    candidate_k: int,
) -> dict[str, Any]:
    successful = [case for case in cases if not case.get("http_error")]
    latencies = sorted(float(case.get("latency_ms", 0.0)) for case in successful)
    count = len(cases)
    denominator = count or 1
    return {
        "schema_version": "1.0",
        "base_url": base_url,
        "endpoint": endpoint,
        "top_k": top_k,
        "candidate_k": candidate_k,
        "summary": {
            "query_count": count,
            "successful_request_count": len(successful),
            "failed_request_count": count - len(successful),
            "missed_query_count": sum(
                not bool(case.get("hit_at_k")) for case in cases
            ),
            "hit_at_k": sum(float(case.get("hit_at_k", 0)) for case in cases)
            / denominator,
            "recall_at_k": sum(float(case.get("recall_at_k", 0)) for case in cases)
            / denominator,
            "mrr": sum(float(case.get("reciprocal_rank", 0)) for case in cases)
            / denominator,
            "ndcg_at_k": sum(float(case.get("ndcg_at_k", 0)) for case in cases)
            / denominator,
            "duplicate_result_case_count": sum(
                bool(case.get("duplicate_source_segment_ids")) for case in cases
            ),
            "result_schema_failure_case_count": sum(
                bool(case.get("result_schema_issues")) for case in cases
            ),
            "filter_failed_case_count": sum(
                case.get("filter_check") == "failed" for case in cases
            ),
            "filter_not_reported_case_count": sum(
                case.get("filter_check") == "not_reported" for case in cases
            ),
            "average_latency_ms": (
                sum(latencies) / len(latencies) if latencies else None
            ),
            "p95_latency_ms": _percentile(latencies, 0.95) if latencies else None,
        },
        "cases": list(cases),
    }


def write_regression_report(path: str | Path, report: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def compare_regression_reports(
    current: Mapping[str, Any], baseline: Mapping[str, Any]
) -> dict[str, Any]:
    current_cases = {
        str(item.get("query_id")): item
        for item in _mapping_items(current.get("cases"))
        if item.get("query_id") is not None
    }
    baseline_cases = {
        str(item.get("query_id")): item
        for item in _mapping_items(baseline.get("cases"))
        if item.get("query_id") is not None
    }
    new_failures = []
    recovered = []
    rank_worsened = []
    for query_id in sorted(set(current_cases) & set(baseline_cases)):
        now = current_cases[query_id]
        before = baseline_cases[query_id]
        now_failed = bool(now.get("http_error")) or not bool(now.get("hit_at_k"))
        before_failed = bool(before.get("http_error")) or not bool(before.get("hit_at_k"))
        if now_failed and not before_failed:
            new_failures.append(query_id)
        if before_failed and not now_failed:
            recovered.append(query_id)
        now_rank = now.get("first_relevant_rank")
        before_rank = before.get("first_relevant_rank")
        if (
            isinstance(now_rank, int)
            and isinstance(before_rank, int)
            and now_rank > before_rank
        ):
            rank_worsened.append(
                {"query_id": query_id, "before": before_rank, "current": now_rank}
            )
    current_summary = current.get("summary") if isinstance(current.get("summary"), Mapping) else {}
    baseline_summary = baseline.get("summary") if isinstance(baseline.get("summary"), Mapping) else {}
    metric_deltas = {}
    for metric in ("hit_at_k", "recall_at_k", "mrr", "ndcg_at_k"):
        now = current_summary.get(metric)
        before = baseline_summary.get(metric)
        if isinstance(now, (int, float)) and isinstance(before, (int, float)):
            metric_deltas[metric] = float(now) - float(before)
    negative_metric_deltas = {
        metric: delta
        for metric, delta in metric_deltas.items()
        if delta < -1e-9
    }
    return {
        "baseline_query_count": len(baseline_cases),
        "current_query_count": len(current_cases),
        "added_query_ids": sorted(set(current_cases) - set(baseline_cases)),
        "removed_query_ids": sorted(set(baseline_cases) - set(current_cases)),
        "new_failure_query_ids": new_failures,
        "recovered_query_ids": recovered,
        "rank_worsened": rank_worsened,
        "metric_deltas": metric_deltas,
        "negative_metric_deltas": negative_metric_deltas,
        "has_regression": bool(
            new_failures or rank_worsened or negative_metric_deltas
        ),
    }


def _post_json(
    url: str,
    body: Mapping[str, Any],
    *,
    timeout: float,
    bearer_token: str | None,
) -> Mapping[str, Any]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {detail[:500]}") from error
    if not isinstance(payload, Mapping):
        raise ValueError("검색 API 응답은 JSON 객체여야 합니다.")
    return payload


def _extract_results(response: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw: object = response.get("results")
    if raw is None and isinstance(response.get("data"), Mapping):
        raw = response["data"].get("results")
    if not isinstance(raw, list):
        raise ValueError("검색 API 응답에 results 배열이 없습니다.")
    invalid = [index for index, item in enumerate(raw) if not isinstance(item, Mapping)]
    if invalid:
        raise ValueError(f"results에 객체가 아닌 항목이 있습니다: {invalid}")
    return list(raw)


def _extract_filters(response: Mapping[str, Any]) -> dict[str, tuple[str, ...]] | None:
    candidates: list[object] = [
        response.get("applied_filters"),
        response.get("filters"),
    ]
    data = response.get("data")
    if isinstance(data, Mapping):
        candidates.extend([data.get("applied_filters"), data.get("filters")])
    parsed = response.get("parsed_query")
    if isinstance(parsed, Mapping):
        candidates.extend([parsed.get("applied_filters"), parsed.get("filters")])
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return _normalize_filter_mapping(candidate)
    return None


def _normalize_filter_mapping(value: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, tuple[str, ...]] = {}
    for field, raw in value.items():
        values = _string_list(raw)
        if values:
            result[str(field)] = tuple(sorted(item.casefold() for item in values))
    return result


def _result_source_id(item: Mapping[str, Any]) -> str:
    value = item.get("source_segment_id")
    return str(value).strip() if value is not None else ""


def _result_schema_issues(results: Sequence[Mapping[str, Any]]) -> list[str]:
    required = (
        "source_segment_id",
        "segment_id",
        "place_id",
        "place_name",
        "region",
        "city",
        "start_time",
        "end_time",
        "keyframe_path",
        "final_score",
    )
    issues: list[str] = []
    for index, result in enumerate(results):
        for field in required:
            if field not in result:
                issues.append(f"results[{index}].{field} 누락")
        if result.get("keyframe_id") not in (None, result.get("segment_id")):
            issues.append(f"results[{index}].keyframe_id != segment_id")
    return issues


def _ndcg(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, value in enumerate(retrieved[:k], 1)
        if value in relevant
    )
    ideal_hits = min(len(relevant), k)
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / ideal if ideal else 0.0


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        raise ValueError("values가 비어 있습니다.")
    index = max(0, math.ceil(len(values) * fraction) - 1)
    return values[index]


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}은 빈 문자열이 아니어야 합니다.")
    return value.strip()


def _mapping_items(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]
