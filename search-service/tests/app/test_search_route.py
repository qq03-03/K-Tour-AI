from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_pipeline, get_query_parser


class FakePipeline:
    def __init__(self):
        self.received_search_depth = None
        self.received_filter_overrides = "(호출되지 않음)"

    def search(self, query, *, parser, top_k, search_depth, methods, **kwargs):
        self.received_search_depth = search_depth
        self.received_filter_overrides = kwargs.get("filter_overrides")
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
