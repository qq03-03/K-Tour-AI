from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from ktour_search_automation.regression import (
    evaluate_backend_api,
    load_evaluation_queries,
    compare_regression_reports,
    write_regression_report,
)
from ktour_search_automation.contract import evaluate_backend_contract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="배포된 FastAPI 검색 서버에 평가 질문을 재실행합니다."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--contract-cases", type=Path)
    parser.add_argument("--endpoint", default="/api/search")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--token-env", default="KTOUR_API_TOKEN")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "output" / "backend_regression.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queries = load_evaluation_queries(args.evaluation)
    report = evaluate_backend_api(
        base_url=args.base_url,
        endpoint=args.endpoint,
        queries=queries,
        top_k=args.top_k,
        candidate_k=args.candidate_k,
        timeout=args.timeout,
        bearer_token=os.environ.get(args.token_env),
    )
    if args.contract_cases:
        payload = json.loads(args.contract_cases.read_text(encoding="utf-8-sig"))
        contract_cases = payload.get("cases") if isinstance(payload, dict) else None
        if not isinstance(contract_cases, list) or not contract_cases:
            raise ValueError("contract-cases 파일에 cases 배열이 없습니다.")
        report["contract"] = evaluate_backend_contract(
            base_url=args.base_url,
            endpoint=args.endpoint,
            cases=contract_cases,
            timeout=args.timeout,
            bearer_token=os.environ.get(args.token_env),
        )
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
        if not isinstance(baseline, dict):
            raise ValueError("baseline 보고서는 JSON 객체여야 합니다.")
        report["baseline_comparison"] = compare_regression_reports(report, baseline)
    write_regression_report(args.output, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"보고서: {args.output.resolve()}")
    failed = report["summary"]["failed_request_count"]
    failed += report["summary"]["missed_query_count"]
    failed += report["summary"]["duplicate_result_case_count"]
    failed += report["summary"]["result_schema_failure_case_count"]
    failed += report["summary"]["filter_failed_case_count"]
    failed += report["summary"]["filter_not_reported_case_count"]
    if "contract" in report:
        failed += report["contract"]["summary"]["failed_case_count"]
    if report.get("baseline_comparison", {}).get("has_regression"):
        failed += 1
    if args.strict and failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
