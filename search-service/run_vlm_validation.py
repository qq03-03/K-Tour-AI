"""영상 전처리 결과와 VLM 메타데이터의 연결을 검사한다."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.vlm_metadata import build_alignment_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VLM 구간 메타데이터 JSON 검증")
    parser.add_argument("--metadata", required=True, help="VLM 결과 JSON 경로")
    parser.add_argument(
        "--preprocessing",
        required=True,
        help="영상 전처리 결과 JSON 경로",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_alignment_report(
        Path(args.metadata),
        Path(args.preprocessing),
    )

    print("=== VLM·전처리 연결 검증 ===")
    print(f"전처리 장면 수: {report['preprocessing_segment_count']}")
    print(f"VLM 장면 수: {report['vlm_segment_count']}")
    print(f"키프레임으로 연결된 장면 수: {report['linked_segment_count']}")

    if report["is_valid"]:
        print("검증 결과: 정상")
        return

    print(f"검증 결과: 오류 {len(report['issues'])}건")
    for issue in report["issues"]:
        print(f"- {issue}")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
