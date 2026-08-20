from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_segments_repository


_SEGMENT = {
    "segment_id": "V007_P031_S002_SCENE_001", "source_segment_id": "V007_P031_S002",
    "video_id": "V007_Z7u5SNDq0jw", "place_id": "P031", "place_name": "충주 중앙탑공원",
    "region": "충청북도", "city": "충주시", "drama_title": "사랑의 불시착",
    "start_time": 0.0, "end_time": 3.75, "description": "야경",
    "season": "summer", "time_of_day": "night", "keyframe_path": "keyframes/x.jpg",
    "mood": ["peaceful"], "activity": [], "scene_elements": [], "k_culture_elements": [],
}


class FakeSegmentsRepository:
    def __init__(self):
        self.last_video_id = "not_called"
        self.last_place_id = "not_called"
        self.last_drama_title = "not_called"

    def list_segments(self, video_id, place_id, drama_title):
        self.last_video_id = video_id
        self.last_place_id = place_id
        self.last_drama_title = drama_title
        return [_SEGMENT]

    def get_segment(self, segment_id):
        return _SEGMENT if segment_id == _SEGMENT["segment_id"] else None


def _client():
    app.dependency_overrides[get_segments_repository] = lambda: FakeSegmentsRepository()
    return TestClient(app)


def test_list_segments():
    client = _client()
    response = client.get("/api/segments")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["segment_id"] == "V007_P031_S002_SCENE_001"


def test_list_segments_forwards_video_id_query_param():
    repo = FakeSegmentsRepository()
    app.dependency_overrides[get_segments_repository] = lambda: repo
    client = TestClient(app)

    response = client.get("/api/segments?video_id=V007_Z7u5SNDq0jw")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert repo.last_video_id == "V007_Z7u5SNDq0jw"
    assert repo.last_place_id is None
    assert repo.last_drama_title is None


def test_list_segments_forwards_place_id_query_param():
    repo = FakeSegmentsRepository()
    app.dependency_overrides[get_segments_repository] = lambda: repo
    client = TestClient(app)

    response = client.get("/api/segments?place_id=P031")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert repo.last_place_id == "P031"
    assert repo.last_video_id is None
    assert repo.last_drama_title is None


def test_list_segments_forwards_drama_title_query_param():
    repo = FakeSegmentsRepository()
    app.dependency_overrides[get_segments_repository] = lambda: repo
    client = TestClient(app)

    response = client.get("/api/segments?drama_title=사랑의 불시착")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert repo.last_drama_title == "사랑의 불시착"
    assert repo.last_video_id is None
    assert repo.last_place_id is None


def test_list_segments_forwards_all_three_query_params_combined():
    repo = FakeSegmentsRepository()
    app.dependency_overrides[get_segments_repository] = lambda: repo
    client = TestClient(app)

    response = client.get(
        "/api/segments?video_id=V007_Z7u5SNDq0jw&place_id=P031&drama_title=사랑의 불시착"
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert repo.last_video_id == "V007_Z7u5SNDq0jw"
    assert repo.last_place_id == "P031"
    assert repo.last_drama_title == "사랑의 불시착"


def test_get_segment_found():
    client = _client()
    response = client.get(f"/api/segments/{_SEGMENT['segment_id']}")
    app.dependency_overrides.clear()

    assert response.status_code == 200


def test_get_segment_not_found():
    client = _client()
    response = client.get("/api/segments/does-not-exist")
    app.dependency_overrides.clear()

    assert response.status_code == 404
