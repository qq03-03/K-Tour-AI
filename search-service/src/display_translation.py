"""OpenAI를 이용한 검색 결과 표시용 메타데이터 번역."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from .display_localization import DISPLAY_LANGUAGES, validate_translation_catalog


DEFAULT_TRANSLATION_MODEL = "gpt-5.6-luna"
SEMANTIC_LANGUAGES = DISPLAY_LANGUAGES


class SemanticTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)
    mood: list[str]
    activity: list[str]
    scene_elements: list[str]


class TranslationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int = Field(ge=1)
    ko: SemanticTranslation
    en: SemanticTranslation
    ja: SemanticTranslation
    zh: SemanticTranslation


class TranslationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[TranslationItem]


TRANSLATION_SYSTEM_PROMPT = """You localize tourism search-result metadata for UI display.
Translate only the supplied description, mood, activity, and scene_elements into Korean (ko), English (en), Japanese (ja), and Simplified Chinese (zh).
Keep the anonymous numeric item_id exactly unchanged.
Preserve the number and order of every list. An empty list must remain empty.
Do not add facts, places, seasons, activities, people, or scenery that are absent from the source.
Use short natural UI tags for list values and one faithful sentence for description.
This output is display text only and must not alter search meaning."""


def translation_source_hash(record: Mapping[str, Any]) -> str:
    """Return a stable hash for fields that are sent to the translation API."""

    source = record.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("translation source 레코드에 source가 필요합니다.")
    semantic = {
        "description": _text(source.get("description"), "description"),
        "mood": _list(source.get("mood"), "mood"),
        "activity": _list(source.get("activity"), "activity"),
        "scene_elements": _list(source.get("scene_elements"), "scene_elements"),
    }
    serialized = json.dumps(
        semantic,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def plan_incremental_translations(
    source_records: Sequence[Mapping[str, Any]],
    completed_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Split a checkpoint into reusable, pending, changed, and stale records."""

    source_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in source_records:
        key = (
            _text(record.get("segment_id"), "segment_id"),
            _text(record.get("keyframe_id"), "keyframe_id"),
        )
        if key in source_index:
            raise ValueError(f"번역 source ID 중복: {key[0]}/{key[1]}")
        source_index[key] = record

    completed_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in completed_records:
        key = (
            _text(record.get("segment_id"), "segment_id"),
            _text(record.get("keyframe_id"), "keyframe_id"),
        )
        if key in completed_index:
            raise ValueError(f"번역 checkpoint ID 중복: {key[0]}/{key[1]}")
        completed_index[key] = record

    reusable: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    added_keys: list[tuple[str, str]] = []
    changed_keys: list[tuple[str, str]] = []
    for key, source_record in source_index.items():
        completed = completed_index.get(key)
        expected_hash = translation_source_hash(source_record)
        if completed is None:
            pending.append(dict(source_record))
            added_keys.append(key)
        elif completed.get("source_hash") != expected_hash:
            pending.append(dict(source_record))
            changed_keys.append(key)
        else:
            reusable.append(dict(completed))

    stale_keys = sorted(set(completed_index) - set(source_index))
    return {
        "reusable": reusable,
        "pending": pending,
        "added_keys": sorted(added_keys),
        "changed_keys": sorted(changed_keys),
        "stale_keys": stale_keys,
    }


REGION_NAMES: dict[str, dict[str, str]] = {
    "서울특별시": {"ko": "서울특별시", "en": "Seoul", "ja": "ソウル特別市", "zh": "首尔特别市"},
    "인천광역시": {"ko": "인천광역시", "en": "Incheon", "ja": "仁川広域市", "zh": "仁川广域市"},
    "경기도": {"ko": "경기도", "en": "Gyeonggi-do", "ja": "京畿道", "zh": "京畿道"},
    "강원특별자치도": {"ko": "강원특별자치도", "en": "Gangwon State", "ja": "江原特別自治道", "zh": "江原特别自治道"},
    "전북특별자치도": {"ko": "전북특별자치도", "en": "Jeonbuk State", "ja": "全北特別自治道", "zh": "全北特别自治道"},
    "경상북도": {"ko": "경상북도", "en": "Gyeongsangbuk-do", "ja": "慶尚北道", "zh": "庆尚北道"},
    "제주특별자치도": {"ko": "제주특별자치도", "en": "Jeju Special Self-Governing Province", "ja": "済州特別自治道", "zh": "济州特别自治道"},
}

