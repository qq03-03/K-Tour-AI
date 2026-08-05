"""표시용 다국어 번역의 의미 보존과 UI 자연스러움을 자동 평가한다."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field


DEFAULT_QA_MODEL = "gpt-5.6-luna"
QA_LANGUAGES = ("ko", "en", "ja", "zh")


class LanguageAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    faithful: bool
    natural_for_ui: bool
    has_added_or_missing_facts: bool
    issue_summary_ko: str


class ItemAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int = Field(ge=1)
    ko: LanguageAssessment
    en: LanguageAssessment
    ja: LanguageAssessment
    zh: LanguageAssessment


class QABatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[ItemAssessment]


QA_SYSTEM_PROMPT = """You are a strict multilingual localization QA reviewer.
Compare each ko/en/ja/zh translation with the authoritative source metadata.
Judge semantic faithfulness, naturalness for a short tourism search-result UI, and whether facts were added or omitted.
Names, places, IDs, seasons, and times are handled outside this request; evaluate only description, mood, activity, and scene_elements.
Short tag wording may differ if meaning is preserved. Do not fail harmless word-order or style differences.
Mark faithful=false for meaning changes, wrong actions/scenery/mood, or important omissions.
Mark natural_for_ui=false only for clearly awkward, broken, or misleading wording.
Write issue_summary_ko in concise Korean. Use an empty string when there is no issue.
Keep the anonymous numeric item_id unchanged."""


class OpenAIDisplayTranslationQA:
    def __init__(self, *, model: str | None = None, client: Any | None = None) -> None:
        self.model = model or os.getenv("OPENAI_TRANSLATION_QA_MODEL", DEFAULT_QA_MODEL)
        self._client = client or OpenAI()

    def evaluate_batch(
        self,
        source_records: Sequence[Mapping[str, Any]],
        translation_records: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        translation_index = {
            (_text(item.get("segment_id")), _text(item.get("keyframe_id"))): item
            for item in translation_records
        }
        outbound: list[dict[str, Any]] = []
        local_keys: dict[int, tuple[str, str]] = {}
        for item_id, source_record in enumerate(source_records, start=1):
            key = (_text(source_record.get("segment_id")), _text(source_record.get("keyframe_id")))
            translated = translation_index.get(key)
            if translated is None:
                raise ValueError(f"번역 레코드 누락: {key[0]}/{key[1]}")
            translations = translated.get("translations")
            if not isinstance(translations, Mapping):
                raise ValueError("translations는 객체여야 합니다.")
            source = source_record.get("source")
            if not isinstance(source, Mapping):
                raise ValueError("source는 객체여야 합니다.")
            local_keys[item_id] = key
            outbound.append(
                {
                    "item_id": item_id,
                    "source": _semantic_fields(source),
                    "translations": {
                        language: _semantic_fields(translations[language])
                        for language in QA_LANGUAGES
                    },
                }
            )

        response = self._client.responses.parse(
            model=self.model,
            reasoning={"effort": "none"},
            text={"verbosity": "low"},
            prompt_cache_key="k-tour-display-translation-qa-v1",
            input=[
                {"role": "system", "content": QA_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"records": outbound}, ensure_ascii=False)},
            ],
            text_format=QABatchResponse,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("OpenAI 번역 QA 응답이 비어 있습니다.")
        assessments = [item.model_dump() for item in parsed.records]
        actual_ids = {item["item_id"] for item in assessments}
        expected_ids = set(local_keys)
        if actual_ids != expected_ids or len(assessments) != len(expected_ids):
            raise ValueError(
                f"번역 QA 임시 번호 불일치: missing={expected_ids-actual_ids}, extra={actual_ids-expected_ids}"
            )

        results: list[dict[str, Any]] = []
        for assessment in assessments:
            item_id = assessment.pop("item_id")
            segment_id, keyframe_id = local_keys[item_id]
            failed_languages = [
                language
                for language in QA_LANGUAGES
                if not assessment[language]["faithful"]
                or not assessment[language]["natural_for_ui"]
                or assessment[language]["has_added_or_missing_facts"]
            ]
            results.append(
                {
                    "segment_id": segment_id,
                    "keyframe_id": keyframe_id,
                    "passed": not failed_languages,
                    "failed_languages": failed_languages,
                    "assessments": assessment,
                }
            )
        return results


def build_qa_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    failed = [item for item in records if not item.get("passed")]
    by_language = {
        language: sum(language in item.get("failed_languages", []) for item in records)
        for language in QA_LANGUAGES
    }
    return {
        "record_count": len(records),
        "passed_count": len(records) - len(failed),
        "review_count": len(failed),
        "by_language_review_count": by_language,
    }


def _semantic_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "description": _text(payload.get("description")),
        "mood": _string_list(payload.get("mood")),
        "activity": _string_list(payload.get("activity")),
        "scene_elements": _string_list(payload.get("scene_elements")),
    }


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("문자열 값이 비어 있습니다.")
    return value.strip()


def _string_list(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("태그는 문자열 배열이어야 합니다.")
    return [_text(item) for item in value]
