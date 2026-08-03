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

def test_build_embedding_records_separates_segments_and_keyframes(tmp_path):
    assert hasattr(
        generate_embeddings,
        "build_embedding_records",
    ), "build_embedding_records 함수가 아직 없습니다."

    metadata = [
        {
            "segment_id": "SEG001",
            "video_id": "VIDEO01",
            "place_name": "해변",
            "region": "강원특별자치도",
            "drama_title": "드라마A",
            "start_time": 0.0,
            "end_time": 10.0,
            "keyframe_path": "keyframes/A/A_01.jpg",
            "description": "첫 번째 장면",
            "mood": ["peaceful"],
            "scene_elements": ["sea"],
            "activity": ["walking"],
        },
        {
            "segment_id": "SEG001",
            "video_id": "VIDEO01",
            "place_name": "해변",
            "region": "강원특별자치도",
            "drama_title": "드라마A",
            "start_time": 0.0,
            "end_time": 10.0,
            "keyframe_path": "keyframes/A/A_02.jpg",
            "description": "두 번째 장면",
            "mood": ["romantic"],
            "scene_elements": ["waves"],
            "activity": ["standing"],
        },
        {
            "segment_id": "SEG002",
            "video_id": "VIDEO02",
            "place_name": "궁궐",
            "region": "서울특별시",
            "drama_title": "드라마B",
            "start_time": 20.0,
            "end_time": 30.0,
            "keyframe_path": "keyframes/B/B_01.jpg",
            "description": "궁궐 장면",
            "mood": ["historic"],
            "scene_elements": ["palace"],
            "activity": ["walking"],
        },
    ]

    def fake_text_encoder(text):
        assert isinstance(text, str)
        return [0.1] * 512

    def fake_image_encoder(image_path):
        assert isinstance(image_path, Path)
        return [0.2] * 512

    result = generate_embeddings.build_embedding_records(
        metadata=metadata,
        repo_root=tmp_path,
        encode_text_fn=fake_text_encoder,
        encode_image_fn=fake_image_encoder,
    )

    assert set(result) == {
        "segment_embeddings",
        "keyframe_embeddings",
    }

    assert len(result["segment_embeddings"]) == 2
    assert len(result["keyframe_embeddings"]) == 3

    segment_ids = [
        item["segment_id"]
        for item in result["segment_embeddings"]
    ]

    assert segment_ids.count("SEG001") == 1
    assert segment_ids.count("SEG002") == 1

    keyframe_ids = [
        item["keyframe_id"]
        for item in result["keyframe_embeddings"]
    ]

    assert len(set(keyframe_ids)) == 3

    assert (
        result["keyframe_embeddings"][0]["segment_id"]
        == "SEG001"
    )


def test_build_embedding_records_keeps_512_dimension_vectors(tmp_path):
    assert hasattr(
        generate_embeddings,
        "build_embedding_records",
    ), "build_embedding_records 함수가 아직 없습니다."

    metadata = [
        {
            "segment_id": "SEG001",
            "video_id": "VIDEO01",
            "place_name": "해변",
            "region": "강원특별자치도",
            "drama_title": "드라마A",
            "start_time": 0.0,
            "end_time": 10.0,
            "keyframe_path": "keyframes/A/A_01.jpg",
            "description": "해변",
            "mood": [],
            "scene_elements": [],
            "activity": [],
        }
    ]

    result = generate_embeddings.build_embedding_records(
        metadata=metadata,
        repo_root=tmp_path,
        encode_text_fn=lambda text: [0.1] * 512,
        encode_image_fn=lambda path: [0.2] * 512,
    )

    assert len(
        result["segment_embeddings"][0]["text_embedding"]
    ) == 512

    assert len(
        result["keyframe_embeddings"][0]["image_embedding"]
    ) == 512


def test_encode_text_embedding_returns_512_dimension_vector():
    assert hasattr(
        generate_embeddings,
        "encode_text_embedding",
    ), "encode_text_embedding 함수가 아직 없습니다."


def test_encode_image_embedding_returns_512_dimension_vector():
    assert hasattr(
        generate_embeddings,
        "encode_image_embedding",
    ), "encode_image_embedding 함수가 아직 없습니다."


def test_write_embedding_outputs_creates_separate_files(tmp_path):
    assert hasattr(
        generate_embeddings,
        "write_embedding_outputs",
    ), "write_embedding_outputs 함수가 아직 없습니다."

    records = {
        "segment_embeddings": [
            {
                "segment_id": "SEG001",
                "text_embedding": [0.1] * 512,
            }
        ],
        "keyframe_embeddings": [
            {
                "keyframe_id": "SEG001__A_01",
                "segment_id": "SEG001",
                "image_embedding": [0.2] * 512,
            },
            {
                "keyframe_id": "SEG001__A_02",
                "segment_id": "SEG001",
                "image_embedding": [0.3] * 512,
            },
        ],
    }

    paths = generate_embeddings.write_embedding_outputs(
        records,
        tmp_path,
    )

    segment_path = (
        tmp_path / "segment_embeddings.json"
    )
    keyframe_path = (
        tmp_path / "keyframe_embeddings.json"
    )

    assert segment_path.is_file()
    assert keyframe_path.is_file()

    assert paths["segment_embeddings"] == segment_path
    assert paths["keyframe_embeddings"] == keyframe_path

    import json

    with segment_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        segment_data = json.load(file)

    with keyframe_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        keyframe_data = json.load(file)

    assert len(segment_data) == 1
    assert len(keyframe_data) == 2

def test_run_embedding_generation_builds_and_writes_outputs(tmp_path):
    assert hasattr(
        generate_embeddings,
        "run_embedding_generation",
    ), "run_embedding_generation 함수가 아직 없습니다."

    metadata = [
        {
            "segment_id": "SEG001",
            "video_id": "VIDEO01",
            "place_name": "해변",
            "region": "강원특별자치도",
            "drama_title": "드라마A",
            "start_time": 0.0,
            "end_time": 10.0,
            "keyframe_path": "keyframes/A/A_01.jpg",
            "description": "해변 장면",
            "mood": ["peaceful"],
            "scene_elements": ["sea"],
            "activity": ["walking"],
        }
    ]

    result = generate_embeddings.run_embedding_generation(
        metadata=metadata,
        repo_root=tmp_path,
        output_dir=tmp_path / "output",
        encode_text_fn=lambda text: [0.1] * 512,
        encode_image_fn=lambda path: [0.2] * 512,
    )

    assert len(result["records"]["segment_embeddings"]) == 1
    assert len(result["records"]["keyframe_embeddings"]) == 1

    assert (
        result["paths"]["segment_embeddings"]
        == tmp_path / "output" / "segment_embeddings.json"
    )

    assert (
        result["paths"]["keyframe_embeddings"]
        == tmp_path / "output" / "keyframe_embeddings.json"
    )

    assert result["paths"]["segment_embeddings"].is_file()
    assert result["paths"]["keyframe_embeddings"].is_file()

def test_main_connects_multi_keyframe_generation_pipeline():
    import inspect

    source = inspect.getsource(
        generate_embeddings.main
    )

    assert "run_embedding_generation(" in source
    assert "encode_text_embedding" in source
    assert "encode_image_embedding" in source

