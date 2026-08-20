import psycopg
import pytest
from fastapi.testclient import TestClient

from app.dependencies import ConfigurationError, ping_database
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_dependency_overrides():
    yield
    app.dependency_overrides.pop(ping_database, None)


def test_health_returns_ok():
    app.dependency_overrides[ping_database] = lambda: None

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_database_ping_fails():
    def _fail() -> None:
        raise psycopg.OperationalError("connection refused")

    app.dependency_overrides[ping_database] = _fail

    response = client.get("/health")

    assert response.status_code == 503
    assert "detail" in response.json()
    assert "connection refused" not in response.json()["detail"]


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


def test_non_operational_psycopg_error_returns_503_with_a_safe_message():
    @app.get("/__test_db_programming_error")
    def _raise_db_programming_error():
        raise psycopg.ProgrammingError("relation \"video_segments\" does not exist")

    response = client.get("/__test_db_programming_error")
    assert response.status_code == 503
    assert "detail" in response.json()
    assert "video_segments" not in response.json()["detail"]


def test_configuration_error_returns_503_with_a_safe_message():
    @app.get("/__test_config_error")
    def _raise_config_error():
        raise ConfigurationError("DB 환경변수가 없습니다: POSTGRES_HOST")

    response = client.get("/__test_config_error")
    assert response.status_code == 503
    assert "detail" in response.json()
