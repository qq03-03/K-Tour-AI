"""실제 멀티모달 평가 JSON의 실패 사례를 별도 보고서로 저장한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.multimodal_failure_analysis import analyze_multimodal_report


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="멀티모달 검색 실패 사례 분석")
    parser.add_argument(
        "--evaluation",
        type=Path,
        default=PROJECT_ROOT / "output" / "multimodal_evaluation.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "multimodal_failure_cases.json",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    payload = json.loads(args.evaluation.read_text(encoding="utf-8-sig"))
    report = analyze_multimodal_report(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    print("=== 멀티모달 검색 실패 분석 ===")
    print(f"평가 질문: {summary['evaluation_query_count']}")
    print(f"실패 레코드: {summary['failure_record_count']}")
    print(f"실패 유형: {summary['failure_type_counts']}")
    print(f"보고서: {args.output}")


if __name__ == "__main__":
    main()
