"""앱 시작 시 CLIP 런타임 warmup()이 호출되는지 확인한다.

lifespan은 `with TestClient(app) as client:` 형태로만 발동하므로
(맨몸 `TestClient(app)`은 발동하지 않음 - 기존 스위트가 이 형태를 쓰는 이유),
이 테스트는 명시적으로 컨텍스트 매니저 형태를 사용한다.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main


class _FakeRuntime:
    def __init__(self) -> None:
        self.warmup_calls = 0

    def warmup(self) -> None:
        self.warmup_calls += 1


def test_lifespan_warms_up_the_clip_runtime_on_startup(monkeypatch) -> None:
    fake_runtime = _FakeRuntime()
    monkeypatch.setattr(main, "get_runtime", lambda: fake_runtime)

    with TestClient(main.app) as client:
        client.get("/nonexistent-route-just-to-ensure-app-is-up")

    assert fake_runtime.warmup_calls == 1
