from __future__ import annotations

import json

from src.final_metadata_validation import build_final_metadata_report


def metadata_record(**overrides):
    value = {
        "segment_id": "VID_01_SCENE_001",
        "source_segment_id": "V001_P001_S001",
        "video_id": "VID_01",
        "place_id": "P001",
        "place_name": "테스트 장소",
        "region": "서울특별시",
        "city": "서울특별시",
        "drama_title": "테스트 작품",
        "start_time": 1.0,
        "end_time": 5.0,
        "keyframe_path": "keyframes/VID_01/VID_01_SCENE_001.jpg",
        "season": "봄",
        "time_of_day": "낮",
        "mood": ["평화로운"],
        "activity": ["산책"],
        "scene_elements": ["나무"],
        "description": "나무가 보이는 봄 장면",
    }
    value.update(overrides)
    return value


def write_inputs(tmp_path, record=None):
    record = record or metadata_record()
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps([record], ensure_ascii=False), encoding="utf-8"
    )
    preprocessing_path = tmp_path / "preprocessed_segments.json"
    preprocessing_path.write_text(
        json.dumps(
            [
                {
                    "video_id": "VID_01",
                    "segments": [
                        {
                            "segment_id": "VID_01_SCENE_001",
                            "source_segment_id": "V001_P001_S001",
                            "start_time": 1.0,
                            "end_time": 5.0,
                            "keyframe_path": (
                                "keyframes/VID_01/VID_01_SCENE_001.jpg"
                            ),
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    return metadata_path, preprocessing_path


def test_final_report_passes_when_quality_and_alignment_match(tmp_path) -> None:
    metadata_path, preprocessing_path = write_inputs(tmp_path)
    keyframe = tmp_path / "assets" / "keyframes" / "VID_01"
    keyframe.mkdir(parents=True)
    (keyframe / "VID_01_SCENE_001.jpg").write_bytes(b"image")

    report = build_final_metadata_report(
        metadata_path,
        preprocessing_path,
        keyframe_root=tmp_path / "assets",
    )

    assert report["is_valid"] is True
    assert report["summary"]["linked_segment_count"] == 1
    assert report["summary"]["alignment_issue_count"] == 0


def test_final_report_combines_quality_and_alignment_failures(tmp_path) -> None:
    metadata_path, preprocessing_path = write_inputs(
        tmp_path,
        metadata_record(
            source_segment_id="WRONG_SOURCE",
            season="spring",
            start_time=2.0,
        ),
    )
    keyframe = tmp_path / "keyframes" / "VID_01"
    keyframe.mkdir(parents=True)
    (keyframe / "VID_01_SCENE_001.jpg").write_bytes(b"image")

    report = build_final_metadata_report(metadata_path, preprocessing_path)

    assert report["is_valid"] is False
    quality_codes = {issue["code"] for issue in report["quality"]["issues"]}
    assert "NON_CANONICAL_SEASON" in quality_codes
    assert any(
        "source_segment_id 불일치" in issue
        for issue in report["alignment"]["issues"]
    )
    assert any(
        "start_time 불일치" in issue
        for issue in report["alignment"]["issues"]
    )
