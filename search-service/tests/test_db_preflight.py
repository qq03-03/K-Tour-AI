from __future__ import annotations

from src.db_preflight import analyze_db_snapshot, build_dry_run_snapshot


def metadata() -> list[dict[str, str]]:
    return [
        {
            "segment_id": "SEG_A",
            "place_id": "P001",
            "keyframe_path": "keyframes/A.jpg",
        },
        {
            "segment_id": "SEG_B",
            "place_id": "P030",
            "keyframe_path": "keyframes/B.jpg",
        },
    ]


def test_dry_run_snapshot_passes_all_checks() -> None:
    report = analyze_db_snapshot(build_dry_run_snapshot(metadata()), metadata())

    assert report["summary"]["status"] == "pass"
    assert report["summary"]["failed_checks"] == []


def test_stale_missing_and_inconsistent_vectors_are_reported() -> None:
    snapshot = build_dry_run_snapshot(metadata())
    snapshot["segment_ids"] = ["SEG_A", "STALE"]
    snapshot["text_vector_dimensions"] = [512, 768]
    snapshot["p030_segment_ids"] = []

    report = analyze_db_snapshot(snapshot, metadata())

    assert report["summary"]["status"] == "fail"
    assert set(report["summary"]["failed_checks"]) == {
        "segments",
        "text_vector_dimensions",
        "p030_changgyeonggung",
    }
    segment_check = next(item for item in report["checks"] if item["name"] == "segments")
    assert segment_check["missing"] == ["SEG_B"]
    assert segment_check["stale"] == ["STALE"]


def test_missing_tables_stops_before_data_queries() -> None:
    report = analyze_db_snapshot({"tables": ["video_segments"]}, metadata())

    assert report["summary"]["status"] == "fail"
    assert report["summary"]["failed_checks"] == ["required_tables"]
