from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_spots_repository


class FakeSpotsRepository:
    def list_spots(self, region):
        return [{"spot_id": 1, "spot_name": "충주 중앙탑공원", "region": "충청북도", "address": "주소", "latitude": 37.0, "longitude": 127.8, "description": "설명", "source_url": None}]

    def get_spot(self, spot_id):
        if spot_id == 1:
            return {"spot_id": 1, "spot_name": "충주 중앙탑공원", "region": "충청북도", "address": "주소", "latitude": 37.0, "longitude": 127.8, "description": "설명", "source_url": None}
        return None


def _client():
    app.dependency_overrides[get_spots_repository] = lambda: FakeSpotsRepository()
    return TestClient(app)


def test_list_spots():
    client = _client()
    response = client.get("/api/spots")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["spot_name"] == "충주 중앙탑공원"


def test_get_spot_found():
    client = _client()
    response = client.get("/api/spots/1")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["spot_id"] == 1


def test_get_spot_not_found():
    client = _client()
    response = client.get("/api/spots/999")
    app.dependency_overrides.clear()

    assert response.status_code == 404
