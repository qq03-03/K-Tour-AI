"""프로젝트 작품 카탈로그를 기준으로 질의 안의 드라마 제목을 판별한다."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from .location_matcher import first_known_location_start


TitleMatchStatus = Literal["matched", "not_found", "ambiguous", "none"]

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "drama_title_catalog.json"

_WORK_INTENT_PATTERNS = (
    r"촬영\s*지", r"촬영\s*장소", r"로케이션", r"드라마",
    r"filming\s+locations?", r"drama\s+locations?", r"k[- ]?drama", r"tv\s+show",
    r"ロケ地", r"撮影地", r"ドラマ",
    r"拍攝地", r"拍摄地", r"取景地", r"電視劇", r"电视剧",
)
_WORK_INTENT_RE = re.compile("|".join(_WORK_INTENT_PATTERNS), re.IGNORECASE)
_QUOTED_TITLE_RE = re.compile(r"[\"'‘’“”「」『』《》]([^\"'‘’“”「」『』《》]{2,80})[\"'‘’“”「」『』《》]")
_KNOWN_PLACE_RE = re.compile(
    r"\bNami\s+Island\b|남이섬|南怡島|南怡岛|경복궁|Gyeongbokgung|한옥마을|Hanok\s+Village",
    re.IGNORECASE,
)
_LEADING_EXPLICIT_FILTER_RE = re.compile(
    r"^(?:(?:봄|여름|가을|겨울)(?:에|에는|의)\s+|"
    r"(?:새벽|아침|낮|해질녘|밤)(?:에|에는|의)\s+)+"
)
_FILTER_ONLY_CANDIDATE_RE = re.compile(
    r"^(?:\s|[,.，。:：'’‘\"“”\-–—]|"
    r"봄|여름|가을|겨울|새벽|아침|낮|해질녘|밤|에|에는|의|"
    r"spring|summer|autumn|fall|winter|dawn|morning|daytime|sunset|dusk|night|"
    r"before\s+sunrise|during\s+the\s+day|"
    r"a|an|the|in|during|at|on|of|"
    r"春|夏|秋|冬|春天|夏天|秋天|冬天|春季|夏季|秋季|冬季|"
    r"明け方|朝|昼|夕暮れ|夜|夜晚|早晨|上午|白天|黎明|日落|黄昏|"
    r"の|に|で|ある|있는|에서|때|的|时|時|时候|時候)+$",
    re.IGNORECASE,
)
_KOREAN_REGION_SEASON_TITLE_RE = re.compile(
    r"^\s*[가-힣]+의\s*(?:봄|여름|가을|겨울)\s*$"
)
_CONTEXT_REQUIRED_ALIASES = frozenset({"kingdom", "goblin", "guardian"})


@dataclass(frozen=True)
class TitleSpan:
    start: int
    end: int
    text: str
    canonical_title: str | None


@dataclass(frozen=True)
class DramaTitleMatch:
    status: TitleMatchStatus
    matched_titles: tuple[str, ...] = ()
    possible_title: str | None = None
    protected_spans: tuple[TitleSpan, ...] = ()


@dataclass(frozen=True)
class _AliasEntry:
    canonical_title: str
    alias: str


@lru_cache(maxsize=1)
def load_title_catalog() -> tuple[dict[str, object], ...]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    titles = payload.get("titles")
    if not isinstance(titles, list) or not titles:
        raise ValueError("드라마 제목 카탈로그의 titles가 비어 있습니다.")
    canonical_seen: set[str] = set()
    validated: list[dict[str, object]] = []
    for index, raw in enumerate(titles):
        if not isinstance(raw, dict):
            raise ValueError(f"titles[{index}]는 객체여야 합니다.")
        canonical = raw.get("canonical_title")
        aliases = raw.get("aliases")
        if not isinstance(canonical, str) or not canonical.strip():
            raise ValueError(f"titles[{index}].canonical_title이 비어 있습니다.")
        key = normalize_title(canonical)
        if key in canonical_seen:
            raise ValueError(f"중복 canonical_title: {canonical}")
        if not isinstance(aliases, dict):
            raise ValueError(f"titles[{index}].aliases는 객체여야 합니다.")
        canonical_seen.add(key)
        validated.append(raw)
    return tuple(validated)


@lru_cache(maxsize=1)
def _alias_entries() -> tuple[_AliasEntry, ...]:
    entries: list[_AliasEntry] = []
    seen: dict[str, str] = {}
    for item in load_title_catalog():
        canonical = str(item["canonical_title"])
        aliases = item["aliases"]
        assert isinstance(aliases, dict)
        for values in aliases.values():
            if not isinstance(values, list):
                raise ValueError(f"{canonical}의 언어별 aliases는 배열이어야 합니다.")
            for alias in values:
                if not isinstance(alias, str) or not alias.strip():
                    raise ValueError(f"{canonical}에 빈 별칭이 있습니다.")
                normalized = normalize_title(alias)
                owner = seen.get(normalized)
                if owner is not None and owner != canonical:
                    raise ValueError(f"서로 다른 작품이 같은 별칭을 사용합니다: {alias}")
                seen[normalized] = canonical
                entries.append(_AliasEntry(canonical, alias.strip()))
    entries.sort(key=lambda entry: len(entry.alias), reverse=True)
    return tuple(entries)


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[\s\-–—_:：,，.。'’‘\"“”]+", "", normalized)
    return normalized


def analyze_drama_titles(query: str) -> DramaTitleMatch:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query는 빈 문자열이 아니어야 합니다.")
    has_work_intent = _WORK_INTENT_RE.search(query) is not None
    quoted_ranges = [(match.start(1), match.end(1)) for match in _QUOTED_TITLE_RE.finditer(query)]
    matched_spans: list[TitleSpan] = []

    for entry in _alias_entries():
        alias_key = normalize_title(entry.alias)
        if alias_key in _CONTEXT_REQUIRED_ALIASES and not has_work_intent:
            if not any(normalize_title(query[start:end]) == alias_key for start, end in quoted_ranges):
                continue
        for start, end in _find_alias_spans(query, entry.alias):
            if any(start < span.end and end > span.start for span in matched_spans):
                continue
            matched_spans.append(TitleSpan(start, end, query[start:end], entry.canonical_title))

    if matched_spans:
        matched_spans.sort(key=lambda span: span.start)
        titles = tuple(dict.fromkeys(span.canonical_title for span in matched_spans if span.canonical_title))
        return DramaTitleMatch("matched", titles, None, tuple(matched_spans))

    if has_work_intent:
        possible_span = _extract_possible_title_span(query)
        if possible_span is not None:
            return DramaTitleMatch(
                "not_found",
                (),
                possible_span.text,
                (possible_span,),
            )

    if quoted_ranges:
        start, end = quoted_ranges[0]
        possible = query[start:end].strip()
        if possible:
            return DramaTitleMatch(
                "ambiguous",
                (),
                possible,
                (TitleSpan(start, end, possible, None),),
            )
    return DramaTitleMatch("none")


def mask_protected_titles(query: str, match: DramaTitleMatch) -> str:
    characters = list(query)
    for span in match.protected_spans:
        characters[span.start:span.end] = " " * (span.end - span.start)
    return "".join(characters)


def _find_alias_spans(query: str, alias: str) -> list[tuple[int, int]]:
    escaped = re.escape(alias)
    escaped = escaped.replace(r"\ ", r"[\s\-–—_:：,，.。'’‘\"“”]*")
    pattern = re.compile(escaped, re.IGNORECASE)
    return [(match.start(), match.end()) for match in pattern.finditer(query)]


def _extract_possible_title_span(query: str) -> TitleSpan | None:
    intent_match = _WORK_INTENT_RE.search(query)
    if intent_match is None:
        return None
    prefix = query[:intent_match.start()]
    place_match = _KNOWN_PLACE_RE.search(prefix)
    known_starts = [place_match.start()] if place_match is not None else []
    catalog_start = (
        first_known_location_start(prefix)
        if prefix.strip() and _KOREAN_REGION_SEASON_TITLE_RE.fullmatch(prefix) is None
        else None
    )
    if catalog_start is not None:
        known_starts.append(catalog_start)
    if known_starts:
        prefix = prefix[:min(known_starts)]
    leading_removed = _LEADING_EXPLICIT_FILTER_RE.sub("", prefix)
    removed_length = len(prefix) - len(leading_removed)
    start = removed_length
    candidate = leading_removed.strip(" \t\r\n,，.。:：-–—")
    if not candidate:
        return None
    if _FILTER_ONLY_CANDIDATE_RE.fullmatch(candidate):
        return None
    relative_start = leading_removed.find(candidate)
    start += relative_start
    end = start + len(candidate)
    return TitleSpan(start, end, query[start:end], None)
