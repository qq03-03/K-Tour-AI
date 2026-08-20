"""검색 순위 품질을 측정하는 Hit@K, Recall@K, MRR, nDCG@K 함수."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from math import log2
from statistics import fmean


def _relevant_set(relevant_ids: Collection[str]) -> set[str]:
    # 같은 정답 ID가 중복 입력돼도 평가 분모에 한 번만 포함한다.
    relevant = set(relevant_ids)
    if not relevant:
        raise ValueError("정답 구간은 하나 이상이어야 합니다.")
    return relevant


def recall_at_k(
    relevant_ids: Collection[str],
    retrieved_ids: Sequence[str],
    k: int = 5,
) -> float:
    """전체 정답 중 상위 K개 결과에서 찾은 정답의 비율."""

    if k <= 0:
        raise ValueError("k는 1 이상이어야 합니다.")

    relevant = _relevant_set(relevant_ids)
    # Recall@K = 상위 K개에서 찾은 정답 수 / 전체 정답 수
    retrieved_at_k = set(retrieved_ids[:k])
    return len(relevant & retrieved_at_k) / len(relevant)


def hit_at_k(
    relevant_ids: Collection[str],
    retrieved_ids: Sequence[str],
    k: int = 5,
) -> float:
    """상위 K개 결과에 정답이 하나라도 있으면 1, 없으면 0."""

    if k <= 0:
        raise ValueError("k는 1 이상이어야 합니다.")

    relevant = _relevant_set(relevant_ids)
    return 1.0 if relevant.intersection(retrieved_ids[:k]) else 0.0


def ndcg_at_k(
    relevant_ids: Collection[str],
    retrieved_ids: Sequence[str],
    k: int = 5,
) -> float:
    """이진 관련도를 사용해 상위 K개 결과의 순위 품질을 계산한다."""

    if k <= 0:
        raise ValueError("k는 1 이상이어야 합니다.")

    relevant = _relevant_set(relevant_ids)
    seen: set[str] = set()
    dcg = 0.0
    for rank, segment_id in enumerate(retrieved_ids[:k], start=1):
        # 같은 구간이 중복 반환돼도 정답 점수를 한 번만 부여한다.
        if segment_id in relevant and segment_id not in seen:
            dcg += 1.0 / log2(rank + 1)
            seen.add(segment_id)

    # 이진 관련도에서 이상적인 순위는 모든 정답이 맨 앞에 배치된 경우다.
    ideal_count = min(len(relevant), k)
    idcg = sum(1.0 / log2(rank + 1) for rank in range(1, ideal_count + 1))
    return dcg / idcg


def first_relevant_rank(
    relevant_ids: Collection[str], retrieved_ids: Sequence[str]
) -> int | None:
    """첫 번째 정답이 등장한 1부터 시작하는 순위. 없으면 None."""

    relevant = _relevant_set(relevant_ids)
    for rank, segment_id in enumerate(retrieved_ids, start=1):
        if segment_id in relevant:
            return rank
    return None


def reciprocal_rank(
    relevant_ids: Collection[str], retrieved_ids: Sequence[str]
) -> float:
    """첫 번째 정답 순위의 역수. 정답이 검색되지 않으면 0."""

    # 첫 정답이 1위면 1, 2위면 1/2, 검색되지 않으면 0이다.
    rank = first_relevant_rank(relevant_ids, retrieved_ids)
    return 0.0 if rank is None else 1.0 / rank


def mean_recall_at_k(
    relevant_by_query: Sequence[Collection[str]],
    retrieved_by_query: Sequence[Sequence[str]],
    k: int = 5,
) -> float:
    """여러 질문의 Recall@K 평균."""

    _validate_query_groups(relevant_by_query, retrieved_by_query)
    # 질문별 Recall@K를 먼저 계산한 뒤 산술평균한다.
    return fmean(
        recall_at_k(relevant, retrieved, k)
        for relevant, retrieved in zip(
            relevant_by_query, retrieved_by_query, strict=True
        )
    )


def mean_reciprocal_rank(
    relevant_by_query: Sequence[Collection[str]],
    retrieved_by_query: Sequence[Sequence[str]],
) -> float:
    """여러 질문의 Reciprocal Rank 평균인 MRR."""

    _validate_query_groups(relevant_by_query, retrieved_by_query)
    # MRR은 질문별 Reciprocal Rank의 산술평균이다.
    return fmean(
        reciprocal_rank(relevant, retrieved)
        for relevant, retrieved in zip(
            relevant_by_query, retrieved_by_query, strict=True
        )
    )


def mean_hit_at_k(
    relevant_by_query: Sequence[Collection[str]],
    retrieved_by_query: Sequence[Sequence[str]],
    k: int = 5,
) -> float:
    """여러 질문의 Hit@K 평균."""

    _validate_query_groups(relevant_by_query, retrieved_by_query)
    return fmean(
        hit_at_k(relevant, retrieved, k)
        for relevant, retrieved in zip(
            relevant_by_query, retrieved_by_query, strict=True
        )
    )


def mean_ndcg_at_k(
    relevant_by_query: Sequence[Collection[str]],
    retrieved_by_query: Sequence[Sequence[str]],
    k: int = 5,
) -> float:
    """여러 질문의 nDCG@K 평균."""

    _validate_query_groups(relevant_by_query, retrieved_by_query)
    return fmean(
        ndcg_at_k(relevant, retrieved, k)
        for relevant, retrieved in zip(
            relevant_by_query, retrieved_by_query, strict=True
        )
    )


def _validate_query_groups(
    relevant_by_query: Sequence[Collection[str]],
    retrieved_by_query: Sequence[Sequence[str]],
) -> None:
    if not relevant_by_query:
        raise ValueError("평가 질문은 하나 이상이어야 합니다.")
    if len(relevant_by_query) != len(retrieved_by_query):
        raise ValueError("정답 목록과 검색 결과 목록의 질문 수가 같아야 합니다.")
