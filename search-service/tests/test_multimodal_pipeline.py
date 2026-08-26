"""필터·텍스트/이미지 검색·결합의 실제 흐름을 대역으로 검증한다."""

from __future__ import annotations

import numpy as np

from src.multimodal_pipeline import (
    MultimodalSearchPipeline,
    collapse_results_by_source_segment,
    collapse_source_results,
)
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


def test_scene_results_are_collapsed_to_best_result_per_source_segment() -> None:
    rows = [
        {
            "rank": 1,
            "segment_id": "V014_P021_S001_SCENE_001",
            "source_segment_id": "V014_P021_S001",
            "keyframe_path": "keyframes/scene_001.jpg",
            "final_score": 0.72,
            "image_score": 0.80,
            "fusion_rank": 1,
        },
        {
            "rank": 2,
            "segment_id": "V014_P021_S001_SCENE_002",
            "source_segment_id": "V014_P021_S001",
            "keyframe_path": "keyframes/scene_002.jpg",
            "final_score": 0.91,
            "image_score": 0.88,
            "fusion_rank": 2,
        },
        {
            "rank": 3,
            "segment_id": "V001_P032_S001_SCENE_001",
            "source_segment_id": "V001_P032_S001",
            "keyframe_path": "keyframes/hwahongmun.jpg",
            "final_score": 0.83,
            "image_score": 0.90,
            "fusion_rank": 3,
        },
    ]

    collapsed = collapse_results_by_source_segment(rows, top_k=5)

    assert [item["source_segment_id"] for item in collapsed] == [
        "V014_P021_S001",
        "V001_P032_S001",
    ]
    assert collapsed[0]["segment_id"] == "V014_P021_S001_SCENE_002"
    assert collapsed[0]["keyframe_path"] == "keyframes/scene_002.jpg"
    assert [item["rank"] for item in collapsed] == [1, 2]


def test_source_segment_id_is_inferred_from_scene_id_for_transition_data() -> None:
    rows = [
        {
            "rank": 1,
            "segment_id": "V003_P006_S001_SCENE_001",
            "final_score": 0.70,
            "image_score": 0.75,
        },
        {
            "rank": 2,
            "segment_id": "V003_P006_S001_SCENE_002",
            "final_score": 0.80,
            "image_score": 0.85,
        },
        {
            "rank": 3,
            "segment_id": "LEGACY_SEGMENT",
            "final_score": 0.60,
            "image_score": 0.65,
        },
    ]

    collapsed = collapse_results_by_source_segment(rows, top_k=5)

    assert [item["segment_id"] for item in collapsed] == [
        "V003_P006_S001_SCENE_002",
        "LEGACY_SEGMENT",
    ]
    assert collapsed[0]["source_segment_id"] == "V003_P006_S001"
    assert collapsed[1]["source_segment_id"] == "LEGACY_SEGMENT"


def test_source_segment_collapse_applies_top_k_after_deduplication() -> None:
    rows = [
        {
            "rank": rank,
            "segment_id": segment_id,
            "source_segment_id": source_segment_id,
            "final_score": score,
        }
        for rank, (segment_id, source_segment_id, score) in enumerate(
            [
                ("A_SCENE_001", "A", 0.95),
                ("A_SCENE_002", "A", 0.90),
                ("B_SCENE_001", "B", 0.85),
                ("C_SCENE_001", "C", 0.80),
            ],
            start=1,
        )
    ]

    collapsed = collapse_results_by_source_segment(rows, top_k=2)

    assert [item["source_segment_id"] for item in collapsed] == ["A", "B"]
    assert len(collapsed) == 2


def test_source_segment_collapse_uses_stable_scene_id_tiebreaker() -> None:
    rows = [
        {
            "rank": 1,
            "segment_id": "V001_P001_S001_SCENE_002",
            "source_segment_id": "V001_P001_S001",
            "final_score": 0.8,
            "image_score": 0.9,
            "fusion_rank": 1,
        },
        {
            "rank": 1,
            "segment_id": "V001_P001_S001_SCENE_001",
            "source_segment_id": "V001_P001_S001",
            "final_score": 0.8,
            "image_score": 0.9,
            "fusion_rank": 1,
        },
    ]

    collapsed = collapse_results_by_source_segment(rows, top_k=1)

    assert collapsed[0]["segment_id"] == "V001_P001_S001_SCENE_001"


