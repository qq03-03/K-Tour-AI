from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEARCH_SERVICE = PROJECT_ROOT / "search-service"
if str(SEARCH_SERVICE) not in sys.path:
    sys.path.insert(0, str(SEARCH_SERVICE))

from src.frontend_data_automation import (  # noqa: E402
    COORDINATE_REVIEW_FIELDS,
    build_coordinate_review_rows,
    coordinate_summary,
    extract_segment_ids,
    filter_accepted_segments,
    flatten_metadata,
    load_existing_coordinates,
    load_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "최종 metadata와 전처리 통과 목록에서 장소를 추출하고, "
            "기존 좌표를 재사용한 카카오 API 검수 입력을 생성합니다."
        )
    )
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument(
        "--accepted",
        type=Path,
        help="선택 사항: 최종 전처리 manifest 또는 통과 segment JSON",
    )
    parser.add_argument(
        "--existing",
        type=Path,
        action="append",
        default=[],
        help="기존 좌표 CSV/JSON. 여러 번 지정할 수 있습니다.",
    )
    parser.add_argument("--output", type=Path, required=True, help="좌표 검수 CSV")
    parser.add_argument(
        "--flat-metadata-output",
        type=Path,
        help="통과 segment만 포함한 평탄화 metadata JSON",
    )
    parser.add_argument("--report", type=Path, help="자동화 준비 결과 JSON")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _ensure_outputs_available(
        [args.output, args.flat_metadata_output, args.report], args.overwrite
    )
    records = flatten_metadata(load_json(args.metadata))
    accepted_ids = (
        extract_segment_ids(load_json(args.accepted)) if args.accepted else None
    )
    accepted_records = filter_accepted_segments(records, accepted_ids)
    coordinates = load_existing_coordinates(args.existing)
    review_rows = build_coordinate_review_rows(
        accepted_records,
        existing_coordinates=coordinates,
    )
    summary = {
        "metadata_segment_count": len(records),
        "accepted_segment_count": len(accepted_records),
        **coordinate_summary(review_rows),
        "source_metadata": str(args.metadata.resolve()),
        "accepted_source": str(args.accepted.resolve()) if args.accepted else None,
        "source_files_modified": False,
    }

    _write_csv_atomic(args.output, review_rows)
    if args.flat_metadata_output:
        _write_json_atomic(args.flat_metadata_output, accepted_records)
    if args.report:
        _write_json_atomic(args.report, summary)

    print("=== 좌표·표시언어 입력 준비 완료 ===")
    print(f"metadata segment: {summary['metadata_segment_count']}건")
    print(f"전처리 통과 segment: {summary['accepted_segment_count']}건")
    print(f"고유 장소: {summary['place_count']}건")
    print(f"기존 좌표 재사용: {summary['reused_count']}건")
    print(f"좌표 조회 필요: {summary['lookup_count']}건")
    print(f"장소명 검토 필요: {summary['review_count']}건")
    print(f"좌표 검수 CSV: {args.output}")
    print("원본 수정: 없음")


def _ensure_outputs_available(paths: list[Path | None], overwrite: bool) -> None:
    if overwrite:
        return
    existing = [str(path) for path in paths if path is not None and path.exists()]
    if existing:
        raise SystemExit(
            "출력 파일이 이미 있습니다. --overwrite를 사용하세요: "
            + ", ".join(existing)
        )


def _write_csv_atomic(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COORDINATE_REVIEW_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(f"자동화 입력 검증 실패: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
