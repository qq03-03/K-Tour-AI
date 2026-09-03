"""더미 검색 평가셋으로 Recall@K와 MRR을 계산한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.dummy_embedder import DummyTextEmbedder
from src.metrics import (
    first_relevant_rank,
    hit_at_k,
    mean_hit_at_k,
    mean_ndcg_at_k,
    mean_recall_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from src.search import search_segments


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SEGMENTS_PATH = PROJECT_ROOT / "data" / "dummy_segments.json"
DEFAULT_QUERIES_PATH = PROJECT_ROOT / "data" / "eval_queries.json"


def load_json_items(path: Path, key: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)[key]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="더미 텍스트 검색 품질 평가")
    parser.add_argument("--k", type=int, default=5, help="Recall을 계산할 검색 결과 수")
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS_PATH)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES_PATH)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if args.k <= 0:
        raise SystemExit("평가 오류: k는 1 이상이어야 합니다.")

    segments = load_json_items(args.segments, "segments")
    queries = load_json_items(args.queries, "queries")
    embedder = DummyTextEmbedder()

    all_relevant: list[list[str]] = []
    all_retrieved: list[list[str]] = []

    print(f"평가 질문 수: {len(queries)}")
    print(f"평가 지표: Hit@{args.k}, Recall@{args.k}, MRR, nDCG@{args.k}")
    print()

    for item in queries:
        error_message: str | None = None
        # MRR은 전체 순위에서 첫 정답을 찾아야 하므로 모든 구간을 검색한다.
        try:
            results = search_segments(
                item["query"], segments, embedder, top_k=len(segments)
            )
        except ValueError as error:
            results = []
            error_message = str(error)

        retrieved_ids = [result["segment_id"] for result in results]
        relevant_ids = item["relevant_segment_ids"]
        hit = hit_at_k(relevant_ids, retrieved_ids, k=args.k)
        recall = recall_at_k(relevant_ids, retrieved_ids, k=args.k)
        rr = reciprocal_rank(relevant_ids, retrieved_ids)
        ndcg = ndcg_at_k(relevant_ids, retrieved_ids, k=args.k)
        first_rank = first_relevant_rank(relevant_ids, retrieved_ids)

        # 전체 평균을 마지막에 계산하기 위해 질문별 정답과 순위를 보관한다.
        all_relevant.append(relevant_ids)
        all_retrieved.append(retrieved_ids)

        print(f"[{item['query_id']}] {item['query']}")
        print(f"  정답: {', '.join(relevant_ids)}")
        print(f"  상위 {args.k}개: {', '.join(retrieved_ids[:args.k]) or '(결과 없음)'}")
        print(
            f"  Hit@{args.k}: {hit:.3f} | Recall@{args.k}: {recall:.3f} | "
            f"첫 정답 순위: {first_rank if first_rank is not None else '-'} | "
            f"RR: {rr:.3f} | nDCG@{args.k}: {ndcg:.3f}"
        )
        if error_message:
            print(f"  검색 오류: {error_message}")
        print()

    average_hit = mean_hit_at_k(all_relevant, all_retrieved, k=args.k)
    average_recall = mean_recall_at_k(all_relevant, all_retrieved, k=args.k)
    mrr = mean_reciprocal_rank(all_relevant, all_retrieved)
    average_ndcg = mean_ndcg_at_k(all_relevant, all_retrieved, k=args.k)

    print("=== 전체 결과 ===")
    print(f"Hit@{args.k}: {average_hit:.3f}")
    print(f"Recall@{args.k}: {average_recall:.3f}")
    print(f"MRR: {mrr:.3f}")
    print(f"nDCG@{args.k}: {average_ndcg:.3f}")


if __name__ == "__main__":
    main()
