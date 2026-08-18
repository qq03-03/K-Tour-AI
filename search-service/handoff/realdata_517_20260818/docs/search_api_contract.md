# K-Tour AI 검색 API 입출력 규격 (517 SCENE 기준)

## 고정 원칙

- DB에는 SCENE 단위 데이터를 유지합니다.
- 검색 결과는 `source_segment_id` 단위로 중복 제거합니다.
- `keyframe_id = segment_id`로 사용합니다.
- 좌표는 `place_id`, 표시언어는 `segment_id + keyframe_id + lang`으로 연결합니다.
- P063은 metadata·keyframe·좌표·평가 대상에서 제외합니다.

## 요청

`POST /api/search`

- `query`: 자연어 질문
- `lang`: ko/en/ja/zh
- `place_id`, `drama_title`, `region`, `city`, `season`, `time_of_day`: 선택 배열 필터
- `top_k`: 최종 반환 개수
- `candidate_k`: 후보 수. 생략 시 `max(top_k × 5, 50)`

동일 필드의 여러 값은 OR, 서로 다른 필드는 AND입니다. null·빈 문자열·빈 배열은 미적용합니다. mood·activity·scene_elements·k_culture_elements는 하드 필터가 아니라 query_text의 소프트 힌트로 사용합니다.

## 검색·결합 순서

1. 하드 필터 적용
2. SCENE별 텍스트·이미지 후보와 1-based rank 반환
3. RRF: `final_score = 1/(60 + text_rank) + 1/(60 + image_rank)`
4. 한쪽 rank가 null이면 해당 항은 0
5. 동일 source_segment_id에서 final_score가 가장 높은 SCENE 선택
6. 동점: image_score → text_score → segment_id 오름차순
7. 대표 SCENE final_score 내림차순 정렬 후 top_k 적용

## 최종 응답 필드

rank, source_segment_id, segment_id, keyframe_id, keyframe_path, video_id, place_id, place_name, region, city, latitude, longitude, drama_title, start_time, end_time, season, time_of_day, description, mood, activity, scene_elements, k_culture_elements, text_score, image_score, text_rank, image_rank, final_score
