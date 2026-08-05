"""필터·텍스트/이미지 검색·결합의 실제 흐름을 대역으로 검증한다."""

from __future__ import annotations

import numpy as np

from src.multimodal_pipeline import MultimodalSearchPipeline, collapse_source_results
from src.query_parser import ParsedQuery


class FixedParser:
    def parse(self, query: str) -> ParsedQuery:
        return ParsedQuery(
            original_query=query,
            search_text="summer hydrangea path on Nami Island",
            filters={"season": ["여름"]},
            soft_hints={"mood": ["평화로운"]},
        )


class FakeRuntime:
    model_name = "fake-clip"
    device = "cpu"
    load_count = 1
    load_latency_ms = 10.0

    def __init__(self) -> None:
        self.encode_calls = 0

    def encode_text(self, text: str):
        self.encode_calls += 1
        return np.ones(512, dtype=np.float32)

    def warmup(self) -> None:
        return None


class FakeRepository:
    def __init__(self) -> None:
        self.sources: list[str] = []

    def list_segments(self):
        return [
            {
                "segment_id": "SEG_A",
                "video_id": "VID_A",
                "start_time": 0.0,
                "end_time": 5.0,
                "region": "강원",
                "season": "여름",
                "time_of_day": "낮",
                "mood": ["peaceful"],
                "activity": [],
                "landscape": ["hydrangea"],
            },
            {
                "segment_id": "SEG_B",
                "video_id": "VID_B",
                "start_time": 0.0,
                "end_time": 5.0,
                "region": "강원",
                "season": "겨울",
                "time_of_day": "낮",
                "mood": ["calm"],
                "activity": [],
                "landscape": ["snow"],
            },
        ]

    def search(self, vector, source, *, candidate_ids, top_k):
        self.sources.append(source)
        assert candidate_ids == ["SEG_A"]
        score = 0.8 if source == "text" else 0.9
        return [
            {
                "segment_id": "SEG_A",
                "keyframe_id": "KF_A",
                "keyframe_path": "keyframes/SEG_A.jpg",
                "description": "대표 장면",
                "text_score": 0.8,
                "image_score": 0.9,
                "score": score,
            }
        ]


def test_pipeline_encodes_once_and_searches_both_embeddings() -> None:
    runtime = FakeRuntime()
    repository = FakeRepository()
    pipeline = MultimodalSearchPipeline(
        runtime=runtime,
        repository=repository,
    )

    output = pipeline.search(
        "여름의 평화로운 남이섬 수국길",
        parser=FixedParser(),
        methods=("rrf", "normalized"),
    )

    assert output["candidate_count"] == 1
    assert runtime.encode_calls == 1
    assert repository.sources == ["text", "image"]
    assert output["results_by_method"]["rrf"][0]["segment_id"] == "SEG_A"
    assert output["results_by_method"]["normalized"][0]["segment_id"] == "SEG_A"
    assert output["results_by_method"]["rrf"][0]["soft_hint_matches"] == {
        "mood": ["평화로운"]
    }
    assert output["results_by_method"]["rrf"][0]["keyframe_id"] == "KF_A"
    assert output["results_by_method"]["rrf"][0]["text_score"] == 0.8
    assert output["results_by_method"]["rrf"][0]["image_score"] == 0.9


def test_keyframe_rows_are_collapsed_to_best_image_per_segment() -> None:
    rows = [
        {
            "segment_id": "SEG_A",
            "keyframe_id": "KF_A1",
            "description": "건물 장면",
            "text_score": 0.8,
            "image_score": 0.4,
        },
        {
            "segment_id": "SEG_A",
            "keyframe_id": "KF_A2",
            "description": "벚꽃 장면",
            "text_score": 0.8,
            "image_score": 0.95,
        },
        {
            "segment_id": "SEG_B",
            "keyframe_id": "KF_B1",
            "description": "바다 장면",
            "text_score": 0.7,
            "image_score": 0.7,
        },
    ]

    collapsed = collapse_source_results(rows, source="image")

    assert [item["segment_id"] for item in collapsed] == ["SEG_A", "SEG_B"]
    assert collapsed[0]["keyframe_id"] == "KF_A2"
    assert collapsed[0]["description"] == "벚꽃 장면"
    assert collapsed[0]["image_score"] == 0.95


def test_unregistered_title_stops_before_embedding_and_db_search() -> None:
    runtime = FakeRuntime()
    repository = FakeRepository()
    pipeline = MultimodalSearchPipeline(runtime=runtime, repository=repository)

    output = pipeline.search(
        "서울의 봄 촬영지",
        parser=FixedParser(),
        methods=("rrf", "normalized"),
    )

    assert output["query_status"] == "not_found"
    assert output["possible_title"] == "서울의 봄"
    assert output["candidate_count"] == 0
    assert output["results_by_method"] == {"rrf": [], "normalized": []}
    assert runtime.encode_calls == 0
    assert repository.sources == []
