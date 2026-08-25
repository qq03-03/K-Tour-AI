import logging

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


def test_cors_allows_local_dev_origin():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


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


def test_db_connection_failure_is_logged_server_side(caplog):
    @app.get("/__test_db_error_logged")
    def _raise_db_error():
        raise psycopg.OperationalError("connection refused")

    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = client.get("/__test_db_error_logged")

    assert response.status_code == 503
    matching_records = [record for record in caplog.records if record.name == "app.main"]
    assert matching_records, "expected app.main to log the DB error"
    assert all(record.levelno >= logging.ERROR for record in matching_records)
    assert any("__test_db_error_logged" in record.getMessage() for record in matching_records)
    # the underlying exception must actually be attached, not just a generic message
    assert any(record.exc_info is not None for record in matching_records)


def test_configuration_error_is_logged_server_side(caplog):
    @app.get("/__test_config_error_logged")
    def _raise_config_error():
        raise ConfigurationError("DB 환경변수가 없습니다: POSTGRES_HOST")

    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = client.get("/__test_config_error_logged")

    assert response.status_code == 503
    matching_records = [record for record in caplog.records if record.name == "app.main"]
    assert matching_records, "expected app.main to log the configuration error"
    assert all(record.levelno >= logging.ERROR for record in matching_records)
    assert any("__test_config_error_logged" in record.getMessage() for record in matching_records)
    assert any(record.exc_info is not None for record in matching_records)
