from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.display_localization import load_json
from src.display_translation_qa import (
    DEFAULT_QA_MODEL,
    OpenAIDisplayTranslationQA,
    build_qa_summary,
)


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="표시용 번역 45건을 자동 품질 검수합니다.")
    parser.add_argument(
        "--source",
        default=str(PROJECT_ROOT / "data" / "display_translation_source.json"),
    )
    parser.add_argument(
        "--translations",
        default=str(PROJECT_ROOT / "data" / "display_translations.json"),
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "output" / "display_translation_qa.json"),
    )
    parser.add_argument("--model", default=DEFAULT_QA_MODEL)
    parser.add_argument("--batch-size", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size < 1 or args.batch_size > 10:
        raise SystemExit("--batch-size는 1~10이어야 합니다.")
    source = load_json(args.source)
    translations = load_json(args.translations)
    if not isinstance(source, dict) or not isinstance(translations, dict):
        raise SystemExit("source와 translations는 JSON 객체여야 합니다.")
    source_records = source.get("records", [])
    translation_records = translations.get("records", [])
    if not isinstance(source_records, list) or not isinstance(translation_records, list):
        raise SystemExit("records는 배열이어야 합니다.")

    evaluator = OpenAIDisplayTranslationQA(model=args.model)
    results: list[dict] = []
    total_batches = (len(source_records) + args.batch_size - 1) // args.batch_size
    print("=== 표시용 번역 자동 검수 시작 ===")
    print(f"레코드: {len(source_records)}건 / 배치: {args.batch_size}건 / API 호출: {total_batches}회")
    for start in range(0, len(source_records), args.batch_size):
        source_batch = source_records[start : start + args.batch_size]
        batch_keys = {(item["segment_id"], item["keyframe_id"]) for item in source_batch}
        translation_batch = [
            item
            for item in translation_records
            if (item["segment_id"], item["keyframe_id"]) in batch_keys
        ]
        number = start // args.batch_size + 1
        print(f"[{number}/{total_batches}] {len(source_batch)}건 검수 중...", flush=True)
        results.extend(evaluator.evaluate_batch(source_batch, translation_batch))
        print(f"[{number}/{total_batches}] 누적 {len(results)}건 완료", flush=True)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "execution_mode": "anonymous_semantic_translation_qa",
        "summary": build_qa_summary(results),
        "records": results,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    print("=== 표시용 번역 자동 검수 완료 ===")
    print(f"통과: {summary['passed_count']}건 / 재검토: {summary['review_count']}건")
    print(f"언어별 재검토: {summary['by_language_review_count']}")
    print(f"보고서: {output_path}")


if __name__ == "__main__":
    main()
