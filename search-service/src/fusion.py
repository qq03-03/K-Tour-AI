"""텍스트·이미지 검색 순위를 Reciprocal Rank Fusion으로 결합한다."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any


def reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[str]],
    *,
    weights: Mapping[str, float] | None = None,
    rrf_k: float = 60.0,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """여러 검색 순위를 RRF 점수로 결합해 최종 순위를 반환한다.

    ``rankings``의 키는 ``text``, ``image`` 같은 검색 방식 이름이고,
    값은 높은 순위부터 정렬된 segment_id 목록이다. ``weights``를 생략하면
    모든 검색 방식의 가중치를 1로 사용한다.
    """

    _validate_inputs(rankings, weights, rrf_k, top_k)
    source_weights = {
        source: float(weights.get(source, 1.0)) if weights else 1.0
        for source in rankings
    }

    candidates: dict[str, dict[str, Any]] = {}
    for source, segment_ids in rankings.items():
        weight = source_weights[source]
        seen: set[str] = set()

        for source_rank, segment_id in enumerate(segment_ids, start=1):
            if not isinstance(segment_id, str) or not segment_id.strip():
                raise ValueError(
                    f"{source} 검색 결과의 segment_id는 빈 문자열이 아니어야 합니다."
                )
            if segment_id in seen:
                raise ValueError(
                    f"{source} 검색 결과에 segment_id가 중복되었습니다: {segment_id}"
                )
            seen.add(segment_id)

            # 가중치가 0인 검색 방식은 검증만 하고 최종 후보에는 포함하지 않는다.
            if weight == 0:
                continue

            contribution = weight / (rrf_k + source_rank)
            candidate = candidates.setdefault(
                segment_id,
                {
                    "segment_id": segment_id,
                    "rrf_score": 0.0,
                    "source_ranks": {},
                    "contributions": {},
                },
            )
            candidate["rrf_score"] += contribution
            candidate["source_ranks"][source] = source_rank
            candidate["contributions"][source] = contribution

    ordered = sorted(
        candidates.values(),
        key=lambda item: (-item["rrf_score"], item["segment_id"]),
    )
    if top_k is not None:
        ordered = ordered[:top_k]

    return [
        {"rank": final_rank, **candidate}
        for final_rank, candidate in enumerate(ordered, start=1)
    ]


def normalized_score_fusion(
    results_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    weights: Mapping[str, float] | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """검색 방식별 점수를 0~1로 정규화한 뒤 가중합한다.

    실제 임베딩 점수 분포를 받은 뒤 RRF와 비교하기 위한 기준 구현이다.
    각 항목에는 ``segment_id``와 유한한 숫자 ``score``가 필요하다.
    """

    rankings = {
        source: [str(item.get("segment_id", "")) for item in items]
        for source, items in results_by_source.items()
    }
    _validate_inputs(rankings, weights, 60.0, top_k)
    source_weights = {
        source: float(weights.get(source, 1.0)) if weights else 1.0
        for source in results_by_source
    }

    candidates: dict[str, dict[str, Any]] = {}
    for source, items in results_by_source.items():
        raw_scores: list[float] = []
        seen_segment_ids: set[str] = set()
        for item in items:
            segment_id = item.get("segment_id")
            if not isinstance(segment_id, str) or not segment_id.strip():
                raise ValueError(
                    f"{source} 검색 결과의 segment_id는 빈 문자열이 아니어야 합니다."
                )
            if segment_id in seen_segment_ids:
                raise ValueError(
                    f"{source} 검색 결과에 segment_id가 중복되었습니다: {segment_id}"
                )
            seen_segment_ids.add(segment_id)
            score = item.get("score")
            if isinstance(score, bool) or not isinstance(score, Real):
                raise TypeError(f"{source} 검색 점수는 숫자여야 합니다.")
            numeric_score = float(score)
            if not math.isfinite(numeric_score):
                raise ValueError(f"{source} 검색 점수는 유한한 숫자여야 합니다.")
            raw_scores.append(numeric_score)

        normalized_scores = _min_max_normalize(raw_scores)
        for item, raw_score, normalized_score in zip(
            items, raw_scores, normalized_scores
        ):
            segment_id = str(item["segment_id"])
            contribution = source_weights[source] * normalized_score
            candidate = candidates.setdefault(
                segment_id,
                {
                    "segment_id": segment_id,
                    "combined_score": 0.0,
                    "source_scores": {},
                    "normalized_scores": {},
                    "contributions": {},
                },
            )
            candidate["combined_score"] += contribution
            candidate["source_scores"][source] = raw_score
            candidate["normalized_scores"][source] = normalized_score
            candidate["contributions"][source] = contribution

    ordered = sorted(
        candidates.values(),
        key=lambda item: (-item["combined_score"], item["segment_id"]),
    )
    if top_k is not None:
        ordered = ordered[:top_k]
    return [
        {"rank": rank, **candidate}
        for rank, candidate in enumerate(ordered, start=1)
    ]


def _min_max_normalize(scores: Sequence[float]) -> list[float]:
    if not scores:
        return []
    minimum = min(scores)
    maximum = max(scores)
    if maximum == minimum:
        return [1.0 for _ in scores]
    scale = maximum - minimum
    return [(score - minimum) / scale for score in scores]


def _validate_inputs(
    rankings: Mapping[str, Sequence[str]],
    weights: Mapping[str, float] | None,
    rrf_k: float,
    top_k: int | None,
) -> None:
    if not rankings:
        raise ValueError("결합할 검색 순위는 하나 이상이어야 합니다.")

    for source, segment_ids in rankings.items():
        if not isinstance(source, str) or not source.strip():
            raise ValueError("검색 방식 이름은 빈 문자열이 아니어야 합니다.")
        if isinstance(segment_ids, (str, bytes)) or not isinstance(
            segment_ids, Sequence
        ):
            raise TypeError(f"{source} 검색 결과는 segment_id 순서 목록이어야 합니다.")

    if isinstance(rrf_k, bool) or not isinstance(rrf_k, Real) or rrf_k <= 0:
        raise ValueError("rrf_k는 0보다 큰 숫자여야 합니다.")

    if top_k is not None and (
        isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0
    ):
        raise ValueError("top_k는 1 이상의 정수이거나 None이어야 합니다.")

    if weights is None:
        return

    unknown_sources = set(weights) - set(rankings)
    if unknown_sources:
        names = ", ".join(sorted(unknown_sources))
        raise ValueError(f"검색 순위에 없는 가중치 이름입니다: {names}")

    resolved_weights: list[float] = []
    for source in rankings:
        weight = weights.get(source, 1.0)
        if isinstance(weight, bool) or not isinstance(weight, Real) or weight < 0:
            raise ValueError(f"{source} 가중치는 0 이상의 숫자여야 합니다.")
        resolved_weights.append(float(weight))

    if not any(weight > 0 for weight in resolved_weights):
        raise ValueError("검색 가중치는 하나 이상 0보다 커야 합니다.")
