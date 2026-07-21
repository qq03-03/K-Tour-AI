"""더미 검색 평가 결과에서 실패 질문과 가능한 원인을 찾는다."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from typing import Any

from .interfaces import ExplainableTextEmbedder
from .metrics import first_relevant_rank, recall_at_k, reciprocal_rank
from .search import build_segment_text, search_segments


FAILURE_EXPLANATIONS = {
    "vocabulary_gap": "질의 표현을 더미 임베더의 등록 어휘가 인식하지 못했다.",
    "no_results": "검색기가 결과를 반환하지 못했다.",
    "missed_at_k": "정답 구간이 평가 상위 K개 안에 포함되지 않았다.",
    "wrong_top_rank": "정답이 상위 K개에는 있지만 1위가 아니다.",
    "feature_collision": "오답과 정답이 질의에 대해 같은 더미 개념을 공유해 구분되지 않았다.",
}


def classify_failure(
    relevant_ids: Collection[str],
    retrieved_ids: Sequence[str],
    matched_concepts: Sequence[str],
    k: int = 5,
    feature_collision: bool = False,
) -> list[str]:
    """한 질문의 실패 상태를 원인 유형 목록으로 변환한다."""

    # 하나의 질문에 여러 원인이 동시에 존재할 수 있으므로 목록으로 반환한다.
    labels: list[str] = []
    if not matched_concepts:
        labels.append("vocabulary_gap")
    if not retrieved_ids:
        labels.append("no_results")

    # 상위 K에 정답이 없는 경우와 정답이 1위가 아닌 경우를 분리한다.
    rank = first_relevant_rank(relevant_ids, retrieved_ids)
    if rank is None or rank > k:
        labels.append("missed_at_k")
    elif rank > 1:
        labels.append("wrong_top_rank")

    if feature_collision:
        labels.append("feature_collision")
    return labels


def detect_feature_collision(
    query_concepts: Sequence[str],
    results: Sequence[Mapping[str, Any]],
    relevant_ids: Collection[str],
    segment_lookup: Mapping[str, Mapping[str, Any]],
    embedder: ExplainableTextEmbedder,
) -> bool:
    """1위 오답과 정답이 동일한 질의 개념을 공유하는지 확인한다."""

    if not results or results[0]["segment_id"] in relevant_ids:
        return False

    query_set = set(query_concepts)
    if not query_set:
        return False

    # 1위 오답과 정답이 질의에서 동일한 개념만 공유하면
    # 현재 더미 특징만으로 두 구간을 구분하기 어렵다고 판단한다.
    top_segment = segment_lookup[results[0]["segment_id"]]
    top_overlap = query_set & set(
        embedder.matched_concepts(build_segment_text(top_segment))
    )

    for relevant_id in relevant_ids:
        relevant_segment = segment_lookup[relevant_id]
        relevant_overlap = query_set & set(
            embedder.matched_concepts(build_segment_text(relevant_segment))
        )
        if top_overlap and top_overlap == relevant_overlap:
            return True
    return False


def analyze_failures(
    queries: Sequence[Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
    embedder: ExplainableTextEmbedder,
    k: int = 5,
) -> dict[str, Any]:
    """전체 평가 질문을 실행하고 실패 사례만 구조화해 반환한다."""

    if k <= 0:
        raise ValueError("k는 1 이상이어야 합니다.")

    # ID로 원본 메타데이터를 빠르게 찾기 위한 조회용 사전이다.
    segment_lookup = {segment["segment_id"]: segment for segment in segments}
    cases: list[dict[str, Any]] = []

    for item in queries:
        query = item["query"]
        relevant_ids = item["relevant_segment_ids"]
        query_concepts = embedder.matched_concepts(query)
        search_error: str | None = None

        # 어휘를 전혀 인식하지 못한 질의도 평가 전체를 중단하지 않고
        # 결과가 없는 실패 사례로 기록한다.
        try:
            results = search_segments(query, segments, embedder, top_k=len(segments))
        except ValueError as error:
            results = []
            search_error = str(error)

        retrieved_ids = [result["segment_id"] for result in results]
        collision = detect_feature_collision(
            query_concepts,
            results,
            relevant_ids,
            segment_lookup,
            embedder,
        )
        labels = classify_failure(
            relevant_ids,
            retrieved_ids,
            query_concepts,
            k=k,
            feature_collision=collision,
        )
        # 정상 검색 질문은 보고서에서 제외하고 실패 질문만 보존한다.
        if not labels:
            continue

        first_rank = first_relevant_rank(relevant_ids, retrieved_ids)
        relevant_ranks = {
            segment_id: (
                retrieved_ids.index(segment_id) + 1
                if segment_id in retrieved_ids
                else None
            )
            for segment_id in relevant_ids
        }

        cases.append(
            {
                "query_id": item["query_id"],
                "query": query,
                "relevant_segment_ids": list(relevant_ids),
                "query_concepts": query_concepts,
                "failure_types": labels,
                "explanations": [FAILURE_EXPLANATIONS[label] for label in labels],
                "recall_at_k": recall_at_k(relevant_ids, retrieved_ids, k=k),
                "first_relevant_rank": first_rank,
                "reciprocal_rank": reciprocal_rank(relevant_ids, retrieved_ids),
                "relevant_ranks": relevant_ranks,
                "top_results": [
                    {
                        "rank": result["rank"],
                        "segment_id": result["segment_id"],
                        "location_name": result["location_name"],
                        "score": round(result["score"], 6),
                        "is_relevant": result["segment_id"] in relevant_ids,
                    }
                    for result in results[:k]
                ],
                "search_error": search_error,
            }
        )

    failure_counts = Counter(
        label for case in cases for label in case["failure_types"]
    )
    return {
        "summary": {
            "total_queries": len(queries),
            "failure_queries": len(cases),
            "failure_rate": len(cases) / len(queries) if queries else 0.0,
            "failure_type_counts": dict(sorted(failure_counts.items())),
            "k": k,
        },
        "cases": cases,
    }
