"""CLIP 지연 로딩과 프로세스 내 재사용 테스트."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from src import clip_backend


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


def test_database_metadata_normalizes_filter_values() -> None:
    row = (
        "SEG_A",
        "VID_A",
        0.0,
        5.0,
        "frame.jpg",
        "summary",
        "nami_island",
        "숲길",
        ["trees"],
        ["peaceful"],
        ["summer"],
        {
            "place_name": "nami_island",
            "place_id": "P001",
            "city": "춘천시",
            "address": "강원특별자치도 춘천시 남산면 남이섬길 1",
            "season": "summer",
            "time_of_day": "evening",
        },
    )

    segment = clip_backend.PgVectorRepository._segment_from_row(row)

    assert segment["region"] == "강원"
    assert segment["place_id"] == "P001"
    assert segment["city"] == "춘천시"
    assert segment["address"] == "강원특별자치도 춘천시 남산면 남이섬길 1"
    assert segment["season"] == "여름"
    assert segment["time_of_day"] == "해질녘"
