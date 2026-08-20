"""get_pipeline()이 프로세스 수명 동안 단일 인스턴스를 재사용하는지 확인한다."""

from __future__ import annotations

from app import dependencies


def test_get_pipeline_returns_the_same_cached_instance(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")

    first = dependencies.get_pipeline()
    second = dependencies.get_pipeline()

    assert first is second
