"""4개 언어의 실제 DB 검색과 RRF/점수 결합을 한 번에 평가한다."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.clip_backend import ClipRuntime, DatabaseConfig, PgVectorRepository
from src.llm_query_parser import LLMQueryParser
from src.multimodal_evaluation import (
    evaluate_multimodal_search,
    load_multimodal_cases,
)
from src.multimodal_pipeline import MultimodalSearchPipeline
from src.openai_client import DEFAULT_QUERY_MODEL, OpenAIStructuredClient


PROJECT_ROOT = Path(__file__).resolve().parent
EMBEDDING_ROOT = PROJECT_ROOT.parent / "embedding-db"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="K-Tour 실제 멀티모달 검색 평가")
    parser.add_argument("--model", default=DEFAULT_QUERY_MODEL)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--cases",
        type=Path,
        default=PROJECT_ROOT / "data" / "nami_multimodal_eval.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "multimodal_evaluation.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    pipeline = MultimodalSearchPipeline(
        runtime=ClipRuntime(local_files_only=True),
        repository=PgVectorRepository(
            DatabaseConfig.from_environment(EMBEDDING_ROOT / ".env")
        ),
    )
    pipeline.warmup()
    parser = LLMQueryParser(OpenAIStructuredClient(model=args.model))
    report = evaluate_multimodal_search(
        pipeline,
        parser,
        load_multimodal_cases(args.cases),
        top_k=args.top_k,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report={args.output}")


if __name__ == "__main__":
    main()
