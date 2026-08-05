"""백엔드 전달용 검색 요청·응답 계약의 최소 검증기."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


SUPPORTED_LANGUAGES = frozenset({"auto", "ko", "en", "ja", "zh"})
QUERY_STATUSES = frozenset({"matched", "not_found", "ambiguous", "none"})
OPTIONAL_REQUEST_FILTERS = ("region", "season", "time_of_day")
REQUIRED_RESULT_FIELDS = (
    "rank",
    "segment_id",
    "video_id",
    "place_id",
    "drama_title",
    "place_name",
    "region",
    "start_time",
    "end_time",
    "description",
    "mood",
    "activity",
    "scene_elements",
    "keyframe_id",
    "keyframe_path",
    "text_score",
    "image_score",
    "final_score",
)


def validate_search_request(payload: object) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("검색 요청은 JSON 객체여야 합니다.")
    query = _nonempty_text(payload.get("query"), "query")
    language = _nonempty_text(payload.get("lang", "auto"), "lang")
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("lang은 auto/ko/en/ja/zh 중 하나여야 합니다.")
    top_k = payload.get("top_k", 5)
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 50:
        raise ValueError("top_k는 1~50 사이의 정수여야 합니다.")

    result: dict[str, Any] = {"query": query, "lang": language, "top_k": top_k}
    for field_name in OPTIONAL_REQUEST_FILTERS:
        value = payload.get(field_name)
        if value is not None:
            result[field_name] = _nonempty_text(value, field_name)
    result["mood"] = _string_list(payload.get("mood", []), "mood")
    return result


def validate_search_response(payload: object) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("검색 응답은 JSON 객체여야 합니다.")
    _nonempty_text(payload.get("query"), "query")
    _nonempty_text(payload.get("lang"), "lang")
    query_status = _nonempty_text(payload.get("query_status", "none"), "query_status")
    if query_status not in QUERY_STATUSES:
        raise ValueError("query_status는 matched/not_found/ambiguous/none 중 하나여야 합니다.")
    matched_titles = _string_list(
        payload.get("matched_drama_titles", []),
        "matched_drama_titles",
    )
    possible_title = payload.get("possible_title")
    if possible_title is not None:
        possible_title = _nonempty_text(possible_title, "possible_title")
    raw_results = payload.get("results")
    if isinstance(raw_results, (str, bytes)) or not isinstance(raw_results, Sequence):
        raise ValueError("results는 검색 결과 배열이어야 합니다.")
    if query_status == "not_found" and raw_results:
        raise ValueError("미등록 작품 검색은 results가 비어 있어야 합니다.")

    seen_segments: set[str] = set()
    validated_results: list[dict[str, Any]] = []
    for index, item in enumerate(raw_results):
        if not isinstance(item, Mapping):
            raise ValueError(f"results[{index}]는 객체여야 합니다.")
        missing = sorted(field for field in REQUIRED_RESULT_FIELDS if field not in item)
        if missing:
            raise ValueError(f"results[{index}] 필수 항목 누락: {', '.join(missing)}")
        rank = item["rank"]
        if rank != index + 1:
            raise ValueError("rank는 1부터 결과 순서대로 증가해야 합니다.")
        segment_id = _nonempty_text(item["segment_id"], f"results[{index}].segment_id")
        if segment_id in seen_segments:
            raise ValueError(f"segment_id가 중복 노출됐습니다: {segment_id}")
        seen_segments.add(segment_id)

        for field_name in ("start_time", "end_time", "text_score", "image_score", "final_score"):
            _finite_number(item[field_name], f"results[{index}].{field_name}")
        if float(item["start_time"]) >= float(item["end_time"]):
            raise ValueError(f"results[{index}]의 종료 시간은 시작 시간보다 커야 합니다.")
        for field_name in ("mood", "activity", "scene_elements"):
            _string_list(item[field_name], f"results[{index}].{field_name}")

        latitude = item.get("latitude")
        longitude = item.get("longitude")
        if (latitude is None) != (longitude is None):
            raise ValueError("latitude와 longitude는 둘 다 있거나 둘 다 없어야 합니다.")
        if latitude is not None:
            lat = _finite_number(latitude, f"results[{index}].latitude")
            lon = _finite_number(longitude, f"results[{index}].longitude")
            if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("위도·경도 범위를 확인하세요.")
        validated_results.append(dict(item))
    return {
        **dict(payload),
        "query_status": query_status,
        "matched_drama_titles": matched_titles,
        "possible_title": possible_title,
        "results": validated_results,
    }


def _nonempty_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}은 빈 문자열이 아니어야 합니다.")
    return value.strip()


def _string_list(value: object, field_name: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name}은 문자열 배열이어야 합니다.")
    result: list[str] = []
    for item in value:
        result.append(_nonempty_text(item, field_name))
    return result


def _finite_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name}은 숫자여야 합니다.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name}은 유한한 숫자여야 합니다.")
    return result
