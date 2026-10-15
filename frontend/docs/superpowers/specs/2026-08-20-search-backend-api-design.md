# 검색·조회 백엔드 API 설계

## 목적

지금 프론트엔드는 정적 JSON 데이터를 대상으로 클라이언트 사이드 키워드 검색만 하고 있다. 팀의 `feature/search-core-kdh` 브랜치에 이미 구현·검증된 검색 로직(`search-service/`, 159개 테스트 통과, 2026-07-24 기준)을 FastAPI HTTP API로 감싸서 실제 클라우드에 배포하고, 프론트엔드가 이 API를 호출하도록 연결한다.

이 스펙은 두 단계 중 **1단계(백엔드)**만 다룬다. 2단계(프론트엔드를 정적 데이터에서 API 호출로 전환)는 이 스펙이 끝난 뒤 별도로 브레인스토밍한다.

## 배경

- **검색 로직은 이미 완성되어 있다.** `feature/search-core-kdh` 브랜치의 `search-service/`에 OpenAI 기반 QueryParser(규칙 기반 폴백 포함), CLIP 텍스트 임베딩, pgvector 검색, RRF 결합까지 구현·테스트되어 있다. `search-service/run_multimodal_search.py`의 `MultimodalSearchPipeline.search(query, parser=..., top_k=..., methods=...)`가 핵심 진입점이다. 이 브랜치엔 아직 HTTP API 서버가 없다 — CLI 스크립트로만 실행 가능하다.
- **DB 스키마는 이미 정의되어 있다.** `main` 브랜치의 `embedding-db/schema.sql`에 `spots`(관광지), `videos`, `video_segments`(검색 핵심 단위), `segment_embeddings`, `segment_keyframes`, `keyframe_embeddings` 테이블이 있고, `embedding-db/docker-compose.yml`로 로컬 Postgres+pgvector 컨테이너를 띄울 수 있다. 팀 노트에 따르면 로컬 DB에는 이미 517개 세그먼트가 적재되어 있다.
- **검색 API 계약은 이미 문서화되어 있다.** 백엔드 전달본의 `docs/search_api_contract.md`에 `POST /api/search`의 요청/응답 필드, RRF 결합 규칙, 하드 필터 규칙이 정의되어 있다. 관광지 조회·영상 구간 조회 API는 아직 문서화되어 있지 않다 — 이 스펙에서 최소 스펙으로 정의한다.
- **`search-service/`는 아직 `main`에 머지되어 있지 않다.** 이 작업의 첫 단계는 `feature/search-core-kdh`를 `main`에 머지하는 것이다.
- **OpenAI API 키가 아직 없다.** `search-service`는 키 없이도 규칙 기반 QueryParser로 동작하도록 이미 설계되어 있으므로, 키 발급 전에도 개발·배포는 진행할 수 있다. 실제 QueryParser 품질 검증(팀이 이미 수행한 RRF Hit@5 1.000 등의 평가)은 키가 있어야 재현 가능하다.

## 범위

**포함:**
- `feature/search-core-kdh` → `main` 머지
- FastAPI 앱: `POST /api/search`, `GET /api/spots`, `GET /api/spots/{spot_id}`, `GET /api/segments`, `GET /api/segments/{segment_id}`, `GET /health`
- Dockerfile 작성
- Railway에 Postgres+pgvector 서비스 + FastAPI 서비스 배포
- 로컬 DB(517건 적재 완료) → Railway DB로 `pg_dump`/`pg_restore` 이전
- CORS를 프론트 배포 주소(`https://qq03-03.github.io`)로 제한
- FastAPI 라우트 계층 테스트 추가

**제외(다음 단계 또는 별도 작업):**
- 프론트엔드를 정적 데이터에서 이 API로 전환하는 작업 (2단계, 별도 브레인스토밍)
- OpenAI API 키 발급 자체 (사용자가 직접 처리)
- `search-service/` 내부 검색 로직 수정 (이미 검증된 코드는 그대로 재사용)

## 아키텍처

단일 FastAPI 서비스가 검색·관광지 조회·영상 구간 조회를 모두 처리한다. 서버 시작 시 CLIP 모델과 DB 연결을 한 번만 로드하고 요청마다 재사용한다(`search-service`의 `ClipRuntime`/`PgVectorRepository`/`MultimodalSearchPipeline`을 그대로 재사용). 별도 마이크로서비스로 분리하지 않는 이유: 지금 규모(517개 세그먼트, 소규모 트래픽)에서는 복잡도만 늘어나고, 서비스마다 CLIP 모델을 따로 로드하면 메모리가 낭비된다.

