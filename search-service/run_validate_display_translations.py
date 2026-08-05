from __future__ import annotations

import argparse
from pathlib import Path

from src.display_localization import load_json, validate_translation_catalog


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="표시용 번역과 최종 VLM metadata의 ID·언어·필드를 검증합니다."
    )
    parser.add_argument("--metadata", required=True, help="최종 VLM metadata JSON")
    parser.add_argument(
        "--translations",
        default=str(PROJECT_ROOT / "data" / "display_translations.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = load_json(args.metadata)
    catalog = validate_translation_catalog(
        load_json(args.translations),
        expected_source=metadata,
        require_all_languages=True,
    )
    print("=== 표시용 번역 검증 통과 ===")
    print(f"레코드: {catalog['record_count']}건")
    print("언어: ko, en, ja, zh")
    print("ID 연결: 누락 0건 / stale 0건 / 중복 0건")
    print(f"번역 파일: {Path(args.translations)}")


if __name__ == "__main__":
    main()
