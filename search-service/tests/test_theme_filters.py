from __future__ import annotations

import pytest

from src.theme_filters import (
    build_theme_index,
    filter_by_themes,
    normalize_themes,
)


def test_frontend_theme_aliases_are_normalized() -> None:
    assert normalize_themes(
        ["night-view", "cherry-blossom", "autumn-leaves", "beach"]
    ) == ["night_view", "flower", "autumn_leaves", "sea"]


def test_theme_mapping_filters_by_source_segment_with_or_semantics() -> None:
    payload = {
        "entries": [
            {"source_segment_id": "SOURCE_A", "themes": ["flower", "traditional"]},
            {"source_segment_id": "SOURCE_B", "themes": ["sea"]},
        ]
    }
    segments = [
        {"segment_id": "SOURCE_A_SCENE_001", "source_segment_id": "SOURCE_A"},
        {"segment_id": "SOURCE_A_SCENE_002", "source_segment_id": "SOURCE_A"},
        {"segment_id": "SOURCE_B_SCENE_001", "source_segment_id": "SOURCE_B"},
        {"segment_id": "SOURCE_C_SCENE_001", "source_segment_id": "SOURCE_C"},
    ]

    results = filter_by_themes(
        segments,
        ["cherry-blossom", "beach"],
        theme_index=build_theme_index(payload),
    )

    assert [item["segment_id"] for item in results] == [
        "SOURCE_A_SCENE_001",
        "SOURCE_A_SCENE_002",
        "SOURCE_B_SCENE_001",
    ]


def test_duplicate_theme_mapping_source_is_rejected() -> None:
    with pytest.raises(ValueError, match="중복"):
        build_theme_index(
            {
                "entries": [
                    {"source_segment_id": "SOURCE_A", "themes": ["flower"]},
                    {"source_segment_id": "SOURCE_A", "themes": ["sea"]},
                ]
            }
        )
