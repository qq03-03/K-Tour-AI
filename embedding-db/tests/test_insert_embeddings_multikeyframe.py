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
            "time_of_day": "day",
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
            "time_of_day": "evening",
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

    keyframe = records["keyframes"][0]

    assert keyframe["description"] == metadata[0]["description"]
    assert keyframe["time_of_day"] == metadata[0]["time_of_day"]
    assert keyframe["mood"] == metadata[0]["mood"]
    assert keyframe["activity"] == metadata[0]["activity"]
    assert keyframe["scene_elements"] == metadata[0]["scene_elements"]


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

def test_insert_prepared_records_writes_keyframe_structured_metadata():

    records = {
        "segments": [
            {
                "segment_id": "SEG_001",
                "video_id": "VID_001",
                "place_id": "P001",
                "spot_name": "테스트 장소",
                "region": "서울특별시",
                "drama_title": "테스트 드라마",
                "start_time": 0.0,
                "end_time": 5.0,
                "search_text": "테스트",
                "text_embedding": [0.0] * 512,
                "metadata": {},
            }
        ],
        "keyframes": [
            {
                "keyframe_id": "KF_001",
                "segment_id": "SEG_001",
                "keyframe_path": "frame.jpg",
                "description": "테스트 설명",
                "time_of_day": "day",
                "mood": ["peaceful"],
                "activity": ["walking"],
                "scene_elements": ["palace"],
                "image_embedding": [0.0] * 512,
                "metadata": {},
            }
        ],
    }

    class RecordingCursor:
        def __init__(self):
            self.queries = []

        def execute(self, query, params=None):
            self.queries.append(str(query))

    cursor = RecordingCursor()

    insert_embeddings.insert_prepared_records(
    cursor,
    records,
)

    sql = "\n".join(cursor.queries)

    assert "segment_keyframes" in sql
    assert "description" in sql
    assert "time_of_day" in sql
    assert "mood" in sql
    assert "activity" in sql
    assert "scene_elements" in sql

def test_delete_stale_records_removes_missing_keyframes_and_segments():
    executed = []

    class FakeCursor:
        def execute(self, query, params):
            executed.append(
                (
                    " ".join(str(query).split()),
                    params,
                )
            )

    records = {
        "segments": [
            {"segment_id": "SEG_001"},
            {"segment_id": "SEG_002"},
        ],
        "keyframes": [
            {"keyframe_id": "KF_001"},
            {"keyframe_id": "KF_002"},
        ],
    }

    cursor = FakeCursor()

    insert_embeddings.delete_stale_records(
        cursor,
        records,
    )

    assert len(executed) == 2

    keyframe_query, keyframe_params = executed[0]
    segment_query, segment_params = executed[1]

    assert "DELETE FROM segment_keyframes" in keyframe_query
    assert "keyframe_id = ANY(%s)" in keyframe_query
    assert keyframe_params == (
        ["KF_001", "KF_002"],
    )

    assert "DELETE FROM video_segments" in segment_query
    assert "segment_id = ANY(%s)" in segment_query
    assert segment_params == (
        ["SEG_001", "SEG_002"],
    )


def test_delete_stale_records_rejects_empty_records_without_query():
    executed = []

    class FakeCursor:
        def execute(self, query, params):
            executed.append((query, params))

    with pytest.raises(
        ValueError,
        match="빈 metadata/embedding 입력",
    ):
        insert_embeddings.delete_stale_records(
            FakeCursor(),
            {"segments": [], "keyframes": []},
        )

    assert executed == []


def test_validate_non_empty_records_rejects_missing_keyframes():
    with pytest.raises(
        ValueError,
        match="segments=1, keyframes=0",
    ):
        insert_embeddings.validate_non_empty_records(
            {
                "segments": [{"segment_id": "SEG_001"}],
                "keyframes": [],
            }
        )


def test_full_sync_requires_explicit_command_line_option():
    assert insert_embeddings.parse_args([]).full_sync is False
    assert insert_embeddings.parse_args(["--full-sync"]).full_sync is True
