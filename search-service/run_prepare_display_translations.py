from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.display_localization import build_translation_source, load_json


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VLM metadata를 표시용 다국어 번역 입력 JSON으로 변환합니다."
    )
    parser.add_argument("--metadata", required=True, help="최종 VLM metadata JSON")
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "data" / "display_translation_source.json"),
        help="번역 입력 JSON 저장 경로",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="기존 출력 파일이 있으면 덮어씁니다.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"출력 파일이 이미 있습니다. --overwrite를 사용하세요: {output_path}")

    payload = build_translation_source(load_json(args.metadata))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("=== 표시용 번역 입력 준비 완료 ===")
    print(f"레코드: {payload['record_count']}건")
    print(f"대상 언어: {', '.join(payload['target_languages'])}")
    print(f"용도: {payload['purpose']}")
    print(f"출력: {output_path}")


if __name__ == "__main__":
    main()
