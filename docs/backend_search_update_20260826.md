# K-Tour AI 백엔드 검색 보완 전달본

- 전달일: 2026-08-26
- 대상: 테마 하드 필터와 다국어 주소 표시
- metadata·text/image embedding: 변경 없음
- 재임베딩: 필요 없음

## 1. 포함 파일

### data/theme_mapping.confirmed_final_v6.json

- 101개 `source_segment_id`의 확정 테마 매핑
- 허용 테마: `night_view`, `drive`, `flower`, `autumn_leaves`, `sea`, `traditional`, `field`, `hiking`, `forest`
- metadata 또는 DB와 `source_segment_id`로 연결

### data/place_display_catalog.translated.json

- `place_id`별 한국어·영어·일본어·중국어 표시값과 주소
- 백엔드는 요청 언어에 해당하는 `localized[lang]`을 반환
- 해당 언어 주소가 없으면 한국어 주소로 fallback

### data/places_coordinates_517.json / CSV

- `place_id`별 주소·위도·경도
- P072 아침고요수목원 서화연 대표 주소를 공식 관광 주소인 `수목원로 432`로 보완
- P072 좌표는 기존 서화연 카카오 POI 좌표 유지

## 2. API 입력 기준

현재 프론트와 백엔드가 사용 중인 `query`를 자연어 입력 필드로 유지합니다.

권장 입력 필드:

```json
{
  "query": "",
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
- `query`가 있는 자연어 요청만 OpenAI QueryParser 호출
- 테마·계절·작품·지역 버튼처럼 조건이 확정된 요청은 OpenAI를 호출하지 않음
- 자연어 파싱 필터와 UI 필터가 겹치면 UI 입력이 우선

## 3. 테마 적용 기준

1. `theme_mapping.confirmed_final_v6.json`을 로드하거나 별도 테이블에 적재합니다.
2. metadata/DB와 `source_segment_id` 기준으로 연결합니다.
3. 테마 필터는 Text/Image 후보 검색 전에 적용합니다.
4. 여러 테마가 들어오면 하나 이상 일치하는 원본 구간을 선택합니다.
5. 테마가 없는 데이터는 일반 자연어 검색에서는 유지하고, 테마 필터 요청에서만 제외합니다.
6. 검색 응답에 `themes` 배열을 포함합니다.

권장 테이블:

```sql
CREATE TABLE source_segment_themes (
    source_segment_id TEXT NOT NULL,
    theme_id TEXT NOT NULL,
    PRIMARY KEY (source_segment_id, theme_id)
);
```

## 4. 검색 결과 처리 순서

구조화 필터 적용
→ SCENE 단위 Text/Image 후보 검색
→ RRF 결합
→ `source_segment_id`별 최고 SCENE 선택
→ `final_score` 내림차순 정렬
→ 마지막에 `top_k` 적용

현재 백엔드의 RRF 및 중복 제거 순서가 위와 같다면 변경하지 않아도 됩니다.

## 5. 주소·표시언어 적용 기준

주소를 기존 한국어 전용 `placeCoordinates517.js`에 고정하지 말고 다음처럼 연결합니다.

1. 검색 결과의 `place_id` 확인
2. `place_display_catalog.translated.json`에서 같은 `place_id` 조회
3. `localized[lang]`의 `place_name`, `region`, `city`, `address`, `location_label` 반환
4. 주소 번역이 없으면 한국어 주소로 fallback

주소 웹 검증 및 수정 내역은 `docs/address_translation_web_review_20260826.md`를 참고합니다.

## 6. 필수 확인 테스트

- `theme=flower`: V001_P003_S001, V046_P072_S002 포함
- `theme=drive`: V028_P052_S001 포함
- V056_P004_S001: `field`, `flower` 포함, `autumn_leaves` 제외
- 동일 `source_segment_id`: 최종 결과에서 한 번만 반환
- `lang=en`, `ja`, `zh`: 주소도 해당 언어로 반환
- 테마 버튼 요청: OpenAI QueryParser 호출 0회
- 자연어 `query`와 UI 필터 동시 요청: UI 필터 우선

## 7. 검증 현황

- metadata 기준: 517 SCENE / 109 source_segment_id
- 테마 확정: 101 source_segment_id / 495 SCENE
- 테마 보류: 0건
- 매핑 ID 중복: 0건
- 허용되지 않은 theme_id: 0건
- 주소 자동화 테스트: 24 passed
