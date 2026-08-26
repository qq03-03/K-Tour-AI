"""metadata place_id와 좌표 전달본의 연결을 읽기 전용으로 검증한다."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


KOREA_LATITUDE_RANGE = (32.0, 39.5)
KOREA_LONGITUDE_RANGE = (124.0, 132.5)


def validate_coordinate_alignment(
    metadata_records: Sequence[Mapping[str, Any]],
    coordinate_payload: object | None,
    *,
    near_distance_meters: float = 50.0,
) -> dict[str, Any]:
    if coordinate_payload is None:
        return {
            "provided": False,
            "metadata_place_count": len(_metadata_places(metadata_records)),
            "coordinate_count": 0,
            "issues": [],
            "duplicate_or_near_candidates": [],
            "error_count": 0,
            "warning_count": 0,
            "is_valid": True,
        }
    records = _coordinate_records(coordinate_payload)
    metadata_places = _metadata_places(metadata_records)
    ids = [str(row.get("place_id") or "").strip() for row in records]
    coordinate_by_id = {
        str(row.get("place_id") or "").strip(): row
        for row in records
        if str(row.get("place_id") or "").strip()
    }
    issues: list[dict[str, Any]] = []
    for place_id, count in Counter(ids).items():
        if not place_id:
            issues.append(_issue("error", "MISSING_PLACE_ID", None, "place_id가 비어 있습니다."))
        elif count > 1:
            issues.append(_issue("error", "DUPLICATE_PLACE_ID", place_id, f"{count}건"))
    for place_id in sorted(set(metadata_places) - set(coordinate_by_id)):
        issues.append(_issue("error", "MISSING_COORDINATE", place_id, "metadata 장소의 좌표가 없습니다."))
    for place_id in sorted(set(coordinate_by_id) - set(metadata_places)):
        issues.append(_issue("warning", "STALE_COORDINATE", place_id, "현재 metadata에 없는 좌표입니다."))

    valid_points: list[tuple[str, float, float]] = []
    for place_id, row in sorted(coordinate_by_id.items()):
        latitude = row.get("latitude")
        longitude = row.get("longitude")
        if not _finite(latitude) or not _finite(longitude):
            issues.append(_issue("error", "INVALID_COORDINATE", place_id, "위도/경도가 유한 숫자가 아닙니다."))
            continue
        lat = float(latitude)
        lon = float(longitude)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            issues.append(_issue("error", "COORDINATE_OUT_OF_RANGE", place_id, f"{lat}, {lon}"))
            continue
        if not (
            KOREA_LATITUDE_RANGE[0] <= lat <= KOREA_LATITUDE_RANGE[1]
            and KOREA_LONGITUDE_RANGE[0] <= lon <= KOREA_LONGITUDE_RANGE[1]
        ):
            issues.append(
                _issue(
                    "error",
                    "COORDINATE_OUTSIDE_KOREA_BOUNDS",
                    place_id,
                    f"K-Tour 한국 영역 밖 좌표: {lat}, {lon}",
                )
            )
            continue
        valid_points.append((place_id, lat, lon))
        metadata = metadata_places.get(place_id)
        if metadata:
            for field in ("place_name", "region", "city"):
                expected = str(metadata.get(field) or "").strip().casefold()
                actual = str(row.get(field) or "").strip().casefold()
                if expected != actual:
                    issues.append(
                        _issue(
                            "error",
                            "COORDINATE_METADATA_MISMATCH",
                            place_id,
                            f"{field}: coordinate={row.get(field)!r}, metadata={metadata.get(field)!r}",
                        )
                    )

    near_candidates = []
    for index, (left_id, left_lat, left_lon) in enumerate(valid_points):
        for right_id, right_lat, right_lon in valid_points[index + 1 :]:
            distance = _haversine_meters(left_lat, left_lon, right_lat, right_lon)
            if distance <= near_distance_meters:
                near_candidates.append(
                    {
                        "left_place_id": left_id,
                        "right_place_id": right_id,
                        "distance_meters": round(distance, 3),
                        "exact_same_coordinate": distance < 0.001,
                        "action": "자동 병합하지 말고 장소 의미를 사람이 확인",
                    }
                )
    error_count = sum(item["severity"] == "error" for item in issues)
    warning_count = sum(item["severity"] == "warning" for item in issues)
    return {
        "provided": True,
        "metadata_place_count": len(metadata_places),
        "coordinate_count": len(records),
        "missing_place_ids": sorted(set(metadata_places) - set(coordinate_by_id)),
        "stale_place_ids": sorted(set(coordinate_by_id) - set(metadata_places)),
        "issues": issues,
        "duplicate_or_near_candidates": near_candidates,
        "error_count": error_count,
        "warning_count": warning_count,
        "is_valid": error_count == 0,
    }


def _metadata_places(records: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("place_id") or "").strip(): row
        for row in records
        if str(row.get("place_id") or "").strip()
    }


def _coordinate_records(payload: object) -> list[dict[str, Any]]:
    raw = payload.get("records") if isinstance(payload, Mapping) else payload
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise ValueError("좌표 JSON은 records 배열을 가져야 합니다.")
    invalid = [index for index, item in enumerate(raw) if not isinstance(item, Mapping)]
    if invalid:
        raise ValueError(f"좌표 records에 객체가 아닌 항목이 있습니다: {invalid}")
    return [dict(item) for item in raw]


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _finite(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _issue(
    severity: str, code: str, place_id: str | None, message: str
) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "place_id": place_id,
        "message": message,
    }
