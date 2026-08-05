import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "insert_embeddings.py"
)

spec = importlib.util.spec_from_file_location(
    "insert_embeddings",
    SCRIPT_PATH,
)

insert_embeddings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(insert_embeddings)


def test_prepare_records_preserves_multiple_keyframes_per_segment():
    assert hasattr(
        insert_embeddings,
        "prepare_records",
    ), "prepare_records 함수가 아직 없습니다."

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
            "description": "첫 장면",
            "season": "winter",
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
            "season": "winter",
            "mood": ["romantic"],
            "scene_elements": ["waves"],
            "activity": ["standing"],
        },
    ]

    segment_embeddings = [
        {
            "segment_id": "SEG001",
            "video_id": "VIDEO01",
            "place_name": "해변",
            "region": "강원특별자치도",
            "drama_title": "드라마A",
            "start_time": 0.0,
            "end_time": 10.0,
            "search_text": "강원특별자치도 드라마A 해변",
            "text_embedding": [0.1] * 512,
        }
    ]

    keyframe_embeddings = [
        {
            "keyframe_id": "SEG001__A_01",
            "segment_id": "SEG001",
            "keyframe_path": "keyframes/A/A_01.jpg",
            "image_embedding": [0.2] * 512,
        },
        {
            "keyframe_id": "SEG001__A_02",
            "segment_id": "SEG001",
            "keyframe_path": "keyframes/A/A_02.jpg",
            "image_embedding": [0.3] * 512,
        },
    ]

    records = insert_embeddings.prepare_records(
        metadata_list=metadata,
        segment_embedding_list=segment_embeddings,
        keyframe_embedding_list=keyframe_embeddings,
    )

    assert len(records["segments"]) == 1
    assert len(records["keyframes"]) == 2

    segment = records["segments"][0]

    assert segment["segment_id"] == "SEG001"
    assert segment["region"] == "강원특별자치도"
    assert segment["drama_title"] == "드라마A"

    assert (
        records["keyframes"][0]["segment_id"]
        == "SEG001"
    )

    assert (
        records["keyframes"][1]["segment_id"]
        == "SEG001"
    )


def test_prepare_records_rejects_missing_keyframe_embedding():
    assert hasattr(
        insert_embeddings,
        "prepare_records",
    ), "prepare_records 함수가 아직 없습니다."

    metadata = [
        {
            "segment_id": "SEG001",
            "video_id": "VIDEO01",
            "keyframe_path": "keyframes/A/A_01.jpg",
        },
        {
            "segment_id": "SEG001",
            "video_id": "VIDEO01",
            "keyframe_path": "keyframes/A/A_02.jpg",
        },
    ]

    segment_embeddings = [
        {
            "segment_id": "SEG001",
            "text_embedding": [0.1] * 512,
        }
    ]

    keyframe_embeddings = [
        {
            "keyframe_id": "SEG001__A_01",
            "segment_id": "SEG001",
            "keyframe_path": "keyframes/A/A_01.jpg",
            "image_embedding": [0.2] * 512,
        }
    ]

    with pytest.raises(
        ValueError,
        match="keyframe",
    ):
        insert_embeddings.prepare_records(
            metadata_list=metadata,
            segment_embedding_list=segment_embeddings,
            keyframe_embedding_list=keyframe_embeddings,
        )

def test_prepare_records_preserves_final_45_segments_and_keyframes():
    import json

    repo_root = Path(__file__).resolve().parents[2]

    metadata_path = (
        repo_root
        / "embedding-db"
        / "metadata"
        / "metadata.json"
    )

    with metadata_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    segment_embeddings = [
        {
            "segment_id": item["segment_id"],
            "search_text": item.get(
                "description",
                "",
            ),
            "text_embedding": [0.1] * 512,
        }
        for item in metadata
    ]

    keyframe_embeddings = [
        {
            "keyframe_id": (
                f"{item['segment_id']}__"
                f"{Path(item['keyframe_path']).stem}"
            ),
            "segment_id": item["segment_id"],
            "keyframe_path": item[
                "keyframe_path"
            ],
            "image_embedding": [0.2] * 512,
        }
        for item in metadata
    ]

    records = insert_embeddings.prepare_records(
        metadata_list=metadata,
        segment_embedding_list=segment_embeddings,
        keyframe_embedding_list=keyframe_embeddings,
    )

    assert len(records["segments"]) == 45
    assert len(records["keyframes"]) == 45

    segment_ids = {
        item["segment_id"]
        for item in records["segments"]
    }

    keyframe_ids = {
        item["keyframe_id"]
        for item in records["keyframes"]
    }

    place_ids = {
        item["place_id"]
        for item in records["segments"]
    }

    assert len(segment_ids) == 45
    assert len(keyframe_ids) == 45
    assert len(place_ids) == 19

def test_insert_prepared_records_writes_new_embedding_tables():
    assert hasattr(
        insert_embeddings,
        "insert_prepared_records",
    ), "insert_prepared_records 함수가 아직 없습니다."

    class FakeCursor:
        def __init__(self):
            self.queries = []

        def execute(self, query, params=None):
            self.queries.append(
                (" ".join(query.split()), params)
            )

    cursor = FakeCursor()

    records = {
        "segments": [
            {
                "segment_id": "SEG001",
                "video_id": "VIDEO01",
                "place_id": "P001",
                "place_name": "테스트 장소",
                "spot_name": None,
                "region": "서울특별시",
                "drama_title": "테스트 드라마",
                "start_time": 0.0,
                "end_time": 10.0,
                "search_text": "테스트 검색 텍스트",
                "text_embedding": [0.1] * 512,
                "metadata": [
                    {
                        "segment_id": "SEG001",
                        "video_id": "VIDEO01",
                        "place_id": "P001",
                        "keyframe_path": "keyframes/A/A_01.jpg",
                        "season": "봄",
                        "mood": ["peaceful"],
                        "scene_elements": ["tree"],
                        "activity": ["walking"],
                        "description": "테스트 장면",
                    }
                ],
            }
        ],
        "keyframes": [
            {
                "keyframe_id": "SEG001__A_01",
                "segment_id": "SEG001",
                "keyframe_path": "keyframes/A/A_01.jpg",
                "image_embedding": [0.2] * 512,
                "metadata": {
                    "segment_id": "SEG001",
                    "keyframe_path": "keyframes/A/A_01.jpg",
                },
            }
        ],
    }

    insert_embeddings.insert_prepared_records(
        cursor,
        records,
    )

    sql = "\n".join(
        query
        for query, _ in cursor.queries
    )

    assert "INSERT INTO videos" in sql
    assert "INSERT INTO video_segments" in sql
    assert "INSERT INTO segment_embeddings" in sql
    assert "INSERT INTO segment_keyframes" in sql
    assert "INSERT INTO keyframe_embeddings" in sql

    assert "place_id" in sql
    assert "region" in sql
    assert "drama_title" in sql

def test_main_connects_multikeyframe_insert_pipeline():
    import inspect

    source = inspect.getsource(
        insert_embeddings.main
    )

    assert "keyframe_embeddings.json" in source
    assert "prepare_records" in source
    assert "insert_prepared_records" in source

def test_validate_vector_returns_plain_python_list():
    vector = [0.1] * 512

    result = insert_embeddings.validate_vector(
        vector,
        "SEG001",
        "text_embedding",
    )

    assert isinstance(result, list)
    assert len(result) == 512
    assert all(
        isinstance(value, float)
        for value in result
    )