import psycopg
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_the_frontend_origin():
    response = client.options(
        "/health",
        headers={
            "Origin": "https://qq03-03.github.io",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "https://qq03-03.github.io"


def test_db_connection_failure_returns_503_with_a_safe_message():
    @app.get("/__test_db_error")
    def _raise_db_error():
        raise psycopg.OperationalError("connection refused")

    response = client.get("/__test_db_error")
    assert response.status_code == 503
    assert "detail" in response.json()
    assert "connection refused" not in response.json()["detail"]
