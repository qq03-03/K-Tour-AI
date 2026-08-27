"""place_id 단위 다국어 표시 카탈로그: backend_integrated_search_catalog_v2.json의
locations.places 로드/조회.

BACKEND_APPLY_GUIDE.md 6절: 검색 결과의 place_id로 이 카탈로그를 조회해
localized[lang]의 place_name/region/city/address/location_label을 반환한다.
요청 언어의 주소 번역이 없으면 한국어 주소로, 그마저 없으면 빈 문자열로
대체한다. 조회 전에 legacy place_id(P013 등)는 canonical id(P044)로
정규화한다 (5절, place_id_normalization.py 참고).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

from .place_id_normalization import canonicalize_place_id

_DEFAULT_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "backend_integrated_search_catalog_v2.json"
)

_DISPLAY_FIELDS = ("place_name", "region", "city", "address", "location_label")


class PlaceDisplay(TypedDict):
    place_name: str
    region: str
    city: str
    address: str
    location_label: str
    latitude: float | None
    longitude: float | None


@lru_cache
def load_place_catalog(path: str | Path = _DEFAULT_PATH) -> dict[str, dict[str, Any]]:
    """place_id -> 카탈로그 레코드(원본) 매핑을 로드한다. 프로세스당 한 번만 읽는다."""
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    return {record["place_id"]: record for record in data["locations"]["places"]}


def display_for(
    place_id: str,
    lang: str,
    *,
    catalog: dict[str, dict[str, Any]] | None = None,
) -> PlaceDisplay | None:
    """이 place_id에 대한 요청 언어 표시값을 반환한다.

    카탈로그에 없는 place_id면 None (호출부는 DB에서 읽은 원본 필드를
    그대로 유지해야 한다). 요청 언어의 주소가 비어 있으면 한국어 주소로
    대체하고, 그마저 없으면 빈 문자열로 둔다.
    """
    resolved_catalog = catalog if catalog is not None else load_place_catalog()
    record = resolved_catalog.get(canonicalize_place_id(place_id))
    if record is None:
        return None

    localized = record.get("localized", {})
    requested = localized.get(lang) or localized.get("ko") or {}
    korean = localized.get("ko") or {}

    result: dict[str, Any] = {field: requested.get(field, "") for field in _DISPLAY_FIELDS}
    if not result["address"]:
        result["address"] = korean.get("address", "")
    result["latitude"] = record.get("latitude")
    result["longitude"] = record.get("longitude")
    return result  # type: ignore[return-value]
