"""필터·텍스트/이미지 검색·결합의 실제 흐름을 대역으로 검증한다."""

from __future__ import annotations

import numpy as np

from src.multimodal_pipeline import MultimodalSearchPipeline
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
        return [{"segment_id": "SEG_A", "score": score}]


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


class NoFilterParser:
    """자연어에서 아무 하드 필터도 추출하지 않는 분석기."""

    def parse(self, query: str) -> ParsedQuery:
        return ParsedQuery(
            original_query=query,
            search_text=query,
            filters={},
            soft_hints={},
        )


class UnmatchableRegionParser:
    """어떤 구간과도 일치하지 않는 지역 필터를 자연어에서 추출하는 분석기."""

    def parse(self, query: str) -> ParsedQuery:
        return ParsedQuery(
            original_query=query,
            search_text=query,
            filters={"region": ["없는지역"]},
            soft_hints={},
        )


class UiFilterRepository:
    """UI 하드 필터 3종을 포함한, 실제 DB 구간 형태에 가까운 대역 저장소."""

    def __init__(self) -> None:
        self.candidate_id_calls: list[list[str]] = []

    def list_segments(self):
        return [
            {
                "segment_id": "SEG_A",
                "video_id": "VID_A",
                "start_time": 0.0,
                "end_time": 5.0,
                "place_id": "P042",
                "city": "춘천시",
                "region": "강원",
                "drama_title": "겨울연가",
                "season": "여름",
                "time_of_day": "낮",
                "mood": ["peaceful"],
                "activity": [],
                "scene_elements": ["hydrangea"],
            },
            {
                "segment_id": "SEG_B",
                "video_id": "VID_B",
                "start_time": 0.0,
                "end_time": 5.0,
                "place_id": "P042",
                "city": "춘천시",
                "region": "강원",
                "drama_title": "겨울연가",
                "season": "겨울",
                "time_of_day": "밤",
                "mood": ["calm"],
                "activity": [],
                "scene_elements": ["snow"],
            },
            {
                "segment_id": "SEG_C",
                "video_id": "VID_C",
                "start_time": 0.0,
                "end_time": 5.0,
                "place_id": "P001",
                "city": "종로구",
                "region": "서울",
                "drama_title": "사랑의 불시착",
                "season": "여름",
                "time_of_day": "해질녘",
                "mood": ["lively"],
                "activity": [],
                "scene_elements": ["palace"],
            },
        ]

    def search(self, vector, source, *, candidate_ids, top_k):
        self.candidate_id_calls.append(list(candidate_ids))
        # 실제 PgVectorRepository와 동일하게 후보가 없으면 즉시 빈 결과를 준다.
        if not candidate_ids:
            return []
        return [
            {"segment_id": segment_id, "score": 0.9 - index * 0.1}
            for index, segment_id in enumerate(candidate_ids[:top_k])
        ]


def _ui_pipeline() -> tuple[MultimodalSearchPipeline, UiFilterRepository]:
    repository = UiFilterRepository()
    pipeline = MultimodalSearchPipeline(
        runtime=FakeRuntime(),
        repository=repository,
    )
    return pipeline, repository


def _result_ids(output, method: str = "rrf") -> list[str]:
    return [item["segment_id"] for item in output["results_by_method"][method]]


def test_filter_overrides_narrow_results_by_region() -> None:
    pipeline, repository = _ui_pipeline()

    output = pipeline.search(
        "촬영지 풍경",
        parser=NoFilterParser(),
        methods=("rrf",),
        filter_overrides={"region": ["서울"]},
    )

    assert output["candidate_count"] == 1
    assert output["filters"] == {"region": ["서울"]}
    assert output["filter_arguments"] == {"regions": ["서울"]}
    assert repository.candidate_id_calls[0] == ["SEG_C"]
    assert _result_ids(output) == ["SEG_C"]
    assert output["fallback_used"] is False


def test_filter_overrides_narrow_results_by_drama_title() -> None:
    pipeline, repository = _ui_pipeline()

    output = pipeline.search(
        "촬영지 풍경",
        parser=NoFilterParser(),
        methods=("rrf",),
        filter_overrides={"drama_title": ["겨울연가"]},
    )

    assert output["candidate_count"] == 2
    assert output["filter_arguments"] == {"drama_titles": ["겨울연가"]}
    assert repository.candidate_id_calls[0] == ["SEG_A", "SEG_B"]
    assert sorted(_result_ids(output)) == ["SEG_A", "SEG_B"]


