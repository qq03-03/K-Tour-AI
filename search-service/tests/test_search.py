"""더미 텍스트 검색 기준선의 자동 테스트."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.dummy_embedder import DummyTextEmbedder
from src.search import cosine_similarity, search_segments


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "dummy_segments.json"


@pytest.fixture(scope="module")
def segments() -> list[dict[str, object]]:
    """테스트 전체에서 더미 영상 구간 20개를 한 번만 불러온다."""

    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)["segments"]


@pytest.fixture(scope="module")
def embedder() -> DummyTextEmbedder:
    return DummyTextEmbedder()


def test_identical_vectors_have_similarity_one() -> None:
    vector = np.asarray([1.0, 2.0, 3.0])

    assert cosine_similarity(vector, vector) == pytest.approx(1.0)


def test_orthogonal_vectors_have_similarity_zero() -> None:
    left = np.asarray([1.0, 0.0])
    right = np.asarray([0.0, 1.0])

    assert cosine_similarity(left, right) == pytest.approx(0.0)


def test_zero_vector_similarity_is_zero() -> None:
    zero = np.asarray([0.0, 0.0])
    other = np.asarray([1.0, 1.0])

    assert cosine_similarity(zero, other) == 0.0


def test_different_vector_dimensions_raise_error() -> None:
    with pytest.raises(ValueError, match="차원"):
        cosine_similarity(np.asarray([1.0]), np.asarray([1.0, 0.0]))


def test_hanok_palace_and_fortress_are_separate_concepts(
    embedder: DummyTextEmbedder,
) -> None:
    hanok_concepts = embedder.matched_concepts("조용한 한옥")
    palace_concepts = embedder.matched_concepts("눈 내린 궁궐")
    fortress_concepts = embedder.matched_concepts("노을이 보이는 성곽")

    assert "hanok" in hanok_concepts
    assert "palace" not in hanok_concepts
    assert "fortress" not in hanok_concepts
    assert "palace" in palace_concepts
    assert "fortress" in fortress_concepts


def test_search_returns_requested_number_and_sorted_scores(
    segments: list[dict[str, object]],
    embedder: DummyTextEmbedder,
) -> None:
    results = search_segments("여름 바다 해변", segments, embedder, top_k=3)

    assert len(results) == 3
    assert [result["rank"] for result in results] == [1, 2, 3]
    assert [result["score"] for result in results] == sorted(
        [result["score"] for result in results], reverse=True
    )


def test_hanok_query_ranks_hanok_above_fortress(
    segments: list[dict[str, object]],
    embedder: DummyTextEmbedder,
) -> None:
    results = search_segments(
        "가을 단풍이 보이는 조용한 한옥 촬영지",
        segments,
        embedder,
        top_k=5,
    )
    result_ids = [result["segment_id"] for result in results]

    assert result_ids[:2] == ["SEG_001", "SEG_020"]
    assert result_ids.index("SEG_018") > result_ids.index("SEG_020")


def test_unknown_query_raises_clear_error(
    segments: list[dict[str, object]],
    embedder: DummyTextEmbedder,
) -> None:
    with pytest.raises(ValueError, match="인식한 키워드가 없습니다"):
        search_segments("아무 의미도 등록되지 않은 표현 xyz", segments, embedder)


@pytest.mark.parametrize("top_k", [0, -1])
def test_non_positive_top_k_raises_error(
    segments: list[dict[str, object]],
    embedder: DummyTextEmbedder,
    top_k: int,
) -> None:
    with pytest.raises(ValueError, match="top_k"):
        search_segments("가을 한옥", segments, embedder, top_k=top_k)
