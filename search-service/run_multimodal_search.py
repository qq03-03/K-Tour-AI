"""OpenAI QueryParser와 실제 pgvector DB를 이용한 단일 검색 실행기."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.clip_backend import ClipRuntime, DatabaseConfig, PgVectorRepository
from src.llm_query_parser import LLMQueryParser
from src.multimodal_pipeline import MultimodalSearchPipeline
from src.openai_client import DEFAULT_QUERY_MODEL, OpenAIStructuredClient


PROJECT_ROOT = Path(__file__).resolve().parent
EMBEDDING_ROOT = PROJECT_ROOT.parent / "embedding-db"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="K-Tour 실제 멀티모달 검색")
    parser.add_argument("query")
    parser.add_argument("--model", default=DEFAULT_QUERY_MODEL)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--method",
        choices=("rrf", "normalized"),
        default="rrf",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    runtime = ClipRuntime(local_files_only=True)
    repository = PgVectorRepository(
        DatabaseConfig.from_environment(EMBEDDING_ROOT / ".env")
    )
    pipeline = MultimodalSearchPipeline(runtime=runtime, repository=repository)
    parser = LLMQueryParser(OpenAIStructuredClient(model=args.model))
    output = pipeline.search(
        args.query,
        parser=parser,
        top_k=args.top_k,
        methods=(args.method,),
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
