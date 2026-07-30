from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from run_synthetic_search_evaluation import select_cases


ROOT = Path(__file__).resolve().parent
CASE_FILE = ROOT / "synthetic_search_cases.json"


def load_queries() -> list[dict[str, object]]:
    payload = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    return payload["queries"]


def test_cases_are_balanced_and_do_not_expose_segment_ids_in_queries() -> None:
    queries = load_queries()

    assert len(queries) == 12
    assert Counter(item["language"] for item in queries) == {
        "ko": 3,
        "en": 3,
        "ja": 3,
        "zh": 3,
    }
    assert len({item["query_id"] for item in queries}) == 12
    assert all("SEG_" not in str(item["query"]) for item in queries)


def test_smoke_limit_selects_only_requested_cases() -> None:
    cases = [{"query_id": str(index)} for index in range(3)]

    assert select_cases(cases, 1) == [{"query_id": "0"}]
    assert select_cases(cases, None) == cases
