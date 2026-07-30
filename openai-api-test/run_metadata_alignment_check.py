"""통합 구간 JSON과 PostgreSQL 검색 메타데이터의 태그 정합성을 검사한다."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import fmean
from typing import Any


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
SEARCH_ROOT = PROJECT_ROOT / "search-service"
EMBEDDING_ROOT = PROJECT_ROOT / "embedding-db"
sys.path.insert(0, str(SEARCH_ROOT))

from src.clip_backend import DatabaseConfig, PgVectorRepository
from src.metadata_reranker import concepts_for_values


FIELDS = ("scene_elements", "activity", "mood")


def compare_metadata(
    expected_segments: Sequence[Mapping[str, Any]],
    actual_segments: Sequence[Mapping[str, Any]],
    *,
    minimum_coverage: float = 0.5,
) -> dict[str, Any]:
    actual_by_id = {
        str(segment["segment_id"]): segment
        for segment in actual_segments
    }
    details: list[dict[str, Any]] = []
    field_coverages: dict[str, list[float]] = {field: [] for field in FIELDS}

    for expected in expected_segments:
        segment_id = str(expected["segment_id"])
        actual = actual_by_id.get(segment_id)
        if actual is None:
            details.append(
                {
                    "segment_id": segment_id,
                    "status": "missing_in_database",
                    "fields": {},
                }
            )
            continue

        fields: dict[str, Any] = {}
        active_coverages: list[float] = []
        for field in FIELDS:
            expected_concepts = concepts_for_values(expected.get(field))
            actual_concepts = concepts_for_values(actual.get(field))
            if not expected_concepts:
                continue
            matched = expected_concepts & actual_concepts
            missing = expected_concepts - actual_concepts
            coverage = len(matched) / len(expected_concepts)
            active_coverages.append(coverage)
            field_coverages[field].append(coverage)
            fields[field] = {
                "coverage": round(coverage, 6),
                "expected": sorted(expected_concepts),
                "actual": sorted(actual_concepts),
                "matched": sorted(matched),
                "missing": sorted(missing),
            }

        overall = fmean(active_coverages) if active_coverages else 1.0
        field_below_minimum = any(
            coverage < minimum_coverage
            for coverage in active_coverages
        )
        details.append(
            {
                "segment_id": segment_id,
                "status": (
                    "low_coverage"
                    if field_below_minimum
                    else "aligned"
                ),
                "overall_coverage": round(overall, 6),
                "fields": fields,
            }
        )

    return {
        "summary": {
            "segment_count": len(expected_segments),
            "database_segment_count": len(actual_segments),
            "minimum_coverage": minimum_coverage,
            "low_coverage_count": sum(
                item["status"] != "aligned" for item in details
            ),
            "field_average_coverage": {
                field: (
                    round(fmean(values), 6)
                    if values
                    else None
                )
                for field, values in field_coverages.items()
            },
        },
        "segments": details,
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JSON/DB 메타데이터 정합성 검사")
    parser.add_argument(
        "--expected",
        type=Path,
        default=SEARCH_ROOT / "data" / "nami_segments_10.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "metadata_alignment_report.json",
    )
    parser.add_argument("--minimum-coverage", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    payload = json.loads(args.expected.read_text(encoding="utf-8"))
    expected_segments = (
        payload["segments"]
        if isinstance(payload, Mapping) and "segments" in payload
        else payload
    )
    if not isinstance(expected_segments, list):
        raise ValueError("expected JSON은 구간 목록이어야 합니다.")

    repository = PgVectorRepository(
        DatabaseConfig.from_environment(EMBEDDING_ROOT / ".env")
    )
    report = compare_metadata(
        expected_segments,
        repository.list_segments(),
        minimum_coverage=args.minimum_coverage,
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
