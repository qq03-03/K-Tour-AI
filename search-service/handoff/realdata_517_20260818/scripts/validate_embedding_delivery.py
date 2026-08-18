#!/usr/bin/env python3
"""K-Tour AI 517 SCENE 임베딩 전달물 검증기. 표준 라이브러리만 사용합니다."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path


def load_records(path: Path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        return data
    for key in ("records", "segments", "embeddings", "items", "data"):
        value = data.get(key) if isinstance(data, dict) else None
        if isinstance(value, list):
            return value
    raise ValueError(f"레코드 배열을 찾을 수 없습니다: {path}")


def record_id(row: dict):
    for key in ("segment_id", "keyframe_id", "id"):
        if row.get(key):
            return str(row[key])
    return None


def validate_embedding_file(path: Path, expected_ids: set[str], label: str):
    rows = load_records(path)
    ids = [record_id(row) for row in rows]
    missing_id = sum(value is None for value in ids)
    known = {value for value in ids if value is not None}
    return {
        "label": label,
        "path": str(path),
        "records": len(rows),
        "unique_ids": len(known),
        "missing_id_fields": missing_id,
        "missing_expected_ids": sorted(expected_ids - known),
        "unexpected_ids": sorted(known - expected_ids),
        "passed": len(rows) == len(expected_ids) and len(known) == len(expected_ids) and not missing_id,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--translations", type=Path)
    parser.add_argument("--coordinates", type=Path)
    parser.add_argument("--keyframes-zip", type=Path)
    parser.add_argument("--text-embeddings", type=Path)
    parser.add_argument("--image-embeddings", type=Path)
    parser.add_argument("--expected-count", type=int, default=517)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    metadata = load_records(args.metadata)
    ids = [str(row.get("segment_id", "")) for row in metadata]
    paths = [str(row.get("keyframe_path", "")) for row in metadata]
    expected_ids = set(ids)
    errors = []

    if len(metadata) != args.expected_count:
        errors.append(f"metadata count {len(metadata)} != {args.expected_count}")
    if len(expected_ids) != args.expected_count:
        errors.append("segment_id 중복 또는 누락")
    if len(set(paths)) != args.expected_count:
        errors.append("keyframe_path 중복 또는 누락")
    if any("_P063_" in value for value in ids):
        errors.append("P063 잔존")
    if any("_P064_" in value for value in ids):
        errors.append("P064 잔존")
    if any(float(row["end_time"]) <= float(row["start_time"]) for row in metadata):
        errors.append("start_time/end_time 오류")

    checks = []
    if args.translations:
        translations = load_records(args.translations)
        translation_ids = {str(row.get("segment_id", "")) for row in translations}
        ok = len(translations) == args.expected_count and translation_ids == expected_ids
        checks.append({"label": "translations", "records": len(translations), "unique_ids": len(translation_ids), "passed": ok})
        if not ok:
            errors.append("표시언어 ID 또는 건수 불일치")

    if args.coordinates:
        coordinates = load_records(args.coordinates)
        place_ids = {str(row.get("place_id", "")) for row in metadata}
        coordinate_ids = {str(row.get("place_id", "")) for row in coordinates}
        missing = sorted(place_ids - coordinate_ids)
        ok = not missing and all(row.get("latitude") is not None and row.get("longitude") is not None for row in coordinates)
        checks.append({"label": "coordinates", "records": len(coordinates), "missing_place_ids": missing, "passed": ok})
        if not ok:
            errors.append("좌표 누락")

    if args.keyframes_zip:
        with zipfile.ZipFile(args.keyframes_zip) as archive:
            names = {name.replace("\\", "/") for name in archive.namelist() if not name.endswith("/")}
        missing = sorted(set(paths) - names)
        unexpected = sorted(names - set(paths))
        ok = len(names) == args.expected_count and not missing and not unexpected
        checks.append({"label": "keyframes_zip", "records": len(names), "missing": missing, "unexpected": unexpected, "passed": ok})
        if not ok:
            errors.append("keyframe ZIP 불일치")

    if args.text_embeddings:
        result = validate_embedding_file(args.text_embeddings, expected_ids, "text_embeddings")
        checks.append(result)
        if not result["passed"]:
            errors.append("text embedding 불일치")

    if args.image_embeddings:
        result = validate_embedding_file(args.image_embeddings, expected_ids, "image_embeddings")
        checks.append(result)
        if not result["passed"]:
            errors.append("image embedding 불일치")

    report = {
        "metadata_records": len(metadata),
        "unique_segment_ids": len(expected_ids),
        "unique_keyframe_paths": len(set(paths)),
        "checks": checks,
        "errors": errors,
        "passed": not errors,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
