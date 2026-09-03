"""검색 결과 표시용 다국어 번역 데이터의 준비·검증·적용 도구."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any


DISPLAY_LANGUAGES = ("ko", "en", "ja", "zh")
TEXT_FIELDS = (
    "drama_title",
    "place_name",
    "region",
    "season",
    "time_of_day",
    "description",
)
LIST_FIELDS = ("mood", "activity", "scene_elements")
LOCALIZABLE_FIELDS = TEXT_FIELDS + LIST_FIELDS


def load_json(path: str | Path) -> object:
    """UTF-8 BOM 유무와 관계없이 JSON을 읽는다."""

    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def derive_keyframe_id(record: Mapping[str, Any]) -> str:
    """임베딩 DB와 같은 segment_id__파일명 형식의 keyframe_id를 만든다."""

    segment_id = _required_text(record.get("segment_id"), "segment_id")
    explicit = _clean_text(record.get("keyframe_id"))
    if explicit:
        return canonical_keyframe_id(segment_id, explicit)
    keyframe_path = _clean_text(record.get("keyframe_path")).replace("\\", "/")
    if not keyframe_path:
        raise ValueError("keyframe_id 또는 keyframe_path가 필요합니다.")
    keyframe_stem = PurePosixPath(keyframe_path).stem
    if not keyframe_stem:
        raise ValueError(f"keyframe_path에서 ID를 만들 수 없습니다: {keyframe_path}")
    return canonical_keyframe_id(segment_id, keyframe_stem)


def canonical_keyframe_id(segment_id: str, keyframe_id: str) -> str:
    """기존 파일명 ID도 임베딩 DB의 정규 keyframe_id로 변환한다."""

    segment = _required_text(segment_id, "segment_id")
    keyframe = _required_text(keyframe_id, "keyframe_id")
    prefix = f"{segment}__"
    return keyframe if keyframe.startswith(prefix) else prefix + keyframe


def build_translation_source(metadata_payload: object) -> dict[str, Any]:
    """VLM metadata를 외부 번역에 사용할 최소 입력 데이터로 변환한다."""

    records = _metadata_records(metadata_payload)
    prepared: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for index, record in enumerate(records):
        segment_id = _required_text(record.get("segment_id"), f"metadata[{index}].segment_id")
        keyframe_id = derive_keyframe_id(record)
        composite_key = (segment_id, keyframe_id)
        if composite_key in seen_keys:
            raise ValueError(f"번역 연결 키가 중복됐습니다: {segment_id}/{keyframe_id}")
        seen_keys.add(composite_key)

        source: dict[str, Any] = {}
        for field_name in TEXT_FIELDS:
            source[field_name] = _required_text(
                record.get(field_name),
                f"metadata[{index}].{field_name}",
            )
        for field_name in LIST_FIELDS:
            source[field_name] = _string_list(
                record.get(field_name),
                f"metadata[{index}].{field_name}",
            )

        prepared.append(
            {
                "segment_id": segment_id,
                "keyframe_id": keyframe_id,
                "video_id": _required_text(record.get("video_id"), f"metadata[{index}].video_id"),
                "place_id": _required_text(record.get("place_id"), f"metadata[{index}].place_id"),
                "keyframe_path": _required_text(
                    record.get("keyframe_path"),
                    f"metadata[{index}].keyframe_path",
                ).replace("\\", "/"),
                "source": source,
            }
        )

    return {
        "schema_version": 1,
        "purpose": "display_localization_only_no_reembedding",
        "target_languages": list(DISPLAY_LANGUAGES),
        "record_count": len(prepared),
        "records": prepared,
    }


def validate_translation_catalog(
    payload: object,
    *,
    expected_source: object | None = None,
    require_all_languages: bool = True,
) -> dict[str, Any]:
    """번역 카탈로그의 언어·ID·필드 구성을 검증한다."""

    if not isinstance(payload, Mapping):
        raise ValueError("번역 카탈로그는 JSON 객체여야 합니다.")
    raw_records = payload.get("records")
    if isinstance(raw_records, (str, bytes)) or not isinstance(raw_records, Sequence):
        raise ValueError("번역 카탈로그의 records는 배열이어야 합니다.")

    expected_keys: set[tuple[str, str]] | None = None
    if expected_source is not None:
        source = build_translation_source(expected_source)
        expected_keys = {
            (item["segment_id"], item["keyframe_id"])
            for item in source["records"]
        }

    normalized_records: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, Mapping):
            raise ValueError(f"records[{index}]는 객체여야 합니다.")
        segment_id = _required_text(raw_record.get("segment_id"), f"records[{index}].segment_id")
        keyframe_id = canonical_keyframe_id(
            segment_id,
            _required_text(raw_record.get("keyframe_id"), f"records[{index}].keyframe_id"),
        )
        composite_key = (segment_id, keyframe_id)
        if composite_key in seen_keys:
            raise ValueError(f"번역 레코드가 중복됐습니다: {segment_id}/{keyframe_id}")
        seen_keys.add(composite_key)

        translations = raw_record.get("translations")
        if not isinstance(translations, Mapping):
            raise ValueError(f"records[{index}].translations는 객체여야 합니다.")
        unknown_languages = sorted(set(translations) - set(DISPLAY_LANGUAGES))
        if unknown_languages:
            raise ValueError(f"지원하지 않는 번역 언어: {', '.join(unknown_languages)}")
        if require_all_languages:
            missing_languages = [lang for lang in DISPLAY_LANGUAGES if lang not in translations]
            if missing_languages:
                raise ValueError(
                    f"{segment_id}/{keyframe_id} 번역 언어 누락: {', '.join(missing_languages)}"
                )

        normalized_translations: dict[str, dict[str, Any]] = {}
        for language, localized in translations.items():
            if not isinstance(localized, Mapping):
                raise ValueError(
                    f"{segment_id}/{keyframe_id}/{language} 번역은 객체여야 합니다."
                )
            missing_fields = [field for field in LOCALIZABLE_FIELDS if field not in localized]
            if missing_fields:
                raise ValueError(
                    f"{segment_id}/{keyframe_id}/{language} 필드 누락: "
                    + ", ".join(missing_fields)
                )
            values: dict[str, Any] = {}
            for field_name in TEXT_FIELDS:
                values[field_name] = _required_text(
                    localized.get(field_name),
                    f"{segment_id}/{keyframe_id}/{language}.{field_name}",
                )
            for field_name in LIST_FIELDS:
                values[field_name] = _string_list(
                    localized.get(field_name),
                    f"{segment_id}/{keyframe_id}/{language}.{field_name}",
                )
            normalized_translations[str(language)] = values

        normalized_records.append(
            {
                "segment_id": segment_id,
                "keyframe_id": keyframe_id,
                "translations": normalized_translations,
            }
        )

    if expected_keys is not None:
        missing = sorted(expected_keys - seen_keys)
        stale = sorted(seen_keys - expected_keys)
        if missing or stale:
            parts: list[str] = []
            if missing:
                parts.append(f"metadata 기준 누락 {len(missing)}건")
            if stale:
                parts.append(f"metadata에 없는 번역 {len(stale)}건")
            raise ValueError("번역 ID 연결 실패: " + ", ".join(parts))

    return {
        **dict(payload),
        "record_count": len(normalized_records),
        "records": normalized_records,
    }


def localize_search_result(
    result: Mapping[str, Any],
    *,
    lang: str,
    catalog: Mapping[str, Any],
    fallback_lang: str = "ko",
) -> dict[str, Any]:
    """검색 점수와 ID는 유지하고 표시 필드만 요청 언어로 교체한다."""

    requested = normalize_display_language(lang)
    fallback = normalize_display_language(fallback_lang)
    segment_id = _required_text(result.get("segment_id"), "result.segment_id")
    keyframe_id = derive_keyframe_id(result)
    translation_index = _translation_index(catalog)
    translations = translation_index.get((segment_id, keyframe_id), {})
    localized = translations.get(requested) or translations.get(fallback)

    output = dict(result)
    output["requested_lang"] = requested
    if localized is None:
        output["display_lang"] = "source"
        return output
    for field_name in LOCALIZABLE_FIELDS:
        if field_name in localized:
            value = localized[field_name]
            output[field_name] = list(value) if field_name in LIST_FIELDS else value
    output["display_lang"] = requested if requested in translations else fallback
    return output


def localize_search_results(
    results: Sequence[Mapping[str, Any]],
    *,
    lang: str,
    catalog: Mapping[str, Any],
    fallback_lang: str = "ko",
) -> list[dict[str, Any]]:
    """검색 결과 배열 전체에 표시용 번역을 적용한다."""

    return [
        localize_search_result(
            result,
            lang=lang,
            catalog=catalog,
            fallback_lang=fallback_lang,
        )
        for result in results
    ]


def normalize_display_language(value: str) -> str:
    """ja-JP/zh-CN 같은 요청을 프로젝트 언어 코드로 정규화한다."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("lang은 빈 문자열이 아니어야 합니다.")
    normalized = value.strip().lower().replace("_", "-")
    if normalized == "auto":
        return "ko"
    primary = normalized.split("-", 1)[0]
    if primary not in DISPLAY_LANGUAGES:
        raise ValueError("lang은 ko/en/ja/zh 중 하나여야 합니다.")
    return primary


