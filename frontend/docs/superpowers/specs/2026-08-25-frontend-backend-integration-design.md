# 프론트엔드 ↔ 실제 검색 백엔드 연결 설계

## 목표

지금까지 프론트엔드는 정적으로 번들된 517개 목업 데이터(`mockSegments517.js`)를 대상으로 클라이언트에서 직접 검색/필터링을 수행했다. 이 프로젝트는 검색 페이지와 상세 페이지를 Railway에 배포된 실제 백엔드(`https://k-tour-ai-production.up.railway.app`)로 전환한다.

## 배경 / 현재 상태

- 백엔드는 `POST /api/search`, `GET /api/segments/{id}`, `GET /api/segments`, `GET /api/spots`, `GET /api/spots/{id}`, `GET /health`를 제공하며 이미 517개 실 데이터(임베딩 포함)가 적재되어 있고 검증됐다.
- 프론트엔드는 검색어 기반 검색(`SearchResults.jsx` + `searchSegments.js`), 계절/테마별 둘러보기, 상세 페이지(`Detail.jsx`)를 로컬 배열(`mockSegments517.js`)에서 동기적으로 처리한다.
- 키프레임 이미지 517개는 이미 `public/keyframes/`에 번들되어 있어 백엔드가 반환하는 `keyframe_path`를 그대로 사용할 수 있다.
- 다국어 번역(`localizeSegment.js`)은 `segment_id` 기준으로 클라이언트 측 `segmentTranslations517.json`을 조회하는 방식이라, 백엔드가 `segment_id`만 정확히 반환하면 별도 수정 없이 그대로 동작한다.
- 지도 좌표(`placeCoordinates.js`)도 클라이언트에 이미 있고, 백엔드 응답의 `latitude`/`longitude`는 `null`이므로 계속 클라이언트 좌표를 사용한다.

## 아키텍처

```
SearchResults.jsx / Detail.jsx
        │
        ▼
  src/lib/api.js  (신규)
        │  fetch(VITE_API_BASE_URL + ...)
        ▼
  Railway 백엔드 (POST /api/search, GET /api/segments/{id})
        │
        ▼
  응답을 프론트 필드 형태로 매핑 (segment_id → uid, final_score → similarity 등)
```

`src/lib/api.js`가 유일한 네트워크 접점이 되고, 나머지 컴포넌트/유틸(`ResultCard`, `dedupeByPlace`, `dedupeByDrama`, `getMapMarkers`, `localizeSegment`)은 지금과 동일한 필드 이름(`uid`, `place_id`, `drama_title`, `keyframe_path` 등)을 기대하는 객체를 받는다. 즉 이 유틸들은 수정하지 않고, `api.js`가 백엔드 응답을 이 형태로 변환한다.

## 컴포넌트별 변경

### 1. `src/lib/api.js` (신규)

- `searchSegmentsApi({ query, season, filters, lang })`: `POST /api/search` 호출. 응답의 `results` 배열 각 항목을 다음처럼 매핑한다:
  - `uid` ← `segment_id`
  - `similarity` ← 아래 "유사도 변환" 참조
  - 나머지 필드(`place_name`, `region`, `city`, `drama_title`, `description`, `mood`, `activity`, `scene_elements`, `season`, `time_of_day`, `start_time`, `end_time`, `keyframe_path`, `place_id`, `video_id`)는 그대로 통과
- `getSegmentByIdApi(segmentId)`: `GET /api/segments/{id}` 호출, 동일한 매핑 적용. 404면 `undefined` 반환 (기존 `Detail.jsx`의 "찾을 수 없음" 분기와 호환).
- 두 함수 모두 네트워크 실패/비 2xx 응답 시 예외를 던진다. 호출부(컴포넌트)가 잡아서 에러 상태로 표시한다.
- `VITE_API_BASE_URL` 환경변수를 base URL로 사용. 값이 없으면 명확한 에러를 던져 설정 누락을 조기에 드러낸다.

### 2. `src/lib/mapSearchResponse.js` (신규, api.js에서 사용할 순수 함수로 분리)

