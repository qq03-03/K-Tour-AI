from __future__ import annotations

import json
from pathlib import Path

from src.production_evaluation import (
    load_anchor_cases,
    resolve_anchor_cases,
    summarize_anchor_cases,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DRAFT_PATH = PROJECT_ROOT / "data" / "production_eval_queries_draft.json"


def test_actual_draft_has_recommended_size_and_all_languages() -> None:
    cases = load_anchor_cases(DRAFT_PATH)
    summary = summarize_anchor_cases(cases)

    assert summary["query_count"] == 40
    assert summary["recommended_size_met"] is True
    assert summary["by_language"] == {"en": 4, "ja": 3, "ko": 30, "zh": 3}


def test_anchor_is_resolved_to_current_segment_id() -> None:
    cases = [
        {
            "query_id": "Q1",
            "language": "ko",
            "query": "눈 덮인 다리",
            "relevant_video_ids": ["VID_01"],
            "relevant_keyframe_paths": ["keyframes/VID_01/SCENE_01.jpg"],
            "expected_filters": {"season": ["겨울"]},
        }
    ]
    metadata = [
        {
            "segment_id": "NEW_SEGMENT_ID",
            "video_id": "VID_01",
            "keyframe_path": "keyframes/VID_01/SCENE_01.jpg",
        }
    ]

    report = resolve_anchor_cases(cases, metadata)

    assert report["resolution"]["resolved_queries"] == 1
    assert report["queries"][0]["relevant_segment_ids"] == ["NEW_SEGMENT_ID"]


def test_multiple_keyframes_of_same_segment_are_deduplicated() -> None:
    cases = [
        {
            "query_id": "Q1",
            "language": "ko",
            "query": "궁궐",
            "relevant_keyframe_paths": [
                "keyframes/V/SCENE_01.jpg",
                "keyframes/V/SCENE_02.jpg",
            ],
            "expected_filters": {},
        }
    ]
    metadata = [
        {"segment_id": "SEG", "video_id": "V", "keyframe_path": path}
        for path in cases[0]["relevant_keyframe_paths"]
    ]

    report = resolve_anchor_cases(cases, metadata)

    assert report["queries"][0]["relevant_segment_ids"] == ["SEG"]


def test_missing_keyframe_is_reported_without_fake_answer() -> None:
    cases = [
        {
            "query_id": "Q1",
            "language": "ko",
            "query": "없는 장면",
            "relevant_keyframe_paths": ["keyframes/missing.jpg"],
            "expected_filters": {},
        }
    ]

    report = resolve_anchor_cases(
        cases,
        [
            {
                "segment_id": "OTHER_SEGMENT",
                "video_id": "OTHER_VIDEO",
                "keyframe_path": "keyframes/other.jpg",
            }
        ],
    )

    assert report["queries"] == []
    assert report["resolution"]["unresolved_queries"] == 1


def test_loader_accepts_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    payload = {
        "queries": [
            {
                "query_id": "Q1",
                "language": "ko",
                "query": "한옥",
                "relevant_keyframe_paths": ["keyframes/a.jpg"],
                "expected_filters": {},
            }
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8-sig")

    assert load_anchor_cases(path)[0]["query"] == "한옥"
