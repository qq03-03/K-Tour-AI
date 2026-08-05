"""CLIP·DB 없이 OpenAI QueryParser만 평가한다."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from src.llm_query_parser import LLMQueryParser
from src.openai_client import (
    ALLOWED_REASONING_EFFORTS,
    DEFAULT_QUERY_MODEL,
    DEFAULT_QUERY_REASONING_EFFORT,
    OpenAIStructuredClient,
)
from src.query_parser_evaluation import evaluate_query_parser, load_query_parser_cases


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenAI QueryParser 정확도·속도 평가")
    parser.add_argument(
        "--queries",
        type=Path,
        default=PROJECT_ROOT / "data" / "production_eval_queries_draft.json",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_QUERY_MODEL", DEFAULT_QUERY_MODEL),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "openai_query_parser_evaluation.json",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=sorted(ALLOWED_REASONING_EFFORTS),
        default=os.getenv("OPENAI_REASONING_EFFORT", DEFAULT_QUERY_REASONING_EFFORT),
        help="OpenAI reasoning effort. 속도 기준선은 none을 권장합니다.",
    )
    parser.add_argument("--show-cases", action="store_true")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY 환경변수를 먼저 설정해주세요.")

    cases = load_query_parser_cases(args.queries)
    openai_client = OpenAIStructuredClient(
        model=args.model,
        reasoning_effort=args.reasoning_effort,
    )
    parser = LLMQueryParser(openai_client)
    report = evaluate_query_parser(parser, cases)
    report["configuration"] = {
        "model": openai_client.model,
        "reasoning_effort": openai_client.reasoning_effort,
        "verbosity": openai_client.verbosity,
        "prompt_cache_key": openai_client.prompt_cache_key,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print("=== OpenAI QueryParser 평가 ===")
    print(f"모델: {args.model}")
    print(f"Reasoning effort: {args.reasoning_effort}")
    print(f"질문 수: {summary['query_count']}")
    print(f"필터 Micro F1: {summary['micro_f1']:.3f}")
    print(f"Soft hint Micro F1: {summary['soft_hint_micro_f1']:.3f}")
    print(f"Fallback 비율: {summary['fallback_rate']:.3f}")
    print(f"평균 분석 시간: {summary['average_latency_ms']:.3f}ms")
    print(f"P95 분석 시간: {summary['p95_latency_ms']:.3f}ms")
    print(f"보고서: {args.output}")
    if args.show_cases:
        for item in report["cases"]:
            status = "PASS" if item["exact_match"] else "FAIL"
            print(f"[{status}] {item['query_id']} {item['query']}")
            print(f"  예상 필터: {item['expected_filters']}")
            print(f"  실제 필터: {item['actual_filters']}")


if __name__ == "__main__":
    main()
