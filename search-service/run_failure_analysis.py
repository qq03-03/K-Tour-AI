"""평가셋의 검색 실패 사례를 분석하고 JSON 보고서로 저장한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.dummy_embedder import DummyTextEmbedder
from src.failure_analysis import analyze_failures


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SEGMENTS_PATH = PROJECT_ROOT / "data" / "dummy_segments.json"
DEFAULT_QUERIES_PATH = PROJECT_ROOT / "data" / "eval_queries.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "reports" / "failure_cases.json"


def load_json_items(path: Path, key: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)[key]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="더미 검색 실패 사례 분석")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS_PATH)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    segments = load_json_items(args.segments, "segments")
    queries = load_json_items(args.queries, "queries")
    # 평가 질문을 다시 검색해 실패한 질문과 원인을 구조화한다.
    report = analyze_failures(queries, segments, DummyTextEmbedder(), k=args.k)

    # 사람이 읽을 수 있는 UTF-8 JSON으로 저장해 발표 자료나 후속 분석에 사용한다.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print(
        f"실패 질문: {summary['failure_queries']}/{summary['total_queries']} "
        f"({summary['failure_rate']:.1%})"
    )
    print("실패 유형:")
    for label, count in summary["failure_type_counts"].items():
        print(f"  - {label}: {count}")

    print()
    for case in report["cases"]:
        labels = ", ".join(case["failure_types"])
        print(f"[{case['query_id']}] {case['query']}")
        print(f"  유형: {labels}")
        print(
            f"  Recall@{args.k}: {case['recall_at_k']:.3f} | "
            f"첫 정답 순위: {case['first_relevant_rank'] or '-'}"
        )
        print()

    print(f"저장 위치: {args.output}")


if __name__ == "__main__":
    main()
