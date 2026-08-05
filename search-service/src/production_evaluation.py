"""변경 가능한 place_id 대신 keyframe 경로로 평가 정답을 연결한다."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .project_data_validation import extract_metadata_records


SUPPORTED_LANGUAGES = frozenset({"ko", "en", "ja", "zh"})


def load_anchor_cases(path: str | Path) -> list[dict[str, Any]]:
    """실데이터 평가 초안을 읽고 ID 독립 정답 앵커를 검증한다."""

    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, Mapping):
        raise ValueError("평가 JSON 최상위 값은 객체여야 합니다.")
    raw_cases = payload.get("queries")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("queries는 하나 이상의 평가 질문 목록이어야 합니다.")

    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_cases):
        if not isinstance(raw, Mapping):
            raise ValueError(f"queries[{index}]는 객체여야 합니다.")
        required = {
            "query_id",
            "language",
            "query",
            "relevant_keyframe_paths",
            "expected_filters",
        }
        missing = sorted(required - set(raw))
        if missing:
            raise ValueError(f"queries[{index}] 필수 항목 누락: {', '.join(missing)}")

        query_id = _nonempty_text(raw["query_id"], f"queries[{index}].query_id")
        if query_id in seen_ids:
            raise ValueError(f"query_id가 중복되었습니다: {query_id}")
        seen_ids.add(query_id)
        language = _nonempty_text(raw["language"], f"{query_id}.language")
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"{query_id}.language은 ko/en/ja/zh 중 하나여야 합니다.")
        _nonempty_text(raw["query"], f"{query_id}.query")
        _string_list(raw["relevant_keyframe_paths"], f"{query_id}.relevant_keyframe_paths")
        if not isinstance(raw["expected_filters"], Mapping):
            raise ValueError(f"{query_id}.expected_filters는 객체여야 합니다.")
        if not isinstance(raw.get("expected_soft_hints", {}), Mapping):
            raise ValueError(f"{query_id}.expected_soft_hints는 객체여야 합니다.")
        cases.append(dict(raw))
    return cases


def summarize_anchor_cases(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """질문 수와 언어 분포, 권장 30~50개 충족 여부를 반환한다."""

    by_language = {
        language: sum(str(case.get("language")) == language for case in cases)
        for language in sorted(SUPPORTED_LANGUAGES)
    }
    return {
        "query_count": len(cases),
        "recommended_size_met": 30 <= len(cases) <= 50,
        "by_language": by_language,
    }


def resolve_anchor_cases(
    cases: Sequence[Mapping[str, Any]],
    metadata_payload: object,
) -> dict[str, Any]:
    """keyframe 정답을 현재 메타데이터의 segment_id로 변환한다."""

    records = extract_metadata_records(metadata_payload)
    by_keyframe: dict[str, Mapping[str, Any]] = {}
    for record in records:
        keyframe_path = _normalize_path(record.get("keyframe_path"))
        if not keyframe_path:
            continue
        if keyframe_path in by_keyframe:
            raise ValueError(f"메타데이터 keyframe_path가 중복되었습니다: {keyframe_path}")
        by_keyframe[keyframe_path] = record

    resolved_queries: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for case in cases:
        query_id = str(case["query_id"])
        missing_paths: list[str] = []
        relevant_ids: list[str] = []
        matched_video_ids: list[str] = []
        for raw_path in case["relevant_keyframe_paths"]:
            path = _normalize_path(raw_path)
            record = by_keyframe.get(path)
            if record is None:
                missing_paths.append(str(raw_path))
                continue
            segment_id = _nonempty_text(
                record.get("segment_id"),
                f"metadata[{path}].segment_id",
            )
            video_id = _nonempty_text(
                record.get("video_id"),
                f"metadata[{path}].video_id",
            )
            if segment_id not in relevant_ids:
                relevant_ids.append(segment_id)
            if video_id not in matched_video_ids:
                matched_video_ids.append(video_id)

        if missing_paths:
            unresolved.append(
                {
                    "query_id": query_id,
                    "missing_keyframe_paths": missing_paths,
                }
            )
            continue

        expected_video_ids = [
            str(value) for value in case.get("relevant_video_ids", [])
        ]
        if expected_video_ids and set(expected_video_ids) != set(matched_video_ids):
            unresolved.append(
                {
                    "query_id": query_id,
                    "video_id_mismatch": {
                        "expected": expected_video_ids,
                        "actual": matched_video_ids,
                    },
                }
            )
            continue

        resolved_queries.append(
            {
                "query_id": query_id,
                "language": case["language"],
                "query": case["query"],
                "relevant_segment_ids": relevant_ids,
                "expected_filters": dict(case.get("expected_filters", {})),
                "expected_soft_hints": dict(case.get("expected_soft_hints", {})),
                "case_type": case.get("case_type", "production_draft"),
                "rationale": case.get("rationale", ""),
                "source_anchors": {
                    "keyframe_paths": list(case["relevant_keyframe_paths"]),
                    "video_ids": matched_video_ids,
                },
            }
        )

    return {
        "schema_version": "1.0",
        "result_unit": "segment",
        "ground_truth_status": "draft_needs_human_review",
        "resolution": {
            "total_queries": len(cases),
            "resolved_queries": len(resolved_queries),
            "unresolved_queries": len(unresolved),
            "unresolved": unresolved,
        },
        "queries": resolved_queries,
    }


def _nonempty_text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}는 빈 문자열이 아니어야 합니다.")
    return value.strip()


def _string_list(value: object, context: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise ValueError(f"{context}는 하나 이상의 문자열 목록이어야 합니다.")
    result: list[str] = []
    for item in value:
        result.append(_nonempty_text(item, context))
    return result


def _normalize_path(value: object) -> str:
    return str(value or "").strip().replace("\\", "/").casefold()
