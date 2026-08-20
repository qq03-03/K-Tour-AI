"""CLIP 지연 로딩과 프로세스 내 재사용 테스트."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from src import clip_backend
from src.clip_backend import DatabaseConfig, PgVectorRepository


def test_clip_runtime_loads_model_only_once(monkeypatch) -> None:
    calls = {"model": 0, "processor": 0}

    class FakeModel:
        @classmethod
        def from_pretrained(cls, name, local_files_only):
            calls["model"] += 1
            return cls()

        def to(self, device):
            return self

        def eval(self):
            return self

        def get_text_features(self, **inputs):
            return torch.ones((1, 512), dtype=torch.float32)

    class FakeProcessor:
        @classmethod
        def from_pretrained(cls, name, local_files_only):
            calls["processor"] += 1
            return cls()

        def __call__(self, **kwargs):
            return {"input_ids": torch.ones((1, 3), dtype=torch.int64)}

    monkeypatch.setattr(clip_backend, "CLIPModel", FakeModel)
    monkeypatch.setattr(clip_backend, "CLIPProcessor", FakeProcessor)

    runtime = clip_backend.ClipRuntime(device="cpu")
    first = runtime.encode_text("first query")
    second = runtime.encode_text("second query")

    assert first.shape == (512,)
    assert np.linalg.norm(second) == pytest.approx(1.0)
    assert runtime.load_count == 1
    assert calls == {"model": 1, "processor": 1}


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, query, params=None):
        self._executed_query = query

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def cursor(self):
        return _FakeCursor(self._rows)


def _fake_connect(rows):
    def connect(connection_string):
        return _FakeConnection(rows)

    return connect


def test_list_segments_uses_the_517_dataset_columns(monkeypatch):
    row = (
        "V007_P031_S002_SCENE_001", "V007_P031_S002", "V007_Z7u5SNDq0jw",
        "P031", "충주 중앙탑공원", "충청북도", "충주시", "사랑의 불시착",
        0.0, 3.75, "야경", "summer", "night", "keyframes/x.jpg",
        ["peaceful"], ["walking"], ["bridge"], ["K드라마성지"],
    )
    monkeypatch.setattr(clip_backend.psycopg, "connect", _fake_connect([row]))
    repository = PgVectorRepository(DatabaseConfig("fake-connection-string"))

    segments = repository.list_segments()

    assert segments == [
        {
            "segment_id": "V007_P031_S002_SCENE_001",
            "source_segment_id": "V007_P031_S002",
            "video_id": "V007_Z7u5SNDq0jw",
            "place_id": "P031",
            "place_name": "충주 중앙탑공원",
            "region": "충청북도",
            "city": "충주시",
            "drama_title": "사랑의 불시착",
            "start_time": 0.0,
            "end_time": 3.75,
            "description": "야경",
            "season": "summer",
            "time_of_day": "night",
            "keyframe_path": "keyframes/x.jpg",
            "mood": ["peaceful"],
            "activity": ["walking"],
            "scene_elements": ["bridge"],
            "k_culture_elements": ["K드라마성지"],
        }
    ]
