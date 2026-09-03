"""검색 로직이 특정 임베딩 구현체에 종속되지 않는지 확인한다."""

from __future__ import annotations

import numpy as np

from src.dummy_embedder import DummyTextEmbedder
from src.interfaces import ExplainableTextEmbedder, TextEmbedder
from src.search import search_segments


class StubTextEmbedder:
    """실제 모델 교체 가능성을 검증하기 위한 최소 대체 임베더."""

    def encode(self, text: str) -> np.ndarray:
        if "target" in text:
            return np.asarray([1.0, 0.0])
        return np.asarray([0.0, 1.0])


def test_dummy_embedder_satisfies_explainable_interface() -> None:
    embedder = DummyTextEmbedder()

    assert isinstance(embedder, TextEmbedder)
    assert isinstance(embedder, ExplainableTextEmbedder)


def test_minimal_stub_satisfies_search_interface_only() -> None:
    embedder = StubTextEmbedder()

    assert isinstance(embedder, TextEmbedder)
    assert not isinstance(embedder, ExplainableTextEmbedder)


def test_search_works_with_alternative_embedder() -> None:
    segments = [
        {
            "segment_id": "A",
            "video_id": "VIDEO_A",
            "location_name": "target location",
            "metadata_text": "target scene",
            "start_sec": 0.0,
            "end_sec": 10.0,
        },
        {
            "segment_id": "B",
            "video_id": "VIDEO_B",
            "location_name": "other location",
            "metadata_text": "other scene",
            "start_sec": 10.0,
            "end_sec": 20.0,
        },
    ]

    results = search_segments("target query", segments, StubTextEmbedder(), top_k=2)

    assert [result["segment_id"] for result in results] == ["A", "B"]
    assert results[0]["score"] == 1.0
