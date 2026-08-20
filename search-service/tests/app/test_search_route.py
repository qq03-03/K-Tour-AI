from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_pipeline, get_query_parser


class FakePipeline:
    def search(self, query, *, parser, top_k, methods, **kwargs):
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
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
    app.dependency_overrides[get_query_parser] = lambda: FakeParser()
    return TestClient(app)


def test_search_returns_mapped_results():
    client = _client()
    response = client.post("/api/search", json={"query": "봄 궁궐 산책"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["place_name"] == "충주 중앙탑공원"
    assert body["results"][0]["rank"] == 1
    assert body["fallback_used"] is False


def test_search_rejects_an_empty_query():
    client = _client()
    response = client.post("/api/search", json={"query": ""})
    app.dependency_overrides.clear()

    assert response.status_code == 422
