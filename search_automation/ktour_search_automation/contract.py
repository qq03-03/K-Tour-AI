"""배포된 검색 API의 필터·RRF·응답 계약을 고정 사례로 검사한다."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from typing import Any

from .regression import _extract_filters, _extract_results, _post_json


REQUIRED_RESULT_FIELDS = (
    "rank",
    "source_segment_id",
    "segment_id",
    "keyframe_id",
    "keyframe_path",
    "video_id",
    "place_id",
    "place_name",
    "region",
    "city",
    "latitude",
    "longitude",
    "drama_title",
    "start_time",
    "end_time",
    "season",
    "time_of_day",
    "description",
    "mood",
    "activity",
    "scene_elements",
    "k_culture_elements",
    "text_score",
    "image_score",
    "text_rank",
    "image_rank",
    "final_score",
)


def evaluate_backend_contract(
    *,
    base_url: str,
    cases: Sequence[Mapping[str, Any]],
    endpoint: str = "/api/search",
    timeout: float = 30.0,
    bearer_token: str | None = None,
    rrf_k: float = 60.0,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/" + endpoint.strip("/")
    case_reports = []
    for case in cases:
        request_body = dict(_mapping(case.get("request"), "request"))
        started = time.perf_counter()
        try:
            response = _post_json(
                url,
                request_body,
                timeout=timeout,
                bearer_token=bearer_token,
            )
            results = _extract_results(response)
            failures = evaluate_contract_response(
                request_body,
                _mapping(case.get("expected"), "expected"),
                response,
                results,
                rrf_k=rrf_k,
            )
            http_error = None
        except Exception as error:
            results = []
            failures = [f"HTTP/응답 오류: {type(error).__name__}: {error}"]
            http_error = f"{type(error).__name__}: {error}"
        case_reports.append(
            {
                "case_id": case.get("case_id"),
                "label": case.get("label"),
                "request": request_body,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "result_count": len(results),
                "http_error": http_error,
                "failures": failures,
                "passed": not failures,
            }
        )
    failed = sum(not item["passed"] for item in case_reports)
    return {
        "schema_version": "1.0",
        "suite": "backend_search_contract",
        "base_url": base_url,
        "endpoint": endpoint,
        "summary": {
            "case_count": len(case_reports),
            "passed_case_count": len(case_reports) - failed,
            "failed_case_count": failed,
            "passed": failed == 0,
        },
        "cases": case_reports,
    }


def evaluate_contract_response(
    request_body: Mapping[str, Any],
    expected: Mapping[str, Any],
    response: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
    *,
    rrf_k: float = 60.0,
) -> list[str]:
    failures: list[str] = []
    top_k = int(request_body.get("top_k", 5))
    if len(results) > top_k:
        failures.append(f"결과 수 {len(results)}가 top_k={top_k}를 초과")

    count_rule = expected.get("result_count")
    if isinstance(count_rule, Mapping):
        if "exact" in count_rule and len(results) != int(count_rule["exact"]):
            failures.append(f"결과 수 {len(results)} != {count_rule['exact']}")
        if "min" in count_rule and len(results) < int(count_rule["min"]):
            failures.append(f"결과 수 {len(results)} < {count_rule['min']}")
        if "max" in count_rule and len(results) > int(count_rule["max"]):
            failures.append(f"결과 수 {len(results)} > {count_rule['max']}")

    expected_filters = expected.get("applied_filters")
    if isinstance(expected_filters, Mapping):
        actual_filters = _extract_filters(response)
        if actual_filters is None:
            failures.append("applied_filters가 응답에 없음")
        else:
            for field, values in expected_filters.items():
                wanted = {_normalized(item) for item in _values(values)}
                actual = set(actual_filters.get(str(field), ()))
                if actual != wanted:
                    failures.append(
                        f"applied_filters.{field}={sorted(actual)} != {sorted(wanted)}"
                    )

    required_filter_fields = _values(expected.get("require_applied_filter_fields"))
    if required_filter_fields:
        actual_filters = _extract_filters(response)
        for field in required_filter_fields:
            if actual_filters is None or field not in actual_filters:
                failures.append(f"applied_filters.{field}가 응답에 없음")

    forbidden_filter_fields = _values(expected.get("forbidden_filter_fields"))
    if forbidden_filter_fields:
        actual_filters = _extract_filters(response) or {}
        for field in forbidden_filter_fields:
            if actual_filters.get(field):
                failures.append(f"금지된 필터 {field}가 적용됨: {actual_filters[field]}")

    all_results = expected.get("all_results")
    if isinstance(all_results, Mapping):
        for index, result in enumerate(results):
            for field, values in all_results.items():
                allowed = {_normalized(item) for item in _values(values)}
                actual = _normalized(result.get(field))
                if actual not in allowed:
                    failures.append(
                        f"results[{index}].{field}={result.get(field)!r}가 허용값이 아님"
                    )

    contains_sources = set(_values(expected.get("contains_source_segment_ids")))
    if contains_sources:
        retrieved = {str(item.get("source_segment_id") or "") for item in results}
        missing = sorted(contains_sources - retrieved)
        if missing:
            failures.append(f"필수 source_segment_id 미포함: {missing}")

    allowed_sources = set(_values(expected.get("all_source_segment_ids_in")))
    if allowed_sources:
        unexpected = sorted(
            {
                str(item.get("source_segment_id") or "")
                for item in results
                if str(item.get("source_segment_id") or "") not in allowed_sources
            }
        )
        if unexpected:
            failures.append(f"허용 테마 밖 source_segment_id 반환: {unexpected}")

    minimum_distinct = expected.get("minimum_distinct_result_values")
    if isinstance(minimum_distinct, Mapping):
        for field, minimum in minimum_distinct.items():
            values = {
                _normalized(item.get(field))
                for item in results
                if _normalized(item.get(field))
            }
            if len(values) < int(minimum):
                failures.append(
                    f"results의 {field} 고유값 {len(values)}개 < {minimum}개"
                )

    if expected.get("unique_source_segment_id", True):
        source_ids = [str(item.get("source_segment_id") or "") for item in results]
        if "" in source_ids:
            failures.append("source_segment_id가 빈 결과가 있음")
        duplicate = sorted({value for value in source_ids if source_ids.count(value) > 1})
        if duplicate:
            failures.append(f"source_segment_id 중복: {duplicate}")

    if expected.get("no_filter_relaxation") and _fallback_used(response):
        failures.append("명시 필터가 완화되거나 fallback이 사용됨")

    if expected.get("strict_result_contract"):
        failures.extend(_strict_result_contract(results, rrf_k=rrf_k))
    return failures


def _strict_result_contract(
    results: Sequence[Mapping[str, Any]], *, rrf_k: float
) -> list[str]:
    failures: list[str] = []
    previous_score = float("inf")
    previous_result: Mapping[str, Any] | None = None
    for index, result in enumerate(results):
        for field in REQUIRED_RESULT_FIELDS:
            if field not in result:
                failures.append(f"results[{index}].{field} 누락")
        if result.get("keyframe_id") != result.get("segment_id"):
            failures.append(f"results[{index}].keyframe_id != segment_id")
        if result.get("rank") != index + 1:
            failures.append(f"results[{index}].rank가 1-based 연속 순위가 아님")

        final_score = result.get("final_score")
        if not _finite_number(final_score):
            failures.append(f"results[{index}].final_score가 유한 숫자가 아님")
            continue
        final_number = float(final_score)
        if final_number > previous_score + 1e-12:
            failures.append("final_score 내림차순 정렬이 아님")
        previous_score = final_number

        expected_rrf = 0.0
        for branch in ("text", "image"):
            score = result.get(f"{branch}_score")
            rank = result.get(f"{branch}_rank")
            if (score is None) != (rank is None):
                failures.append(f"results[{index}].{branch}_score/rank null 쌍 불일치")
            if rank is not None:
                if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
                    failures.append(f"results[{index}].{branch}_rank가 1-based 정수가 아님")
                else:
                    expected_rrf += 1.0 / (rrf_k + rank)
            if score is not None and not _finite_number(score):
                failures.append(f"results[{index}].{branch}_score가 유한 숫자가 아님")
        if abs(final_number - expected_rrf) > 1e-8:
            failures.append(
                f"results[{index}].final_score RRF 불일치: {final_number} != {expected_rrf}"
            )
        if previous_result is not None:
            previous_final = previous_result.get("final_score")
            if _finite_number(previous_final) and abs(
                float(previous_final) - final_number
            ) <= 1e-12:
                if _tie_break_key(previous_result) > _tie_break_key(result):
                    failures.append(
                        f"results[{index - 1}:{index + 1}] RRF 동점 정렬 규칙 불일치"
                    )
        previous_result = result
    return failures


def _fallback_used(response: Mapping[str, Any]) -> bool:
    containers = [response]
    for key in ("data", "meta", "parsed_query"):
        value = response.get(key)
        if isinstance(value, Mapping):
            containers.append(value)
    keys = (
        "fallback_used",
        "filter_fallback_used",
        "filters_relaxed",
        "filter_relaxed",
    )
    return any(bool(container.get(key)) for container in containers for key in keys)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"contract case의 {label}는 객체여야 합니다.")
    return value


def _values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(item) for item in value]
    return []


def _normalized(value: object) -> str:
    return str(value or "").strip().casefold()


def _finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _tie_break_key(result: Mapping[str, Any]) -> tuple[float, float, str]:
    image = result.get("image_score")
    text = result.get("text_score")
    image_number = float(image) if _finite_number(image) else float("-inf")
    text_number = float(text) if _finite_number(text) else float("-inf")
    segment_id = str(result.get("segment_id") or "")
    return (-image_number, -text_number, segment_id)
