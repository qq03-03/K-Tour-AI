"""CLIP 결합 결과를 활동·장면·감성 메타데이터로 소프트 재정렬한다."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any


DEFAULT_BASE_WEIGHT = 0.7
DEFAULT_METADATA_WEIGHT = 0.3
DEFAULT_MIN_METADATA_CONFIDENCE = 0.6

_FIELD_WEIGHTS: Mapping[str, float] = {
    "scene_elements": 0.5,
    "activity": 0.3,
    "mood": 0.2,
}

# 전체 데이터에서는 VLM 저장값을 표준 코드로 통일하는 것이 우선이다.
# 이 별칭은 현재처럼 여러 언어의 검색 힌트와 한글 DB 태그가 섞인 경우를
# 안전하게 연결하기 위한 검색 계층의 보정표다.
_CONCEPT_ALIASES: Mapping[str, frozenset[str]] = {
    "hydrangea": frozenset(
        {"수국", "hydrangea", "hydrangeas", "紫陽花", "アジサイ", "绣球花", "繡球花"}
    ),
    "pavilion": frozenset(
        {"정자", "pavilion", "traditional pavilion", "亭子", "東屋"}
    ),
    "forest": frozenset({"숲", "forest", "woodland", "woods", "森", "树林", "樹林"}),
    "picnic": frozenset({"피크닉", "picnic", "野餐"}),
    "pool": frozenset({"수영장", "pool", "outdoor pool", "プール", "游泳池"}),
    "lantern": frozenset({"등불", "lantern", "lanterns", "提灯", "灯笼", "燈籠"}),
    "path": frozenset(
        {
            "길",
            "산책길",
            "꽃길",
            "path",
            "walking path",
            "trail",
            "小道",
            "花道",
            "步道",
        }
    ),
    "walking": frozenset(
        {
            "산책",
            "걷기",
            "걷는",
            "walking",
            "walk",
            "strolling",
            "歩く",
            "散歩",
            "漫步",
            "散步",
        }
    ),
    "rabbit": frozenset({"토끼", "rabbit", "rabbits", "ウサギ", "うさぎ", "兔", "白兔"}),
    "feeding": frozenset(
        {"먹이주기", "먹이를 주는", "feeding", "feed", "餌をあげる", "喂食"}
    ),
    "lotus": frozenset({"연꽃", "lotus", "lotus flower", "蓮", "荷花"}),
    "pond": frozenset({"연못", "pond", "池", "池塘"}),
    "duck": frozenset({"오리", "duck", "ducks", "アヒル", "鸭", "鴨"}),
    "lawn": frozenset({"잔디밭", "lawn", "grass", "芝生", "草坪"}),
    "tree": frozenset({"나무", "trees", "tree", "木", "木々", "树", "樹"}),
    "bench": frozenset({"벤치", "bench", "ベンチ", "长椅", "長椅"}),
    "traditional_building": frozenset(
        {
            "전통 건축물",
            "전통 건물",
            "traditional building",
            "traditional buildings",
            "伝統的な建物",
            "传统建筑",
            "傳統建築",
        }
    ),
    "flower": frozenset({"꽃", "flower", "flowers", "花"}),
    "dessert": frozenset({"디저트", "dessert", "デザート", "甜点", "甜點"}),
    "rest": frozenset({"휴식", "rest", "relaxing", "休憩", "休息"}),
    "animal_watching": frozenset(
        {"동물 관찰", "animal watching", "wildlife watching", "動物観察", "观察动物"}
    ),
    "peaceful": frozenset(
        {
            "평화로운",
            "고요한",
            "peaceful",
            "calm",
            "quiet",
            "serene",
            "tranquil",
            "穏やか",
            "静か",
            "宁静",
            "平静",
        }
    ),
    "cute": frozenset({"귀여운", "cute", "adorable", "かわいい", "可爱", "可愛"}),
}


def concepts_for_values(value: object) -> set[str]:
    """여러 언어의 태그 값을 비교 가능한 검색 개념 집합으로 변환한다."""

    return _concepts(_string_values(value))


def rerank_with_metadata(
    results: Sequence[Mapping[str, Any]],
    *,
    segment_by_id: Mapping[str, Mapping[str, Any]],
    soft_hints: Mapping[str, Sequence[str]],
    top_k: int,
    base_weight: float = DEFAULT_BASE_WEIGHT,
    metadata_weight: float = DEFAULT_METADATA_WEIGHT,
    min_metadata_confidence: float = DEFAULT_MIN_METADATA_CONFIDENCE,
    enabled: bool = True,
) -> list[dict[str, Any]]:
    """결합 점수와 메타데이터 일치도를 같은 범위에서 결합한다."""

    _validate_inputs(
        top_k,
        base_weight,
        metadata_weight,
        min_metadata_confidence,
    )
    if not results:
        return []

    raw_base_scores = [_base_score(item) for item in results]
    normalized_base_scores = _min_max_normalize(raw_base_scores)
    metadata_is_requested = any(
        _string_values(soft_hints.get(field))
        for field in _FIELD_WEIGHTS
    )
    weight_sum = base_weight + metadata_weight
    resolved_base_weight = base_weight / weight_sum
    resolved_metadata_weight = metadata_weight / weight_sum

    scored_candidates: list[
        tuple[Mapping[str, Any], float, float, dict[str, list[str]], dict[str, float]]
    ] = []
    for position, (result, base_score) in enumerate(
        zip(results, normalized_base_scores),
        start=1,
    ):
        segment_id = str(result.get("segment_id", ""))
        if segment_id not in segment_by_id:
            raise KeyError(f"메타데이터에 없는 segment_id입니다: {segment_id}")
        metadata_score, matches, field_scores = _metadata_match_score(
            soft_hints,
            segment_by_id[segment_id],
        )
        scored_candidates.append(
            (result, base_score, metadata_score, matches, field_scores)
        )

    best_metadata_score = max(
        (item[2] for item in scored_candidates),
        default=0.0,
    )
    metadata_is_active = (
        enabled
        and metadata_is_requested
        and best_metadata_score >= min_metadata_confidence
    )
    if not enabled:
        rerank_reason = "disabled"
    elif not metadata_is_requested:
        rerank_reason = "no_soft_hints"
    elif metadata_is_active:
        rerank_reason = "sufficient_metadata_match"
    else:
        rerank_reason = "insufficient_metadata_match"

    candidates: list[dict[str, Any]] = []
    for position, (
        result,
        base_score,
        metadata_score,
        matches,
        field_scores,
    ) in enumerate(scored_candidates, start=1):
        if metadata_is_active:
            final_score = (
                resolved_base_weight * base_score
                + resolved_metadata_weight * metadata_score
            )
        else:
            final_score = base_score
        candidates.append(
            {
                **dict(result),
                "fusion_rank": int(result.get("rank", position)),
                "base_score_normalized": round(base_score, 12),
                "metadata_score": round(metadata_score, 12),
                "final_score": round(final_score, 12),
                "metadata_rerank_applied": metadata_is_active,
                "metadata_rerank_reason": rerank_reason,
                "metadata_confidence": round(best_metadata_score, 12),
                "soft_hint_matches": matches,
                "soft_hint_match_scores": field_scores,
            }
        )

    ordered = sorted(
        candidates,
        key=lambda item: (
            -float(item["final_score"]),
            int(item["fusion_rank"]),
            str(item["segment_id"]),
        ),
    )[:top_k]
    return [
        {"rank": rank, **{key: value for key, value in item.items() if key != "rank"}}
        for rank, item in enumerate(ordered, start=1)
    ]


def _metadata_match_score(
    soft_hints: Mapping[str, Sequence[str]],
    segment: Mapping[str, Any],
) -> tuple[float, dict[str, list[str]], dict[str, float]]:
    weighted_score = 0.0
    active_weight = 0.0
    matches: dict[str, list[str]] = {}
    field_scores: dict[str, float] = {}

    for field, field_weight in _FIELD_WEIGHTS.items():
        requested_values = _string_values(soft_hints.get(field))
        if not requested_values:
            continue
        segment_values = _segment_values(segment, field)
        requested_concepts = _concepts(requested_values)
        actual_concepts = _concepts(segment_values)
        intersection = requested_concepts & actual_concepts
        score = (
            len(intersection) / len(requested_concepts)
            if requested_concepts
            else 0.0
        )
        matches[field] = [
            value
            for value in requested_values
            if _concepts([value]) & actual_concepts
        ]
        field_scores[field] = round(score, 12)
        weighted_score += field_weight * score
        active_weight += field_weight

    if active_weight == 0:
        return 0.0, matches, field_scores
    return weighted_score / active_weight, matches, field_scores


def _segment_values(
    segment: Mapping[str, Any],
    field: str,
) -> list[str]:
    if field == "scene_elements":
        values = segment.get("scene_elements")
        if not _string_values(values):
            values = segment.get("landscape")
        return _string_values(values)
    return _string_values(segment.get(field))


def _concepts(values: Sequence[str]) -> set[str]:
    concepts: set[str] = set()
    for value in values:
        normalized = _normalize_text(value)
        matched = False
        for concept, aliases in _CONCEPT_ALIASES.items():
            if any(_contains_alias(normalized, alias) for alias in aliases):
                concepts.add(concept)
                matched = True
        if not matched and normalized:
            concepts.add(normalized)
    return concepts


def _contains_alias(normalized: str, alias: str) -> bool:
    normalized_alias = _normalize_text(alias)
    if not normalized_alias:
        return False
    if normalized_alias.isascii():
        return bool(
            re.search(
                rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])",
                normalized,
            )
        )
    return normalized_alias in normalized


def _normalize_text(value: str) -> str:
    cleaned = value.strip().casefold()
    return re.sub(r"[\s\-_/]+", " ", cleaned)


def _string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        ]
    return []


def _base_score(result: Mapping[str, Any]) -> float:
    for field in ("combined_score", "rrf_score"):
        value = result.get(field)
        if isinstance(value, Real) and not isinstance(value, bool):
            score = float(value)
            if math.isfinite(score):
                return score
    raise ValueError("결합 결과에 유한한 combined_score 또는 rrf_score가 필요합니다.")


def _min_max_normalize(scores: Sequence[float]) -> list[float]:
    minimum = min(scores)
    maximum = max(scores)
    if maximum == minimum:
        return [1.0 for _ in scores]
    scale = maximum - minimum
    return [(score - minimum) / scale for score in scores]


def _validate_inputs(
    top_k: int,
    base_weight: float,
    metadata_weight: float,
    min_metadata_confidence: float,
) -> None:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k는 1 이상의 정수여야 합니다.")
    for name, value in (
        ("base_weight", base_weight),
        ("metadata_weight", metadata_weight),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(float(value))
            or float(value) < 0
        ):
            raise ValueError(f"{name}는 0 이상의 유한한 숫자여야 합니다.")
    if base_weight + metadata_weight <= 0:
        raise ValueError("base_weight와 metadata_weight 중 하나는 0보다 커야 합니다.")
    if (
        isinstance(min_metadata_confidence, bool)
        or not isinstance(min_metadata_confidence, Real)
        or not math.isfinite(float(min_metadata_confidence))
        or not 0 <= float(min_metadata_confidence) <= 1
    ):
        raise ValueError("min_metadata_confidence는 0과 1 사이 숫자여야 합니다.")
