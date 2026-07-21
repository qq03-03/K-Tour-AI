"""관광 영상 구간의 더미 텍스트 유사도 검색."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .interfaces import TextEmbedder


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    """두 벡터의 코사인 유사도를 계산한다."""

    if left.shape != right.shape:
        raise ValueError("비교할 두 벡터의 차원이 같아야 합니다.")

    # 내적을 두 벡터 길이의 곱으로 나눠 방향의 유사성만 비교한다.
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator == 0.0:
        return 0.0

    return float(np.dot(left, right) / denominator)


def build_segment_text(segment: Mapping[str, Any]) -> str:
    """구간의 문장과 구조화 메타데이터를 하나의 검색용 문자열로 합친다."""

    # 자연어 설명뿐 아니라 필터용 구조화 태그도 검색 정보로 활용한다.
    scalar_fields = (
        "metadata_text",
        "location_name",
        "region",
        "season",
        "time_of_day",
    )
    list_fields = ("mood", "landscape", "activity", "category")

    parts = [str(segment.get(field, "")) for field in scalar_fields]
    for field in list_fields:
        values = segment.get(field, [])
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            parts.extend(str(value) for value in values)

    return " ".join(part for part in parts if part)


def search_segments(
    query: str,
    segments: Sequence[Mapping[str, Any]],
    embedder: TextEmbedder,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """질의와 가까운 영상 구간을 코사인 유사도순으로 반환한다."""

    if top_k <= 0:
        raise ValueError("top_k는 1 이상이어야 합니다.")

    # 검색어와 각 영상 구간을 반드시 같은 임베더로 벡터화한다.
    query_vector = embedder.encode(query)
    if float(np.linalg.norm(query_vector)) == 0.0:
        raise ValueError("더미 임베더가 질의에서 인식한 키워드가 없습니다.")

    candidates: list[dict[str, Any]] = []
    for segment in segments:
        # 실제 임베딩 모델을 연결해도 이 반복 구조는 그대로 사용할 수 있다.
        segment_vector = embedder.encode(build_segment_text(segment))
        candidates.append(
            {
                "segment_id": segment["segment_id"],
                "video_id": segment["video_id"],
                "location_name": segment["location_name"],
                "start_sec": segment["start_sec"],
                "end_sec": segment["end_sec"],
                "score": cosine_similarity(query_vector, segment_vector),
            }
        )

    # 점수가 같으면 segment_id 순으로 정렬해 실행할 때마다 결과를 고정한다.
    candidates.sort(key=lambda item: (-item["score"], item["segment_id"]))

    results: list[dict[str, Any]] = []
    for rank, candidate in enumerate(candidates[:top_k], start=1):
        results.append({"rank": rank, **candidate})
    return results
