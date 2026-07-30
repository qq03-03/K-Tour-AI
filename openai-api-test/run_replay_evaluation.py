"""저장된 OpenAI 분석 결과를 재사용해 검색 순위 코드만 결정적으로 평가한다."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
SEARCH_ROOT = PROJECT_ROOT / "search-service"
EMBEDDING_ROOT = PROJECT_ROOT / "embedding-db"

os.environ.setdefault(
    "HF_HOME",
    str(PROJECT_ROOT / ".cache" / "huggingface"),
)
os.environ.setdefault(
    "TORCH_HOME",
    str(PROJECT_ROOT / ".cache" / "torch"),
)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
sys.path.insert(0, str(SEARCH_ROOT))

from src.clip_backend import ClipRuntime, DatabaseConfig, PgVectorRepository
from src.multimodal_evaluation import (
    evaluate_multimodal_search,
    load_multimodal_cases,
)
from src.multimodal_pipeline import MultimodalSearchPipeline
from src.query_parser import ParsedQuery


class ReplayParser:
    def __init__(self, stored_cases: list[Mapping[str, Any]]) -> None:
        self._by_query = {
            str(item["query"]): item
            for item in stored_cases
        }

    def parse(self, query: str) -> ParsedQuery:
        item = self._by_query[query]
        return ParsedQuery(
            original_query=query,
            search_text=str(item["search_text"]),
            filters={
                str(key): [str(value) for value in values]
                for key, values in dict(item["filters"]).items()
            },
            soft_hints={
                str(key): [str(value) for value in values]
                for key, values in dict(item["soft_hints"]).items()
            },
        )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="저장된 QueryParser 결과 재현 평가")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "output" / "synthetic_search_evaluation.json",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "synthetic_search_cases.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "synthetic_search_evaluation_replay.json",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--enable-metadata-rerank",
        action="store_true",
        help="정합성 검사를 통과한 메타데이터에서만 사용하세요.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    stored_cases = baseline.get("cases")
    if not isinstance(stored_cases, list) or not stored_cases:
        raise ValueError("baseline 결과에 cases가 필요합니다.")

    cases = load_multimodal_cases(args.cases)
    pipeline = MultimodalSearchPipeline(
        runtime=ClipRuntime(local_files_only=True),
        repository=PgVectorRepository(
            DatabaseConfig.from_environment(EMBEDDING_ROOT / ".env")
        ),
        metadata_rerank_enabled=args.enable_metadata_rerank,
    )
    pipeline.warmup()
    report = evaluate_multimodal_search(
        pipeline,
        ReplayParser(stored_cases),
        cases,
        top_k=args.top_k,
    )
    report["replay"] = {
        "openai_api_called": False,
        "baseline": str(args.baseline),
        "reused_fields": ["search_text", "filters", "soft_hints"],
        "metadata_rerank_enabled": args.enable_metadata_rerank,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
