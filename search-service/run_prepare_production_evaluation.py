"""실데이터 평가 정답을 현재 segment_id에 연결한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.production_evaluation import (
    load_anchor_cases,
    resolve_anchor_cases,
    summarize_anchor_cases,
)
from src.project_data_validation import load_metadata_payload


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="실데이터 평가셋 segment_id 연결")
    parser.add_argument(
        "--cases",
        type=Path,
        default=PROJECT_ROOT / "data" / "production_eval_queries_draft.json",
    )
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "production_eval_resolved.json",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    cases = load_anchor_cases(args.cases)
    summary = summarize_anchor_cases(cases)
    report = resolve_anchor_cases(cases, load_metadata_payload(args.metadata))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("=== 실데이터 평가셋 준비 ===")
    print(f"질문 수: {summary['query_count']} ({summary['by_language']})")
    print(f"30~50개 기준 충족: {summary['recommended_size_met']}")
    print(f"정답 연결 완료: {report['resolution']['resolved_queries']}")
    print(f"연결 실패: {report['resolution']['unresolved_queries']}")
    print(f"출력: {args.output}")
    raise SystemExit(0 if not report["resolution"]["unresolved"] else 1)


if __name__ == "__main__":
    main()