def test_pipeline_returns_distinct_source_segments_after_scene_search() -> None:
    class SceneRepository:
        def list_segments(self):
            return [
                {
                    "segment_id": segment_id,
                    "video_id": source_segment_id,
                    "start_time": float(index * 5),
                    "end_time": float(index * 5 + 5),
                    "region": "강원",
                    "season": "여름",
                    "time_of_day": "낮",
                    "mood": ["peaceful"],
                    "activity": [],
                    "landscape": ["hydrangea"],
                }
                for index, (segment_id, source_segment_id) in enumerate(
                    [
                        ("V014_P021_S001_SCENE_001", "V014_P021_S001"),
                        ("V014_P021_S001_SCENE_002", "V014_P021_S001"),
                        ("V001_P032_S001_SCENE_001", "V001_P032_S001"),
                    ]
                )
            ]

        def search(self, vector, source, *, candidate_ids, top_k):
            del vector
            score_by_id = {
                "V014_P021_S001_SCENE_001": 0.70,
                "V014_P021_S001_SCENE_002": 0.95,
                "V001_P032_S001_SCENE_001": 0.80,
            }
            score_field = "text_score" if source == "text" else "image_score"
            return [
                {
                    "segment_id": segment_id,
                    "keyframe_id": f"KF_{index}",
                    "keyframe_path": f"keyframes/{segment_id}.jpg",
                    score_field: score_by_id[segment_id],
                    "score": score_by_id[segment_id],
                }
                for index, segment_id in enumerate(
                    sorted(candidate_ids, key=score_by_id.get, reverse=True)[:top_k]
                )
            ]

    pipeline = MultimodalSearchPipeline(
        runtime=FakeRuntime(),
        repository=SceneRepository(),
    )

    output = pipeline.search(
        "여름의 평화로운 남이섬 수국길",
        parser=FixedParser(),
        top_k=5,
        methods=("normalized",),
    )

    results = output["results_by_method"]["normalized"]
    assert [item["source_segment_id"] for item in results] == [
        "V014_P021_S001",
        "V001_P032_S001",
    ]
    assert results[0]["segment_id"] == "V014_P021_S001_SCENE_002"
    assert results[0]["keyframe_path"].endswith("SCENE_002.jpg")


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


def test_registered_title_limits_candidates_and_survives_filter_fallback() -> None:
    class WinterTitleParser:
        def parse(self, query: str) -> ParsedQuery:
            return ParsedQuery(
                original_query=query,
                search_text="winter lighthouse filming location",
                filters={"season": ["겨울"]},
                soft_hints={"scene_elements": ["등대"]},
            )

    class TitleRepository:
        def __init__(self) -> None:
            self.candidate_ids: list[list[str]] = []

        def list_segments(self):
            return [
                {
                    "segment_id": "HCCC_A",
                    "drama_title": "갯마을 차차차",
                    "region": "경북",
                    "season": "여름",
                    "time_of_day": "낮",
                    "mood": [],
                    "activity": [],
                    "scene_elements": ["등대"],
                },
                {
                    "segment_id": "OTHER_A",
                    "drama_title": "우리들의 블루스",
                    "region": "제주",
                    "season": "여름",
                    "time_of_day": "낮",
                    "mood": [],
                    "activity": [],
                    "scene_elements": ["등대"],
                },
            ]

        def search(self, vector, source, *, candidate_ids, top_k):
            self.candidate_ids.append(list(candidate_ids))
            return [{"segment_id": "HCCC_A", "score": 0.9}]

    runtime = FakeRuntime()
    repository = TitleRepository()
    pipeline = MultimodalSearchPipeline(runtime=runtime, repository=repository)

    output = pipeline.search(
        "겨울 갯마을 차차차 촬영지의 등대",
        parser=WinterTitleParser(),
        methods=("rrf",),
    )

    assert output["matched_drama_titles"] == ["갯마을 차차차"]
    assert output["candidate_count"] == 1
    assert output["fallback_used"] is True
    assert repository.candidate_ids == [["HCCC_A"], ["HCCC_A"]]
