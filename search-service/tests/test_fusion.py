"""텍스트·이미지 검색 순위의 RRF 결합 테스트."""

from __future__ import annotations

import pytest

from src.fusion import reciprocal_rank_fusion


def test_rrf_combines_text_and_image_rankings() -> None:
    rankings = {
        "text": ["SEG_A", "SEG_B", "SEG_C"],
        "image": ["SEG_B", "SEG_D", "SEG_A"],
    }

    results = reciprocal_rank_fusion(rankings)

    assert [result["segment_id"] for result in results] == [
        "SEG_B",
        "SEG_A",
        "SEG_D",
        "SEG_C",
    ]


def test_rrf_returns_source_ranks_and_contributions() -> None:
    results = reciprocal_rank_fusion(
        {"text": ["SEG_A"], "image": ["SEG_B", "SEG_A"]}
    )
    segment_a = next(result for result in results if result["segment_id"] == "SEG_A")

    assert segment_a["source_ranks"] == {"text": 1, "image": 2}
    assert segment_a["contributions"]["text"] == pytest.approx(1 / 61)
    assert segment_a["contributions"]["image"] == pytest.approx(1 / 62)
    assert segment_a["rrf_score"] == pytest.approx(1 / 61 + 1 / 62)


def test_weighted_rrf_can_prioritize_image_ranking() -> None:
    rankings = {
        "text": ["SEG_A", "SEG_B"],
        "image": ["SEG_B", "SEG_A"],
    }

    results = reciprocal_rank_fusion(
        rankings,
        weights={"text": 0.3, "image": 0.7},
    )

    assert results[0]["segment_id"] == "SEG_B"


def test_zero_weight_source_does_not_add_candidates() -> None:
    results = reciprocal_rank_fusion(
        {"text": ["SEG_A"], "image": ["SEG_B"]},
        weights={"text": 1.0, "image": 0.0},
    )

    assert [result["segment_id"] for result in results] == ["SEG_A"]


def test_equal_scores_use_segment_id_for_stable_order() -> None:
    results = reciprocal_rank_fusion({"text": ["SEG_B"], "image": ["SEG_A"]})

    assert [result["segment_id"] for result in results] == ["SEG_A", "SEG_B"]


def test_top_k_limits_final_results() -> None:
    results = reciprocal_rank_fusion(
        {"text": ["SEG_A", "SEG_B", "SEG_C"]},
        top_k=2,
    )

    assert len(results) == 2
    assert [result["rank"] for result in results] == [1, 2]


def test_empty_source_result_is_allowed() -> None:
    results = reciprocal_rank_fusion({"text": [], "image": ["SEG_A"]})

    assert [result["segment_id"] for result in results] == ["SEG_A"]


def test_duplicate_segment_id_in_one_source_raises_error() -> None:
    with pytest.raises(ValueError, match="중복"):
        reciprocal_rank_fusion({"text": ["SEG_A", "SEG_A"]})


@pytest.mark.parametrize("rrf_k", [0, -1, True])
def test_invalid_rrf_k_raises_error(rrf_k: object) -> None:
    with pytest.raises(ValueError, match="rrf_k"):
        reciprocal_rank_fusion({"text": ["SEG_A"]}, rrf_k=rrf_k)  # type: ignore[arg-type]


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True])
def test_invalid_top_k_raises_error(top_k: object) -> None:
    with pytest.raises(ValueError, match="top_k"):
        reciprocal_rank_fusion({"text": ["SEG_A"]}, top_k=top_k)  # type: ignore[arg-type]


def test_unknown_weight_source_raises_error() -> None:
    with pytest.raises(ValueError, match="없는 가중치"):
        reciprocal_rank_fusion(
            {"text": ["SEG_A"]},
            weights={"text": 1.0, "image": 1.0},
        )


def test_all_zero_weights_raise_error() -> None:
    with pytest.raises(ValueError, match="하나 이상"):
        reciprocal_rank_fusion(
            {"text": ["SEG_A"], "image": ["SEG_B"]},
            weights={"text": 0.0, "image": 0.0},
        )
