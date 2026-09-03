from __future__ import annotations

from src.display_translation import (
    plan_incremental_translations,
    translation_source_hash,
)


def source_record(segment_id: str, description: str) -> dict:
    return {
        "segment_id": segment_id,
        "keyframe_id": f"{segment_id}__KF001",
        "source": {
            "description": description,
            "mood": ["고요한"],
            "activity": ["산책"],
            "scene_elements": ["나무"],
        },
    }


def completed_record(source: dict) -> dict:
    return {
        "segment_id": source["segment_id"],
        "keyframe_id": source["keyframe_id"],
        "source_hash": translation_source_hash(source),
        "ko": {},
        "en": {},
        "ja": {},
        "zh": {},
    }


def test_unchanged_translation_is_reused() -> None:
    source = source_record("SEG_001", "고요한 숲길입니다.")

    plan = plan_incremental_translations([source], [completed_record(source)])

    assert len(plan["reusable"]) == 1
    assert plan["pending"] == []
    assert plan["changed_keys"] == []
    assert plan["stale_keys"] == []


def test_changed_source_is_retranslated() -> None:
    old_source = source_record("SEG_001", "고요한 숲길입니다.")
    changed_source = source_record("SEG_001", "비가 내리는 고요한 숲길입니다.")

    plan = plan_incremental_translations(
        [changed_source],
        [completed_record(old_source)],
    )

    assert plan["reusable"] == []
    assert plan["pending"] == [changed_source]
    assert plan["changed_keys"] == [("SEG_001", "SEG_001__KF001")]


def test_new_and_deleted_records_are_separated() -> None:
    current = source_record("SEG_NEW", "새 장면입니다.")
    deleted = source_record("SEG_OLD", "삭제된 장면입니다.")

    plan = plan_incremental_translations([current], [completed_record(deleted)])

    assert plan["added_keys"] == [("SEG_NEW", "SEG_NEW__KF001")]
    assert plan["stale_keys"] == [("SEG_OLD", "SEG_OLD__KF001")]
    assert plan["pending"] == [current]
    assert plan["reusable"] == []


def test_legacy_checkpoint_without_hash_is_refreshed() -> None:
    source = source_record("SEG_001", "고요한 숲길입니다.")
    legacy = {
        "segment_id": source["segment_id"],
        "keyframe_id": source["keyframe_id"],
        "en": {},
    }

    plan = plan_incremental_translations([source], [legacy])

    assert plan["pending"] == [source]
    assert plan["changed_keys"] == [("SEG_001", "SEG_001__KF001")]


def test_source_hash_ignores_mapping_key_order() -> None:
    first = source_record("SEG_001", "고요한 숲길입니다.")
    second = {
        "keyframe_id": first["keyframe_id"],
        "segment_id": first["segment_id"],
        "source": {
            "scene_elements": ["나무"],
            "activity": ["산책"],
            "mood": ["고요한"],
            "description": "고요한 숲길입니다.",
        },
    }

    assert translation_source_hash(first) == translation_source_hash(second)
