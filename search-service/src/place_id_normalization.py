"""동일 장소를 가리키는 legacy/canonical place_id 정규화 (예: P013/P044).

BACKEND_APPLY_GUIDE.md 5절: "P013 또는 P044 필터는 둘 다 검색하도록 OR
확장하고, 결과 표시는 P044 주문진 방파제로 통일". 기존 source_segment_id,
segment_id, keyframe_id, vector는 변경하지 않는다 -- 이 모듈은 필터 확장과
표시용 id 정규화에만 관여한다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

_DEFAULT_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "backend_integrated_search_catalog_v2.json"
)


@lru_cache
def load_place_id_normalization_index(path: str | Path = _DEFAULT_PATH) -> dict[str, str]:
    """legacy_place_id -> canonical_place_id 매핑을 로드한다."""
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    mapping: dict[str, str] = {}
    for entry in data["locations"]["place_id_normalization"]:
        canonical = entry["canonical_place_id"]
        for legacy in entry["legacy_place_ids"]:
            mapping[legacy] = canonical
    return mapping


def canonicalize_place_id(place_id: str, index: dict[str, str] | None = None) -> str:
    """표시용으로 legacy id를 canonical id로 정규화한다. legacy가 아니면 그대로 반환."""
    resolved_index = index if index is not None else load_place_id_normalization_index()
    return resolved_index.get(place_id, place_id)


def expand_place_ids(place_ids: Sequence[str], index: dict[str, str] | None = None) -> list[str]:
    """place_id 필터 요청 목록을 legacy<->canonical 짝끼리 OR로 확장한다."""
    resolved_index = index if index is not None else load_place_id_normalization_index()
    canonical_to_legacy: dict[str, list[str]] = {}
    for legacy, canonical in resolved_index.items():
        canonical_to_legacy.setdefault(canonical, []).append(legacy)

    expanded: list[str] = []
    seen: set[str] = set()
    for place_id in place_ids:
        canonical = resolved_index.get(place_id, place_id)
        for candidate in (place_id, canonical, *canonical_to_legacy.get(canonical, [])):
            if candidate not in seen:
                seen.add(candidate)
                expanded.append(candidate)
    return expanded
