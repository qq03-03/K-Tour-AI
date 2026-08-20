"""명령줄에서 더미 텍스트 검색을 실행하는 진입점."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.data_loader import SegmentDataError, load_segments
from src.dummy_embedder import DummyTextEmbedder
from src.query_parser import RuleBasedQueryParser
from src.search_pipeline import run_search_pipeline


PROJECT_ROOT = Path(__file__).resolve().parent
# 실행 위치가 달라도 프로젝트 내부의 기본 데이터 파일을 찾도록 절대 경로를 만든다.
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "dummy_segments.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="더미 관광 영상 구간 텍스트 검색")
    parser.add_argument("--query", required=True, help="검색할 한국어 자연어 질의")
    parser.add_argument("--top-k", type=int, default=5, help="반환할 결과 수")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH, help="더미 JSON 경로")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    # 현재는 더미 구현체를 사용하지만 TextEmbedder 규약을 지키는 모델로 교체할 수 있다.
    try:
        segments = load_segments(args.data)
        embedder = DummyTextEmbedder()
        output = run_search_pipeline(
            args.query,
            segments,
            parser=RuleBasedQueryParser(),
            embedder=embedder,
            top_k=args.top_k,
        )
    except (OSError, SegmentDataError, TypeError, ValueError) as error:
        raise SystemExit(f"검색 오류: {error}") from error

    concepts = ", ".join(embedder.matched_concepts(args.query))
    print(f"질의: {args.query}")
    print(f"인식한 더미 개념: {concepts}")
    print(f"적용 필터: {output['filters'] or '없음'}")
    if output["fallback_used"]:
        print(f"재검색: {output['fallback_reason']}")
    print()

    for result in output["results"]:
        print(
            f"{result['rank']}. {result['segment_id']} | "
            f"{result['location_name']} | "
            f"{result['start_sec']:.1f}-{result['end_sec']:.1f}초 | "
            f"유사도 {result['score']:.4f}"
        )


if __name__ == "__main__":
    main()
