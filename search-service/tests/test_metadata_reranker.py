from __future__ import annotations

import pytest

from src.metadata_reranker import rerank_with_metadata


def fused_results(target_id: str) -> list[dict[str, object]]:
    return [
        {"rank": 1, "segment_id": "DECOY_A", "combined_score": 1.0},
        {"rank": 2, "segment_id": "DECOY_B", "combined_score": 0.9},
        {"rank": 3, "segment_id": "DECOY_C", "combined_score": 0.8},
        {"rank": 4, "segment_id": "DECOY_D", "combined_score": 0.7},
        {"rank": 5, "segment_id": "DECOY_E", "combined_score": 0.6},
        {"rank": 6, "segment_id": target_id, "combined_score": 0.55},
    ]


def empty_decoys(target_id: str) -> dict[str, dict[str, object]]:
    metadata = {
        segment_id: {
            "segment_id": segment_id,
            "scene_elements": ["연못"],
            "activity": ["휴식"],
            "mood": [],
        }
        for segment_id in (
            "DECOY_A",
            "DECOY_B",
            "DECOY_C",
            "DECOY_D",
            "DECOY_E",
        )
    }
    metadata[target_id] = {"segment_id": target_id}
    return metadata


def test_hydrangea_pavilion_picnic_is_promoted_before_top_k_cutoff() -> None:
    target_id = "SEG_NAMI_01_02"
    metadata = empty_decoys(target_id)
    metadata[target_id].update(
        {
            "scene_elements": ["수국", "정자", "숲"],
            "activity": ["피크닉"],
            "mood": [],
        }
    )

    results = rerank_with_metadata(
        fused_results(target_id),
        segment_by_id=metadata,
        soft_hints={
            "scene_elements": ["pink hydrangeas", "traditional pavilion", "forest"],
            "activity": ["picnic"],
        },
        top_k=5,
    )

    target = next(item for item in results if item["segment_id"] == target_id)
    assert target["rank"] <= 5
    assert target["fusion_rank"] == 6
    assert target["metadata_score"] == pytest.approx(1.0)


def test_pool_lantern_walking_path_is_promoted_with_multilingual_aliases() -> None:
    target_id = "SEG_NAMI_01_04"
    metadata = empty_decoys(target_id)
    metadata[target_id].update(
        {
            "scene_elements": ["수영장", "등불", "산책길"],
            "activity": ["산책"],
            "mood": [],
        }
    )

    results = rerank_with_metadata(
        fused_results(target_id),
        segment_by_id=metadata,
        soft_hints={
            "scene_elements": ["outdoor pool", "lantern-lined path"],
            "activity": ["walking"],
        },
        top_k=5,
    )

    target = next(item for item in results if item["segment_id"] == target_id)
    assert target["rank"] <= 5
    assert target["soft_hint_matches"] == {
        "scene_elements": ["outdoor pool", "lantern-lined path"],
        "activity": ["walking"],
    }


def test_no_soft_hints_preserves_fusion_order() -> None:
    results = fused_results("TARGET")
    metadata = empty_decoys("TARGET")

    reranked = rerank_with_metadata(
        results,
        segment_by_id=metadata,
        soft_hints={},
        top_k=5,
    )

    assert [item["segment_id"] for item in reranked] == [
        "DECOY_A",
        "DECOY_B",
        "DECOY_C",
        "DECOY_D",
        "DECOY_E",
    ]
    assert all(not item["metadata_rerank_applied"] for item in reranked)
    assert all(
        item["metadata_rerank_reason"] == "no_soft_hints"
        for item in reranked
    )


def test_insufficient_metadata_match_preserves_fusion_order() -> None:
    results = fused_results("TARGET")
    metadata = empty_decoys("TARGET")
    metadata["TARGET"].update(
        {
            "scene_elements": ["나무"],
            "activity": ["산책"],
            "mood": [],
        }
    )

    reranked = rerank_with_metadata(
        results,
        segment_by_id=metadata,
        soft_hints={
            "scene_elements": ["outdoor pool", "lantern"],
            "activity": ["walking"],
        },
        top_k=5,
    )

    assert [item["segment_id"] for item in reranked] == [
        "DECOY_A",
        "DECOY_B",
        "DECOY_C",
        "DECOY_D",
        "DECOY_E",
    ]
    assert all(not item["metadata_rerank_applied"] for item in reranked)
    assert all(
        item["metadata_rerank_reason"] == "insufficient_metadata_match"
        for item in reranked
    )


def test_disabled_reranker_preserves_order_even_with_full_match() -> None:
    target_id = "TARGET"
    results = fused_results(target_id)
    metadata = empty_decoys(target_id)
    metadata[target_id].update(
        {
            "scene_elements": ["수국", "정자", "숲"],
            "activity": ["피크닉"],
            "mood": [],
        }
    )

    reranked = rerank_with_metadata(
        results,
        segment_by_id=metadata,
        soft_hints={
            "scene_elements": ["hydrangeas", "pavilion", "forest"],
            "activity": ["picnic"],
        },
        top_k=5,
        enabled=False,
    )

    assert [item["segment_id"] for item in reranked] == [
        "DECOY_A",
        "DECOY_B",
        "DECOY_C",
        "DECOY_D",
        "DECOY_E",
    ]
    assert all(item["metadata_rerank_reason"] == "disabled" for item in reranked)


@pytest.mark.parametrize(
    ("base_weight", "metadata_weight"),
    [(-0.1, 1.0), (1.0, -0.1), (0.0, 0.0)],
)
def test_invalid_weights_are_rejected(
    base_weight: float,
    metadata_weight: float,
) -> None:
    with pytest.raises(ValueError, match="weight"):
        rerank_with_metadata(
            [{"rank": 1, "segment_id": "A", "rrf_score": 1.0}],
            segment_by_id={"A": {"segment_id": "A"}},
            soft_hints={},
            top_k=1,
            base_weight=base_weight,
            metadata_weight=metadata_weight,
        )
