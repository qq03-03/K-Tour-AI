"""QueryParser부터 필터·검색 결과까지 이어지는 통합 테스트."""

from __future__ import annotations

from pathlib import Path

from src.data_loader import load_segments
from src.dummy_embedder import DummyTextEmbedder
from src.query_parser import RuleBasedQueryParser
from src.search_pipeline import run_search_pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_parser_filters_are_applied_before_search() -> None:
    segments = load_segments(PROJECT_ROOT / "data" / "dummy_segments.json")

    output = run_search_pipeline(
        "서울 봄 궁궐",
        segments,
        parser=RuleBasedQueryParser(),
        embedder=DummyTextEmbedder(),
        top_k=5,
    )

    assert output["filters"] == {"region": ["서울"], "season": ["봄"]}
    assert output["filter_arguments"] == {
        "regions": ["서울"],
        "seasons": ["봄"],
    }
    assert output["candidate_count"] == 2
    assert output["results"][0]["segment_id"] == "SEG_006"


def test_empty_filter_result_retries_without_filters() -> None:
    segments = load_segments(PROJECT_ROOT / "data" / "dummy_segments.json")

    output = run_search_pipeline(
        "강원 여름 바다",
        segments,
        parser=RuleBasedQueryParser(),
        embedder=DummyTextEmbedder(),
        top_k=3,
    )

    assert output["filters"] == {}
    assert output["fallback_used"] is True
    assert output["candidate_count"] == 20
    assert output["results"][0]["segment_id"] == "SEG_012"


def test_latest_integrated_data_returns_service_fields() -> None:
    segments = load_segments(
        PROJECT_ROOT / "data" / "nami_segments_10.json",
        require_contiguous=True,
    )

    output = run_search_pipeline(
        "여름 남이섬 숲 산책",
        segments,
        parser=RuleBasedQueryParser(),
        embedder=DummyTextEmbedder(),
        top_k=3,
    )

    first = output["results"][0]
    assert first["video_id"].startswith("VID_NAMI_")
    assert first["place_id"] == "PLC_NAMI_001"
    assert first["place_name"] == "남이섬"
    assert first["start_sec"] < first["end_sec"]
    assert "description" in first
    assert "keyframe_path" in first