def test_filter_overrides_by_place_id_and_city() -> None:
    pipeline, _ = _ui_pipeline()

    output = pipeline.search(
        "촬영지 풍경",
        parser=NoFilterParser(),
        methods=("rrf",),
        filter_overrides={"place_id": ["P001"], "city": ["종로구"]},
    )

    assert output["candidate_count"] == 1
    assert _result_ids(output) == ["SEG_C"]


def test_filter_overrides_from_different_fields_use_and_condition() -> None:
    pipeline, _ = _ui_pipeline()

    output = pipeline.search(
        "촬영지 풍경",
        parser=NoFilterParser(),
        methods=("rrf",),
        filter_overrides={"drama_title": ["겨울연가"], "season": ["겨울"]},
    )

    assert output["candidate_count"] == 1
    assert _result_ids(output) == ["SEG_B"]


def test_filter_overrides_replace_the_same_field_from_natural_language() -> None:
    """UI가 지정한 필드는 자연어에서 추출된 같은 필드 값을 완전히 대체한다."""

    pipeline, _ = _ui_pipeline()

    # FixedParser는 자연어에서 season=여름을 추출한다.
    output = pipeline.search(
        "여름의 평화로운 남이섬 수국길",
        parser=FixedParser(),
        methods=("rrf",),
        filter_overrides={"season": ["겨울"]},
    )

    assert output["filters"]["season"] == ["겨울"]
    assert output["candidate_count"] == 1
    assert _result_ids(output) == ["SEG_B"]


def test_ui_filter_override_with_no_match_does_not_retry_without_filters() -> None:
    """UI가 명시한 하드 필터가 0건이면 필터 없는 재검색으로 넓히지 않는다."""

    pipeline, repository = _ui_pipeline()

    output = pipeline.search(
        "촬영지 풍경",
        parser=NoFilterParser(),
        methods=("rrf",),
        filter_overrides={"place_id": ["P999"]},
    )

    assert output["candidate_count"] == 0
    assert output["fallback_used"] is False
    assert output["fallback_reason"] is None
    assert output["filters"] == {"place_id": ["P999"]}
    assert output["filter_arguments"] == {"place_ids": ["P999"]}
    assert repository.candidate_id_calls == [[], []]
    assert output["results_by_method"]["rrf"] == []


def test_natural_language_filter_with_no_match_still_retries_without_filters() -> None:
    """UI 지정이 없는 자연어 추출 필터는 기존대로 필터 없이 재검색한다(회귀 방지)."""

    pipeline, repository = _ui_pipeline()

    output = pipeline.search(
        "없는지역 촬영지 풍경",
        parser=UnmatchableRegionParser(),
        methods=("rrf",),
    )

    assert output["fallback_used"] is True
    assert output["fallback_reason"] == "필터 결과가 없어 필터 없이 다시 검색했습니다."
    assert output["filters"] == {}
    assert output["filter_arguments"] == {}
    assert output["candidate_count"] == 3
    assert repository.candidate_id_calls[0] == ["SEG_A", "SEG_B", "SEG_C"]


def test_filter_overrides_apply_the_same_alias_canonicalization_as_natural_language() -> None:
    """UI가 보낸 filter_overrides 값도 자연어 필터와 동일하게 별칭이 정규화되어야 한다."""

    pipeline, repository = _ui_pipeline()

    # UiFilterRepository의 SEG_A/SEG_C는 season이 "여름"(canonical)으로 저장돼 있다.
    # UI는 별칭인 "summer"를 그대로 보낼 수 있다.
    output = pipeline.search(
        "촬영지 풍경",
        parser=NoFilterParser(),
        methods=("rrf",),
        filter_overrides={"season": ["summer"]},
    )

    assert output["candidate_count"] == 2
    assert output["filters"] == {"season": ["여름"]}
    assert sorted(_result_ids(output)) == ["SEG_A", "SEG_C"]
    assert repository.candidate_id_calls[0] == ["SEG_A", "SEG_C"]


def test_empty_filter_overrides_leave_natural_language_fallback_unchanged() -> None:
    """빈 filter_overrides는 UI 지정으로 취급하지 않는다."""

    pipeline, _ = _ui_pipeline()

    output = pipeline.search(
        "없는지역 촬영지 풍경",
        parser=UnmatchableRegionParser(),
        methods=("rrf",),
        filter_overrides={},
    )

    assert output["fallback_used"] is True
    assert output["candidate_count"] == 3
