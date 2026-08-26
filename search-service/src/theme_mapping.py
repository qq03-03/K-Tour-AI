"""source_segment_id 단위 테마 하드 필터: theme_mapping.confirmed_final_v6.json 로드/적용.

이 매핑은 기존 517건 metadata·embedding을 대체하지 않는다. source_segment_id
기준으로 연결되는 별도의 구조화 필터 데이터이며, 재임베딩이 필요 없다.
자세한 내용은 BACKEND_THEME_MAPPING_APPLY_GUIDE.txt 참고.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

ALLOWED_THEMES = frozenset(
    {
        "night_view",
        "flower",
        "autumn_leaves",
        "traditional",
        "field",
        "hiking",
        "forest",
        "drive",
        "sea",
    }
)

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "theme_mapping.confirmed_final_v6.json"


@lru_cache
def load_theme_index(path: str | Path = _DEFAULT_PATH) -> dict[str, list[str]]:
    """source_segment_id -> themes 매핑을 로드한다.

    프로세스 수명 동안 한 번만 파일을 읽는다 (``lru_cache``). 매핑에 없는
    source_segment_id는 인덱스에 아예 포함되지 않으며, 이는 "테마가 없는
    데이터도 일반 자연어 검색에서는 제외하지 않는다"는 정책과 맞는다 —
    호출부는 없는 키를 빈 테마 목록으로 취급해야 한다 (``themes_for`` 참고).
    """
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    return {entry["source_segment_id"]: list(entry["themes"]) for entry in data["entries"]}


def themes_for(
    source_segment_id: str,
    index: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """이 구간에 매핑된 테마 목록을 반환한다. 매핑이 없으면 빈 목록."""
    resolved_index = index if index is not None else load_theme_index()
    return list(resolved_index.get(source_segment_id, []))


def filter_by_theme(
    segments: Sequence[Mapping[str, Any]],
    theme_ids: Sequence[str] | None,
    *,
    index: Mapping[str, Sequence[str]] | None = None,
) -> list[Mapping[str, Any]]:
    """요청된 테마 중 하나 이상을 가진 구간만 남긴다 (OR 조건).

    ``theme_ids``가 비어 있거나 None이면 필터를 적용하지 않고 원래
    목록을 그대로 반환한다.
    """
    if not theme_ids:
        return list(segments)
    resolved_index = index if index is not None else load_theme_index()
    requested = set(theme_ids)
    return [
        segment
        for segment in segments
        if requested & set(resolved_index.get(str(segment.get("source_segment_id")), []))
    ]
