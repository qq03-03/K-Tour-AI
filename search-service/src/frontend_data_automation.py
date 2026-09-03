"""Helpers for incremental coordinate and display-localization preparation.

The functions in this module are deliberately side-effect free.  They read a
metadata payload and return new dictionaries so the source metadata is never
modified in place.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


COORDINATE_REVIEW_FIELDS = (
    "place_id",
    "source_segment_id",
    "video_id",
    "source_url",
    "current_place_candidates",
    "region",
    "city",
    "latitude",
    "longitude",
    "selection_status",
    "notes",
)

BROAD_PLACE_NAMES = {
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "경기도",
    "강원도",
    "충청도",
    "전라도",
    "경상도",
    "제주도",
}


class PlaceIdentityConflict(ValueError):
    """Raised when one place_id points at more than one place name."""


def load_json(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def flatten_metadata(payload: object) -> list[dict[str, Any]]:
    """Return flat segment records from flat VLM or nested collection JSON."""

    raw_records: object = payload
    if isinstance(payload, Mapping) and "segments" in payload:
        raw_records = payload["segments"]
    if isinstance(raw_records, (str, bytes)) or not isinstance(raw_records, Sequence):
        raise ValueError("metadata는 배열 또는 segments 배열을 가진 객체여야 합니다.")

    values = list(raw_records)
    if not values:
        raise ValueError("metadata에 레코드가 없습니다.")
    if all(isinstance(item, Mapping) and item.get("segment_id") for item in values):
        return [dict(item) for item in values if isinstance(item, Mapping)]

    flattened: list[dict[str, Any]] = []
    for root_index, root in enumerate(values):
        if not isinstance(root, Mapping):
            raise ValueError(f"metadata[{root_index}]는 객체여야 합니다.")
        places = root.get("places")
        if isinstance(places, (str, bytes)) or not isinstance(places, Sequence):
            raise ValueError(f"metadata[{root_index}].places는 배열이어야 합니다.")
        video_id = _optional_text(root.get("video_id")) or _optional_text(
            root.get("video_id_prefix")
        )
        drama_title = _optional_text(root.get("drama_title"))
        for place_index, place in enumerate(places):
            if not isinstance(place, Mapping):
                raise ValueError(
                    f"metadata[{root_index}].places[{place_index}]는 객체여야 합니다."
                )
            segments = place.get("segments")
            if isinstance(segments, (str, bytes)) or not isinstance(segments, Sequence):
                raise ValueError(
                    f"metadata[{root_index}].places[{place_index}].segments는 배열이어야 합니다."
                )
            inherited = {
                "video_id": video_id,
                "drama_title": drama_title,
                "place_id": _optional_text(place.get("place_id")),
                "place_name": _optional_text(place.get("place_name")),
                "region": _optional_text(place.get("region")),
                "city": _optional_text(place.get("city")),
                "youtube_id": _optional_text(place.get("youtube_id")),
                "source_url": _optional_text(place.get("source_url")),
            }
            for segment_index, segment in enumerate(segments):
                if not isinstance(segment, Mapping):
                    raise ValueError(
                        "metadata"
                        f"[{root_index}].places[{place_index}].segments[{segment_index}]"
                        "는 객체여야 합니다."
                    )
                record = dict(inherited)
                record.update(dict(segment))
                flattened.append(record)
    if not flattened:
        raise ValueError("metadata에 segment가 없습니다.")
    return flattened


def extract_segment_ids(payload: object) -> set[str]:
    """Collect segment_id values from a preprocessing manifest of any depth."""

    found: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            segment_id = value.get("segment_id")
            if isinstance(segment_id, str) and segment_id.strip():
                found.add(segment_id.strip())
            for child in value.values():
                visit(child)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for child in value:
                visit(child)

    visit(payload)
    if not found:
        raise ValueError("전처리 파일에서 segment_id를 찾지 못했습니다.")
    return found


def filter_accepted_segments(
    records: Sequence[Mapping[str, Any]], accepted_segment_ids: set[str] | None
) -> list[dict[str, Any]]:
    copied = [dict(record) for record in records]
    if accepted_segment_ids is None:
        return copied
    available = {
        _required_text(record.get("segment_id"), "segment_id") for record in copied
    }
    missing = sorted(accepted_segment_ids - available)
    if missing:
        preview = ", ".join(missing[:5])
        suffix = " ..." if len(missing) > 5 else ""
        raise ValueError(
            f"전처리 통과 segment가 metadata에 없습니다: {preview}{suffix}"
        )
    return [
        record
        for record in copied
        if _required_text(record.get("segment_id"), "segment_id")
        in accepted_segment_ids
    ]


def validate_segment_and_place_identity(records: Sequence[Mapping[str, Any]]) -> None:
    segment_occurrences: dict[str, int] = defaultdict(int)
    names_by_place: dict[str, set[str]] = defaultdict(set)
    for index, record in enumerate(records):
        segment_id = _required_text(record.get("segment_id"), f"metadata[{index}].segment_id")
        place_id = _required_text(record.get("place_id"), f"metadata[{index}].place_id")
        place_name = _required_text(record.get("place_name"), f"metadata[{index}].place_name")
        segment_occurrences[segment_id] += 1
        names_by_place[place_id].add(place_name)

    duplicate_segments = sorted(
        segment_id for segment_id, count in segment_occurrences.items() if count > 1
    )
    if duplicate_segments:
        raise ValueError("segment_id 중복: " + ", ".join(duplicate_segments))

    conflicts = {
        place_id: sorted(names)
        for place_id, names in names_by_place.items()
        if len(names) > 1
    }
    if conflicts:
        detail = "; ".join(
            f"{place_id}={' / '.join(names)}"
            for place_id, names in sorted(conflicts.items())
        )
        raise PlaceIdentityConflict("place_id와 place_name 충돌: " + detail)


def load_existing_coordinates(paths: Iterable[str | Path]) -> dict[str, dict[str, str]]:
    """Load approved coordinates from CSV or JSON files, keyed by place_id."""

    result: dict[str, dict[str, str]] = {}
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(f"기존 좌표 파일을 찾을 수 없습니다: {path}")
        rows = _coordinate_rows(path)
        for row in rows:
            place_id = _optional_text(row.get("place_id"))
            latitude = _coordinate_text(row.get("latitude"))
            longitude = _coordinate_text(row.get("longitude"))
            if not place_id or not latitude or not longitude:
                continue
            candidate = {
                "place_id": place_id,
                "place_name": _optional_text(row.get("place_name")),
                "region": _optional_text(row.get("region")),
                "city": _optional_text(row.get("city")),
                "latitude": latitude,
                "longitude": longitude,
            }
            existing = result.get(place_id)
            if existing and (
                existing["latitude"] != latitude or existing["longitude"] != longitude
            ):
                raise ValueError(f"기존 좌표 파일에서 {place_id} 좌표가 충돌합니다.")
            result[place_id] = candidate
    return result


def build_coordinate_review_rows(
    records: Sequence[Mapping[str, Any]],
    *,
    existing_coordinates: Mapping[str, Mapping[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Create one Kakao-review row per unique place_id."""

    validate_segment_and_place_identity(records)
    existing_coordinates = existing_coordinates or {}
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[_required_text(record.get("place_id"), "place_id")].append(record)

    output: list[dict[str, str]] = []
    for place_id in sorted(grouped, key=_place_sort_key):
        place_records = grouped[place_id]
        first = place_records[0]
        place_name = _required_text(first.get("place_name"), f"{place_id}.place_name")
        known = existing_coordinates.get(place_id, {})
        latitude = _optional_text(known.get("latitude"))
        longitude = _optional_text(known.get("longitude"))
        if latitude and longitude:
            status = "기존 좌표 재사용"
            notes = ""
        elif place_name in BROAD_PLACE_NAMES:
            status = "장소명 검토 필요"
            notes = "좌표를 지정하기에는 장소명이 너무 포괄적입니다."
        else:
            status = "좌표 조회 필요"
            notes = ""
        output.append(
            {
                "place_id": place_id,
                "source_segment_id": "; ".join(
                    _unique_texts(record.get("segment_id") for record in place_records)
                ),
                "video_id": "; ".join(
                    _unique_texts(record.get("video_id") for record in place_records)
                ),
                "source_url": "; ".join(
                    _unique_texts(record.get("source_url") for record in place_records)
                ),
                "current_place_candidates": place_name,
                "region": _optional_text(first.get("region")),
                "city": _optional_text(first.get("city")),
                "latitude": latitude,
                "longitude": longitude,
                "selection_status": status,
                "notes": notes,
            }
        )
    return output


