"""합성 질문만 OpenAI로 보내고 실제 검색은 로컬에서 수행한다."""

from __future__ import annotations

import argparse
import json
import os
import sys
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
from src.llm_query_parser import LLMQueryParser
from src.multimodal_evaluation import (
    evaluate_multimodal_search,
    load_multimodal_cases,
)
from src.multimodal_pipeline import MultimodalSearchPipeline
from src.openai_client import OpenAIStructuredClient


DEFAULT_MODEL = "gpt-5.6-luna"


def select_cases(
    cases: list[dict[str, Any]],
    limit: int | None,
) -> list[dict[str, Any]]:
    if limit is None:
        return cases
    if limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")
    return cases[:limit]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="합성 다국어 질문의 실제 DB 검색 평가"
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_QUERY_MODEL", DEFAULT_MODEL),
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--enable-metadata-rerank",
        action="store_true",
        help="정합성 검사를 통과한 메타데이터에서만 사용하세요.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "synthetic_search_cases.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "synthetic_search_evaluation.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY 환경변수가 필요합니다.")

    cases = select_cases(load_multimodal_cases(args.cases), args.limit)
    pipeline = MultimodalSearchPipeline(
        runtime=ClipRuntime(local_files_only=True),
        repository=PgVectorRepository(
            DatabaseConfig.from_environment(EMBEDDING_ROOT / ".env")
        ),
        metadata_rerank_enabled=args.enable_metadata_rerank,
    )
    pipeline.warmup()
    parser = LLMQueryParser(OpenAIStructuredClient(model=args.model))
    report = evaluate_multimodal_search(
        pipeline,
        parser,
        cases,
        top_k=args.top_k,
    )
    report["scope"] = {
        "external_payload": "query text only",
        "local_only": [
            "relevant_segment_ids",
            "segment metadata",
            "embeddings",
            "database rows",
            "retrieval results",
        ],
    }
    report["model"] = args.model
    report["case_file"] = str(args.cases)
    report["metadata_rerank_enabled"] = args.enable_metadata_rerank

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
