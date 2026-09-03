"""프로젝트 다국어 QueryParser 평가셋의 구조와 범위를 검증한다."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from src.query_parser_evaluation import load_query_parser_cases


DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "project_multilingual_query_parser_eval.json"
)
EXPECTED_PLACE_IDS = {f"P{index:03d}" for index in range(1, 31)}


def test_project_eval_has_44_balanced_valid_cases() -> None:
    cases = load_query_parser_cases(DATA_PATH)

    assert len(cases) == 44
    assert Counter(case["language"] for case in cases) == {
        "ko": 11,
        "en": 11,
        "ja": 11,
        "zh": 11,
    }


def test_project_eval_covers_all_p001_through_p030() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    covered_place_ids = {
        case["target_place_id"]
        for case in payload["queries"]
        if "target_place_id" in case
    }

    assert covered_place_ids == EXPECTED_PLACE_IDS


def test_project_eval_uses_only_supported_filter_and_soft_hint_fields() -> None:
    cases = load_query_parser_cases(DATA_PATH)
    allowed_filters = {"region", "season", "time_of_day"}
    allowed_soft_hints = {"mood"}

    for case in cases:
        assert set(case["expected_filters"]) <= allowed_filters
        assert set(case.get("expected_soft_hints", {})) <= allowed_soft_hints