def _translation_index(
    catalog: Mapping[str, Any],
) -> dict[tuple[str, str], Mapping[str, Mapping[str, Any]]]:
    raw_records = catalog.get("records")
    if isinstance(raw_records, (str, bytes)) or not isinstance(raw_records, Sequence):
        raise ValueError("번역 카탈로그의 records는 배열이어야 합니다.")
    index: dict[tuple[str, str], Mapping[str, Mapping[str, Any]]] = {}
    for record in raw_records:
        if not isinstance(record, Mapping):
            raise ValueError("번역 records 항목은 객체여야 합니다.")
        segment_id = _required_text(record.get("segment_id"), "translation.segment_id")
        key = (
            segment_id,
            canonical_keyframe_id(
                segment_id,
                _required_text(record.get("keyframe_id"), "translation.keyframe_id"),
            ),
        )
        if key in index:
            raise ValueError(f"번역 레코드가 중복됐습니다: {key[0]}/{key[1]}")
        translations = record.get("translations")
        if not isinstance(translations, Mapping):
            raise ValueError("translation.translations는 객체여야 합니다.")
        index[key] = translations  # type: ignore[assignment]
    return index


def _metadata_records(payload: object) -> list[Mapping[str, Any]]:
    raw_records = payload.get("segments") if isinstance(payload, Mapping) else payload
    if (
        isinstance(raw_records, (str, bytes))
        or not isinstance(raw_records, Sequence)
        or not raw_records
    ):
        raise ValueError("metadata는 하나 이상의 레코드를 가진 배열이어야 합니다.")
    records: list[Mapping[str, Any]] = []
    for index, record in enumerate(raw_records):
        if not isinstance(record, Mapping):
            raise ValueError(f"metadata[{index}]는 객체여야 합니다.")
        records.append(record)
    return records


def _clean_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _required_text(value: object, field_name: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        raise ValueError(f"{field_name}은 빈 문자열이 아니어야 합니다.")
    return cleaned


def _string_list(value: object, field_name: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name}은 문자열 배열이어야 합니다.")
    return [_required_text(item, field_name) for item in value]
