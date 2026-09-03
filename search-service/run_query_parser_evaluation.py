"""QueryParser 구현체의 구조화 정확도와 지연시간을 평가한다."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.llm_query_parser import LLMQueryParser
from src.ollama_client import OllamaStructuredClient
from src.query_parser import RuleBasedQueryParser
from src.query_parser_evaluation import evaluate_query_parser, load_query_parser_cases


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_QUERIES_PATH = PROJECT_ROOT / "data" / "query_parser_eval.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QueryParser 정확도·속도 평가")
    parser.add_argument(
        "--parser",
        choices=("rule", "ollama"),
        default="rule",
        help="평가할 검색어 분석기",
    )
    parser.add_argument(
        "--model",
        default="llama3.1",
        help="--parser ollama에서 사용할 로컬 모델 이름",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://127.0.0.1:11434",
        help="Ollama 로컬 API 주소",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="질문 한 건당 Ollama 제한 시간(초)",
    )
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES_PATH)
    parser.add_argument(
        "--show-cases",
        action="store_true",
        help="질문별 예상 필터와 실제 필터를 출력합니다.",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if args.parser == "rule":
        query_parser = RuleBasedQueryParser()
    else:
        query_parser = LLMQueryParser(
            OllamaStructuredClient(
                model=args.model,
                base_url=args.ollama_url,
                timeout_seconds=args.timeout,
            )
        )
    cases = load_query_parser_cases(args.queries)
    evaluation = evaluate_query_parser(query_parser, cases)
    summary = evaluation["summary"]

    print("=== QueryParser 평가 ===")
    print(f"분석기: {args.parser}")
    print(f"질문 수: {summary['query_count']}")
    print(f"필터 완전 일치율: {summary['exact_match_rate']:.3f}")
    print(f"필터 Micro Precision: {summary['micro_precision']:.3f}")
    print(f"필터 Micro Recall: {summary['micro_recall']:.3f}")
    print(f"필터 Micro F1: {summary['micro_f1']:.3f}")
    print(f"감성 힌트 완전 일치율: {summary['soft_hint_exact_match_rate']:.3f}")
    print(f"감성 힌트 Micro F1: {summary['soft_hint_micro_f1']:.3f}")
    print(f"Fallback 비율: {summary['fallback_rate']:.3f}")
    print(f"원본 질문 보존율: {summary['original_query_preservation_rate']:.3f}")
    print(f"평균 분석 시간: {summary['average_latency_ms']:.3f}ms")
    print(f"P50 분석 시간: {summary['p50_latency_ms']:.3f}ms")
    print(f"P95 분석 시간: {summary['p95_latency_ms']:.3f}ms")

    print("\n=== 언어별 비교 ===")
    for language, language_summary in evaluation["by_language"].items():
        print(
            f"{language}: 질문 {language_summary['query_count']}개, "
            f"필터 F1 {language_summary['micro_f1']:.3f}, "
            f"감성 힌트 F1 {language_summary['soft_hint_micro_f1']:.3f}, "
            f"평균 {language_summary['average_latency_ms']:.3f}ms, "
            f"P50 {language_summary['p50_latency_ms']:.3f}ms, "
            f"P95 {language_summary['p95_latency_ms']:.3f}ms"
        )

    if args.show_cases:
        print("\n=== 질문별 결과 ===")
        for item in evaluation["cases"]:
            status = "PASS" if item["exact_match"] else "FAIL"
            print(f"[{status}] {item['query_id']} ({item['language']}) {item['query']}")
            print(f"  예상: {item['expected_filters']}")
            print(f"  실제: {item['actual_filters']}")
            print(f"  예상 감성 힌트: {item['expected_soft_hints']}")
            print(f"  실제 감성 힌트: {item['actual_soft_hints']}")


if __name__ == "__main__":
    main()