배포는 Railway를 사용한다: 기존 `embedding-db/docker-compose.yml` 구조(임의 Docker 이미지를 서비스로 붙이는 방식)를 거의 그대로 옮길 수 있고, FastAPI 앱도 Dockerfile 하나로 GitHub 연동 자동 배포가 가능하며, `OPENAI_API_KEY` 같은 비밀값을 대시보드 환경변수로 안전하게 관리할 수 있다.

## API 엔드포인트

### `POST /api/search`
`docs/search_api_contract.md`에 정의된 요청/응답 규격을 그대로 따른다. 요청: `query`, `lang`, `place_id`/`drama_title`/`region`/`city`/`season`/`time_of_day`(선택 필터), `top_k`, `candidate_k`. 응답: `rank`, `source_segment_id`, `segment_id`, `keyframe_id`, `keyframe_path`, `video_id`, 장소·작품·계절·시간대 메타데이터, `text_score`/`image_score`/`text_rank`/`image_rank`/`final_score`.

내부적으로 `MultimodalSearchPipeline.search()`를 호출하는 얇은 래퍼로 구현한다. `parsed.fallback_used` 값을 응답에 그대로 포함해, OpenAI 호출이 실패했거나 키가 없어 규칙 기반으로 대체됐는지 프론트가 알 수 있게 한다.

### `GET /api/spots`, `GET /api/spots/{spot_id}`
`spots` 테이블 조회. 목록 조회는 `region` 쿼리 파라미터로 선택적 필터링을 지원한다. 페이지네이션은 두지 않는다(74개 장소 규모에서는 불필요).

### `GET /api/segments`, `GET /api/segments/{segment_id}`
`video_segments` 테이블 조회. 목록 조회는 `video_id`, `place_id`, `drama_title` 쿼리 파라미터로 선택적 필터링을 지원한다.

### `GET /health`
DB 연결 상태를 포함한 헬스체크. Railway 배포 확인 및 향후 모니터링에 사용한다.

## 배포 절차

1. `feature/search-core-kdh`를 `main`에 머지하고 충돌을 해결한다.
2. FastAPI 앱용 `Dockerfile`을 작성한다(`search-service/requirements.txt` 재사용 + `fastapi`/`uvicorn` 추가).
3. Railway에 Postgres+pgvector 서비스를 만든다(`pgvector/pgvector:pg16` 이미지, 기존 `schema.sql` 적용).
4. 로컬 DB에서 `pg_dump`로 517건을 내보내고, Railway DB에 `pg_restore`로 복원한다.
5. FastAPI 앱을 Railway에 두 번째 서비스로 배포하고, `DATABASE_URL`, `OPENAI_API_KEY`(있으면), CLIP 모델 캐시 경로 등 환경변수를 설정한다.
6. CORS를 프론트 배포 주소(`https://qq03-03.github.io`)만 허용하도록 설정한다(와일드카드 금지).
7. `GET /health`로 배포를 확인한다.

## 에러 처리

- OpenAI API 키가 없거나 호출이 실패하면 `search-service`에 이미 구현된 규칙 기반 QueryParser로 조용히 대체하고, 응답의 `fallback_used`로 표시한다.
- DB 연결 실패 시 503과 함께 원인이 드러나지 않는 일반 에러 메시지를 반환한다(스택트레이스 미노출).
- 잘못된 요청 파라미터는 FastAPI/Pydantic 기본 검증에 따라 422를 반환한다.
- 검색 결과가 0건이어도 에러가 아니라 200과 빈 배열을 반환한다.

## 테스트

- 기존 `search-service`의 159개 테스트를 그대로 유지·재사용한다(로직 자체는 수정하지 않으므로 회귀 검증 용도).
- FastAPI 라우트 계층에 새 테스트를 추가해, 요청/응답 형식이 `docs/search_api_contract.md`와 일치하는지 검증한다.
- 로컬 `docker compose up`으로 DB+API를 함께 띄워 통합 테스트를 수행한다.
- Railway 배포 후 실제 URL에 대해 수동으로 검증한다(curl 또는 브라우저).
