# K-Tour 검색 API 입출력 계약 v2

이 문서는 검색 파트(⑤)가 백엔드 파트(⑥)에 전달할 최소 계약이다. v2는
하나의 원본 영상 구간에 여러 장면(`SCENE`)과 keyframe이 연결되는 2차 데이터
구조를 지원한다. 좌표와 최종 `place_id`가 바뀌어도 검색 요청 형식은 유지한다.

## 요청

`POST /api/v1/search`

```json
{
  "query": "강원도의 평화로운 겨울 숲길을 걷는 장면",
  "lang": "ko",
  "region": "강원",
  "season": "겨울",
  "time_of_day": "낮",
  "mood": ["평화로운"],
  "top_k": 5
}
```

- `query`: 필수 자연어 질문
- `lang`: `auto`, `ko`, `en`, `ja`, `zh`; 기본값 `auto`
- `region`, `season`, `time_of_day`: 선택 하드 필터
- `mood`: 선택 소프트 힌트 배열
- `top_k`: 1~50, 기본값 5

자연어에서 OpenAI QueryParser가 추출한 조건과 사용자가 UI에서 직접 고른
조건이 충돌하면 UI 조건을 우선한다.

## 응답

검색 결과의 노출 단위는 원본 영상 구간인 `source_segment_id`다. 한 원본 구간에
여러 장면과 keyframe이 있어도 결과는 한 번만 노출한다. 검색 후보 중
`final_score`가 가장 높은 장면을 우선하고, 동점이면 `image_score`가 높은 장면의
keyframe을 대표로 반환한다. `top_k`는 이 중복 제거가 끝난 뒤 적용한다.

ID의 의미는 다음과 같다.

- `source_segment_id`: 같은 원본 영상 구간을 묶는 부모 ID이자 중복 제거 기준
- `segment_id`: 검색 결과를 대표하도록 선택된 실제 장면 ID
- `keyframe_id`, `keyframe_path`: 선택된 장면의 대표 이미지
- `start_time`, `end_time`: 선택된 장면의 실제 재생 시간

질의의 작품명 판별 상태는 응답 최상위에 함께 반환한다.

- `query_status`: `matched`, `not_found`, `ambiguous`, `none`
- `matched_drama_titles`: 프로젝트 카탈로그에서 일치한 한국어 기준 작품명 배열
- `possible_title`: 미등록·불명확 작품명 후보, 없으면 `null`

`not_found`는 사용자가 촬영지 등 작품 검색 의도를 밝혔지만 프로젝트 카탈로그에
제목이 없는 경우다. 이때 무관한 장소를 추천하지 않도록 `results`는 빈 배열로 반환한다.

필수 결과 필드:

- 식별·순위: `rank`, `source_segment_id`, `segment_id`, `video_id`, `place_id`
- 표시: `drama_title`, `place_name`, `region`, `city`, `address`
- 지도: `latitude`, `longitude` — 좌표 미확정 시 둘 다 `null`
- 재생: `start_time`, `end_time`
- 내용: `description`, `mood`, `activity`, `scene_elements`
- 대표 이미지: `keyframe_id`, `keyframe_path`
- 설명 가능한 점수: `text_score`, `image_score`, `final_score`

`lang`에 해당하는 사전 번역이 있으면 번역값을 반환한다. 번역값이 없으면 한국어
원문으로 대체하고 응답 최상위 `translation_fallback`을 `true`로 설정한다.

## 불변 조건

1. 같은 응답에서 `source_segment_id`는 중복되면 안 된다.
2. 같은 응답에서 대표 장면인 `segment_id`도 중복되면 안 된다.
3. `rank`는 1부터 결과 순서대로 증가한다.
4. `end_time`은 `start_time`보다 커야 한다.
5. `latitude`와 `longitude`는 둘 다 있거나 둘 다 `null`이어야 한다.
6. `text_score`, `image_score`, `final_score`를 모두 제공해 검색 결과를 설명할 수 있어야 한다.
7. 좌표는 `place_id` 기준으로 연결하고 keyframe마다 복제 저장하지 않는다.
8. `query_status`가 `not_found`이면 `results`는 비어 있어야 한다.

## 응답 예시

```json
{
  "query": "밤에 걷기 좋은 궁궐 촬영지를 보여줘",
  "lang": "ko",
  "query_status": "none",
  "matched_drama_titles": [],
  "possible_title": null,
  "fallback_used": false,
  "translation_fallback": false,
  "results": [
    {
      "rank": 1,
      "source_segment_id": "V001_P032_S001",
      "segment_id": "V001_P032_S001_SCENE_003",
      "video_id": "V001_VIDEO_01",
      "place_id": "P032",
      "drama_title": "선재 업고 튀어",
      "place_name": "화홍문",
      "region": "경기도",
      "city": "수원시",
      "address": null,
      "latitude": null,
      "longitude": null,
      "start_time": 15.2,
      "end_time": 20.8,
      "description": "밤에 조명이 켜진 화홍문 주변을 걷는 장면",
      "mood": ["낭만적인"],
      "activity": ["산책"],
      "scene_elements": ["성곽", "야경"],
      "keyframe_id": "V001_P032_S001_SCENE_003",
      "keyframe_path": "keyframes/V001_VIDEO_01/V001_P032_S001_SCENE_003.jpg",
      "text_score": 0.82,
      "image_score": 0.91,
      "final_score": 0.87,
      "content_language": "ko"
    }
  ]
}
```

## 오류 응답 권장

- `400`: 빈 질문, 잘못된 필터, 잘못된 `top_k`
- `422`: 요청 JSON 형식 오류
- `503`: 임베딩 DB 또는 검색 서비스 연결 실패
- `504`: OpenAI 분석 또는 벡터 검색 시간 초과

QueryParser가 실패해도 가능한 경우 `503`을 반환하지 않고 원문·필터 없는 검색으로
fallback한 뒤 `fallback_used: true`와 원인을 응답에 포함한다.
