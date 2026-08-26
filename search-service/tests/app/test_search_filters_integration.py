"""POST /api/search 하드 필터의 요청 계층 → 최종 결과 통합 테스트.

FakePipeline 대신 실제 MultimodalSearchPipeline·RuleBasedQueryParser·
filter_segments를 그대로 사용하고, CLIP 런타임과 pgvector 저장소만 대역으로
바꿔 6개 하드 필터가 최종 응답 결과까지 반영되는지 확인한다.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_pipeline, get_query_parser
from app.main import app
from src.multimodal_pipeline import MultimodalSearchPipeline
from src.query_parser import RuleBasedQueryParser


# RuleBasedQueryParser가 자연어에서 어떤 하드 필터도 뽑지 않는 중립 질의.
NEUTRAL_QUERY = "촬영지 풍경 보여줘"


def _segment(
    segment_id: str,
    *,
    place_id: str,
    city: str,
    region: str,
    drama_title: str,
    season: str,
    time_of_day: str,
) -> dict[str, object]:
    return {
        "segment_id": segment_id,
        "source_segment_id": f"SRC_{segment_id}",
        "video_id": f"VID_{segment_id}",
        "place_id": place_id,
        "place_name": f"{city} 촬영지",
        "region": region,
        "city": city,
        "drama_title": drama_title,
        "start_time": 0.0,
        "end_time": 5.0,
        "description": "설명",
        "season": season,
        "time_of_day": time_of_day,
        "keyframe_path": f"keyframes/{segment_id}.jpg",
        "mood": ["peaceful"],
        "activity": [],
        "scene_elements": [],
        "k_culture_elements": [],
    }


SEGMENTS = [
    _segment(
        "SEG_A",
        place_id="P042",
        city="춘천시",
        region="강원",
        drama_title="겨울연가",
        season="여름",
        time_of_day="낮",
    ),
    _segment(
        "SEG_B",
        place_id="P042",
        city="춘천시",
        region="강원",
        drama_title="겨울연가",
        season="겨울",
        time_of_day="밤",
    ),
    _segment(
        "SEG_C",
        place_id="P001",
        city="종로구",
        region="서울",
        drama_title="사랑의 불시착",
        season="여름",
        time_of_day="해질녘",
    ),
    _segment(
        "SEG_D",
        place_id="P031",
        city="충주시",
        region="충청북도",
        drama_title="사랑의 불시착",
        season="겨울",
        time_of_day="밤",
    ),
]


class FakeRuntime:
    model_name = "fake-clip"
    device = "cpu"
    load_count = 1
    load_latency_ms = 10.0

    def encode_text(self, text: str):
        return np.ones(512, dtype=np.float32)

    def warmup(self) -> None:
        return None


class FakeRepository:
    """후보 구간만 돌려주는 대역 저장소(실제 pgvector 동작과 동일한 계약)."""

    def list_segments(self):
        return [dict(segment) for segment in SEGMENTS]

    def search(self, vector, source, *, candidate_ids, top_k):
        if not candidate_ids:
            return []
        return [
            {"segment_id": segment_id, "score": 0.9 - index * 0.01}
            for index, segment_id in enumerate(candidate_ids[:top_k])
        ]


def _client() -> TestClient:
    pipeline = MultimodalSearchPipeline(
        runtime=FakeRuntime(),
        repository=FakeRepository(),
    )
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    app.dependency_overrides[get_query_parser] = lambda: RuleBasedQueryParser()
    return TestClient(app)


def _result_ids(body: dict) -> list[str]:
    return sorted(item["segment_id"] for item in body["results"])


@pytest.mark.parametrize(
    ("field_name", "values", "expected_ids"),
    [
        ("region", ["서울"], ["SEG_C"]),
        ("season", ["겨울"], ["SEG_B", "SEG_D"]),
        ("time_of_day", ["낮"], ["SEG_A"]),
        ("drama_title", ["겨울연가"], ["SEG_A", "SEG_B"]),
        ("place_id", ["P031"], ["SEG_D"]),
        ("city", ["춘천시"], ["SEG_A", "SEG_B"]),
    ],
)
def test_each_hard_filter_narrows_the_final_results(
    field_name: str,
    values: list[str],
    expected_ids: list[str],
) -> None:
    client = _client()
    response = client.post(
        "/api/search",
        json={"q": NEUTRAL_QUERY, field_name: values, "top_k": 10},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert _result_ids(body) == expected_ids
    assert body["fallback_used"] is False


def test_no_hard_filter_returns_every_segment() -> None:
    client = _client()
    response = client.post("/api/search", json={"q": NEUTRAL_QUERY, "top_k": 10})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert _result_ids(response.json()) == ["SEG_A", "SEG_B", "SEG_C", "SEG_D"]


def test_multiple_values_for_one_field_use_or_condition() -> None:
    client = _client()
    response = client.post(
        "/api/search",
        json={"q": NEUTRAL_QUERY, "place_id": ["P001", "P031"], "top_k": 10},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert _result_ids(response.json()) == ["SEG_C", "SEG_D"]


def test_different_fields_use_and_condition() -> None:
    client = _client()
    response = client.post(
        "/api/search",
        json={
            "q": NEUTRAL_QUERY,
            "drama_title": ["겨울연가"],
            "season": ["겨울"],
            "top_k": 10,
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert _result_ids(response.json()) == ["SEG_B"]


def test_hard_filter_values_are_matched_case_insensitively() -> None:
    client = _client()
    response = client.post(
        "/api/search",
        json={"q": NEUTRAL_QUERY, "place_id": [" p031 "], "top_k": 10},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert _result_ids(response.json()) == ["SEG_D"]


@pytest.mark.parametrize("empty_value", [None, []])
def test_empty_hard_filter_is_not_applied(empty_value: object) -> None:
    client = _client()
    response = client.post(
        "/api/search",
        json={"q": NEUTRAL_QUERY, "region": empty_value, "top_k": 10},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert _result_ids(response.json()) == ["SEG_A", "SEG_B", "SEG_C", "SEG_D"]


def test_ui_hard_filter_with_no_match_returns_empty_without_fallback() -> None:
    """UI가 고른 조건이 0건이면 조건을 무시한 전국 결과로 넓히지 않는다."""

    client = _client()
    response = client.post(
        "/api/search",
        json={"q": NEUTRAL_QUERY, "place_id": ["P999"], "top_k": 10},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["fallback_used"] is False
    assert body["fallback_reason"] is None


def test_ui_hard_filter_unrecognized_alias_value_returns_empty_without_fallback() -> None:
    """별칭 테이블에 없는 값("저녁")도 필터가 사라지지 않고 그대로 적용돼야 한다.

    ``_canonical_value("time_of_day", "저녁")``는 별칭 테이블에 없어 None을
    반환한다. 이전 구현은 이 경우 time_of_day 필터 전체를 조용히 버려 4개
    구간을 모두 돌려주었다. 값을 있는 그대로 적용해 정직하게 0건을
    돌려주는 것이 올바른 동작이다.
    """

    client = _client()
    response = client.post(
        "/api/search",
        json={"q": NEUTRAL_QUERY, "time_of_day": ["저녁"], "top_k": 10},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["fallback_used"] is False
    assert body["fallback_reason"] is None


def test_ui_hard_filter_alias_value_is_canonicalized_before_matching() -> None:
    """UI가 별칭("강원도")을 보내도 정식 표기("강원")로 정규화되어 매칭돼야 한다."""

    client = _client()
    response = client.post(
        "/api/search",
        json={"q": NEUTRAL_QUERY, "region": ["강원도"], "top_k": 10},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert _result_ids(body) == ["SEG_A", "SEG_B"]
    assert body["fallback_used"] is False


def test_natural_language_filter_with_no_match_still_falls_back() -> None:
    """UI 지정이 없는 자연어 추출 필터는 기존대로 필터 없이 재검색한다(회귀 방지)."""

    client = _client()
    # RuleBasedQueryParser가 '부산'을 region 필터로 뽑지만 일치하는 구간이 없다.
    response = client.post(
        "/api/search",
        json={"q": "부산 촬영지 풍경 보여줘", "top_k": 10},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is True
    assert _result_ids(body) == ["SEG_A", "SEG_B", "SEG_C", "SEG_D"]
