"""get_pipeline()이 프로세스 수명 동안 단일 인스턴스를 재사용하는지 확인한다."""

from __future__ import annotations

import psycopg
import pytest

from app import dependencies
from src.clip_backend import DatabaseConfig


def test_get_pipeline_returns_the_same_cached_instance(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")

    first = dependencies.get_pipeline()
    second = dependencies.get_pipeline()

    assert first is second


def test_repository_reraises_missing_env_vars_as_configuration_error(monkeypatch) -> None:
    def _raise_value_error(cls, env_path=None):
        raise ValueError("DB 환경변수가 없습니다: POSTGRES_HOST")

    monkeypatch.setattr(DatabaseConfig, "from_environment", classmethod(_raise_value_error))
    dependencies._repository.cache_clear()

    try:
        with pytest.raises(dependencies.ConfigurationError):
            dependencies._repository()
    finally:
        dependencies._repository.cache_clear()


class _FakeCursor:
    """search-service/tests/test_clip_backend.py의 _FakeCursor/_FakeConnection과
    동일한 패턴을 따른다 (psycopg 커서/커넥션을 흉내내는 최소 페이크)."""

    def __init__(self) -> None:
        self.executed_query = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, query, params=None):
        self.executed_query = query


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *exc_info):
        self.exited = True
        return False

    def cursor(self):
        return self._cursor


def test_ping_database_executes_select_1_and_closes_the_connection(monkeypatch) -> None:
    """ping_database()의 실제 본문(연결 -> SELECT 1 실행 -> 종료)이
    한 번도 실행되지 않고 항상 dependency_overrides로 대체되어 왔던
    커버리지 공백을 메운다. psycopg.connect만 페이크로 교체하고
    ping_database 자체는 그대로 호출한다."""

    class _FakeConfig:
        connection_string = "fake-connection-string"

    class _FakeRepository:
        _config = _FakeConfig()

    monkeypatch.setattr(dependencies, "_repository", lambda: _FakeRepository())

    fake_cursor = _FakeCursor()
    fake_connection = _FakeConnection(fake_cursor)
    seen_connection_strings = []

    def _fake_connect(connection_string):
        seen_connection_strings.append(connection_string)
        return fake_connection

    monkeypatch.setattr(psycopg, "connect", _fake_connect)

    dependencies.ping_database()

    assert seen_connection_strings == ["fake-connection-string"]
    assert fake_cursor.executed_query == "SELECT 1"
    assert fake_connection.entered is True
    assert fake_connection.exited is True