- 유사도 변환: 한 응답 안에서 반환된 `final_score` 중 최댓값을 100%로 두고, 각 항목의 `similarity = final_score / maxFinalScore` (최댓값이 0이면 전부 0으로 처리, 0으로 나누기 방지). 결과가 0개면 빈 배열.

### 3. `SearchResults.jsx`

- `useState`로 `results`, `isLoading`, `error` 관리. `useEffect`에서 `query`/`season`/`themeId` 변경 시 API 호출.
- **일반 검색어 검색** (`query`가 있음): `query`를 그대로 백엔드에 전달.
- **계절 둘러보기** (`season`만 있고 검색어 없음): `searchSegmentsApi({ query: season, season: [season] })` — 계절 이름 자체를 자연어 질의로도 함께 보내 하드 필터와 텍스트 검색이 같은 방향을 가리키게 한다.
- **테마 둘러보기** (`themeId`만 있음): 해당 테마의 `keywords` 배열을 공백으로 join해서 `query`로 사용. `keywords`가 빈 배열이면 API를 호출하지 않고 즉시 빈 배열을 결과로 표시 (기존 `matchesTheme([])`의 "빈 배열 = 매칭 데이터 없음, 정직하게 0건" 원칙 유지).
- 로딩 중에는 스피너/스켈레톤 표시, 에러 시 에러 메시지 표시(사용자가 재시도할 수 있게 안내 문구 포함). 재시도 버튼은 범위 밖(별도 요청 없으면 추가하지 않음).
- 기존 `dedupeByPlace`/`dedupeByDrama`/`localizeSegment`/`getMapMarkers` 호출 로직은 그대로 유지 (API 응답을 매핑한 배열에 대해 동일하게 적용).

### 4. `Detail.jsx`

- `mockSegments.find(...)` 대신 `useEffect` + `getSegmentByIdApi(uid)`로 전환. 로딩 상태 추가. 실패/404 시 기존 "찾을 수 없음" UI 그대로 재사용.

### 5. 백엔드 CORS (`search-service/app/main.py`)

- `allow_origins`에 로컬 개발 주소(Vite 기본 포트, `http://localhost:5173`)를 추가해 로컬에서 실제 API를 대상으로 개발/확인할 수 있게 한다. 배포된 GitHub Pages 주소(`https://qq03-03.github.io`)는 유지.

### 6. 환경변수

- `.env.example`에 `VITE_API_BASE_URL=https://k-tour-ai-production.up.railway.app` 추가.
- 로컬 `.env`에도 동일하게 설정 (이미 다른 값 하나 있는 `.env`에 줄 추가).

## 에러 처리

- API 호출 실패(네트워크 오류, 4xx/5xx) 시 로컬 폴백 없이 에러 메시지를 사용자에게 보여준다. 문구는 "검색 결과를 불러오지 못했어요. 잠시 후 다시 시도해주세요." 형태.
- Detail 페이지에서 API 실패는 기존 "결과를 찾을 수 없어요" 문구로 통일한다 (404와 네트워크 오류를 사용자에게는 구분하지 않음 — 둘 다 "이 항목을 지금 보여줄 수 없다"는 동일한 결과이기 때문).

## 테스트

- `src/lib/mapSearchResponse.js`: 순수 함수라 유사도 변환 로직(최댓값 100%, 0건, 동점 등)을 단위 테스트로 검증.
- `src/lib/api.js`: `fetch`를 모킹해서 요청 URL/바디 구성과 에러 처리 검증 (테마 keywords join, 계절 하드필터+쿼리 동시 전달, 404 처리 등).
- `SearchResults.jsx`/`Detail.jsx`: 기존 테스트가 있다면 API 모킹으로 전환, 로딩/에러/정상 3가지 상태 렌더링 검증.

## 범위 밖 (이번엔 하지 않음)

- `GET /api/spots`, `GET /api/spots/{id}` 연결 (현재 프론트에 대응하는 화면 없음).
- 재시도 버튼, 오프라인 캐싱, 검색 결과 페이지네이션.
- Railway 백엔드 자체의 추가 개선 (이미 별도로 완료됨).
