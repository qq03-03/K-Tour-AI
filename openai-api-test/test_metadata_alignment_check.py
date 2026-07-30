from __future__ import annotations

from run_metadata_alignment_check import compare_metadata


def test_compare_metadata_reports_multilingual_alias_matches() -> None:
    report = compare_metadata(
        [
            {
                "segment_id": "SEG_A",
                "scene_elements": ["수국", "정자"],
                "activity": ["피크닉"],
                "mood": [],
            }
        ],
        [
            {
                "segment_id": "SEG_A",
                "scene_elements": ["hydrangeas", "traditional pavilion"],
                "activity": ["picnic"],
                "mood": [],
            }
        ],
    )

    assert report["summary"]["low_coverage_count"] == 0
    assert report["segments"][0]["overall_coverage"] == 1.0


def test_compare_metadata_reports_missing_segment_concepts() -> None:
    report = compare_metadata(
        [
            {
                "segment_id": "SEG_A",
                "scene_elements": ["수영장", "등불"],
                "activity": ["산책"],
                "mood": [],
            }
        ],
        [
            {
                "segment_id": "SEG_A",
                "scene_elements": ["balloons", "trees"],
                "activity": ["walking"],
                "mood": [],
            }
        ],
    )

    assert report["summary"]["low_coverage_count"] == 1
    scene = report["segments"][0]["fields"]["scene_elements"]
    assert scene["coverage"] == 0.0
    assert scene["missing"] == ["lantern", "pool"]