SEASON_NAMES: dict[str, dict[str, str]] = {
    "봄": {"ko": "봄", "en": "spring", "ja": "春", "zh": "春季"},
    "여름": {"ko": "여름", "en": "summer", "ja": "夏", "zh": "夏季"},
    "가을": {"ko": "가을", "en": "autumn", "ja": "秋", "zh": "秋季"},
    "겨울": {"ko": "겨울", "en": "winter", "ja": "冬", "zh": "冬季"},
}

TIME_NAMES: dict[str, dict[str, str]] = {
    "dawn": {"ko": "새벽", "en": "dawn", "ja": "明け方", "zh": "黎明"},
    "morning": {"ko": "아침", "en": "morning", "ja": "朝", "zh": "早晨"},
    "day": {"ko": "낮", "en": "daytime", "ja": "昼", "zh": "白天"},
    "daytime": {"ko": "낮", "en": "daytime", "ja": "昼", "zh": "白天"},
    "evening": {"ko": "저녁", "en": "evening", "ja": "夕方", "zh": "傍晚"},
    "sunset": {"ko": "해질녘", "en": "sunset", "ja": "日没", "zh": "日落"},
    "night": {"ko": "밤", "en": "night", "ja": "夜", "zh": "夜晚"},
}


class OpenAIDisplayTranslator:
    """배치 입력을 세 언어의 구조화된 표시 문구로 번역한다."""

    def __init__(
        self,
        *,
        model: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model or os.getenv("OPENAI_TRANSLATION_MODEL", DEFAULT_TRANSLATION_MODEL)
        self._client = client or OpenAI()

    def translate_batch(self, records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        if not records:
            return []
        inputs: list[dict[str, Any]] = []
        expected_item_ids: set[int] = set()
        local_keys: dict[int, tuple[str, str]] = {}
        expected_lengths: dict[int, dict[str, int]] = {}
        for item_id, record in enumerate(records, start=1):
            segment_id = _text(record.get("segment_id"), "segment_id")
            keyframe_id = _text(record.get("keyframe_id"), "keyframe_id")
            source = record.get("source")
            if not isinstance(source, Mapping):
                raise ValueError(f"{segment_id}/{keyframe_id}: source가 필요합니다.")
            key = (segment_id, keyframe_id)
            if key in local_keys.values():
                raise ValueError(f"번역 배치 ID 중복: {segment_id}/{keyframe_id}")
            expected_item_ids.add(item_id)
            local_keys[item_id] = key
            semantic = {
                "description": _text(source.get("description"), "description"),
                "mood": _list(source.get("mood"), "mood"),
                "activity": _list(source.get("activity"), "activity"),
                "scene_elements": _list(source.get("scene_elements"), "scene_elements"),
            }
            expected_lengths[item_id] = {
                field: len(semantic[field]) for field in ("mood", "activity", "scene_elements")
            }
            inputs.append(
                {
                    "item_id": item_id,
                    **semantic,
                }
            )

        response = self._client.responses.parse(
            model=self.model,
            reasoning={"effort": "none"},
            text={"verbosity": "low"},
            prompt_cache_key="k-tour-display-translation-v1",
            input=[
                {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps({"records": inputs}, ensure_ascii=False),
                },
            ],
            text_format=TranslationBatch,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("OpenAI 번역 응답이 비어 있습니다.")
        raw_output = [item.model_dump() for item in parsed.records]
        actual_item_ids = {item["item_id"] for item in raw_output}
        if actual_item_ids != expected_item_ids or len(raw_output) != len(expected_item_ids):
            missing = expected_item_ids - actual_item_ids
            extra = actual_item_ids - expected_item_ids
            raise ValueError(f"OpenAI 번역 임시 번호 불일치: missing={missing}, extra={extra}")
        output: list[dict[str, Any]] = []
        for item in raw_output:
            item_id = item.pop("item_id")
            key = local_keys[item_id]
            for language in SEMANTIC_LANGUAGES:
                for field, expected_length in expected_lengths[item_id].items():
                    actual_length = len(item[language][field])
                    if actual_length != expected_length:
                        raise ValueError(
                            f"{key[0]}/{key[1]}/{language}.{field} 배열 길이 불일치: "
                            f"{actual_length} != {expected_length}"
                        )
            output.append(
                {
                    "segment_id": key[0],
                    "keyframe_id": key[1],
                    **item,
                }
            )
        return output


def build_display_translation_catalog(
    source_payload: Mapping[str, Any],
    semantic_records: Sequence[Mapping[str, Any]],
    *,
    location_alias_payload: Mapping[str, Any],
    drama_alias_payload: Mapping[str, Any],
    model: str,
    overrides_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """API 번역과 검증된 명칭 사전을 하나의 백엔드 전달 파일로 결합한다."""

    raw_source_records = source_payload.get("records")
    if isinstance(raw_source_records, (str, bytes)) or not isinstance(raw_source_records, Sequence):
        raise ValueError("source records가 필요합니다.")
    semantic_index = {
        (_text(item.get("segment_id"), "segment_id"), _text(item.get("keyframe_id"), "keyframe_id")): item
        for item in semantic_records
    }
    place_names = _place_name_index(location_alias_payload)
    drama_names = _drama_name_index(drama_alias_payload)

    output_records: list[dict[str, Any]] = []
    for source_record in raw_source_records:
        if not isinstance(source_record, Mapping):
            raise ValueError("source record는 객체여야 합니다.")
        segment_id = _text(source_record.get("segment_id"), "segment_id")
        keyframe_id = _text(source_record.get("keyframe_id"), "keyframe_id")
        place_id = _text(source_record.get("place_id"), "place_id")
        source = source_record.get("source")
        if not isinstance(source, Mapping):
            raise ValueError(f"{segment_id}/{keyframe_id}: source가 필요합니다.")
        semantic = semantic_index.get((segment_id, keyframe_id))
        if semantic is None:
            raise ValueError(f"API 번역 누락: {segment_id}/{keyframe_id}")

        translations: dict[str, dict[str, Any]] = {}
        for language in DISPLAY_LANGUAGES:
            semantic_values = semantic.get(language)
            if semantic_values is None and language == "en":
                semantic_values = {
                    "description": _text(source.get("description"), "description"),
                    "mood": _list(source.get("mood"), "mood"),
                    "activity": _list(source.get("activity"), "activity"),
                    "scene_elements": _list(source.get("scene_elements"), "scene_elements"),
                }
            if semantic_values is None:
                raise ValueError(f"API 번역 누락: {segment_id}/{keyframe_id}/{language}")
            drama_title = _text(source.get("drama_title"), "drama_title")
            region = _text(source.get("region"), "region")
            season = _text(source.get("season"), "season")
            time_of_day = _text(source.get("time_of_day"), "time_of_day")
            translations[language] = {
                "drama_title": drama_names.get(drama_title, {}).get(language, drama_title),
                "place_name": place_names.get(place_id, {}).get(
                    language, _text(source.get("place_name"), "place_name")
                ),
                "region": REGION_NAMES.get(region, {}).get(language, region),
                "season": SEASON_NAMES.get(season, {}).get(language, season),
                "time_of_day": TIME_NAMES.get(time_of_day.lower(), {}).get(language, time_of_day),
                "description": semantic_values["description"],
                "mood": list(semantic_values["mood"]),
                "activity": list(semantic_values["activity"]),
                "scene_elements": list(semantic_values["scene_elements"]),
            }
        output_records.append(
            {
                "segment_id": segment_id,
                "keyframe_id": keyframe_id,
                "translations": translations,
            }
        )

    catalog = {
        "schema_version": 1,
        "purpose": "display_localization_only_no_reembedding",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "languages": list(DISPLAY_LANGUAGES),
        "records": output_records,
    }
    if overrides_payload is not None:
        _apply_overrides(catalog, overrides_payload)
    return validate_translation_catalog(catalog, require_all_languages=True)


def write_checkpoint(
    path: str | Path,
    *,
    model: str,
    completed: Sequence[Mapping[str, Any]],
) -> None:
    Path(path).write_text(
        json.dumps(
            {"schema_version": 1, "model": model, "completed": list(completed)},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_checkpoint(path: str | Path) -> list[dict[str, Any]]:
    checkpoint = Path(path)
    if not checkpoint.is_file():
        return []
    payload = json.loads(checkpoint.read_text(encoding="utf-8-sig"))
    completed = payload.get("completed", [])
    if not isinstance(completed, list):
        raise ValueError("체크포인트 completed는 배열이어야 합니다.")
    return completed


def _place_name_index(payload: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for item in payload.get("place_aliases", []):
        place_id = _text(item.get("place_id"), "place_id")
        canonical = _text(item.get("place_name"), "place_name")
        aliases = item.get("aliases", {})
        result[place_id] = {
            language: _preferred_alias(aliases, language, canonical)
            for language in DISPLAY_LANGUAGES
        }
    return result


def _drama_name_index(payload: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for item in payload.get("titles", []):
        canonical = _text(item.get("canonical_title"), "canonical_title")
        aliases = item.get("aliases", {})
        result[canonical] = {
            language: _preferred_alias(aliases, language, canonical)
            for language in DISPLAY_LANGUAGES
        }
    return result


def _preferred_alias(aliases: object, language: str, fallback: str) -> str:
    if not isinstance(aliases, Mapping):
        return fallback
    values = aliases.get(language)
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)) and values:
        candidates = [_text(value, language) for value in values]
        if language == "zh":
            traditional_markers = set("們氣會單燦爛愛無島藍調時屍戰鮮盡來見魯納與為這個處廣華學國臺灣門宮場園縣區鄉鎮裡邊")
            return min(candidates, key=lambda value: sum(char in traditional_markers for char in value))
        return candidates[0]
    return fallback


def _apply_overrides(catalog: dict[str, Any], payload: Mapping[str, Any]) -> None:
    raw_overrides = payload.get("records", [])
    if isinstance(raw_overrides, (str, bytes)) or not isinstance(raw_overrides, Sequence):
        raise ValueError("번역 override records는 배열이어야 합니다.")
    index = {
        (item["segment_id"], item["keyframe_id"]): item
        for item in catalog["records"]
    }
    for override in raw_overrides:
        if not isinstance(override, Mapping):
            raise ValueError("번역 override 항목은 객체여야 합니다.")
        key = (_text(override.get("segment_id"), "segment_id"), _text(override.get("keyframe_id"), "keyframe_id"))
        target = index.get(key)
        if target is None:
            raise ValueError(f"metadata에 없는 번역 override: {key[0]}/{key[1]}")
        translations = override.get("translations")
        if not isinstance(translations, Mapping):
            raise ValueError("번역 override translations는 객체여야 합니다.")
        for language, fields in translations.items():
            if language not in DISPLAY_LANGUAGES or not isinstance(fields, Mapping):
                raise ValueError(f"잘못된 번역 override 언어: {language}")
            for field_name, value in fields.items():
                if field_name not in target["translations"][language]:
                    raise ValueError(f"잘못된 번역 override 필드: {field_name}")
                target["translations"][language][field_name] = value


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}은 빈 문자열이 아니어야 합니다.")
    return value.strip()


def _list(value: object, field_name: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name}은 문자열 배열이어야 합니다.")
    return [_text(item, field_name) for item in value]
