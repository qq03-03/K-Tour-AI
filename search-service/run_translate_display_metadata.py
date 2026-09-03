from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.display_localization import load_json
from src.display_translation import (
    DEFAULT_TRANSLATION_MODEL,
    OpenAIDisplayTranslator,
    build_display_translation_catalog,
    load_checkpoint,
    plan_incremental_translations,
    translation_source_hash,
    write_checkpoint,
)


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="표시용 메타데이터를 ko/en/ja/zh로 번역합니다."
    )
    parser.add_argument(
        "--source",
        default=str(PROJECT_ROOT / "data" / "display_translation_source.json"),
    )
    parser.add_argument(
        "--locations",
        default=str(PROJECT_ROOT / "data" / "location_alias_catalog.json"),
    )
    parser.add_argument(
        "--dramas",
        default=str(PROJECT_ROOT / "data" / "drama_title_catalog.json"),
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "data" / "display_translations.json"),
    )
    parser.add_argument(
        "--overrides",
        default=str(PROJECT_ROOT / "data" / "display_translation_overrides.json"),
    )
    parser.add_argument("--model", default=DEFAULT_TRANSLATION_MODEL)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size < 1 or args.batch_size > 10:
        raise SystemExit("--batch-size는 1~10이어야 합니다.")
    output_path = Path(args.output)
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"출력 파일이 이미 있습니다. --overwrite를 사용하세요: {output_path}")
    checkpoint_path = output_path.with_suffix(".checkpoint.json")

    source = load_json(args.source)
    locations = load_json(args.locations)
    dramas = load_json(args.dramas)
    overrides_path = Path(args.overrides)
    overrides = load_json(overrides_path) if overrides_path.is_file() else {"records": []}
    if not all(isinstance(item, dict) for item in (source, locations, dramas, overrides)):
        raise SystemExit("source/locations/dramas/overrides 파일은 JSON 객체여야 합니다.")
    records = source.get("records", [])
    if not isinstance(records, list):
        raise SystemExit("source.records는 배열이어야 합니다.")

    plan = plan_incremental_translations(records, load_checkpoint(checkpoint_path))
    completed = plan["reusable"]
    pending = plan["pending"]
    source_by_key = {
        (item["segment_id"], item["keyframe_id"]): item for item in records
    }
    translator = OpenAIDisplayTranslator(model=args.model)
    total_batches = (len(pending) + args.batch_size - 1) // args.batch_size
    print("=== 표시용 번역 시작 ===")
    print(
        f"전체: {len(records)}건 / 재사용: {len(completed)}건 / "
        f"신규: {len(plan['added_keys'])}건 / 변경: {len(plan['changed_keys'])}건 / "
        f"stale 정리: {len(plan['stale_keys'])}건"
    )
    print(f"모델: {args.model} / 배치: {args.batch_size}건 / API 호출 예정: {total_batches}회")

    for start in range(0, len(pending), args.batch_size):
        batch = pending[start : start + args.batch_size]
        batch_number = start // args.batch_size + 1
        print(f"[{batch_number}/{total_batches}] {len(batch)}건 번역 중...", flush=True)
        translated = translator.translate_batch(batch)
        for item in translated:
            key = (item["segment_id"], item["keyframe_id"])
            item["source_hash"] = translation_source_hash(source_by_key[key])
        translated_keys = {(item["segment_id"], item["keyframe_id"]) for item in translated}
        completed = [
            item
            for item in completed
            if (item["segment_id"], item["keyframe_id"]) not in translated_keys
        ]
        completed.extend(translated)
        write_checkpoint(checkpoint_path, model=args.model, completed=completed)
        print(f"[{batch_number}/{total_batches}] 누적 {len(completed)}건 완료", flush=True)

    # Persist the reconciled checkpoint even when no API batch was needed so
    # records removed from the current metadata cannot survive indefinitely.
    write_checkpoint(checkpoint_path, model=args.model, completed=completed)
    catalog = build_display_translation_catalog(
        source,
        completed,
        location_alias_payload=locations,
        drama_alias_payload=dramas,
        model=args.model,
        overrides_payload=overrides,
    )
    output_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("=== 표시용 번역 완료 ===")
    print(f"레코드: {catalog['record_count']}건")
    print(f"언어: {', '.join(catalog['languages'])}")
    print(f"출력: {output_path}")
    print(f"체크포인트: {checkpoint_path}")


if __name__ == "__main__":
    main()
