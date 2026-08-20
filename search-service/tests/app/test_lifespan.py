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
    # conftest.py는 tests/app 전체에 SKIP_CLIP_WARMUP을 기본으로 켜둔다
    # (다른 테스트가 실수로 무거운 실제 warmup을 트리거하지 않도록).
    # 이 테스트는 정상적으로(가드가 없을 때) warmup이 호출된다는 것을
    # 증명하는 목적이므로, 이 테스트의 범위 안에서만 그 기본값을 해제한다.
    monkeypatch.delenv("SKIP_CLIP_WARMUP", raising=False)

    fake_runtime = _FakeRuntime()
    monkeypatch.setattr(main, "get_runtime", lambda: fake_runtime)

    with TestClient(main.app) as client:
        client.get("/nonexistent-route-just-to-ensure-app-is-up")

    assert fake_runtime.warmup_calls == 1


def test_lifespan_skips_warmup_when_skip_env_var_is_set(monkeypatch) -> None:
    """SKIP_CLIP_WARMUP이 설정되어 있으면(테스트 스위트 기본값) lifespan은
    get_runtime()조차 호출하지 않아야 한다. 이는 향후 어딘가에 새로 추가되는
    `with TestClient(app) as client:` 형태의 테스트가, 로컬에 없을 수도 있는
    실제 CLIP 모델 가중치를 로딩하려고 시도하지 않는다는 것을 보장한다.
    """
    monkeypatch.setenv("SKIP_CLIP_WARMUP", "1")

    def _fail_if_called():
        raise AssertionError("get_runtime() should not be called when SKIP_CLIP_WARMUP is set")

    monkeypatch.setattr(main, "get_runtime", _fail_if_called)

    with TestClient(main.app) as client:
        client.get("/nonexistent-route-just-to-ensure-app-is-up")
