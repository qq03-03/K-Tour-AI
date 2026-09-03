"""Recall@K와 MRR 계산 함수의 자동 테스트."""

from __future__ import annotations

import pytest

from src.metrics import (
    first_relevant_rank,
    hit_at_k,
    mean_hit_at_k,
    mean_ndcg_at_k,
    mean_recall_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_with_multiple_relevant_segments() -> None:
    relevant = ["SEG_001", "SEG_002", "SEG_003"]
    retrieved = ["SEG_010", "SEG_001", "SEG_011", "SEG_003", "SEG_002"]

    assert recall_at_k(relevant, retrieved, k=4) == pytest.approx(2 / 3)


def test_recall_at_k_ignores_results_after_k() -> None:
    assert recall_at_k(["SEG_001"], ["SEG_010", "SEG_001"], k=1) == 0.0


def test_hit_at_k_returns_one_when_relevant_result_is_in_top_k() -> None:
    assert hit_at_k(["SEG_001"], ["SEG_010", "SEG_001"], k=2) == 1.0


def test_hit_at_k_returns_zero_when_relevant_result_is_after_k() -> None:
    assert hit_at_k(["SEG_001"], ["SEG_010", "SEG_001"], k=1) == 0.0


def test_ndcg_at_k_is_one_for_ideal_ranking() -> None:
    relevant = ["A", "B"]
    retrieved = ["A", "B", "X"]

    assert ndcg_at_k(relevant, retrieved, k=3) == pytest.approx(1.0)


def test_ndcg_at_k_penalizes_relevant_result_at_lower_rank() -> None:
    relevant = ["A"]
    retrieved = ["X", "A"]

    assert ndcg_at_k(relevant, retrieved, k=2) == pytest.approx(
        1 / 1.584962500721156
    )


def test_ndcg_at_k_returns_zero_without_relevant_result() -> None:
    assert ndcg_at_k(["A"], ["X", "Y"], k=2) == 0.0


def test_ndcg_at_k_does_not_count_duplicate_results_twice() -> None:
    assert ndcg_at_k(["A", "B"], ["A", "A"], k=2) == pytest.approx(
        1 / (1 + 1 / 1.584962500721156)
    )


def test_first_relevant_rank() -> None:
    assert first_relevant_rank(["SEG_001"], ["SEG_010", "SEG_011", "SEG_001"]) == 3


def test_first_relevant_rank_returns_none_without_hit() -> None:
    assert first_relevant_rank(["SEG_001"], ["SEG_010", "SEG_011"]) is None


@pytest.mark.parametrize(
    ("retrieved", "expected"),
    [
        (["SEG_001", "SEG_002"], 1.0),
        (["SEG_010", "SEG_011", "SEG_001"], 1 / 3),
        (["SEG_010", "SEG_011"], 0.0),
    ],
)
def test_reciprocal_rank(retrieved: list[str], expected: float) -> None:
    assert reciprocal_rank(["SEG_001"], retrieved) == pytest.approx(expected)


def test_mean_recall_at_k() -> None:
    relevant = [["A"], ["B", "C"]]
    retrieved = [["A", "X"], ["B", "X"]]

    assert mean_recall_at_k(relevant, retrieved, k=2) == pytest.approx(0.75)


def test_mean_reciprocal_rank() -> None:
    relevant = [["A"], ["B"], ["C"]]
    retrieved = [["A"], ["X", "B"], ["X", "Y"]]

    assert mean_reciprocal_rank(relevant, retrieved) == pytest.approx(0.5)


def test_mean_hit_at_k() -> None:
    relevant = [["A"], ["B"]]
    retrieved = [["A"], ["X"]]

    assert mean_hit_at_k(relevant, retrieved, k=1) == pytest.approx(0.5)


def test_mean_ndcg_at_k() -> None:
    relevant = [["A"], ["B"]]
    retrieved = [["A"], ["X", "B"]]

    expected = (1.0 + 1 / 1.584962500721156) / 2
    assert mean_ndcg_at_k(relevant, retrieved, k=2) == pytest.approx(expected)


def test_empty_relevant_ids_raise_error() -> None:
    with pytest.raises(ValueError, match="정답 구간"):
        recall_at_k([], ["SEG_001"], k=5)


def test_non_positive_k_raises_error() -> None:
    with pytest.raises(ValueError, match="k는 1 이상"):
        recall_at_k(["SEG_001"], ["SEG_001"], k=0)

    with pytest.raises(ValueError, match="k는 1 이상"):
        hit_at_k(["SEG_001"], ["SEG_001"], k=0)

    with pytest.raises(ValueError, match="k는 1 이상"):
        ndcg_at_k(["SEG_001"], ["SEG_001"], k=0)


def test_query_count_mismatch_raises_error() -> None:
    with pytest.raises(ValueError, match="질문 수"):
        mean_reciprocal_rank([["A"]], [["A"], ["B"]])
