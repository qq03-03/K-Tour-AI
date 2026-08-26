from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_pipeline, get_query_parser


class FakePipeline:
    def __init__(self):
        self.received_search_depth = None
        self.received_filter_overrides = "(호출되지 않음)"
        self.received_parser = None

    def search(self, query, *, parser, top_k, search_depth, methods, **kwargs):
        self.received_search_depth = search_depth
        self.received_filter_overrides = kwargs.get("filter_overrides")
        self.received_parser = parser
        segment = {
            "segment_id": "V007_P031_S002_SCENE_001",
            "source_segment_id": "V007_P031_S002",
            "video_id": "V007_Z7u5SNDq0jw",
            "place_id": "P031",
            "place_name": "충주 중앙탑공원",
            "region": "충청북도",
            "city": "충주시",
            "drama_title": "사랑의 불시착",
            "start_time": 0.0,
            "end_time": 3.75,
            "season": "summer",
            "time_of_day": "night",
            "description": "야경",
            "mood": ["peaceful"],
            "activity": [],
            "scene_elements": [],
            "k_culture_elements": [],
            "keyframe_path": "keyframes/x.jpg",
            "rrf_score": 0.03,
            "source_ranks": {"text": 1, "image": 1},
        }
        return {
            "results_by_method": {"rrf": [segment]},
            "source_results": {
                "text": [{"segment_id": "V007_P031_S002_SCENE_001", "score": 0.8}],
                "image": [{"segment_id": "V007_P031_S002_SCENE_001", "score": 0.75}],
            },
            "fallback_used": False,
            "fallback_reason": None,
            "latency_ms": {
                "parser": 1.5,
                "metadata_and_filter": 2.0,
                "query_embedding": 3.0,
                "vector_search": 4.0,
                "fusion": 0.5,
                "total": 11.0,
            },
        }


class FakeParser:
    pass


def _client():
    fake_pipeline = FakePipeline()
    app.dependency_overrides[get_pipeline] = lambda: fake_pipeline
    app.dependency_overrides[get_query_parser] = lambda: FakeParser()
    return TestClient(app), fake_pipeline


def test_search_returns_mapped_results():
    client, fake_pipeline = _client()
    response = client.post("/api/search", json={"query": "봄 궁궐 산책"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["place_name"] == "충주 중앙탑공원"
    assert body["results"][0]["rank"] == 1
    assert body["fallback_used"] is False
    # Verify that the pipeline received the correct search_depth (candidate_k = max(5*5, 50) = 50)
    assert fake_pipeline.received_search_depth == 50


def test_search_rejects_an_empty_query():
    client, _ = _client()
    response = client.post("/api/search", json={"query": ""})
    app.dependency_overrides.clear()

    assert response.status_code == 422


def test_search_forwards_region_filter_to_the_pipeline():
    client, fake_pipeline = _client()
    response = client.post("/api/search", json={"query": "봄 궁궐 산책", "region": ["강원"]})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_pipeline.received_filter_overrides == {"region": ["강원"]}


def test_search_forwards_drama_title_filter_to_the_pipeline():
    client, fake_pipeline = _client()
    response = client.post(
        "/api/search",
        json={"query": "촬영지", "drama_title": ["겨울연가", "사랑의 불시착"]},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_pipeline.received_filter_overrides == {
        "drama_title": ["겨울연가", "사랑의 불시착"]
    }


def test_search_forwards_every_hard_filter_field_to_the_pipeline():
    client, fake_pipeline = _client()
    response = client.post(
        "/api/search",
        json={
            "query": "촬영지",
            "place_id": ["P031"],
            "drama_title": ["사랑의 불시착"],
            "region": ["충청북도"],
            "city": ["충주시"],
            "season": ["summer"],
            "time_of_day": ["night"],
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_pipeline.received_filter_overrides == {
        "place_id": ["P031"],
        "drama_title": ["사랑의 불시착"],
        "region": ["충청북도"],
        "city": ["충주시"],
        "season": ["summer"],
        "time_of_day": ["night"],
    }


def test_search_without_hard_filters_sends_no_filter_overrides():
    client, fake_pipeline = _client()
    response = client.post("/api/search", json={"query": "봄 궁궐 산책"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_pipeline.received_filter_overrides is None


def test_search_treats_empty_hard_filter_lists_as_not_set():
    client, fake_pipeline = _client()
    response = client.post(
        "/api/search",
        json={"query": "봄 궁궐 산책", "region": [], "drama_title": None},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_pipeline.received_filter_overrides is None


def test_search_treats_blank_string_filter_element_as_not_set():
    client, fake_pipeline = _client()
    response = client.post(
        "/api/search",
        json={"query": "봄 궁궐 산책", "region": [""]},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_pipeline.received_filter_overrides is None


def test_search_treats_whitespace_only_filter_element_as_not_set():
    client, fake_pipeline = _client()
    response = client.post(
        "/api/search",
        json={"query": "봄 궁궐 산책", "region": ["  "]},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_pipeline.received_filter_overrides is None


def test_search_drops_blank_element_but_keeps_other_values_in_the_same_field():
    client, fake_pipeline = _client()
    response = client.post(
        "/api/search",
        json={"query": "봄 궁궐 산책", "region": ["", "강원"]},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_pipeline.received_filter_overrides == {"region": ["강원"]}


def test_search_without_hard_filters_uses_the_injected_query_parser():
    # A free-text query with no UI filters needs real language understanding,
    # so it should go through whatever parser get_query_parser() resolved to
    # (the LLM parser in production).
    client, fake_pipeline = _client()
    response = client.post("/api/search", json={"query": "봄 궁궐 산책"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert isinstance(fake_pipeline.received_parser, FakeParser)


def test_search_with_hard_filters_skips_the_llm_parser():
    # When the UI already sends explicit filter values (theme/season/drama
    # title clicks), the LLM query parser's structured extraction is
    # redundant -- it costs an OpenAI round trip for no benefit, so this
    # request should be served by the fast rule-based parser instead.
    from src.query_parser import RuleBasedQueryParser

    client, fake_pipeline = _client()
    response = client.post(
        "/api/search",
        json={"query": "촬영지", "drama_title": ["겨울연가"]},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert isinstance(fake_pipeline.received_parser, RuleBasedQueryParser)


def test_search_logs_the_latency_breakdown(caplog):
    import logging

    client, _ = _client()
    with caplog.at_level(logging.INFO, logger="app.main"):
        response = client.post("/api/search", json={"query": "봄 궁궐 산책"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    matching = [r for r in caplog.records if "latency_ms" in r.getMessage()]
    assert matching, f"no latency log found in {[r.getMessage() for r in caplog.records]}"
    assert "total" in matching[0].getMessage()
