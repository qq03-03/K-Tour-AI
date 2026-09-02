"""place_id별 한국어 주소를 영·일·중 표시 주소로 번역하고 검증한다."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field


class AddressTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    place_id: str = Field(min_length=1)
    en: str = Field(min_length=1)
    ja: str = Field(min_length=1)
    zh: str = Field(min_length=1)


class AddressTranslationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    translations: list[AddressTranslation]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="K-Tour place_id 주소 표시언어 생성")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--review-output", type=Path)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY 환경변수가 없습니다.")
    if args.batch_size < 1 or args.max_retries < 1:
        raise SystemExit("batch-size와 max-retries는 1 이상이어야 합니다.")
    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"출력 파일이 이미 있습니다: {args.output}")

    catalog = _mapping(_read_json(args.input), "input catalog")
    records = _mapping_list(catalog.get("records"), "records")
    source_rows = []
    for record in records:
        place_id = _required_text(record.get("place_id"), "place_id")
        localized = _mapping(record.get("localized"), f"{place_id}.localized")
        ko = _mapping(localized.get("ko"), f"{place_id}.localized.ko")
        address = str(ko.get("address") or "").strip()
        if address:
            source_rows.append({"place_id": place_id, "address_ko": address})

    checkpoint = _load_checkpoint(args.checkpoint)
    completed = checkpoint.setdefault("translations", {})
    pending = [row for row in source_rows if row["place_id"] not in completed]
    client = OpenAI()
    total_tokens = 0
    call_count = 0
    started = time.perf_counter()
    for offset in range(0, len(pending), args.batch_size):
        batch = pending[offset : offset + args.batch_size]
        expected_ids = {item["place_id"] for item in batch}
        last_error: Exception | None = None
        for attempt in range(1, args.max_retries + 1):
            try:
                response = client.responses.parse(
                    model=args.model,
                    reasoning={"effort": "none"},
                    text={"verbosity": "low"},
                    store=False,
                    prompt_cache_key="k-tour-address-translation-v1",
                    input=[
                        {
                            "role": "system",
                            "content": (
                                "You translate South Korean postal or road addresses for a tourism UI. "
                                "For every input, return faithful English, Japanese, and Simplified Chinese "
                                "display addresses. Preserve all numbers, lot/building identifiers, and place "
                                "specificity. Do not add explanations, coordinates, or facts. Use standard "
                                "romanization for Korean proper nouns in English. Keep the given place_id exactly."
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps(batch, ensure_ascii=False),
                        },
                    ],
                    text_format=AddressTranslationBatch,
                )
                parsed = response.output_parsed
                if parsed is None:
                    raise ValueError("구조화 번역 결과가 없습니다.")
                rows = [item.model_dump() for item in parsed.translations]
                _validate_batch(rows, expected_ids)
                for item in rows:
                    completed[item["place_id"]] = item
                usage = getattr(response, "usage", None)
                total_tokens += int(getattr(usage, "total_tokens", 0) or 0)
                call_count += 1
                checkpoint.update(
                    {
                        "schema_version": "1.0",
                        "model": args.model,
                        "source_count": len(source_rows),
                        "completed_count": len(completed),
                    }
                )
                _write_json_atomic(args.checkpoint, checkpoint)
                print(
                    f"[완료] {len(completed)}/{len(source_rows)}주소 "
                    f"(호출 {call_count}, 누적 토큰 {total_tokens})",
                    flush=True,
                )
                last_error = None
                break
            except Exception as error:  # SDK 오류와 형식 오류 모두 제한 재시도
                last_error = error
                print(
                    f"[재시도] batch {offset // args.batch_size + 1}, "
                    f"시도 {attempt}/{args.max_retries}: {type(error).__name__}: {error}",
                    flush=True,
                )
        if last_error is not None:
            raise last_error

    normalization_changes = _normalize_duplicate_source_addresses(
        source_rows,
        completed,
    )
    translated_catalog = json.loads(json.dumps(catalog, ensure_ascii=False))
    output_records = _mapping_list(translated_catalog.get("records"), "records")
    validation_issues: list[dict[str, str]] = []
    for record in output_records:
        place_id = _required_text(record.get("place_id"), "place_id")
        item = completed.get(place_id)
        if item is None:
            continue
        localized = _mapping(record.get("localized"), f"{place_id}.localized")
        for language in ("en", "ja", "zh"):
            target = _mapping(localized.get(language), f"{place_id}.{language}")
            address = _required_text(item.get(language), f"{place_id}.{language}")
            target["address"] = address
            target["address_language"] = language
            target["address_status"] = "translated"
            if language == "en" and re.search(r"[가-힣]", address):
                validation_issues.append(
                    {"place_id": place_id, "language": language, "issue": "영문 주소에 한글 포함"}
                )
            source_address = next(
                row["address_ko"] for row in source_rows if row["place_id"] == place_id
            )
            if sorted(re.findall(r"\d+", source_address)) != sorted(
                re.findall(r"\d+", address)
            ):
                validation_issues.append(
                    {
                        "place_id": place_id,
                        "language": language,
                        "issue": "주소 숫자 불일치",
                    }
                )

    translated_catalog["address_translation"] = {
        "model": args.model,
        "source_language": "ko",
        "target_languages": ["en", "ja", "zh"],
        "translated_place_count": len(completed),
    }
    missing_ids = sorted(
        row["place_id"] for row in source_rows if row["place_id"] not in completed
    )
    previous_report = (
        _mapping(_read_json(args.report), "previous report")
        if args.report.exists()
        else {}
    )
    previous_calls = int(
        previous_report.get("api_call_count_total")
        or previous_report.get("api_call_count")
        or 0
    )
    previous_tokens = int(
        previous_report.get("api_total_tokens")
        or previous_report.get("api_total_tokens_this_run")
        or 0
    )
    report = {
        "schema_version": "1.0",
        "model": args.model,
        "source_address_count": len(source_rows),
        "translated_place_count": len(completed),
        "translated_value_count": len(completed) * 3,
        "missing_place_ids": missing_ids,
        "validation_issues": validation_issues,
        "api_call_count_this_run": call_count,
        "api_call_count_total": previous_calls + call_count,
        "api_total_tokens_this_run": total_tokens,
        "api_total_tokens": previous_tokens + total_tokens,
        "duplicate_source_normalization_changes": normalization_changes,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "passed": not missing_ids and not validation_issues,
    }
    _write_json_atomic(args.output, translated_catalog)
    _write_json_atomic(args.report, report)
    review_output = args.review_output or args.report.with_name(
        "address_translation_review_queue.after_translation.json"
    )
    unresolved_source_ids = sorted(
        _required_text(record.get("place_id"), "place_id")
        for record in records
        if not _mapping(record.get("localized"), "localized").get("ko", {}).get("address")
    )
    _write_json_atomic(
        review_output,
        {
            "schema_version": "1.0",
            "purpose": "remaining_address_source_review_after_translation",
            "entries": [
                {
                    "place_id": place_id,
                    "reason": "missing_korean_source_address",
                    "target_languages_blocked": ["en", "ja", "zh"],
                }
                for place_id in unresolved_source_ids
            ],
        },
    )
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


def _validate_batch(rows: list[dict[str, str]], expected_ids: set[str]) -> None:
    actual_ids = [item["place_id"] for item in rows]
    if len(actual_ids) != len(set(actual_ids)):
        raise ValueError("응답 place_id가 중복되었습니다.")
    if set(actual_ids) != expected_ids:
        raise ValueError(
            f"응답 place_id 불일치: missing={sorted(expected_ids - set(actual_ids))}, "
            f"unexpected={sorted(set(actual_ids) - expected_ids)}"
        )


def _normalize_duplicate_source_addresses(
    source_rows: list[dict[str, str]],
    completed: dict[str, object],
) -> list[dict[str, str]]:
    """같은 한국어 주소의 번역은 언어별 다수값으로 통일한다."""

    ids_by_address: dict[str, list[str]] = defaultdict(list)
    for row in source_rows:
        ids_by_address[row["address_ko"]].append(row["place_id"])
    changes: list[dict[str, str]] = []
    for source_address, place_ids in ids_by_address.items():
        if len(place_ids) < 2:
            continue
        for language in ("en", "ja", "zh"):
            values = [
                _required_text(
                    _mapping(completed[place_id], place_id).get(language),
                    f"{place_id}.{language}",
                )
                for place_id in place_ids
            ]
            canonical = Counter(values).most_common(1)[0][0]
            for place_id, previous in zip(place_ids, values):
                if previous == canonical:
                    continue
                _mapping(completed[place_id], place_id)[language] = canonical
                changes.append(
                    {
                        "place_id": place_id,
                        "language": language,
                        "before": previous,
                        "after": canonical,
                        "source_address_ko": source_address,
                    }
                )
    return changes


def _load_checkpoint(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": "1.0", "translations": {}}
    return dict(_mapping(_read_json(path), "checkpoint"))


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label}는 객체여야 합니다.")
    return value


def _mapping_list(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{label}는 객체 배열이어야 합니다.")
    return value


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}는 빈 문자열이 아니어야 합니다.")
    return value.strip()


if __name__ == "__main__":
    main()
