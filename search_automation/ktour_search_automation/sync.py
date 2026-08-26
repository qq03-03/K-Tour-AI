"""신규 검색 데이터의 카탈로그·테마·평가 자산을 증분 준비한다.

이 모듈은 원본 metadata, embedding, DB를 수정하지 않는다. 모든 결과는
호출자가 지정한 별도 출력 폴더에만 기록한다.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .embeddings import validate_embedding_alignment
from .coordinates import validate_coordinate_alignment
from .display_addresses import build_display_address_catalog


LANGUAGES = ("ko", "en", "ja", "zh")
REQUIRED_TEXT_FIELDS = (
    "segment_id",
    "source_segment_id",
    "video_id",
    "place_id",
    "place_name",
    "region",
    "season",
    "time_of_day",
    "keyframe_path",
    "description",
)
ARRAY_FIELDS = ("mood", "activity", "scene_elements")
OPTIONAL_ARRAY_FIELDS = ("k_culture_elements", "theme_category")
SEARCH_RELEVANT_FIELDS = (
    "source_segment_id",
    "video_id",
    "place_id",
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
    "keyframe_path",
    "start_time",
    "end_time",
)
TEXT_EMBEDDING_SOURCE_FIELDS = (
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
)
THEME_EVIDENCE_FIELDS = (
    "place_name",
    "season",
    "time_of_day",
    "description",
    "mood",
    "activity",
    "scene_elements",
    "k_culture_elements",
    "theme_category",
)
DISPLAY_TRANSLATION_SOURCE_FIELDS = (
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
)
IDENTITY_FIELDS = (
    "source_segment_id",
    "video_id",
    "place_id",
    "keyframe_path",
)
ORIGIN_PRIORITY = {"translation": 1, "existing": 2, "canonical": 3}


def load_json(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def extract_metadata_records(payload: object) -> list[dict[str, Any]]:
    raw: object = payload
    if isinstance(payload, Mapping):
        for key in ("records", "segments"):
            if key in payload:
                raw = payload[key]
                break
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence) or not raw:
        raise ValueError("metadata는 하나 이상의 SCENE 객체 배열이어야 합니다.")
    records: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"metadata[{index}]는 객체여야 합니다.")
        records.append(dict(item))
    return records


def prepare_search_assets(
    *,
    metadata_path: str | Path,
    policy_path: str | Path,
    baseline_metadata_path: str | Path | None = None,
    translations_path: str | Path | None = None,
    existing_title_catalog_path: str | Path | None = None,
    existing_location_catalog_path: str | Path | None = None,
    theme_mapping_path: str | Path | None = None,
    theme_decisions_path: str | Path | None = None,
    theme_rules_path: str | Path | None = None,
    evaluation_path: str | Path | None = None,
    text_embeddings_path: str | Path | None = None,
    image_embeddings_path: str | Path | None = None,
    coordinates_path: str | Path | None = None,
) -> dict[str, Any]:
    """검색 담당 신규 데이터 준비 결과를 메모리에서 생성한다."""

    metadata_path = Path(metadata_path)
    policy_path = Path(policy_path)
    records = extract_metadata_records(load_json(metadata_path))
    policy = _required_mapping(load_json(policy_path), "policy")
    baseline_records = (
        extract_metadata_records(load_json(baseline_metadata_path))
        if baseline_metadata_path
        else []
    )
    translations = _load_translation_records(translations_path)
    existing_titles = _optional_mapping(existing_title_catalog_path)
    existing_locations = _optional_mapping(existing_location_catalog_path)
    theme_mapping = _optional_mapping(theme_mapping_path)
    theme_decisions = _optional_mapping(theme_decisions_path)
    theme_rules = _optional_mapping(theme_rules_path)
    evaluation = _optional_mapping(evaluation_path)
    text_embeddings = (
        load_json(text_embeddings_path) if text_embeddings_path else None
    )
    image_embeddings = (
        load_json(image_embeddings_path) if image_embeddings_path else None
    )
    coordinates = load_json(coordinates_path) if coordinates_path else None
    input_manifest = {
        "schema_version": "1.0",
        "files": {
            "metadata": _file_manifest(metadata_path),
            "baseline_metadata": _file_manifest(baseline_metadata_path),
            "translations": _file_manifest(translations_path),
            "existing_title_catalog": _file_manifest(
                existing_title_catalog_path
            ),
            "existing_location_catalog": _file_manifest(
                existing_location_catalog_path
            ),
            "theme_mapping": _file_manifest(theme_mapping_path),
            "theme_decisions": _file_manifest(theme_decisions_path),
            "theme_rules": _file_manifest(theme_rules_path),
            "evaluation": _file_manifest(evaluation_path),
            "text_embeddings": _file_manifest(text_embeddings_path),
            "image_embeddings": _file_manifest(image_embeddings_path),
            "coordinates": _file_manifest(coordinates_path),
            "policy": _file_manifest(policy_path),
        },
    }

    validation = validate_search_metadata(records, policy)
    baseline_validation = (
        validate_search_metadata(baseline_records, policy)
        if baseline_records
        else None
    )
    diff = compare_metadata(records, baseline_records)
    change_impact = classify_change_impact(diff)
    translation_report = validate_translation_alignment(
        records,
        translations,
        provided=translations_path is not None,
    )

    title_catalog, title_review = build_title_catalog(
        records,
        translations,
        existing_titles,
    )
    location_catalog, location_review = build_location_catalog(
        records,
        translations,
        existing_locations,
    )
    theme_result = synchronize_theme_mapping(
        records,
        theme_mapping,
        theme_decisions,
        theme_rules,
        policy,
        changed_source_ids=set(diff["theme_changed_source_segment_ids"]),
        added_source_ids=set(diff["added_source_segment_ids"]),
    )
    evaluation_report = validate_evaluation_compatibility(
        records,
        evaluation,
        policy,
        theme_mapping=theme_result["carried_mapping"],
        provided=evaluation_path is not None,
    )
    embedding_report = validate_embedding_alignment(
        records,
        text_embeddings,
        image_embeddings,
        expected_dimension=_optional_positive_int(policy.get("embedding_dimension")),
        expected_model=_text(policy.get("embedding_model")) or None,
        norm_tolerance=_optional_nonnegative_float(
            policy.get("embedding_norm_tolerance")
        ),
        keyframe_id_rule=_text(policy.get("keyframe_id_rule")) or "segment_id",
    )
    coordinate_report = validate_coordinate_alignment(records, coordinates)
    display_address_result = build_display_address_catalog(
        records,
        coordinates,
        translations,
    )
    filter_catalog = build_filter_catalog(records, theme_result, policy)
    rule_regression_cases = build_rule_regression_cases(
        title_catalog,
        location_catalog,
        filter_catalog,
    )

    blocking_issues = [
        issue for issue in validation["issues"] if issue["severity"] == "error"
    ]
    blocking_issues.extend(
        {
            "severity": "error",
            "code": "TRANSLATION_ALIGNMENT",
            "message": message,
        }
        for message in translation_report["blocking_errors"]
    )
    blocking_issues.extend(
        {
            "severity": "error",
            "code": item["code"],
            "message": f"{item.get('place_id') or '-'}: {item.get('message')}",
        }
        for item in coordinate_report["issues"]
        if item["severity"] == "error"
    )
    blocking_issues.extend(
        {
            "severity": "error",
            "code": "ID_REUSE_IDENTITY_CHANGE",
            "message": f"{segment_id}: 동일 segment_id의 연결 ID/경로가 변경됐습니다.",
        }
        for segment_id in change_impact["identity_reuse_review_segment_ids"]
    )
    blocking_issues.extend(
        {
            "severity": "error",
            "code": "SOURCE_ID_REUSE_IDENTITY_CHANGE",
            "message": (
                f"{source_id}: 동일 source_segment_id의 video_id/place_id 연결이 "
                "기준본과 달라졌습니다."
            ),
        }
        for source_id in change_impact[
            "source_identity_reuse_review_source_segment_ids"
        ]
    )
    blocking_issues.extend(
        {
            "severity": "error",
            "code": item["code"],
            "message": (
                f"{item.get('branch')}: {item.get('segment_id') or '-'}: "
                f"{item.get('message')}"
            ),
        }
        for item in embedding_report["issues"]
        if item["severity"] == "error"
    )
    blocking_issues.extend(
        {
            "severity": "error",
            "code": "EVALUATION_UNRESOLVED",
            "message": item["message"],
        }
        for item in evaluation_report["unresolved"]
    )
    blocking_issues.extend(
        {
            "severity": "error",
            "code": "DUPLICATE_THEME_MAPPING",
            "message": f"{source_id}: 테마 매핑이 중복되었습니다.",
        }
        for source_id in theme_result["summary"][
            "duplicate_mapping_source_segment_ids"
        ]
    )
    blocking_issues.extend(
        {
            "severity": "error",
            "code": "INVALID_THEME_ID",
            "message": (
                f"{item['source_segment_id']}: 허용되지 않은 theme "
                f"{item['invalid_theme_ids']}"
            ),
        }
        for item in theme_result["summary"]["invalid_theme_ids"]
    )
    blocking_issues.extend(
        {
            "severity": "error",
            "code": "DUPLICATE_THEME_DECISION",
            "message": f"{source_id}: 테마 결정 상태가 중복되었습니다.",
        }
        for source_id in theme_result["summary"][
            "duplicate_decision_source_segment_ids"
        ]
    )
    blocking_issues.extend(
        {
            "severity": "error",
            "code": "INVALID_THEME_DECISION_STATUS",
            "message": f"{item['source_segment_id']}: status={item['status']!r}",
        }
        for item in theme_result["summary"]["invalid_decision_statuses"]
    )
    review_items = {
        "metadata_warnings": [
            issue for issue in validation["issues"] if issue["severity"] == "warning"
        ],
        "title_alias_collisions": title_review["alias_collisions"],
        "location_alias_collisions": location_review["alias_collisions"],
        "translation_warnings": translation_report["warnings"],
        "translation_entity_conflicts": translation_report.get(
            "entity_variant_conflicts", []
        ),
        "display_translation_refresh_required": [
            {
                "segment_id": segment_id,
                "reason": "metadata 표시 필드가 기준본과 달라 재번역 또는 source 검증 필요",
            }
            for segment_id in change_impact[
                "display_translation_create_or_refresh_segment_ids"
            ]
        ],
        "theme_review": theme_result["review_queue"],
        "evaluation_unresolved": evaluation_report["unresolved"],
        "embedding_warnings": [
            item
            for item in embedding_report["issues"]
            if item["severity"] == "warning"
        ],
        "coordinate_warnings": [
            item
            for item in coordinate_report["issues"]
            if item["severity"] == "warning"
        ],
        "coordinate_near_duplicates": coordinate_report[
            "duplicate_or_near_candidates"
        ],
    }
    review_count = sum(len(value) for value in review_items.values())
    catalog_review_count = (
        len(title_review["alias_collisions"])
        + len(location_review["alias_collisions"])
        + len(translation_report.get("entity_variant_conflicts", []))
        + len(change_impact["display_translation_create_or_refresh_segment_ids"])
    )
    report = {
        "schema_version": "1.0",
        "purpose": "new_metadata_search_asset_sync",
        "inputs": {
            "metadata": str(metadata_path.resolve()),
            "baseline_metadata": _resolved_or_none(baseline_metadata_path),
            "translations": _resolved_or_none(translations_path),
            "existing_title_catalog": _resolved_or_none(
                existing_title_catalog_path
            ),
            "existing_location_catalog": _resolved_or_none(
                existing_location_catalog_path
            ),
            "theme_mapping": _resolved_or_none(theme_mapping_path),
            "theme_decisions": _resolved_or_none(theme_decisions_path),
            "theme_rules": _resolved_or_none(theme_rules_path),
            "evaluation": _resolved_or_none(evaluation_path),
            "text_embeddings": _resolved_or_none(text_embeddings_path),
            "image_embeddings": _resolved_or_none(image_embeddings_path),
            "policy": str(policy_path.resolve()),
        },
        "input_manifest": input_manifest,
        "summary": {
            "scene_count": len(records),
            "source_segment_count": len(
                {_text(row.get("source_segment_id")) for row in records}
            ),
            "place_count": len({_text(row.get("place_id")) for row in records}),
            "drama_title_count": len(
                {
                    _text(row.get("drama_title"))
                    for row in records
                    if _text(row.get("drama_title"))
                }
            ),
            "added_scene_count": len(diff["added_segment_ids"]),
            "changed_scene_count": len(diff["changed_segment_ids"]),
            "removed_scene_count": len(diff["removed_segment_ids"]),
            "generated_title_count": len(title_catalog["titles"]),
            "generated_place_alias_count": len(location_catalog["place_aliases"]),
            "theme_review_source_count": len(theme_result["review_queue"]),
            "evaluation_query_count": evaluation_report["query_count"],
            "translation_entity_conflict_count": len(
                translation_report.get("entity_variant_conflicts", [])
            ),
            "generated_rule_regression_case_count": len(
                rule_regression_cases["cases"]
            ),
            "text_embedding_count": embedding_report["text"]["record_count"],
            "image_embedding_count": embedding_report["image"]["record_count"],
            "embedding_error_count": embedding_report["error_count"],
            "embedding_warning_count": embedding_report["warning_count"],
            "coordinate_count": coordinate_report["coordinate_count"],
            "coordinate_error_count": coordinate_report["error_count"],
            "coordinate_warning_count": coordinate_report["warning_count"],
            "coordinate_near_duplicate_count": len(
                coordinate_report["duplicate_or_near_candidates"]
            ),
            "display_address_place_count": display_address_result["summary"][
                "place_count"
            ],
            "display_address_review_item_count": display_address_result["summary"][
                "review_item_count"
            ],
            "blocking_error_count": len(blocking_issues),
            "review_item_count": review_count,
            "catalog_review_count": catalog_review_count,
            "generated_assets_structurally_valid": len(blocking_issues) == 0,
            "safe_to_publish_generated_catalogs": (
                len(blocking_issues) == 0 and catalog_review_count == 0
            ),
        },
        "metadata_validation": validation,
        "baseline_validation": baseline_validation,
        "metadata_diff": diff,
        "change_impact": change_impact,
        "translation_alignment": translation_report,
        "title_catalog": title_review,
        "location_catalog": location_review,
        "theme_sync": theme_result["summary"],
        "evaluation": evaluation_report,
        "embedding_alignment": embedding_report,
        "coordinate_alignment": coordinate_report,
        "display_address_summary": display_address_result["summary"],
        "blocking_issues": blocking_issues,
    }
    review_queue = {
        "schema_version": "1.0",
        "blocking_issues": blocking_issues,
        **review_items,
    }
    return {
        "search_sync_report": report,
        "drama_title_catalog": title_catalog,
        "location_alias_catalog": location_catalog,
        "filter_catalog": filter_catalog,
        "theme_mapping_carried_forward": theme_result["carried_mapping"],
        "theme_decision_registry": theme_result["decision_registry"],
        "theme_review_queue": {
            "schema_version": "1.0",
            "result_unit": "source_segment_id",
            "entries": theme_result["review_queue"],
        },
        "evaluation_compatibility": evaluation_report,
        "change_impact": change_impact,
        "embedding_alignment": embedding_report,
        "coordinate_alignment": coordinate_report,
        "place_display_catalog": display_address_result["catalog"],
        "address_translation_review_queue": display_address_result["review_queue"],
        "search_rule_regression_cases": rule_regression_cases,
        "search_review_queue": review_queue,
    }


def validate_search_metadata(
    records: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    segment_seen: dict[str, int] = {}
    keyframe_seen: dict[str, int] = {}
    source_facts: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    place_facts: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    allowed = _required_mapping(policy.get("allowed_values"), "allowed_values")
    allowed_seasons = set(_string_list(allowed.get("season", [])))
    allowed_times = set(_string_list(allowed.get("time_of_day", [])))

    def issue(
        severity: str,
        code: str,
        index: int | None,
        segment_id: str | None,
        message: str,
    ) -> None:
        issues.append(
            {
                "severity": severity,
                "code": code,
                "record_index": index,
                "segment_id": segment_id,
                "message": message,
            }
        )

    for index, row in enumerate(records):
        segment_id = _text(row.get("segment_id"))
        context = segment_id or f"metadata[{index}]"
        for field in REQUIRED_TEXT_FIELDS:
            if not _text(row.get(field)):
                issue(
                    "error",
                    "MISSING_REQUIRED_FIELD",
                    index,
                    segment_id or None,
                    f"{context}: {field} 값이 비어 있습니다.",
                )
        if not _text(row.get("drama_title")):
            issue(
                "warning",
                "DRAMA_TITLE_UNCONFIRMED",
                index,
                segment_id or None,
                f"{context}: drama_title이 없어 작품명 필터에서는 제외됩니다.",
            )
        if not _text(row.get("city")):
            issue(
                "warning",
                "CITY_UNCONFIRMED",
                index,
                segment_id or None,
                f"{context}: city가 없어 도시 필터에서는 제외됩니다.",
            )
        for field in ARRAY_FIELDS:
            _validate_array_field(row, field, index, segment_id, issue, required=True)
        for field in OPTIONAL_ARRAY_FIELDS:
            if field in row:
                _validate_array_field(
                    row, field, index, segment_id, issue, required=False
                )

        start = _finite_number(row.get("start_time"))
        end = _finite_number(row.get("end_time"))
        if start is None or end is None or start >= end:
            issue(
                "error",
                "INVALID_TIME_RANGE",
                index,
                segment_id or None,
                f"{context}: start_time < end_time인 유한한 숫자여야 합니다.",
            )
        season = _text(row.get("season"))
        if season and season not in allowed_seasons:
            issue(
                "error",
                "NON_CANONICAL_SEASON",
                index,
                segment_id or None,
                f"{context}: 허용되지 않은 season입니다: {season}",
            )
        time_value = _text(row.get("time_of_day"))
        if time_value and time_value not in allowed_times:
            issue(
                "error",
                "NON_CANONICAL_TIME_OF_DAY",
                index,
                segment_id or None,
                f"{context}: 허용되지 않은 time_of_day입니다: {time_value}",
            )

        if segment_id:
            previous = segment_seen.get(segment_id)
            if previous is not None:
                issue(
                    "error",
                    "DUPLICATE_SEGMENT_ID",
                    index,
                    segment_id,
                    f"{segment_id}: metadata[{previous}]와 중복됩니다.",
                )
            else:
                segment_seen[segment_id] = index
        source_id = _text(row.get("source_segment_id"))
        place_id = _text(row.get("place_id"))
        video_id = _text(row.get("video_id"))
        if source_id and not re.fullmatch(r"V\d{3}_P\d{3}_S\d{3}", source_id):
            issue(
                "error",
                "INVALID_SOURCE_SEGMENT_ID_FORMAT",
                index,
                segment_id or None,
                f"{context}: source_segment_id는 VNNN_PNNN_SNNN 형식이어야 합니다.",
            )
        if place_id and not re.fullmatch(r"P\d{3}", place_id):
            issue(
                "error",
                "INVALID_PLACE_ID_FORMAT",
                index,
                segment_id or None,
                f"{context}: place_id는 PNNN 형식이어야 합니다.",
            )
        video_prefix = source_id.split("_", 1)[0] if source_id else ""
        if video_prefix and video_id and not video_id.startswith(video_prefix + "_"):
            issue(
                "error",
                "VIDEO_ID_SOURCE_PREFIX_MISMATCH",
                index,
                segment_id or None,
                f"{context}: video_id는 {video_prefix}_로 시작해야 합니다.",
            )
        if segment_id and source_id:
            expected_prefix = f"{source_id}_SCENE_"
            suffix = segment_id.removeprefix(expected_prefix)
            if not segment_id.startswith(expected_prefix) or not re.fullmatch(
                r"\d{3}", suffix
            ):
                issue(
                    "error",
                    "SEGMENT_SOURCE_ID_MISMATCH",
                    index,
                    segment_id,
                    f"{context}: segment_id는 {source_id}_SCENE_NNN 형식이어야 합니다.",
                )
            place_match = re.search(r"_(P\d+)_", source_id)
            if place_match and place_id and place_match.group(1) != place_id:
                issue(
                    "error",
                    "PLACE_ID_EMBEDDED_ID_MISMATCH",
                    index,
                    segment_id,
                    f"{context}: source_segment_id의 {place_match.group(1)}와 place_id {place_id}가 다릅니다.",
                )
        keyframe_id = _text(row.get("keyframe_id"))
        if keyframe_id and keyframe_id != segment_id:
            issue(
                "error",
                "KEYFRAME_ID_MISMATCH",
                index,
                segment_id or None,
                f"{context}: keyframe_id는 segment_id와 같아야 합니다.",
            )
        keyframe_path = _normalized_path(row.get("keyframe_path"))
        if keyframe_path:
            previous = keyframe_seen.get(keyframe_path)
            if previous is not None:
                issue(
                    "error",
                    "DUPLICATE_KEYFRAME_PATH",
                    index,
                    segment_id or None,
                    f"{context}: metadata[{previous}]와 keyframe_path가 중복됩니다.",
                )
            else:
                keyframe_seen[keyframe_path] = index
            if not keyframe_path.startswith("keyframes/"):
                issue(
                    "error",
                    "INVALID_KEYFRAME_PATH",
                    index,
                    segment_id or None,
                    f"{context}: keyframe_path는 keyframes/... 형식이어야 합니다.",
                )
            expected_filename = f"{segment_id}.jpg".casefold()
            actual_filename = keyframe_path.rsplit("/", 1)[-1]
            if segment_id and actual_filename != expected_filename:
                issue(
                    "error",
                    "KEYFRAME_FILENAME_MISMATCH",
                    index,
                    segment_id,
                    f"{context}: JPG 파일명은 {segment_id}.jpg여야 합니다.",
                )
        if source_id:
            source_facts[source_id].append(row)
        if place_id:
            place_facts[place_id].append(row)

    for source_id, rows in sorted(source_facts.items()):
        for field in (
            "video_id",
            "place_id",
            "place_name",
            "region",
            "city",
            "drama_title",
        ):
            values = {_text(row.get(field)).casefold() for row in rows if _text(row.get(field))}
            if len(values) > 1:
                issue(
                    "error",
                    "SOURCE_SEGMENT_CONFLICT",
                    None,
                    source_id,
                    f"{source_id}: SCENE별 {field} 값이 서로 다릅니다.",
                )
    for place_id, rows in sorted(place_facts.items()):
        for field in ("place_name", "region", "city"):
            values = {_text(row.get(field)).casefold() for row in rows if _text(row.get(field))}
            if len(values) > 1:
                issue(
                    "error",
                    "PLACE_ID_CONFLICT",
                    None,
                    None,
                    f"{place_id}: 하나의 place_id에 여러 {field} 값이 연결됐습니다.",
                )

    return {
        "is_valid": not any(item["severity"] == "error" for item in issues),
        "summary": {
            "record_count": len(records),
            "source_segment_count": len(source_facts),
            "place_count": len(place_facts),
            "unique_keyframe_count": len(keyframe_seen),
            "error_count": sum(item["severity"] == "error" for item in issues),
            "warning_count": sum(item["severity"] == "warning" for item in issues),
        },
        "issues": issues,
    }


def compare_metadata(
    current: Sequence[Mapping[str, Any]], baseline: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    current_by_id = {_text(row.get("segment_id")): row for row in current}
    baseline_by_id = {_text(row.get("segment_id")): row for row in baseline}
    current_ids = set(current_by_id)
    baseline_ids = set(baseline_by_id)
    added = sorted(current_ids - baseline_ids)
    removed = sorted(baseline_ids - current_ids)
    changed: list[str] = []
    changed_fields: dict[str, list[str]] = {}
    for segment_id in sorted(current_ids & baseline_ids):
        fields = [
            field
            for field in SEARCH_RELEVANT_FIELDS
            if _stable_value(current_by_id[segment_id].get(field))
            != _stable_value(baseline_by_id[segment_id].get(field))
        ]
        if fields:
            changed.append(segment_id)
            changed_fields[segment_id] = fields

    current_sources = _source_fingerprints(current)
    baseline_sources = _source_fingerprints(baseline)
    current_source_ids = set(current_sources)
    baseline_source_ids = set(baseline_sources)
    changed_sources = sorted(
        source_id
        for source_id in current_source_ids & baseline_source_ids
        if current_sources[source_id] != baseline_sources[source_id]
    )
    current_source_identity = _source_identity(current)
    baseline_source_identity = _source_identity(baseline)
    source_identity_changes = {
        source_id: sorted(
            field
            for field in ("video_id", "place_id")
            if current_source_identity[source_id].get(field)
            != baseline_source_identity[source_id].get(field)
        )
        for source_id in sorted(
            set(current_source_identity) & set(baseline_source_identity)
        )
    }
    source_identity_changes = {
        source_id: fields
        for source_id, fields in source_identity_changes.items()
        if fields
    }
    theme_changed_scene_ids = sorted(
        segment_id
        for segment_id, fields in changed_fields.items()
        if set(fields) & set(THEME_EVIDENCE_FIELDS)
    )
    added_scene_sources = {
        _text(current_by_id[segment_id].get("source_segment_id"))
        for segment_id in added
        if _text(current_by_id[segment_id].get("source_segment_id"))
    }
    removed_scene_sources = {
        _text(baseline_by_id[segment_id].get("source_segment_id"))
        for segment_id in removed
        if _text(baseline_by_id[segment_id].get("source_segment_id"))
    }
    theme_changed_sources = sorted(
        {
            *(
                _text(current_by_id[segment_id].get("source_segment_id"))
                for segment_id in theme_changed_scene_ids
                if _text(current_by_id[segment_id].get("source_segment_id"))
            ),
            *(added_scene_sources & current_source_ids),
            *(removed_scene_sources & current_source_ids),
        }
    )
    current_titles = {
        _text(row.get("drama_title")) for row in current if _text(row.get("drama_title"))
    }
    baseline_titles = {
        _text(row.get("drama_title")) for row in baseline if _text(row.get("drama_title"))
    }
    current_places = {_text(row.get("place_id")) for row in current if _text(row.get("place_id"))}
    baseline_places = {
        _text(row.get("place_id")) for row in baseline if _text(row.get("place_id"))
    }
    return {
        "baseline_provided": bool(baseline),
        "added_segment_ids": added,
        "changed_segment_ids": changed,
        "removed_segment_ids": removed,
        "changed_fields_by_segment_id": changed_fields,
        "added_source_segment_ids": sorted(current_source_ids - baseline_source_ids),
        "changed_source_segment_ids": changed_sources,
        "theme_changed_source_segment_ids": theme_changed_sources,
        "source_identity_changed_fields_by_source_segment_id": source_identity_changes,
        "removed_source_segment_ids": sorted(baseline_source_ids - current_source_ids),
        "new_drama_titles": sorted(current_titles - baseline_titles),
        "removed_drama_titles": sorted(baseline_titles - current_titles),
        "new_place_ids": sorted(current_places - baseline_places, key=_id_sort_key),
        "removed_place_ids": sorted(baseline_places - current_places, key=_id_sort_key),
    }


def classify_change_impact(diff: Mapping[str, Any]) -> dict[str, Any]:
    changed_fields = diff.get("changed_fields_by_segment_id")
    changed_fields = changed_fields if isinstance(changed_fields, Mapping) else {}
    text_refresh = sorted(
        {
            *_string_list(diff.get("added_segment_ids")),
            *(
                segment_id
                for segment_id, fields in changed_fields.items()
                if set(_string_list(fields)) & set(TEXT_EMBEDDING_SOURCE_FIELDS)
            ),
        }
    )
    keyframe_review = sorted(
        segment_id
        for segment_id, fields in changed_fields.items()
        if "keyframe_path" in _string_list(fields)
    )
    display_refresh = sorted(
        {
            *_string_list(diff.get("added_segment_ids")),
            *(
                segment_id
                for segment_id, fields in changed_fields.items()
                if set(_string_list(fields))
                & set(DISPLAY_TRANSLATION_SOURCE_FIELDS)
            ),
        }
    )
    coordinate_review = sorted(
        segment_id
        for segment_id, fields in changed_fields.items()
        if set(_string_list(fields)) & {"place_id", "place_name", "region", "city"}
    )
    identity_reuse = sorted(
        segment_id
        for segment_id, fields in changed_fields.items()
        if set(_string_list(fields)) & set(IDENTITY_FIELDS)
    )
    return {
        "text_embedding_create_or_refresh_segment_ids": text_refresh,
        "image_embedding_create_segment_ids": _string_list(
            diff.get("added_segment_ids")
        ),
        "image_relink_or_reembed_review_segment_ids": keyframe_review,
        "stale_delete_segment_ids": _string_list(diff.get("removed_segment_ids")),
        "db_upsert_segment_ids": sorted(
            {
                *_string_list(diff.get("added_segment_ids")),
                *_string_list(diff.get("changed_segment_ids")),
            }
        ),
        "display_translation_create_or_refresh_segment_ids": display_refresh,
        "display_translation_stale_segment_ids": _string_list(
            diff.get("removed_segment_ids")
        ),
        "coordinate_review_segment_ids": coordinate_review,
        "identity_reuse_review_segment_ids": identity_reuse,
        "source_identity_reuse_review_source_segment_ids": sorted(
            _required_mapping(
                diff.get("source_identity_changed_fields_by_source_segment_id", {}),
                "source_identity_changed_fields_by_source_segment_id",
            )
        ),
        "theme_review_source_segment_ids": _string_list(
            diff.get("theme_changed_source_segment_ids")
        ),
        "notes": [
            "keyframe_path 변경만으로 이미지 내용 변경 여부는 증명할 수 없습니다.",
            "향후 keyframe SHA-256과 search_text source hash를 저장하면 재생성 필요 여부를 더 정확히 판정할 수 있습니다.",
            "표시언어 파일에는 아직 source hash가 없어 metadata 표시 필드 변경 ID는 사람이 재번역 여부를 확인해야 합니다.",
        ],
    }


def validate_translation_alignment(
    records: Sequence[Mapping[str, Any]],
    translations: Sequence[Mapping[str, Any]],
    *,
    provided: bool | None = None,
) -> dict[str, Any]:
    was_provided = bool(translations) if provided is None else provided
    if not translations:
        metadata_ids = sorted(
            _text(row.get("segment_id"))
            for row in records
            if _text(row.get("segment_id"))
        )
        if was_provided:
            return {
                "provided": True,
                "record_count": 0,
                "missing_segment_ids": metadata_ids,
                "unexpected_segment_ids": [],
                "blocking_errors": [
                    "표시언어 파일이 제공되었지만 records가 비어 있습니다.",
                    "표시언어가 없는 metadata segment_id: "
                    + ", ".join(metadata_ids),
                ],
                "warnings": [],
                "entity_variant_conflicts": [],
            }
        return {
            "provided": False,
            "record_count": 0,
            "missing_segment_ids": [],
            "unexpected_segment_ids": [],
            "blocking_errors": [],
            "warnings": ["표시언어 파일이 없어 한국어 정식명만 카탈로그에 사용합니다."],
            "entity_variant_conflicts": [],
        }
    metadata_ids = {_text(row.get("segment_id")) for row in records}
    translation_ids: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    for index, item in enumerate(translations):
        segment_id = _text(item.get("segment_id"))
        if not segment_id:
            blocking.append(f"translations[{index}].segment_id가 비어 있습니다.")
            continue
        translation_ids.append(segment_id)
        keyframe_id = _text(item.get("keyframe_id"))
        if keyframe_id != segment_id:
            blocking.append(
                f"{segment_id}: keyframe_id는 segment_id와 같아야 합니다."
            )
        payload = item.get("translations")
        if not isinstance(payload, Mapping):
            blocking.append(f"{segment_id}: translations 객체가 없습니다.")
            continue
        missing_languages = [lang for lang in LANGUAGES if lang not in payload]
        if missing_languages:
            blocking.append(
                f"{segment_id}: 표시언어 누락: {', '.join(missing_languages)}"
            )
        metadata = next(
            (
                row
                for row in records
                if _text(row.get("segment_id")) == segment_id
            ),
            None,
        )
        for language in LANGUAGES:
            fields = payload.get(language)
            if not isinstance(fields, Mapping):
                if language in payload:
                    blocking.append(f"{segment_id}/{language}: 번역 값은 객체여야 합니다.")
                continue
            for field in (
                "drama_title",
                "place_name",
                "region",
                "city",
                "season",
                "time_of_day",
                "description",
            ):
                translated_value = fields.get(field)
                if not isinstance(translated_value, str):
                    blocking.append(
                        f"{segment_id}/{language}.{field}: 문자열이어야 합니다."
                    )
                elif (
                    metadata is not None
                    and _text(metadata.get(field))
                    and not _text(translated_value)
                ):
                    blocking.append(
                        f"{segment_id}/{language}.{field}: 원문 값이 있으므로 빈 문자열일 수 없습니다."
                    )
            for field in ("mood", "activity", "scene_elements"):
                value = fields.get(field)
                if (
                    isinstance(value, (str, bytes))
                    or not isinstance(value, Sequence)
                    or any(not isinstance(element, str) for element in value)
                ):
                    blocking.append(
                        f"{segment_id}/{language}.{field}: 문자열 배열이어야 합니다."
                    )
                    continue
                if metadata is not None:
                    source_value = metadata.get(field, [])
                    source_length = (
                        len(source_value)
                        if isinstance(source_value, Sequence)
                        and not isinstance(source_value, (str, bytes))
                        else 0
                    )
                    if len(value) != source_length:
                        blocking.append(
                            f"{segment_id}/{language}.{field}: 배열 길이 {len(value)} != {source_length}"
                        )
                    if source_length and any(not _text(element) for element in value):
                        blocking.append(
                            f"{segment_id}/{language}.{field}: 빈 번역 배열 원소가 있습니다."
                        )
    duplicate_ids = sorted(
        segment_id for segment_id, count in Counter(translation_ids).items() if count > 1
    )
    if duplicate_ids:
        blocking.append("표시언어 segment_id 중복: " + ", ".join(duplicate_ids))
    translation_set = set(translation_ids)
    missing_segment_ids = sorted(metadata_ids - translation_set)
    unexpected_segment_ids = sorted(translation_set - metadata_ids)
    if missing_segment_ids:
        blocking.append(
            "표시언어가 없는 metadata segment_id: " + ", ".join(missing_segment_ids)
        )
    if unexpected_segment_ids:
        warnings.append(
            "현재 metadata에 없는 stale 표시언어: "
            + ", ".join(unexpected_segment_ids)
        )
    metadata_by_id = {
        _text(row.get("segment_id")): row
        for row in records
        if _text(row.get("segment_id"))
    }
    entity_variants: dict[
        tuple[str, str, str], dict[str, list[str]]
    ] = defaultdict(lambda: defaultdict(list))
    entity_fields = (
        ("place_name", "place_id"),
        ("drama_title", "drama_title"),
        ("region", "region"),
        ("city", "city"),
    )
    for item in translations:
        segment_id = _text(item.get("segment_id"))
        metadata = metadata_by_id.get(segment_id)
        payload = item.get("translations")
        if metadata is None or not isinstance(payload, Mapping):
            continue
        for language in LANGUAGES:
            fields = payload.get(language)
            if not isinstance(fields, Mapping):
                continue
            for translated_field, owner_field in entity_fields:
                owner = _text(metadata.get(owner_field))
                value = _text(fields.get(translated_field))
                if owner and value:
                    entity_variants[(translated_field, owner, language)][value].append(
                        segment_id
                    )
    entity_conflicts = [
        {
            "field": field,
            "owner": owner,
            "language": language,
            "variant_values": sorted(values),
            "variants": [
                {
                    "value": value,
                    "scene_count": len(segment_ids),
                    "example_segment_ids": segment_ids[:5],
                }
                for value, segment_ids in sorted(values.items())
            ],
        }
        for (field, owner, language), values in sorted(entity_variants.items())
        if len(values) > 1
    ]
    return {
        "provided": True,
        "record_count": len(translations),
        "missing_segment_ids": missing_segment_ids,
        "unexpected_segment_ids": unexpected_segment_ids,
        "blocking_errors": blocking,
        "warnings": warnings,
        "entity_variant_conflicts": entity_conflicts,
    }


def build_title_catalog(
    records: Sequence[Mapping[str, Any]],
    translations: Sequence[Mapping[str, Any]],
    existing_catalog: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    translation_by_id = {
        _text(item.get("segment_id")): item for item in translations
    }
    existing_by_title: dict[str, Mapping[str, Any]] = {}
    for item in _mapping_list(existing_catalog.get("titles")):
        title = _text(item.get("canonical_title"))
        if title:
            existing_by_title[title] = item

    titles = sorted(
        {
            _text(row.get("drama_title"))
            for row in records
            if _text(row.get("drama_title"))
        }
    )
    candidates: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(set))
    )
    rows_by_title: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in records:
        title = _text(row.get("drama_title"))
        if title:
            rows_by_title[title].append(row)
    for title in titles:
        _add_alias(candidates, title, "ko", title, "canonical")
        existing = existing_by_title.get(title, {})
        aliases = existing.get("aliases") if isinstance(existing, Mapping) else None
        if isinstance(aliases, Mapping):
            for language, values in aliases.items():
                for alias in _string_list(values):
                    _add_alias(candidates, title, str(language), alias, "existing")
        for row in rows_by_title[title]:
            translated = translation_by_id.get(_text(row.get("segment_id")), {})
            payload = translated.get("translations") if isinstance(translated, Mapping) else None
            if not isinstance(payload, Mapping):
                continue
            for language in LANGUAGES:
                fields = payload.get(language)
                if isinstance(fields, Mapping):
                    _add_alias(
                        candidates,
                        title,
                        language,
                        _text(fields.get("drama_title")),
                        "translation",
                    )

    resolved, collisions = _resolve_alias_candidates(
        candidates,
        canonical_by_owner={title: title for title in titles},
    )
    catalog_titles = [
        {
            "canonical_title": title,
            "aliases": {
                language: values
                for language, values in resolved.get(title, {}).items()
                if values
            },
        }
        for title in titles
    ]
    missing_existing = sorted(set(existing_by_title) - set(titles))
    return (
        {
            "schema_version": "2.0",
            "generated": True,
            "titles": catalog_titles,
        },
        {
            "metadata_title_count": len(titles),
            "existing_catalog_title_count": len(existing_by_title),
            "new_titles_added": sorted(set(titles) - set(existing_by_title)),
            "stale_existing_titles": missing_existing,
            "alias_collisions": collisions,
        },
    )


def build_location_catalog(
    records: Sequence[Mapping[str, Any]],
    translations: Sequence[Mapping[str, Any]],
    existing_catalog: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    translation_by_id = {
        _text(item.get("segment_id")): item for item in translations
    }
    existing_places = {
        _text(item.get("place_id")): item
        for item in _mapping_list(existing_catalog.get("place_aliases"))
        if _text(item.get("place_id"))
    }
    region_aliases = [dict(item) for item in _mapping_list(existing_catalog.get("region_aliases"))]
    place_rows: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in records:
        place_id = _text(row.get("place_id"))
        if place_id:
            place_rows[place_id].append(row)

    candidates: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(set))
    )
    canonical_by_place: dict[str, str] = {}
    for place_id, rows in place_rows.items():
        place_name = _text(rows[0].get("place_name"))
        canonical_by_place[place_id] = place_name
        _add_alias(candidates, place_id, "ko", place_name, "canonical")
        existing = existing_places.get(place_id, {})
        aliases = existing.get("aliases") if isinstance(existing, Mapping) else None
        if isinstance(aliases, Mapping):
            for language, values in aliases.items():
                for alias in _string_list(values):
                    _add_alias(candidates, place_id, str(language), alias, "existing")
        for row in rows:
            translated = translation_by_id.get(_text(row.get("segment_id")), {})
            payload = translated.get("translations") if isinstance(translated, Mapping) else None
            if not isinstance(payload, Mapping):
                continue
            for language in LANGUAGES:
                fields = payload.get(language)
                if isinstance(fields, Mapping):
                    _add_alias(
                        candidates,
                        place_id,
                        language,
                        _text(fields.get("place_name")),
                        "translation",
                    )

    reserved: dict[str, str] = {}
    for index, item in enumerate(region_aliases):
        aliases = item.get("aliases")
        if not isinstance(aliases, Mapping):
            continue
        for values in aliases.values():
            for alias in _string_list(values):
                reserved[_normalize_alias(alias)] = f"region_aliases[{index}]"
    resolved, collisions = _resolve_alias_candidates(
        candidates,
        canonical_by_owner=canonical_by_place,
        reserved_aliases=reserved,
    )
    output_places = []
    for place_id in sorted(place_rows, key=_id_sort_key):
        existing = existing_places.get(place_id, {})
        output_places.append(
            {
                "place_id": place_id,
                "place_name": canonical_by_place[place_id],
                "explicit_region_filter": (
                    existing.get("explicit_region_filter")
                    if isinstance(existing, Mapping)
                    else None
                ),
                "aliases": {
                    language: values
                    for language, values in resolved.get(place_id, {}).items()
                    if values
                },
            }
        )
    return (
        {
            "schema_version": "2.0",
            "generated": True,
            "region_aliases": region_aliases,
            "place_aliases": output_places,
        },
        {
            "metadata_place_count": len(place_rows),
            "existing_catalog_place_count": len(existing_places),
            "new_place_ids_added": sorted(
                set(place_rows) - set(existing_places), key=_id_sort_key
            ),
            "stale_existing_place_ids": sorted(
                set(existing_places) - set(place_rows), key=_id_sort_key
            ),
            "alias_collisions": collisions,
        },
    )


def synchronize_theme_mapping(
    records: Sequence[Mapping[str, Any]],
    mapping_payload: Mapping[str, Any],
    decision_payload: Mapping[str, Any],
    rules_payload: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    changed_source_ids: set[str],
    added_source_ids: set[str],
) -> dict[str, Any]:
    allowed = set(
        _string_list(
            _required_mapping(policy.get("allowed_values"), "allowed_values").get(
                "theme", []
            )
        )
    )
    source_rows: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in records:
        source_id = _text(row.get("source_segment_id"))
        if source_id:
            source_rows[source_id].append(row)
    current_ids = set(source_rows)
    existing_entries = _mapping_list(mapping_payload.get("entries"))
    input_decisions = _mapping_list(decision_payload.get("entries"))
    input_decision_by_id: dict[str, Mapping[str, Any]] = {}
    duplicate_decision_ids: list[str] = []
    invalid_decision_statuses: list[dict[str, str]] = []
    allowed_decision_statuses = {
        "approved_existing",
        "approved_empty",
        "excluded",
        "needs_review",
        "review_due_to_metadata_change",
    }
    for item in input_decisions:
        source_id = _text(item.get("source_segment_id"))
        if not source_id:
            continue
        if source_id in input_decision_by_id:
            duplicate_decision_ids.append(source_id)
            continue
        status = _text(item.get("status"))
        if status not in allowed_decision_statuses:
            invalid_decision_statuses.append(
                {"source_segment_id": source_id, "status": status}
            )
        input_decision_by_id[source_id] = item
    existing_by_id: dict[str, dict[str, Any]] = {}
    seen_mapping_ids: set[str] = set()
    empty_mapping_ids: list[str] = []
    invalid_theme_ids: list[dict[str, Any]] = []
    duplicate_mapping_ids: list[str] = []
    for item in existing_entries:
        source_id = _text(item.get("source_segment_id"))
        if not source_id:
            continue
        if source_id in seen_mapping_ids:
            duplicate_mapping_ids.append(source_id)
            continue
        seen_mapping_ids.add(source_id)
        themes = _string_list(item.get("themes", []))
        invalid = sorted(set(themes) - allowed)
        if invalid:
            invalid_theme_ids.append(
                {"source_segment_id": source_id, "invalid_theme_ids": invalid}
            )
        copied = dict(item)
        copied["themes"] = sorted(set(themes) & allowed)
        if copied["themes"]:
            existing_by_id[source_id] = copied
        else:
            empty_mapping_ids.append(source_id)
    stale = sorted(set(existing_by_id) - current_ids)
    evidence_hashes = {
        source_id: _theme_evidence_hash(rows)
        for source_id, rows in source_rows.items()
    }
    preserved_empty_or_excluded = {
        source_id
        for source_id, item in input_decision_by_id.items()
        if source_id in current_ids
        and _text(item.get("status")) in {"approved_empty", "excluded"}
        and _text(item.get("evidence_hash")) == evidence_hashes[source_id]
        and source_id not in changed_source_ids
        and source_id not in added_source_ids
    }
    unmapped = current_ids - set(existing_by_id) - preserved_empty_or_excluded
    review_ids = sorted(unmapped | changed_source_ids | added_source_ids)
    carried = [
        existing_by_id[source_id]
        for source_id in sorted(set(existing_by_id) & current_ids)
        if source_id not in set(review_ids)
        and source_id not in preserved_empty_or_excluded
    ]
    themes = _mapping_list(rules_payload.get("themes"))
    review_queue = []
    for source_id in review_ids:
        rows = source_rows.get(source_id, [])
        if not rows:
            continue
        suggestions = _suggest_themes(rows, themes)
        first = rows[0]
        reasons = []
        if source_id in added_source_ids:
            reasons.append("new_source_segment")
        if source_id in changed_source_ids:
            reasons.append("search_relevant_metadata_changed")
        if source_id in unmapped:
            reasons.append("theme_mapping_missing")
        previous_decision = input_decision_by_id.get(source_id)
        if previous_decision and source_id not in preserved_empty_or_excluded:
            reasons.append("previous_theme_decision_stale_or_unapproved")
        review_queue.append(
            {
                "source_segment_id": source_id,
                "place_id": _text(first.get("place_id")),
                "place_name": _text(first.get("place_name")),
                "drama_title": _text(first.get("drama_title")),
                "scene_count": len(rows),
                "current_themes": existing_by_id.get(source_id, {}).get("themes", []),
                "suggested_themes": suggestions,
                "review_reasons": reasons,
            }
        )
    review_by_id = {
        item["source_segment_id"]: item for item in review_queue
    }
    decision_entries = []
    for source_id in sorted(current_ids):
        current = existing_by_id.get(source_id)
        review = review_by_id.get(source_id)
        previous_decision = input_decision_by_id.get(source_id)
        if review is None:
            if source_id in preserved_empty_or_excluded and previous_decision:
                status = _text(previous_decision.get("status"))
            else:
                status = "approved_existing"
        elif current is None:
            status = "needs_review"
        else:
            status = "review_due_to_metadata_change"
        decision_entries.append(
            {
                "source_segment_id": source_id,
                "status": status,
                "themes": (
                    []
                    if status in {"approved_empty", "excluded"}
                    else list(current.get("themes", [])) if current else []
                ),
                "evidence_hash": evidence_hashes[source_id],
                "review_reasons": list(review.get("review_reasons", []))
                if review
                else [],
            }
        )
    return {
        "carried_mapping": {
            "schema_version": "1.0",
            "result_unit": "source_segment_id",
            "entries": carried,
        },
        "review_queue": review_queue,
        "decision_registry": {
            "schema_version": "1.0",
            "result_unit": "source_segment_id",
            "entries": decision_entries,
        },
        "summary": {
            "current_source_segment_count": len(current_ids),
            "mapping_input_count": len(existing_entries),
            "carried_mapping_count": len(carried),
            "unmapped_source_segment_ids": sorted(unmapped),
            "stale_mapping_source_segment_ids": stale,
            "changed_mapped_source_segment_ids": sorted(
                changed_source_ids & set(existing_by_id)
            ),
            "duplicate_mapping_source_segment_ids": sorted(set(duplicate_mapping_ids)),
            "invalid_theme_ids": invalid_theme_ids,
            "empty_mapping_source_segment_ids": sorted(set(empty_mapping_ids)),
            "decision_input_count": len(input_decisions),
            "preserved_empty_or_excluded_source_segment_ids": sorted(
                preserved_empty_or_excluded
            ),
            "duplicate_decision_source_segment_ids": sorted(
                set(duplicate_decision_ids)
            ),
            "invalid_decision_statuses": invalid_decision_statuses,
            "review_queue_count": len(review_queue),
        },
    }


def build_filter_catalog(
    records: Sequence[Mapping[str, Any]],
    theme_result: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    fields: dict[str, list[dict[str, Any]]] = {}
    for field in ("place_id", "drama_title", "region", "city", "season", "time_of_day"):
        counts = Counter(
            _text(row.get(field)) for row in records if _text(row.get(field))
        )
        fields[field] = [
            {"value": value, "scene_count": count}
            for value, count in sorted(counts.items(), key=lambda item: item[0])
        ]
    theme_counts = Counter()
    carried = theme_result.get("carried_mapping", {})
    if isinstance(carried, Mapping):
        for item in _mapping_list(carried.get("entries")):
            theme_counts.update(_string_list(item.get("themes", [])))
    fields["theme"] = [
        {"value": value, "source_segment_count": count}
        for value, count in sorted(theme_counts.items())
    ]
    return {
        "schema_version": "1.0",
        "generated": True,
        "result_unit": policy.get("result_unit", "source_segment_id"),
        "derived_fields": {
            "keyframe_id": policy.get("keyframe_id_rule", "segment_id"),
            "k_culture_elements_default": [],
        },
        "hard_filter_fields": list(policy.get("hard_filter_fields", [])),
        "soft_hint_fields": list(policy.get("soft_hint_fields", [])),
        "fields": fields,
        "value_aliases": policy.get("value_aliases", {}),
        "region_groups": policy.get("region_groups", {}),
        "candidate_k": policy.get("candidate_k", {}),
        "rrf_k": policy.get("rrf_k", 60),
    }


def build_rule_regression_cases(
    title_catalog: Mapping[str, Any],
    location_catalog: Mapping[str, Any],
    filter_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """새 작품명·장소·지역·필터값과 함께 늘어나는 로컬 회귀 사례를 만든다."""

    cases: list[dict[str, Any]] = []
    suffixes = {
        "ko": " 촬영지 보여줘",
        "en": " filming locations",
        "ja": "のロケ地",
        "zh": "的拍摄地",
    }
    for title in _mapping_list(title_catalog.get("titles")):
        canonical = _text(title.get("canonical_title"))
        aliases = title.get("aliases")
        if not canonical or not isinstance(aliases, Mapping):
            continue
        for language in LANGUAGES:
            for alias in _string_list(aliases.get(language, [])):
                cases.append(
                    {
                        "case_id": f"TITLE_{len(cases) + 1:04d}",
                        "case_type": "drama_title_protection",
                        "language": language,
                        "query": alias + suffixes[language],
                        "expected": {
                            "matched_drama_title": canonical,
                            "drama_title_filter": [canonical],
                            "title_words_must_not_become_region_or_season_filters": True,
                        },
                    }
                )
    for region in _mapping_list(location_catalog.get("region_aliases")):
        canonical_value = region.get("canonical")
        expected_regions = _string_list(canonical_value)
        aliases = region.get("aliases")
        if not expected_regions or not isinstance(aliases, Mapping):
            continue
        for language in LANGUAGES:
            for alias in _string_list(aliases.get(language, [])):
                cases.append(
                    {
                        "case_id": f"LOCATION_REGION_{len(cases) + 1:04d}",
                        "case_type": "region_alias_matching",
                        "language": language,
                        "query": alias + suffixes[language],
                        "expected": {"region": expected_regions},
                    }
                )
    for place in _mapping_list(location_catalog.get("place_aliases")):
        place_id = _text(place.get("place_id"))
        aliases = place.get("aliases")
        if not place_id or not isinstance(aliases, Mapping):
            continue
        explicit_region = _text(place.get("explicit_region_filter"))
        for language in LANGUAGES:
            for alias in _string_list(aliases.get(language, [])):
                cases.append(
                    {
                        "case_id": f"LOCATION_PLACE_{len(cases) + 1:04d}",
                        "case_type": "place_alias_matching",
                        "language": language,
                        "query": alias + suffixes[language],
                        "expected": {
                            "place_id": place_id,
                            "region": [explicit_region] if explicit_region else [],
                        },
                    }
                )
    region_groups = filter_catalog.get("region_groups")
    if isinstance(region_groups, Mapping):
        for alias, canonicals in sorted(region_groups.items()):
            cases.append(
                {
                    "case_id": f"REGION_GROUP_{len(cases) + 1:04d}",
                    "case_type": "region_group_expansion",
                    "language": "ko",
                    "query": f"{alias} 촬영지 보여줘",
                    "expected": {"region": _string_list(canonicals)},
                }
            )
    value_aliases = filter_catalog.get("value_aliases")
    if isinstance(value_aliases, Mapping):
        for field in ("season", "time_of_day"):
            groups = value_aliases.get(field)
            if not isinstance(groups, Mapping):
                continue
            for canonical, aliases in groups.items():
                for alias in _string_list(aliases):
                    cases.append(
                        {
                            "case_id": f"FILTER_{len(cases) + 1:04d}",
                            "case_type": "filter_value_normalization",
                            "language": "auto",
                            "query_fragment": alias,
                            "expected": {field: [str(canonical)]},
                        }
                    )
    return {
        "schema_version": "1.0",
        "generated": True,
        "case_count": len(cases),
        "cases": cases,
    }


def validate_evaluation_compatibility(
    records: Sequence[Mapping[str, Any]],
    evaluation: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    theme_mapping: Mapping[str, Any] | None = None,
    provided: bool | None = None,
) -> dict[str, Any]:
    was_provided = bool(evaluation) if provided is None else provided
    if not was_provided:
        return {
            "provided": False,
            "query_count": 0,
            "resolved_query_count": 0,
            "unresolved": [],
            "warnings": ["평가셋이 없어 신규 데이터 검색 회귀 여부는 확인하지 않았습니다."],
        }
    raw_queries = evaluation.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        return {
            "provided": True,
            "query_count": 0,
            "resolved_query_count": 0,
            "language_counts": {},
            "theme_counts": {},
            "unresolved": [
                {
                    "query_id": "evaluation",
                    "message": "평가 파일이 제공되었지만 queries 배열이 없거나 비어 있습니다.",
                }
            ],
            "warnings": [],
        }
    invalid_query_indices = [
        index for index, item in enumerate(raw_queries) if not isinstance(item, Mapping)
    ]
    if invalid_query_indices:
        return {
            "provided": True,
            "query_count": len(raw_queries),
            "resolved_query_count": 0,
            "language_counts": {},
            "theme_counts": {},
            "unresolved": [
                {
                    "query_id": "evaluation",
                    "message": (
                        "평가 queries에 객체가 아닌 항목이 있습니다: "
                        + ", ".join(map(str, invalid_query_indices))
                    ),
                }
            ],
            "warnings": [],
        }
    queries = list(raw_queries)
    scene_by_id = {_text(row.get("segment_id")): row for row in records}
    rows_by_source: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    keyframe_path_to_row: dict[str, Mapping[str, Any]] = {}
    for row in records:
        source_id = _text(row.get("source_segment_id"))
        if source_id:
            rows_by_source[source_id].append(row)
        keyframe_path = _normalized_path(row.get("keyframe_path"))
        if keyframe_path:
            keyframe_path_to_row[keyframe_path] = row
    source_ids = {_text(row.get("source_segment_id")) for row in records}
    place_ids = {_text(row.get("place_id")) for row in records}
    keyframe_paths = {_normalized_path(row.get("keyframe_path")) for row in records}
    hard_filter_fields = set(_string_list(policy.get("hard_filter_fields", [])))
    known_filter_values = {
        field: {_text(row.get(field)) for row in records if _text(row.get(field))}
        for field in ("place_id", "drama_title", "region", "city", "season", "time_of_day")
    }
    known_filter_values["theme"] = set(
        _string_list(
            _required_mapping(policy.get("allowed_values"), "allowed_values").get(
                "theme", []
            )
        )
    )
    raw_region_groups = policy.get("region_groups")
    region_groups = raw_region_groups if isinstance(raw_region_groups, Mapping) else {}
    known_filter_values["region"].update(str(key) for key in region_groups)
    source_themes: dict[str, set[str]] = defaultdict(set)
    if isinstance(theme_mapping, Mapping):
        for item in _mapping_list(theme_mapping.get("entries")):
            source_id = _text(item.get("source_segment_id"))
            if source_id:
                source_themes[source_id].update(_string_list(item.get("themes", [])))
    unresolved: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen_query_ids: set[str] = set()
    language_counts = Counter()
    theme_counts = Counter()
    for index, query in enumerate(queries):
        query_id = _text(query.get("query_id"))
        if not query_id:
            query_id = f"queries[{index}]"
            unresolved.append(
                {"query_id": query_id, "message": f"{query_id}: query_id가 비어 있습니다."}
            )
        if query_id in seen_query_ids:
            unresolved.append(
                {"query_id": query_id, "message": f"query_id 중복: {query_id}"}
            )
        seen_query_ids.add(query_id)
        language = _text(query.get("language"))
        language_counts[language] += 1
        if language not in LANGUAGES:
            unresolved.append(
                {"query_id": query_id, "message": f"{query_id}: 지원하지 않는 language={language!r}"}
            )
        if not _text(query.get("query")):
            unresolved.append(
                {"query_id": query_id, "message": f"{query_id}: query가 비어 있습니다."}
            )
        theme = _text(query.get("theme"))
        if theme:
            theme_counts[theme] += 1
        relevant_sources = set(
            _string_list(query.get("relevant_source_segment_ids", []))
        )
        if not relevant_sources:
            unresolved.append(
                {"query_id": query_id, "message": f"{query_id}: 정답 source_segment_id가 없습니다."}
            )
        missing_sources = sorted(relevant_sources - source_ids)
        relevant_scene_ids = set(
            _string_list(query.get("relevant_segment_ids", []))
        )
        relevant_keyframe_ids = set(
            _string_list(query.get("relevant_keyframe_ids", []))
        )
        relevant_paths = {
            _normalized_path(value)
            for value in _string_list(query.get("relevant_keyframe_paths", []))
        }
        relevant_place_ids = set(
            _string_list(query.get("relevant_place_ids", []))
        )
        missing_scenes = sorted(relevant_scene_ids - set(scene_by_id))
        missing_paths = sorted(
            relevant_paths - keyframe_paths
        )
        missing_keyframe_ids = sorted(
            relevant_keyframe_ids - set(scene_by_id)
        )
        missing_place_ids = sorted(
            relevant_place_ids - place_ids
        )
        relationship_errors: list[str] = []
        mismatched_scenes = sorted(
            scene_id
            for scene_id in relevant_scene_ids & set(scene_by_id)
            if _text(scene_by_id[scene_id].get("source_segment_id"))
            not in relevant_sources
        )
        if mismatched_scenes:
            relationship_errors.append(
                "relevant_segment_ids가 relevant_source_segment_ids에 속하지 않음: "
                + ", ".join(mismatched_scenes)
            )
        mismatched_keyframe_ids = sorted(
            keyframe_id
            for keyframe_id in relevant_keyframe_ids & set(scene_by_id)
            if _text(scene_by_id[keyframe_id].get("source_segment_id"))
            not in relevant_sources
        )
        if mismatched_keyframe_ids:
            relationship_errors.append(
                "relevant_keyframe_ids가 relevant_source_segment_ids에 속하지 않음: "
                + ", ".join(mismatched_keyframe_ids)
            )
        mismatched_paths = sorted(
            path
            for path in relevant_paths & keyframe_paths
            if _text(keyframe_path_to_row[path].get("source_segment_id"))
            not in relevant_sources
        )
        if mismatched_paths:
            relationship_errors.append(
                "relevant_keyframe_paths가 relevant_source_segment_ids에 속하지 않음: "
                + ", ".join(mismatched_paths)
            )
        source_place_ids = {
            _text(row.get("place_id"))
            for source_id in relevant_sources
            for row in rows_by_source.get(source_id, [])
            if _text(row.get("place_id"))
        }
        mismatched_places = sorted(relevant_place_ids - source_place_ids)
        if mismatched_places and not missing_place_ids:
            relationship_errors.append(
                "relevant_place_ids가 relevant_source_segment_ids에 연결되지 않음: "
                + ", ".join(mismatched_places)
            )
        invalid_filters: list[str] = []
        parsed_filters: dict[str, list[str]] = {}
        expected_filters = query.get("expected_filters")
        if expected_filters is not None and not isinstance(expected_filters, Mapping):
            invalid_filters.append("expected_filters는 객체여야 합니다.")
        elif isinstance(expected_filters, Mapping):
            for field, raw_values in expected_filters.items():
                if field not in hard_filter_fields:
                    invalid_filters.append(f"지원하지 않는 필터 필드: {field}")
                    continue
                values = _string_list(raw_values)
                if not values:
                    invalid_filters.append(f"{field}: 값이 비어 있습니다.")
                    continue
                parsed_filters[str(field)] = values
                unknown = sorted(set(values) - known_filter_values.get(str(field), set()))
                if unknown:
                    invalid_filters.append(f"{field}: 현재 데이터에 없는 값 {unknown}")
        if relevant_sources and parsed_filters and not invalid_filters:
            relevant_rows = [
                row
                for source_id in relevant_sources
                for row in rows_by_source.get(source_id, [])
            ]
            matching_rows = [
                row
                for row in relevant_rows
                if all(
                    _evaluation_filter_matches(
                        row,
                        field,
                        values,
                        region_groups=region_groups,
                        source_themes=source_themes,
                    )
                    for field, values in parsed_filters.items()
                )
            ]
            if not matching_rows:
                invalid_filters.append(
                    "expected_filters를 AND 적용하면 정답 source의 SCENE이 모두 제외됩니다."
                )
        if (
            missing_sources
            or missing_scenes
            or missing_paths
            or missing_keyframe_ids
            or missing_place_ids
            or invalid_filters
            or relationship_errors
        ):
            unresolved.append(
                {
                    "query_id": query_id,
                    "message": (
                        f"{query_id}: 현재 metadata에서 정답 앵커를 찾지 못했습니다."
                    ),
                    "missing_source_segment_ids": missing_sources,
                    "missing_segment_ids": missing_scenes,
                    "missing_keyframe_paths": missing_paths,
                    "missing_keyframe_ids": missing_keyframe_ids,
                    "missing_place_ids": missing_place_ids,
                    "invalid_expected_filters": invalid_filters,
                    "anchor_relationship_errors": relationship_errors,
                }
            )
    if not 30 <= len(queries) <= 50:
        warnings.append("평가 질문은 권장 범위인 30~50개가 아닙니다.")
    expected_languages = {"ko", "en", "ja", "zh"}
    if set(language_counts) != expected_languages:
        warnings.append("평가 언어가 ko/en/ja/zh 전체를 포함하지 않습니다.")
    return {
        "provided": True,
        "query_count": len(queries),
        "resolved_query_count": len(queries) - len({item["query_id"] for item in unresolved}),
        "language_counts": dict(sorted(language_counts.items())),
        "theme_counts": dict(sorted(theme_counts.items())),
        "unresolved": unresolved,
        "warnings": warnings,
    }


def _evaluation_filter_matches(
    row: Mapping[str, Any],
    field: str,
    values: Sequence[str],
    *,
    region_groups: Mapping[str, Any],
    source_themes: Mapping[str, set[str]],
) -> bool:
    if field == "theme":
        source_id = _text(row.get("source_segment_id"))
        return bool(set(values) & source_themes.get(source_id, set()))
    actual = _text(row.get(field))
    if field != "region":
        return actual in set(values)
    expanded: list[str] = []
    for value in values:
        group_values = _string_list(region_groups.get(value, []))
        expanded.extend(group_values or [value])
    return any(_region_value_matches(actual, expected) for expected in expanded)


def _region_value_matches(actual: str, expected: str) -> bool:
    if not actual or not expected:
        return False
    canonical_by_short = {
        "경북": "경상북도",
        "경남": "경상남도",
        "전북": "전북특별자치도",
        "전남": "전라남도",
        "충북": "충청북도",
        "충남": "충청남도",
    }
    expected_canonical = canonical_by_short.get(expected, expected)
    return actual == expected_canonical or actual.startswith(expected)


def write_search_assets(
    output_dir: str | Path,
    assets: Mapping[str, Any],
    *,
    overwrite: bool = False,
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filenames = {
        "search_sync_report": "search_sync_report.json",
        "drama_title_catalog": "drama_title_catalog.generated.json",
        "location_alias_catalog": "location_alias_catalog.generated.json",
        "filter_catalog": "filter_catalog.generated.json",
        "theme_mapping_carried_forward": "theme_mapping.carried_forward.json",
        "theme_decision_registry": "theme_decision_registry.generated.json",
        "theme_review_queue": "theme_review_queue.json",
        "evaluation_compatibility": "evaluation_compatibility.json",
        "change_impact": "change_impact.json",
        "embedding_alignment": "embedding_alignment.json",
        "coordinate_alignment": "coordinate_alignment.json",
        "place_display_catalog": "place_display_catalog.generated.json",
        "address_translation_review_queue": "address_translation_review_queue.json",
        "search_rule_regression_cases": "search_rule_regression_cases.generated.json",
        "search_review_queue": "search_review_queue.json",
    }
    for key, filename in filenames.items():
        path = output_dir / filename
        if path.exists() and not overwrite:
            raise FileExistsError(f"출력 파일이 이미 있습니다: {path}")
        _write_json_atomic(path, assets[key])
    readme = output_dir / "SUMMARY.md"
    if readme.exists() and not overwrite:
        raise FileExistsError(f"출력 파일이 이미 있습니다: {readme}")
    _write_text_atomic(readme, _render_summary(assets["search_sync_report"]))


def _load_translation_records(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = load_json(path)
    raw: object = payload.get("records") if isinstance(payload, Mapping) else payload
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise ValueError("표시언어 파일은 records 배열을 가져야 합니다.")
    invalid = [index for index, item in enumerate(raw) if not isinstance(item, Mapping)]
    if invalid:
        raise ValueError(f"표시언어 records에 객체가 아닌 항목이 있습니다: {invalid}")
    return [dict(item) for item in raw]


def _optional_mapping(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return dict(_required_mapping(load_json(path), str(path)))


def _required_mapping(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context}는 JSON 객체여야 합니다.")
    return value


def _mapping_list(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    invalid = [index for index, item in enumerate(value) if not isinstance(item, Mapping)]
    if invalid:
        raise ValueError(f"객체 배열에 잘못된 항목이 있습니다: {invalid}")
    return list(value)


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [_text(item) for item in value if _text(item)]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalized_path(value: object) -> str:
    return _text(value).replace("\\", "/").casefold()


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _validate_array_field(
    row: Mapping[str, Any],
    field: str,
    index: int,
    segment_id: str,
    add_issue: Any,
    *,
    required: bool,
) -> None:
    value = row.get(field)
    if value is None and not required:
        return
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        add_issue(
            "error",
            "INVALID_ARRAY_FIELD",
            index,
            segment_id or None,
            f"{segment_id or f'metadata[{index}]'}: {field}는 문자열 배열이어야 합니다.",
        )
        return
    seen: set[str] = set()
    for item in value:
        cleaned = _text(item)
        if not cleaned:
            add_issue(
                "error",
                "INVALID_ARRAY_ITEM",
                index,
                segment_id or None,
                f"{segment_id or f'metadata[{index}]'}: {field}에 빈 값이 있습니다.",
            )
            continue
        key = cleaned.casefold()
        if key in seen:
            add_issue(
                "warning",
                "DUPLICATE_ARRAY_ITEM",
                index,
                segment_id or None,
                f"{segment_id or f'metadata[{index}]'}: {field} 중복값 {cleaned}",
            )
        seen.add(key)


def _stable_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _record_fingerprint(row: Mapping[str, Any]) -> str:
    selected = {field: row.get(field) for field in SEARCH_RELEVANT_FIELDS}
    return hashlib.sha256(_stable_value(selected).encode("utf-8")).hexdigest()


def _source_fingerprints(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in records:
        source_id = _text(row.get("source_segment_id"))
        if source_id:
            grouped[source_id].append(
                (_text(row.get("segment_id")), _record_fingerprint(row))
            )
    return {
        source_id: hashlib.sha256(_stable_value(sorted(values)).encode("utf-8")).hexdigest()
        for source_id, values in grouped.items()
    }


def _source_identity(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, list[str]]]:
    grouped: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"video_id": set(), "place_id": set()}
    )
    for row in records:
        source_id = _text(row.get("source_segment_id"))
        if not source_id:
            continue
        for field in ("video_id", "place_id"):
            value = _text(row.get(field))
            if value:
                grouped[source_id][field].add(value)
    return {
        source_id: {
            field: sorted(values)
            for field, values in fields.items()
        }
        for source_id, fields in grouped.items()
    }


def _theme_evidence_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    selected = [
        {
            "segment_id": _text(row.get("segment_id")),
            **{field: row.get(field) for field in THEME_EVIDENCE_FIELDS},
        }
        for row in sorted(rows, key=lambda item: _text(item.get("segment_id")))
    ]
    return hashlib.sha256(_stable_value(selected).encode("utf-8")).hexdigest()


def _add_alias(
    candidates: dict[str, dict[str, dict[str, set[str]]]],
    owner: str,
    language: str,
    alias: str,
    origin: str,
) -> None:
    alias = _text(alias)
    language = _text(language)
    if owner and language and alias:
        candidates[owner][language][alias].add(origin)


def _normalize_alias(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


def _resolve_alias_candidates(
    candidates: Mapping[str, Mapping[str, Mapping[str, set[str]]]],
    *,
    canonical_by_owner: Mapping[str, str],
    reserved_aliases: Mapping[str, str] | None = None,
) -> tuple[dict[str, dict[str, list[str]]], list[dict[str, Any]]]:
    reserved_aliases = reserved_aliases or {}
    index: dict[str, dict[str, int]] = defaultdict(dict)
    display: dict[str, set[str]] = defaultdict(set)
    for owner, languages in candidates.items():
        for aliases in languages.values():
            for alias, origins in aliases.items():
                normalized = _normalize_alias(alias)
                if not normalized:
                    continue
                priority = max(ORIGIN_PRIORITY.get(origin, 0) for origin in origins)
                index[normalized][owner] = max(index[normalized].get(owner, 0), priority)
                display[normalized].add(alias)

    blocked: dict[str, set[str]] = defaultdict(set)
    collisions: list[dict[str, Any]] = []
    for normalized, owners in sorted(index.items()):
        if normalized in reserved_aliases:
            blocked[normalized].update(owners)
            collisions.append(
                {
                    "aliases": sorted(display[normalized]),
                    "owners": sorted(owners),
                    "kept_owner": reserved_aliases[normalized],
                    "reason": "region_alias_conflict",
                }
            )
            continue
        if len(owners) <= 1:
            continue
        canonical_owners = [
            owner
            for owner in owners
            if _normalize_alias(canonical_by_owner.get(owner, "")) == normalized
        ]
        if len(canonical_owners) == 1:
            kept_owner = canonical_owners[0]
        else:
            best = max(owners.values())
            best_owners = [owner for owner, score in owners.items() if score == best]
            kept_owner = best_owners[0] if len(best_owners) == 1 else None
        for owner in owners:
            if owner != kept_owner:
                blocked[normalized].add(owner)
        collisions.append(
            {
                "aliases": sorted(display[normalized]),
                "owners": sorted(owners),
                "kept_owner": kept_owner,
                "reason": "same_alias_for_multiple_entities",
            }
        )

    resolved: dict[str, dict[str, list[str]]] = {}
    for owner, languages in candidates.items():
        resolved[owner] = {}
        for language, aliases in languages.items():
            values = [
                alias
                for alias in aliases
                if owner not in blocked.get(_normalize_alias(alias), set())
            ]
            resolved[owner][language] = sorted(
                set(values), key=lambda value: (-len(value), value.casefold())
            )
    return resolved, collisions


def _suggest_themes(
    rows: Sequence[Mapping[str, Any]], themes: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    fields = (
        "place_name",
        "description",
        "scene_elements",
        "activity",
        "mood",
        "theme_category",
    )
    for theme in themes:
        theme_id = _text(theme.get("id"))
        if not theme_id:
            continue
        terms = _string_list(theme.get("terms", []))
        strong_terms = set(_string_list(theme.get("strong_terms", [])))
        activity_terms = set(_string_list(theme.get("activity_terms", [])))
        route_terms = set(_string_list(theme.get("route_terms", [])))
        evidence: list[dict[str, Any]] = []
        matched_all: set[str] = set()
        strong_found = False
        for row in rows:
            field_matches: dict[str, list[str]] = {}
            for field in fields:
                text = _searchable_text(row.get(field))
                matches = [term for term in terms if _contains_term(text, term)]
                if matches:
                    field_matches[field] = sorted(set(matches))
                    matched_all.update(matches)
            activity_text = _searchable_text(row.get("activity"))
            activity_found = [
                term for term in activity_terms if _contains_term(activity_text, term)
            ]
            route_text = " ".join(
                _searchable_text(row.get(field)) for field in fields
            )
            route_found = [term for term in route_terms if _contains_term(route_text, term)]
            if set(matched_all) & strong_terms or activity_found:
                strong_found = True
            if field_matches or activity_found or route_found:
                evidence.append(
                    {
                        "segment_id": _text(row.get("segment_id")),
                        "field_matches": field_matches,
                        "activity_terms": sorted(activity_found),
                        "route_terms": sorted(route_found),
                    }
                )
        time_match = any(
            _text(row.get("time_of_day")) in set(_string_list(theme.get("time_values", [])))
            for row in rows
        )
        season_match = any(
            _text(row.get("season")) in set(_string_list(theme.get("season_values", [])))
            for row in rows
        )
        if time_match:
            strong_found = True
        if strong_found or len(matched_all) >= 2 or (matched_all and season_match):
            suggestions.append(
                {
                    "theme_id": theme_id,
                    "label": _text(theme.get("label")),
                    "matched_terms": sorted(matched_all),
                    "time_match": time_match,
                    "season_match": season_match,
                    "evidence": evidence,
                    "status": "human_review_required",
                }
            )
    return suggestions


def _searchable_text(value: object) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        value = " ".join(str(item) for item in value)
    return unicodedata.normalize("NFKC", str(value or "")).casefold().replace("_", " ")


def _contains_term(text: str, term: str) -> bool:
    cleaned = _searchable_text(term).strip()
    if not cleaned:
        return False
    pattern = rf"(?<![0-9a-z가-힣]){re.escape(cleaned)}(?![0-9a-z가-힣])"
    return re.search(pattern, text) is not None


def _id_sort_key(value: str) -> tuple[str, int, str]:
    match = re.match(r"^([A-Za-z]+)(\d+)$", value)
    if match:
        return (match.group(1), int(match.group(2)), value)
    return (value, 10**9, value)


def _resolved_or_none(path: str | Path | None) -> str | None:
    return str(Path(path).resolve()) if path is not None else None


def _optional_positive_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("embedding_dimension은 양의 정수여야 합니다.")
    return value


def _optional_nonnegative_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError("embedding_norm_tolerance은 0 이상의 숫자여야 합니다.")
    return float(value)


def _file_manifest(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    resolved = Path(path).resolve()
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(resolved),
        "size_bytes": resolved.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def _write_json_atomic(path: Path, value: object) -> None:
    _write_text_atomic(
        path,
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
    )


def _write_text_atomic(path: Path, value: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _render_summary(report: Mapping[str, Any]) -> str:
    summary = _required_mapping(report.get("summary"), "summary")
    diff = _required_mapping(report.get("metadata_diff"), "metadata_diff")
    return "\n".join(
        [
            "# K-Tour AI 신규 검색 데이터 자동화 결과",
            "",
            f"- SCENE: {summary['scene_count']}건",
            f"- 원본 구간: {summary['source_segment_count']}건",
            f"- 장소: {summary['place_count']}곳",
            f"- 작품: {summary['drama_title_count']}개",
            f"- 신규/변경/삭제 SCENE: {summary['added_scene_count']} / {summary['changed_scene_count']} / {summary['removed_scene_count']}",
            f"- 차단 오류: {summary['blocking_error_count']}건",
            f"- 사람 검수 항목: {summary['review_item_count']}건",
            f"- 카탈로그 검수 항목: {summary['catalog_review_count']}건",
            f"- 카탈로그 바로 반영 가능: {summary['safe_to_publish_generated_catalogs']}",
            f"- 테마 검수 대상 원본 구간: {summary['theme_review_source_count']}건",
            "",
            "## 신규 검색 영향",
            "",
            f"- 신규 작품: {', '.join(diff.get('new_drama_titles', [])) or '없음'}",
            f"- 신규 장소 ID: {', '.join(diff.get('new_place_ids', [])) or '없음'}",
            "",
            "생성 파일은 후보 자산입니다. `search_review_queue.json`의 충돌·검수 항목을 확인한 뒤 검색 서비스에 반영하세요.",
            "원본 metadata, embedding, DB는 수정하지 않았습니다.",
            "",
        ]
    )
