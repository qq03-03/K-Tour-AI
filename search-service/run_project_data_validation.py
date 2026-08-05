"""실데이터 메타데이터의 검색·DB 연결 품질 보고서를 생성한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.project_data_validation import load_metadata_payload, validate_project_metadata


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="K-Tour 실데이터 메타데이터 품질검사")
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument(
        "--keyframe-root",
        type=Path,
        help="지정하면 keyframes/... 실제 파일 존재 여부도 확인합니다.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "project_data_validation.json",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    report = validate_project_metadata(
        load_metadata_payload(args.metadata),
        keyframe_root=args.keyframe_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print("=== 프로젝트 메타데이터 품질검사 ===")
    print(f"레코드: {summary['record_count']}")
    print(f"고유 세그먼트: {summary['unique_segment_count']}")
    print(f"고유 장소 ID: {summary['unique_place_id_count']}")
    print(f"오류: {summary['error_count']} | 경고: {summary['warning_count']}")
    print(f"보고서: {args.output}")
    raise SystemExit(0 if report["is_valid"] else 1)


if __name__ == "__main__":
    main()
