"""최종 VLM 메타데이터의 자체 품질과 전처리 연결을 통합 검증한다."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_data_validation import load_metadata_payload, validate_project_metadata
from .vlm_metadata import build_alignment_report


def build_final_metadata_report(
    metadata_path: str | Path,
    preprocessing_path: str | Path,
    *,
    keyframe_root: str | Path | None = None,
) -> dict[str, Any]:
    """독립 품질검사와 전처리 정합성 검사를 한 보고서로 합친다."""

    metadata_path = Path(metadata_path)
    preprocessing_path = Path(preprocessing_path)
    quality = validate_project_metadata(
        load_metadata_payload(metadata_path),
        keyframe_root=keyframe_root,
    )
    alignment = build_alignment_report(
        metadata_path,
        preprocessing_path,
        keyframe_root=keyframe_root,
    )

    quality_summary = quality["summary"]
    return {
        "is_valid": quality["is_valid"] and alignment["is_valid"],
        "summary": {
            **quality_summary,
            "preprocessing_segment_count": alignment[
                "preprocessing_segment_count"
            ],
            "linked_segment_count": alignment["linked_segment_count"],
            "alignment_issue_count": len(alignment["issues"]),
        },
        "quality": quality,
        "alignment": alignment,
    }
