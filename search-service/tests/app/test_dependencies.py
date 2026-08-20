"""get_pipeline()이 프로세스 수명 동안 단일 인스턴스를 재사용하는지 확인한다."""

from __future__ import annotations

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
