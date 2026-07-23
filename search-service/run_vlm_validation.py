"""영상 전처리 결과와 VLM 메타데이터의 연결을 검사한다."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.vlm_metadata import load_expected_segment_ids, load_vlm_metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VLM 구간 메타데이터 JSON 검증")
    parser.add_argument("--metadata", required=True, help="VLM 결과 JSON 경로")
    parser.add_argument(
        "--preprocessing",
        required=True,
        help="영상 전처리 결과 JSON 경로",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    expected_ids = load_expected_segment_ids(Path(args.preprocessing))
    segments = load_vlm_metadata(
        Path(args.metadata),
        expected_segment_ids=expected_ids,
    )

    print("=== VLM 메타데이터 검증 완료 ===")
    print(f"전처리 구간 수: {len(expected_ids)}")
    print(f"VLM 결과 구간 수: {len(segments)}")
    print("segment_id 연결: 정상")


if __name__ == "__main__":
    main()
