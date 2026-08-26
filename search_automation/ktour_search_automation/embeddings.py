"""전달받은 text/image embedding과 metadata의 정합성을 읽기 전용 검증한다."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


def validate_embedding_alignment(
    metadata_records: Sequence[Mapping[str, Any]],
    text_payload: object | None,
    image_payload: object | None,
    *,
    expected_dimension: int | None = None,
    expected_model: str | None = None,
    norm_tolerance: float | None = None,
    keyframe_id_rule: str = "segment_id",
) -> dict[str, Any]:
    """embedding 파일을 바꾸지 않고 ID·벡터·metadata 연결을 검사한다."""

    metadata_by_id = {
        str(row.get("segment_id") or "").strip(): row
        for row in metadata_records
        if str(row.get("segment_id") or "").strip()
    }
    text_records = _embedding_records(text_payload, "text embedding")
    image_records = _embedding_records(image_payload, "image embedding")

    text_report = _validate_branch(
        branch="text",
        records=text_records,
        metadata_by_id=metadata_by_id,
        vector_field="text_embedding",
        expected_dimension=expected_dimension,
        expected_model=expected_model,
        norm_tolerance=norm_tolerance,
        keyframe_id_rule=keyframe_id_rule,
    )
    image_report = _validate_branch(
        branch="image",
        records=image_records,
        metadata_by_id=metadata_by_id,
        vector_field="image_embedding",
        expected_dimension=expected_dimension,
        expected_model=expected_model,
        norm_tolerance=norm_tolerance,
        keyframe_id_rule=keyframe_id_rule,
    )

    cross_branch: dict[str, Any] = {
        "checked": text_records is not None and image_records is not None,
        "text_only_segment_ids": [],
        "image_only_segment_ids": [],
    }
    issues = [*text_report["issues"], *image_report["issues"]]
    if (text_records is None) != (image_records is None):
        issues.append(
            _issue(
                "error",
                "INCOMPLETE_EMBEDDING_PAIR",
                "cross",
                None,
                "text/image full embedding 파일은 함께 제공해야 합니다.",
            )
        )
    if cross_branch["checked"]:
        text_ids = set(text_report["segment_ids"])
        image_ids = set(image_report["segment_ids"])
        cross_branch["text_only_segment_ids"] = sorted(text_ids - image_ids)
        cross_branch["image_only_segment_ids"] = sorted(image_ids - text_ids)
        text_models = set(text_report["models"])
        image_models = set(image_report["models"])
        if text_models != image_models:
            issues.append(
                _issue(
                    "error",
                    "CROSS_BRANCH_MODEL_MISMATCH",
                    "cross",
                    None,
                    f"text={sorted(text_models)}, image={sorted(image_models)}",
                )
            )

    for segment_id in cross_branch["text_only_segment_ids"]:
        issues.append(
            _issue("error", "TEXT_WITHOUT_IMAGE", "text", segment_id, "image embedding이 없습니다.")
        )
    for segment_id in cross_branch["image_only_segment_ids"]:
        issues.append(
            _issue("error", "IMAGE_WITHOUT_TEXT", "image", segment_id, "text embedding이 없습니다.")
        )

    error_count = sum(item["severity"] == "error" for item in issues)
    warning_count = sum(item["severity"] == "warning" for item in issues)
    return {
        "provided": text_records is not None or image_records is not None,
        "expected_metadata_count": len(metadata_by_id),
        "expected_dimension": expected_dimension,
        "expected_model": expected_model,
        "keyframe_id_rule": keyframe_id_rule,
        "text": _public_branch_report(text_report),
        "image": _public_branch_report(image_report),
        "cross_branch": cross_branch,
        "issues": issues,
        "error_count": error_count,
        "warning_count": warning_count,
        "is_valid": error_count == 0,
    }


def _embedding_records(payload: object | None, label: str) -> list[dict[str, Any]] | None:
    if payload is None:
        return None
    raw = payload
    if isinstance(payload, Mapping):
        for key in ("records", "embeddings", "segments", "keyframes"):
            if key in payload:
                raw = payload[key]
                break
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise ValueError(f"{label} JSON은 객체 배열이어야 합니다.")
    invalid = [index for index, item in enumerate(raw) if not isinstance(item, Mapping)]
    if invalid:
        raise ValueError(f"{label}에 객체가 아닌 항목이 있습니다: {invalid}")
    return [dict(item) for item in raw]


def _validate_branch(
    *,
    branch: str,
    records: list[dict[str, Any]] | None,
    metadata_by_id: Mapping[str, Mapping[str, Any]],
    vector_field: str,
    expected_dimension: int | None,
    expected_model: str | None,
    norm_tolerance: float | None,
    keyframe_id_rule: str,
) -> dict[str, Any]:
    if records is None:
        return {
            "provided": False,
            "record_count": 0,
            "segment_ids": [],
            "dimensions": [],
            "models": [],
            "issues": [],
        }

    issues: list[dict[str, Any]] = []
    seen: set[str] = set()
    segment_ids: list[str] = []
    dimensions: set[int] = set()
    models: set[str] = set()
    keyframe_ids: set[str] = set()
    keyframe_paths: set[str] = set()
    vector_owners: dict[tuple[float, ...], list[str]] = {}
    metadata_ids = set(metadata_by_id)

    for index, row in enumerate(records):
        segment_id = str(row.get("segment_id") or "").strip()
        if not segment_id:
            issues.append(_issue("error", "MISSING_SEGMENT_ID", branch, None, f"records[{index}]"))
            continue
        segment_ids.append(segment_id)
        if segment_id in seen:
            issues.append(_issue("error", "DUPLICATE_SEGMENT_ID", branch, segment_id, "동일 ID가 두 번 있습니다."))
        seen.add(segment_id)

        metadata = metadata_by_id.get(segment_id)
        if metadata is None:
            issues.append(_issue("error", "UNKNOWN_SEGMENT_ID", branch, segment_id, "metadata에 없는 ID입니다."))
        else:
            _compare_metadata_fields(branch, segment_id, row, metadata, issues)

        if branch == "image" and keyframe_id_rule == "segment_id":
            keyframe_id = str(row.get("keyframe_id") or "").strip()
            if keyframe_id != segment_id:
                issues.append(
                    _issue(
                        "error",
                        "KEYFRAME_ID_RULE_MISMATCH",
                        branch,
                        segment_id,
                        f"keyframe_id={keyframe_id!r}",
                    )
                )
            normalized_path = _normalize_path(row.get("keyframe_path"))
            if keyframe_id in keyframe_ids:
                issues.append(_issue("error", "DUPLICATE_KEYFRAME_ID", branch, segment_id, keyframe_id))
            if normalized_path in keyframe_paths:
                issues.append(_issue("error", "DUPLICATE_KEYFRAME_PATH", branch, segment_id, normalized_path))
            keyframe_ids.add(keyframe_id)
            keyframe_paths.add(normalized_path)

        vector = row.get(vector_field)
        if isinstance(vector, (str, bytes)) or not isinstance(vector, Sequence):
            issues.append(_issue("error", "MISSING_VECTOR", branch, segment_id, vector_field))
            continue
        dimensions.add(len(vector))
        if expected_dimension is not None and len(vector) != expected_dimension:
            issues.append(
                _issue(
                    "error",
                    "VECTOR_DIMENSION_MISMATCH",
                    branch,
                    segment_id,
                    f"{len(vector)} != {expected_dimension}",
                )
            )
        invalid_number = False
        squared_norm = 0.0
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                invalid_number = True
                break
            number = float(value)
            if not math.isfinite(number):
                invalid_number = True
                break
            squared_norm += number * number
        if invalid_number:
            issues.append(_issue("error", "NON_FINITE_VECTOR", branch, segment_id, "숫자가 아니거나 NaN/Inf가 있습니다."))
        elif squared_norm == 0.0:
            issues.append(_issue("error", "ZERO_VECTOR", branch, segment_id, "모든 벡터 값이 0입니다."))
        else:
            numeric_vector = tuple(float(value) for value in vector)
            vector_owners.setdefault(numeric_vector, []).append(segment_id)
            if norm_tolerance is not None:
                norm = math.sqrt(squared_norm)
                if abs(norm - 1.0) > norm_tolerance:
                    issues.append(
                        _issue(
                            "warning",
                            "VECTOR_NOT_UNIT_NORMALIZED",
                            branch,
                            segment_id,
                            f"L2 norm={norm:.8f}",
                        )
                    )

        model = str(row.get("embedding_model") or "").strip()
        if model:
            models.add(model)
            if expected_model and model != expected_model:
                issues.append(
                    _issue(
                        "error",
                        "UNEXPECTED_EMBEDDING_MODEL",
                        branch,
                        segment_id,
                        f"{model!r} != {expected_model!r}",
                    )
                )
        else:
            issues.append(_issue("warning", "MISSING_EMBEDDING_MODEL", branch, segment_id, "모델명이 없습니다."))

        if branch == "text" and not str(row.get("search_text") or "").strip():
            issues.append(_issue("error", "EMPTY_SEARCH_TEXT", branch, segment_id, "search_text가 비어 있습니다."))

    missing_ids = sorted(metadata_ids - seen)
    for segment_id in missing_ids:
        issues.append(_issue("error", "MISSING_EMBEDDING", branch, segment_id, "metadata에는 있으나 embedding이 없습니다."))
    if len(models) > 1:
        issues.append(_issue("error", "MIXED_EMBEDDING_MODELS", branch, None, ", ".join(sorted(models))))
    if len(dimensions) > 1:
        issues.append(_issue("error", "MIXED_VECTOR_DIMENSIONS", branch, None, str(sorted(dimensions))))

    duplicate_vector_groups = [
        sorted(owners)
        for owners in vector_owners.values()
        if len(owners) > 1
    ]
    for owners in duplicate_vector_groups:
        issues.append(
            _issue(
                "warning",
                "EXACT_DUPLICATE_VECTOR",
                branch,
                None,
                ", ".join(owners),
            )
        )

    return {
        "provided": True,
        "record_count": len(records),
        "segment_ids": segment_ids,
        "dimensions": sorted(dimensions),
        "models": sorted(models),
        "missing_segment_ids": missing_ids,
        "extra_segment_ids": sorted(seen - metadata_ids),
        "duplicate_vector_groups": duplicate_vector_groups,
        "issues": issues,
    }


def _compare_metadata_fields(
    branch: str,
    segment_id: str,
    embedding: Mapping[str, Any],
    metadata: Mapping[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    critical_fields = ["source_segment_id", "place_id"]
    if branch == "image":
        critical_fields.append("keyframe_path")
    for field in critical_fields:
        expected = str(metadata.get(field) or "").strip()
        actual = str(embedding.get(field) or "").strip()
        if field == "keyframe_path":
            expected = _normalize_path(expected)
            actual = _normalize_path(actual)
        if expected != actual:
            issues.append(
                _issue(
                    "error",
                    "METADATA_FIELD_MISMATCH",
                    branch,
                    segment_id,
                    f"{field}: {actual!r} != {expected!r}",
                )
            )

    copied_fields = (
        "video_id",
        "place_name",
        "region",
        "city",
        "drama_title",
        "season",
        "time_of_day",
        "description",
        "mood",
        "activity",
        "scene_elements",
        "k_culture_elements",
        "theme_category",
        "start_time",
        "end_time",
    )
    for field in copied_fields:
        expected = metadata.get(field)
        actual = embedding.get(field)
        if expected == actual:
            continue
        severity = "error" if branch == "text" else "warning"
        issues.append(
            _issue(
                severity,
                "COPIED_METADATA_MISMATCH",
                branch,
                segment_id,
                f"{field}: embedding={actual!r}, metadata={expected!r}",
            )
        )


def _issue(
    severity: str,
    code: str,
    branch: str,
    segment_id: str | None,
    message: str,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "branch": branch,
        "segment_id": segment_id,
        "message": message,
    }


def _public_branch_report(report: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in report.items() if key not in {"segment_ids", "issues"}}


def _normalize_path(value: object) -> str:
    return str(value or "").strip().replace("\\", "/").casefold()
