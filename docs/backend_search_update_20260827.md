# K-Tour AI 백엔드 검색 통합 보완 전달본 v2

- 전달일: 2026-08-27
- 자연어 API 요청 필드: `q`
- metadata·text/image embedding: 변경 없음
- 재임베딩: 필요 없음

## 1. 포함 파일

### search-service/data/backend_integrated_search_catalog_v2.json

- UI 고정 문구와 계절·테마·작품 선택지의 한·영·일·중 표시값
- 작품명 별칭, 지역 별칭, 장소 표시언어·주소·좌표
- 테마 매핑과 검색 정책을 합친 단일 기준 파일

### search-service/data/theme_mapping.confirmed_final_v7.json

- 109개 `source_segment_id`의 확정 테마 매핑
- 허용 테마: `night_view`, `drive`, `flower`, `autumn_leaves`, `sea`, `traditional`, `field`, `hiking`, `forest`
- metadata 또는 DB와 `source_segment_id`로 연결

### search-service/data/place_display_catalog.translated.json

- 74개 `place_id`의 한국어·영어·일본어·중국어 표시값과 주소
- 기존 주소 누락 8곳을 공식·지자체 자료 또는 동일 장소 정규화 근거로 보완
- 주소 누락 0건

### search-service/data/places_coordinates_517.json

- 74개 `place_id`의 주소·위도·경도
- 범위형 관광지는 `address_basis`에 대표 안내 지점 기준을 기록

## 2. API 입력 기준

현재 배포된 프론트·백엔드 규격에 맞춰 `q`를 자연어 입력 필드로 사용합니다.

```json
{
  "q": "",
  "theme": ["flower"],
  "region": [],
  "city": [],
  "season": [],
  "time_of_day": [],
  "drama_title": [],
  "place_id": [],
  "top_k": 20,
  "candidate_k": 100
}
```

- `null`, 빈 문자열, 빈 배열: 필터 미적용
- 동일 필드 복수 값: OR
- 서로 다른 필드: AND
- `q`가 있는 자연어 요청만 OpenAI QueryParser 호출
- 테마·계절·작품·지역 버튼처럼 조건이 확정된 요청은 OpenAI를 호출하지 않음
- 자연어 파싱 필터와 UI 필터가 겹치면 UI 입력이 우선

평가 JSON 내부의 `query`는 평가 문장 저장용 키이므로 유지할 수 있지만, 실제 `/api/search` 요청 payload를 만들 때는 `q`로 전송합니다.

## 3. 테마 적용 기준

1. `theme_mapping.confirmed_final_v7.json`을 로드하거나 별도 테이블에 적재합니다.
2. metadata/DB와 `source_segment_id` 기준으로 연결합니다.
3. 테마 필터는 Text/Image 후보 검색 전에 적용합니다.
4. 같은 필드의 여러 테마는 OR로 처리합니다.
5. 테마가 없는 데이터는 일반 자연어 검색에서는 유지하고 테마 필터 요청에서만 제외합니다.
6. 검색 응답에 `themes` 배열을 포함합니다.

## 4. 검색 결과 처리 순서

구조화 필터 적용
→ SCENE 단위 Text/Image 후보 검색
→ RRF 결합
→ `source_segment_id`별 최고 SCENE 선택
→ `final_score` 내림차순 정렬
→ 마지막에 `top_k` 적용

## 5. 장소 표시 및 P013/P044 정규화

1. 검색 결과의 `place_id`로 `place_display_catalog.translated.json`을 조회합니다.
2. 요청 언어의 `localized[lang]`을 반환합니다.
3. P013과 P044는 동일한 주문진 방파제로 확인됐으므로 필터 요청 시 두 ID를 OR로 조회합니다.
4. 결과 표시는 P044·주문진 방파제로 통일하되 기존 segment/keyframe ID와 임베딩은 변경하지 않습니다.

## 6. 검증 결과

- metadata 기준: 517 SCENE / 109 source_segment_id
- 테마 매핑: 109/109, 중복 0건
- 장소: 74건, 4개 언어 주소 누락 0건
- 자동화 테스트: 25 passed
- 통합 카탈로그 검증: passed
