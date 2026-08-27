"""OpenAI QueryParser, CLIP, pgvector, 필터와 검색 결합의 실제 통합 흐름."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from time import perf_counter
from typing import Any, Literal

from .clip_backend import ClipRuntime, PgVectorRepository
from .filters import filter_segments
from .fusion import normalized_score_fusion, reciprocal_rank_fusion
from .interfaces import QueryParser
from .place_id_normalization import expand_place_ids
from .query_parser import (
    ParsedQuery,
    _canonical_value,
    parse_query_safely,
    to_filter_arguments,
)
from .theme_mapping import filter_by_theme, themes_for


FusionMethod = Literal["rrf", "normalized"]
SUPPORTED_FUSION_METHODS: tuple[FusionMethod, ...] = ("rrf", "normalized")

_MOOD_ALIASES: Mapping[str, frozenset[str]] = {
    "고요한": frozenset({"고요한", "calm", "quiet", "tranquil", "serene"}),
    "평화로운": frozenset(
        {"평화로운", "peaceful", "relaxing", "relaxed", "at ease"}
    ),
    "낭만적인": frozenset({"낭만적인", "romantic"}),
    "활기찬": frozenset({"활기찬", "lively", "vibrant", "energetic"}),
    "신비로운": frozenset({"신비로운", "mysterious"}),
    "화려한": frozenset({"화려한", "glamorous", "colorful", "festive"}),
    "귀여운": frozenset({"귀여운", "cute", "adorable"}),
    "행복한": frozenset({"행복한", "happy", "joyful"}),
}


class MultimodalSearchPipeline:
    """모델과 메타데이터를 캐시해 반복 검색의 초기화 비용을 제거한다."""

    def __init__(
        self,
        *,
        runtime: ClipRuntime,
        repository: PgVectorRepository,
    ) -> None:
        self.runtime = runtime
        self.repository = repository
        self._segments: list[dict[str, Any]] | None = None
        # Caches successful (non-fallback) parses of identical query text so
        # a repeated search -- a popular theme/season click, a user re-
        # running the same search -- doesn't pay the OpenAI round trip
        # again. Keyed by parser class so switching parser types for the
        # same text can't return a stale result from a different parser.
        self._parse_cache: dict[tuple[str, str], ParsedQuery] = {}

    def warmup(self) -> None:
        self.runtime.warmup()
        self._load_segments()

    def refresh_metadata(self) -> None:
        self._segments = None

    def search(
        self,
        query: str,
        *,
        parser: QueryParser,
        top_k: int = 5,
        search_depth: int = 50,
        methods: Sequence[FusionMethod] = SUPPORTED_FUSION_METHODS,
        weights: Mapping[str, float] | None = None,
        rrf_k: float = 60.0,
        filter_overrides: Mapping[str, Sequence[str]] | None = None,
        theme_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        if top_k < 1 or search_depth < 1:
            raise ValueError("top_k와 search_depth는 1 이상이어야 합니다.")
        unknown_methods = set(methods) - set(SUPPORTED_FUSION_METHODS)
        if unknown_methods:
            raise ValueError(f"지원하지 않는 결합 방식입니다: {sorted(unknown_methods)}")

        total_started = perf_counter()
        has_free_text = isinstance(query, str) and bool(query.strip())
        # UI가 명시적으로 전달한 필터(구조화 필터든 테마든)는 QueryParser가
        # 자연어에서 추출한 같은 필드의 값보다 우선한다.
        has_ui_filter_overrides = bool(filter_overrides) or bool(theme_ids)

        if has_free_text:
            parser_started = perf_counter()
            parsed = self._parse_query_cached(query, parser)
            if filter_overrides:
                # 자연어에서 추출한 값과 동일하게, UI가 보낸 값도 별칭
                # 테이블로 정식 표기로 정규화한 뒤 병합한다 (해당 필드는
                # 완전히 대체되며, 병합하지 않는다. 예: "summer" -> "여름").
                canonical_overrides = _canonicalize_filter_overrides(filter_overrides)
                parsed = replace(parsed, filters={**parsed.filters, **canonical_overrides})
            parser_latency_ms = _elapsed_ms(parser_started)
        else:
            # 테마/계절/지역 버튼처럼 자연어가 없는 요청은 파싱할 텍스트가
            # 없으므로 QueryParser(OpenAI 포함)를 아예 호출하지 않는다.
            parser_latency_ms = 0.0
            canonical_overrides = (
                _canonicalize_filter_overrides(filter_overrides) if filter_overrides else {}
            )
            parsed = ParsedQuery(
                original_query=query,
                search_text="",
                filters=canonical_overrides,
            )

        metadata_started = perf_counter()
        segments = self._load_segments()
        filter_arguments = to_filter_arguments(parsed.filters)
        if filter_arguments.get("place_ids"):
            # P013(강릉 주문진)/P044(주문진 방파제)처럼 동일 장소를 가리키는
            # legacy/canonical place_id 쌍은 어느 쪽으로 필터해도 둘 다 검색돼야
            # 한다 (BACKEND_APPLY_GUIDE.md 5절). 표시 정규화는 search_response.py/
            # place_display.py 쪽에서 별도로 처리한다.
            filter_arguments = {
                **filter_arguments,
                "place_ids": expand_place_ids(filter_arguments["place_ids"]),
            }
        candidates = filter_segments(segments, **filter_arguments)
        # UI가 직접 지정한 하드 필터로 0건이 나온 경우에는 필터를 풀어 다시
        # 검색하지 않는다. 사용자가 고른 조건과 다른 결과를 돌려주지 않기 위함이다.
        if parsed.filters and not candidates and not has_ui_filter_overrides:
            parsed = replace(
                parsed,
                filters={},
                fallback_used=True,
                fallback_reason="필터 결과가 없어 필터 없이 다시 검색했습니다.",
            )
            filter_arguments = {}
            candidates = list(segments)
        # 테마는 source_segment_id 기준 하드 필터이며, Text/Image 후보 검색
        # 이전에 적용한다 (BACKEND_THEME_MAPPING_APPLY_GUIDE.txt 6절 참고).
        candidates = filter_by_theme(candidates, theme_ids)
        metadata_latency_ms = _elapsed_ms(metadata_started)

        candidate_ids = [str(segment["segment_id"]) for segment in candidates]
        segment_by_id = {
            str(segment["segment_id"]): dict(segment) for segment in candidates
        }

        if not has_free_text:
            # 순수 필터(테마/계절/지역 버튼) 검색: 랭킹할 자연어가 없으므로
            # CLIP 인코딩과 벡터 검색을 생략하고, 필터를 통과한 구간을 점수
            # 0.0으로 그대로 반환한다 (README_BACKEND_APPLY.md 8절 예시와
            # 동일한 형태).
            encoder_latency_ms = 0.0
            vector_search_latency_ms = 0.0

            fusion_started = perf_counter()
            depth = min(search_depth, len(candidate_ids))
            selected_ids = candidate_ids[:depth]
            # README_BACKEND_APPLY.md section 8's example response shows
            # text_score/image_score/final_score as 0.0 (not null) for a
            # theme-only result, so populate source_results the same way
            # the real vector search would, just with a constant score.
            text_results: list[dict[str, Any]] = [
                {"segment_id": segment_id, "score": 0.0} for segment_id in selected_ids
            ]
            image_results: list[dict[str, Any]] = [
                {"segment_id": segment_id, "score": 0.0} for segment_id in selected_ids
            ]
            synthetic_fused = [
                {"rank": rank, "segment_id": segment_id, "rrf_score": 0.0, "source_ranks": {}}
                for rank, segment_id in enumerate(selected_ids, start=1)
            ]
            enriched = {
                "rrf": self._enrich(
                    synthetic_fused, segment_by_id=segment_by_id, soft_hints=parsed.soft_hints
                )
            }
            fusion_latency_ms = _elapsed_ms(fusion_started)
        else:
            encoder_started = perf_counter()
            query_vector = self.runtime.encode_text(parsed.search_text)
            encoder_latency_ms = _elapsed_ms(encoder_started)

            vector_started = perf_counter()
            depth = min(search_depth, len(candidate_ids))
            text_results = self.repository.search(
                query_vector,
                "text",
                candidate_ids=candidate_ids,
                top_k=depth,
            )
            image_results = self.repository.search(
                query_vector,
                "image",
                candidate_ids=candidate_ids,
                top_k=depth,
            )
            vector_search_latency_ms = _elapsed_ms(vector_started)

            fusion_started = perf_counter()
            fused = self._fuse(
                text_results,
                image_results,
                methods=methods,
                weights=weights,
                rrf_k=rrf_k,
                top_k=top_k,
            )
            enriched = {
                method: self._enrich(
                    results,
                    segment_by_id=segment_by_id,
                    soft_hints=parsed.soft_hints,
                )
                for method, results in fused.items()
            }
            fusion_latency_ms = _elapsed_ms(fusion_started)

        return {
            "original_query": parsed.original_query,
            "search_text": parsed.search_text,
            "filters": parsed.filters,
            "soft_hints": parsed.soft_hints,
            "filter_arguments": filter_arguments,
            "fallback_used": parsed.fallback_used,
            "fallback_reason": parsed.fallback_reason,
            "candidate_count": len(candidates),
            "source_results": {
                "text": text_results,
                "image": image_results,
            },
            "results_by_method": enriched,
            "runtime": {
                "embedding_model": self.runtime.model_name,
                "device": self.runtime.device,
                "model_load_count": self.runtime.load_count,
                "model_load_latency_ms": round(self.runtime.load_latency_ms, 3),
            },
            "latency_ms": {
                "parser": round(parser_latency_ms, 3),
                "metadata_and_filter": round(metadata_latency_ms, 3),
                "query_embedding": round(encoder_latency_ms, 3),
                "vector_search": round(vector_search_latency_ms, 3),
                "fusion": round(fusion_latency_ms, 3),
                "total": round(_elapsed_ms(total_started), 3),
            },
        }

    def _parse_query_cached(self, query: str, parser: QueryParser) -> ParsedQuery:
        cache_key = (query, type(parser).__name__)
        cached = self._parse_cache.get(cache_key)
        if cached is not None:
            return cached
        parsed = parse_query_safely(query, parser)
        if not parsed.fallback_used:
            self._parse_cache[cache_key] = parsed
        return parsed

    def _load_segments(self) -> list[dict[str, Any]]:
        if self._segments is None:
            self._segments = self.repository.list_segments()
        return list(self._segments)

    @staticmethod
    def _fuse(
        text_results: Sequence[Mapping[str, Any]],
        image_results: Sequence[Mapping[str, Any]],
        *,
        methods: Sequence[FusionMethod],
        weights: Mapping[str, float] | None,
        rrf_k: float,
        top_k: int,
    ) -> dict[str, list[dict[str, Any]]]:
        rankings = {
            "text": [str(item["segment_id"]) for item in text_results],
            "image": [str(item["segment_id"]) for item in image_results],
        }
        source_scores = {
            "text": list(text_results),
            "image": list(image_results),
        }
        output: dict[str, list[dict[str, Any]]] = {}
        if "rrf" in methods:
            output["rrf"] = reciprocal_rank_fusion(
                rankings,
                weights=weights,
                rrf_k=rrf_k,
                top_k=top_k,
            )
        if "normalized" in methods:
            output["normalized"] = normalized_score_fusion(
                source_scores,
                weights=weights,
                top_k=top_k,
            )
        return output

    @staticmethod
    def _enrich(
        fused_results: Sequence[Mapping[str, Any]],
        *,
        segment_by_id: Mapping[str, Mapping[str, Any]],
        soft_hints: Mapping[str, Sequence[str]],
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for fused in fused_results:
            segment_id = str(fused["segment_id"])
            segment = dict(segment_by_id[segment_id])
            mood_matches = _matching_moods(
                soft_hints.get("mood", []),
                segment.get("mood", []),
            )
            enriched.append(
                {
                    **segment,
                    **dict(fused),
                    "themes": themes_for(str(segment.get("source_segment_id", ""))),
                    "soft_hint_matches": {"mood": mood_matches},
                }
            )
        return enriched


def _matching_moods(
    requested: Sequence[str],
    segment_moods: object,
) -> list[str]:
    if isinstance(segment_moods, (str, bytes)) or not isinstance(
        segment_moods, Sequence
    ):
        return []
    actual = {str(value).strip().casefold() for value in segment_moods}
    matches: list[str] = []
    for value in requested:
        canonical = str(value).strip()
        aliases = _MOOD_ALIASES.get(canonical, frozenset({canonical}))
        if actual.intersection(alias.casefold() for alias in aliases):
            matches.append(canonical)
    return matches


def _canonicalize_filter_overrides(
    filter_overrides: Mapping[str, Sequence[str]],
) -> dict[str, list[str]]:
    """UI가 보낸 filter_overrides 값에 자연어 필터와 동일한 별칭 정규화를 적용한다.

    ``_canonical_value``는 자연어 후처리(``_postprocess_parsed_query``)에서
    쓰이는 것과 같은 별칭 조회 로직이다. 별칭 테이블이 없는 필드(``place_id``,
    ``city``, ``drama_title``)는 값을 그대로 둔 채 공백만 정리한다.

    ``_canonical_value``는 별칭 테이블에 없는 ``season``/``time_of_day`` 값에
    대해 ``None``(드물게는 빈 문자열)을 반환한다. 이 경우 필드를 통째로
    버리면 UI가 명시한 하드 필터가 조용히 사라져 필터 없는(전체) 결과가
    나가버린다 (``search()``의 ``has_ui_filter_overrides`` 억제 로직의
    취지에 정면으로 반한다). 따라서 정규화값이 없으면 원래 값을 그대로
    하드 필터로 적용한다 — 어떤 구간과도 일치하지 않아 정직하게 0건이
    나오는 편이, 필터가 조용히 사라지는 것보다 낫다.
    """

    canonicalized: dict[str, list[str]] = {}
    for field_name, values in filter_overrides.items():
        resolved_values = [
            _canonical_value(field_name, value) or value.strip() for value in values
        ]
        if resolved_values:
            canonicalized[field_name] = resolved_values
    return canonicalized


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000.0