def coordinate_summary(rows: Sequence[Mapping[str, str]]) -> dict[str, int]:
    statuses = defaultdict(int)
    for row in rows:
        statuses[_optional_text(row.get("selection_status"))] += 1
    return {
        "place_count": len(rows),
        "reused_count": statuses["기존 좌표 재사용"],
        "lookup_count": statuses["좌표 조회 필요"],
        "review_count": statuses["장소명 검토 필요"],
    }


def _coordinate_rows(path: Path) -> list[Mapping[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    payload = load_json(path)
    raw_rows: object = payload
    if isinstance(payload, Mapping):
        for key in ("places", "records", "coordinates"):
            if key in payload:
                raw_rows = payload[key]
                break
    if isinstance(raw_rows, (str, bytes)) or not isinstance(raw_rows, Sequence):
        raise ValueError(f"좌표 JSON은 배열이어야 합니다: {path}")
    rows: list[Mapping[str, Any]] = []
    for index, row in enumerate(raw_rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"{path}의 좌표[{index}]는 객체여야 합니다.")
        rows.append(row)
    return rows


def _place_sort_key(place_id: str) -> tuple[int, str]:
    suffix = place_id[1:] if place_id.startswith("P") else ""
    return (int(suffix), place_id) if suffix.isdigit() else (10**9, place_id)


def _unique_texts(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _optional_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _optional_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _coordinate_text(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return _optional_text(value)


def _required_text(value: object, field_name: str) -> str:
    text = _optional_text(value)
    if not text:
        raise ValueError(f"{field_name}은 빈 문자열이 아니어야 합니다.")
    return text
