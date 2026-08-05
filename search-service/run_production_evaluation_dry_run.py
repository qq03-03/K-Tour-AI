"""최종 50문항 평가 체인을 DB·OpenAI 없이 검증한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.multimodal_evaluation import evaluate_multimodal_search, load_multimodal_cases
from src.multimodal_failure_analysis import analyze_multimodal_report
from src.production_dry_run import ProductionEvaluationDryRunPipeline


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="실데이터 50문항 평가 dry-run")
    parser.add_argument(
        "--cases",
        type=Path,
        default=PROJECT_ROOT / "data" / "production_eval_queries_resolved_final.json",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "production_evaluation_dry_run.json",
    )
    parser.add_argument(
        "--failure-output",
        type=Path,
        default=PROJECT_ROOT / "output" / "production_failure_dry_run.json",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    cases = load_multimodal_cases(args.cases)
    report = evaluate_multimodal_search(
        ProductionEvaluationDryRunPipeline(cases),
        object(),
        cases,
        top_k=args.top_k,
    )
    report["execution_mode"] = "dry_run_oracle_not_search_quality"
    failure_report = analyze_multimodal_report(report)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.failure_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.failure_output.write_text(
        json.dumps(failure_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("=== 실데이터 평가 dry-run ===")
    print("주의: 합성 정답 순위를 사용하므로 검색 정확도 결과가 아닙니다.")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"평가 보고서: {args.output}")
    print(f"실패 보고서: {args.failure_output}")


if __name__ == "__main__":
    main()
