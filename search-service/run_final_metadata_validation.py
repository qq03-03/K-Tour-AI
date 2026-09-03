"""최종 VLM 메타데이터의 임베딩 전 통합 검증 보고서를 생성한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.final_metadata_validation import build_final_metadata_report


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="최종 VLM 메타데이터의 품질·전처리 연결 통합 검사"
    )
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--preprocessing", type=Path, required=True)
    parser.add_argument(
        "--keyframe-root",
        type=Path,
        help=(
            "keyframes 폴더의 상위 경로입니다. 생략하면 전처리 JSON의 "
            "상위 경로를 사용합니다."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "final_metadata_validation.json",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    report = build_final_metadata_report(
        args.metadata,
        args.preprocessing,
        keyframe_root=args.keyframe_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print("=== 최종 VLM 메타데이터 통합 검증 ===")
    print(
        f"메타데이터 {summary['record_count']}건 / "
        f"전처리 장면 {summary['preprocessing_segment_count']}건"
    )
    print(f"정상 연결: {summary['linked_segment_count']}건")
    print(
        f"자체 품질 오류 {summary['error_count']}건 / "
        f"경고 {summary['warning_count']}건"
    )
    print(f"전처리 연결 오류: {summary['alignment_issue_count']}건")
    print(f"최종 결과: {'PASS' if report['is_valid'] else 'FAIL'}")
    print(f"보고서: {args.output}")
    raise SystemExit(0 if report["is_valid"] else 1)


if __name__ == "__main__":
    main()
