"""tests/app 전체에 적용되는 공통 테스트 설정.

app.main의 lifespan은 실제 CLIP 런타임 warmup()을 호출한다. 이는
`with TestClient(app) as client:` 형태로 진입할 때만 발동하는데
(맨몸 `TestClient(app)`은 발동하지 않음), 이 형태는 FastAPI의 공식
권장 사용법이므로 향후 새 테스트가 별다른 이유 없이 이 형태를 쓰면
무겁고 느리고(로컬에 모델 가중치가 없으면) 실패할 수도 있는 실제
모델 로딩을 의도치 않게 트리거하게 된다.

이를 막기 위해 app.main.lifespan은 SKIP_CLIP_WARMUP 환경변수가
설정되어 있으면 warmup()을 건너뛴다. 이 환경변수는 lifespan 함수가
실제로 실행되는 시점에 매번 다시 읽히므로(임포트 시점이 아니라),
app.main이 처음 임포트되기 전에 아래처럼 모듈 수준에서 설정해두면
충분하다 - pytest는 같은 디렉터리의 테스트 모듈을 임포트하기 전에
conftest.py를 먼저 임포트한다.

이 기본값이 필요한 개별 테스트(tests/app/test_lifespan.py 등)는
monkeypatch로 이 값을 지우거나 재설정해서 자기 범위 안에서만
동작을 바꾼다.
"""

import os

os.environ.setdefault("SKIP_CLIP_WARMUP", "1")
