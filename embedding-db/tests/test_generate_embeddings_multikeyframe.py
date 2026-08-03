import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "generate_embeddings.py"
)

spec = importlib.util.spec_from_file_location(
    "generate_embeddings",
    SCRIPT_PATH,
)
generate_embeddings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_embeddings)


def test_build_search_text_includes_region_and_drama_title():
    item = {
        "place_name": "주문진 해변",
        "region": "강원특별자치도",
        "drama_title": "도깨비",
        "season": "winter",
        "time_of_day": "day",
        "description": "눈이 내리는 해변",
        "mood": ["romantic"],
        "scene_elements": ["sea", "snow"],
        "activity": ["walking"],
    }

    text = generate_embeddings.build_search_text(item)

    assert "강원특별자치도" in text
    assert "도깨비" in text


def test_build_keyframe_id_uses_segment_and_filename_stem():
    assert hasattr(
        generate_embeddings,
        "build_keyframe_id",
    ), "build_keyframe_id 함수가 아직 없습니다."

    item = {
        "segment_id": "V005_P010_S001",
        "keyframe_path": (
            "keyframes/HCCC_01/"
            "HCCC_01_SCENE_02.jpg"
        ),
    }

    result = generate_embeddings.build_keyframe_id(item)

    assert result == (
        "V005_P010_S001__HCCC_01_SCENE_02"
    )


def test_resolve_keyframe_path_uses_realdata_root(tmp_path):
    assert hasattr(
        generate_embeddings,
        "resolve_keyframe_path",
    ), "resolve_keyframe_path 함수가 아직 없습니다."

    result = generate_embeddings.resolve_keyframe_path(
        tmp_path,
        "keyframes/GOBLIN_03/GOBLIN_03_SCENE_01.jpg",
    )

    expected = (
        tmp_path
        / "K-contents_preprocessed"
        / "preprocessed_output"
        / "keyframes"
        / "GOBLIN_03"
        / "GOBLIN_03_SCENE_01.jpg"
    )

    assert result == expected


def test_group_metadata_preserves_multiple_keyframes_per_segment():
    assert hasattr(
        generate_embeddings,
        "group_metadata_by_segment",
    ), "group_metadata_by_segment 함수가 아직 없습니다."

    metadata = [
        {
            "segment_id": "SEG001",
            "keyframe_path": "keyframes/A/A_01.jpg",
        },
        {
            "segment_id": "SEG001",
            "keyframe_path": "keyframes/A/A_02.jpg",
        },
        {
            "segment_id": "SEG002",
            "keyframe_path": "keyframes/B/B_01.jpg",
        },
    ]

    grouped = generate_embeddings.group_metadata_by_segment(
        metadata
    )

    assert set(grouped) == {"SEG001", "SEG002"}
    assert len(grouped["SEG001"]) == 2
    assert len(grouped["SEG002"]) == 1


def test_build_segment_search_text_combines_all_keyframes():
    assert hasattr(
        generate_embeddings,
        "build_segment_search_text",
    ), "build_segment_search_text 함수가 아직 없습니다."

    items = [
        {
            "place_name": "주문진 해변",
            "region": "강원특별자치도",
            "drama_title": "도깨비",
            "season": "winter",
            "description": "눈이 내리는 해변",
            "mood": ["romantic"],
            "scene_elements": ["sea"],
            "activity": ["walking"],
        },
        {
            "place_name": "주문진 해변",
            "region": "강원특별자치도",
            "drama_title": "도깨비",
            "season": "winter",
            "description": "파도가 보이는 바닷가",
            "mood": ["peaceful"],
            "scene_elements": ["waves"],
            "activity": ["standing"],
        },
    ]

    text = generate_embeddings.build_segment_search_text(items)

    assert "도깨비" in text
    assert "강원특별자치도" in text
    assert "눈이 내리는 해변" in text
    assert "파도가 보이는 바닷가" in text


def test_realdata_groups_into_24_segments_and_42_keyframes():
    import json

    repo_root = Path(__file__).resolve().parents[2]

    metadata_path = (
        repo_root
        / "metadata_vlm_final.json"
    )

    with metadata_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    grouped = (
        generate_embeddings.group_metadata_by_segment(
            metadata
        )
    )

    keyframe_ids = [
        generate_embeddings.build_keyframe_id(item)
        for item in metadata
    ]

    assert len(metadata) == 42
    assert len(grouped) == 24
    assert len(keyframe_ids) == 42
    assert len(set(keyframe_ids)) == 42
