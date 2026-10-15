# 517 세그먼트 데이터셋 반영 설계

## 목적

팀이 완료한 VLM 처리 결과(45개 세그먼트/11개 드라마 → 517개 세그먼트/42개 드라마)를 정적 프론트엔드 데이터에 반영한다. 기존에 실제 이미지가 붙어 있는 45개 세그먼트는 그대로 유지하고, 새 517개를 추가하는 방식으로 진행한다.

## 배경 및 현재 상태

- 현재 사이트는 `src/data/mockSegments.js`(45개), `src/data/placeCoordinates.js`(19개 장소, `place_id` P001~P030 중 일부 사용), `src/data/segmentTranslations.json`(45개, ko/en/ja/zh)으로 구성되어 있다.
- 팀이 전달한 새 데이터(`K-Tour_AI_Backend_Handoff_517_Yonghwasan_GT_v2_20260818/`)를 조사한 결과:
  - `data/metadata_517_yonghwasan_v2.json`: 517개 SCENE, 74개 장소, 42개 드라마. 필드 구조는 기존 `mockSegments.js`의 raw 세그먼트와 동일(`segment_id`, `video_id`, `place_id`, `place_name`, `season`, `region`, `city`, `drama_title`, `start_time`, `end_time`, `keyframe_path`, `time_of_day`, `mood`, `scene_elements`, `activity`, `description`). 기존에 없던 `source_segment_id`, `city` 필드가 추가됨.
  - `data/places_coordinates_517.json`: 74개 장소 좌표(`place_id`, `place_name`, `region`, `city`, `latitude`, `longitude` 등).
  - `data/display_translations_517_no_P063.json`: 517개 세그먼트 전체의 ko/en/ja/zh 번역. 구조는 기존 `display_translations.json`과 동일(`segment_id`, `keyframe_id`, `translations: { ko, en, ja, zh }`).
  - `video_id`가 `V007_Z7u5SNDq0jw` 형식(접두사_유튜브ID)이며, 517개 레코드에 등장하는 109개 고유 `video_id` 전부가 이 패턴과 일치함을 정규식으로 확인함. 즉 유튜브 ID를 `video_id`에서 직접 추출할 수 있고, 기존 `videoSources.js` 같은 별도 매핑 파일이 필요 없다.
  - **키프레임 이미지 파일(.jpg)은 이번 전달본에 포함되어 있지 않다.** 전달 폴더, 참고용 zip, Git 리포(`origin` = `qq03-03/K-Tour-AI`) 전체 브랜치, 슬랙에 공유된 파일을 모두 확인했지만 517개용 실제 이미지는 어디에도 없었다. 팀 노트에는 "Keyframe: 517건" 생성 및 임베딩 완료라고 되어 있으나, 이미지 원본 파일 자체는 아직 아무에게도 전달되지 않은 상태다. 좌표(`place_id` 기준)와 번역(`segment_id`/`keyframe_id` 기준)만으로 표시가 가능하므로, 이미지는 placeholder로 두고 텍스트/좌표/번역만 우선 반영한다.
  - 검색 백엔드 API 계약(`docs/search_api_contract.md`)은 이번 작업 범위에서 제외한다. 실제 배포된 백엔드 HTTP API가 아직 없고(PostgreSQL+pgvector 컨테이너와 CLI 스크립트만 존재), 프론트는 현재와 동일하게 클라이언트 사이드 키워드 검색(`searchSegments.js`)을 그대로 사용한다.
- 기존 45개와 새 517개를 장소 이름으로 비교한 결과:
  - 기존 45개의 장소 19곳 중 8곳(고창 학원농장, 전주 한옥마을, 포항 구룡포 석병리, 강릉 주문진, 망상해변, 경복궁, 창덕궁, 청계천)이 새 517개에도 등장한다. 이 8곳은 검색 결과에 기존 카드(실제 이미지)와 신규 카드(placeholder)가 함께 노출될 수 있다 — 별도 중복 제거 로직 없이 허용한다.
  - 기존 11개 드라마는 전부 새 42개 드라마에 포함된다(누락 없음).
  - **`place_id` 번호 체계가 서로 다른 장소를 가리킨다.** 예: 기존 `P001` = 화성행궁(37.2827, 127.0141), 새 데이터의 `P001` = 수원 화성(같은 좌표, 다른 레이블). 두 데이터를 그대로 합치면 지도 핀이 잘못된 장소로 표시된다. 새 517 쪽 `place_id`에 네임스페이스를 적용해 충돌을 막는다(아래 참조).
- `src/components/ResultCard.jsx`, `DramaSection.jsx`, `Detail.jsx`는 현재 이미지가 항상 존재한다고 가정하고 `<img>`에 `onError` 처리가 없다. 517개 중 이미지 없는 카드가 깨진 아이콘으로 보이는 것을 막기 위해 처리를 추가해야 한다(로컬 실험 사이트에서 이미 검증한 패턴).

## 범위

**포함:**
- 517개 세그먼트의 텍스트 메타데이터, 장소 좌표, 4개 언어 번역을 정적 데이터로 반영
- `video_id` 기반 유튜브 링크 자동 생성
- 이미지 누락 시 graceful fallback(회색 배경, 깨진 아이콘 숨김)
- 관련 테스트 갱신

**제외(다음 별도 작업으로 진행):**
- 실제 백엔드 검색 API 연결(현재 배포된 API 없음, 클라이언트 사이드 검색 유지)
- 517개 세그먼트의 실제 키프레임 이미지 반영(원본 파일이 아직 팀에서 전달되지 않음 — 전달되면 `mockSegments517.js`/`placeCoordinates517.js`를 건드리지 않고 `public/keyframes/`에 이미지만 추가하면 됨)
- 8곳 중복 장소에 대한 중복 제거/병합 로직

## 아키텍처

### 새 파일 3개 추가

**`src/data/mockSegments517.js`**
`metadata_517_yonghwasan_v2.json`의 517개 레코드를 그대로 옮긴 raw 세그먼트 배열. `place_id`에만 접두사(`N-` + 원본 값, 예: `P031` → `N-P031`)를 적용한다. 나머지 필드(`season`이 한국어, `time_of_day`가 영어인 것 포함)는 기존 `mockSegments.js`의 raw 데이터와 동일한 형태이므로 변환 없이 그대로 사용한다.

**`src/data/placeCoordinates517.js`**
`places_coordinates_517.json`에서 `place_name`/`latitude`/`longitude`만 추출하고, 키(`place_id`)에 `mockSegments517.js`와 동일한 네임스페이스(`N-` 접두사)를 적용한다. `address`/`status`/`notes` 등 기존 `placeCoordinates.js`에 없는 필드는 가져오지 않는다.

**`src/data/segmentTranslations517.json`** (생성 스크립트: `scripts/generate-segment-translations-517.mjs`)
`display_translations_517_no_P063.json`을 기존 `segmentTranslations.json`과 동일한 키 포맷으로 변환한다. 기존 파일의 키가 `${segment_id}__${keyframe_id}` 형태(현재 데이터에서는 `segment_id === keyframe_id`라 사실상 같은 문자열이 두 번 붙는 형태, 예: `WLGYT_01_SCENE_01__WLGYT_01_SCENE_01`)로 되어 있음을 확인했다. `src/lib/localizeSegment.js`는 이 키 포맷으로 조회하므로, 새 파일도 반드시 같은 규칙(`${record.segment_id}__${record.keyframe_id}`)으로 키를 만든다. `place_id`는 번역 데이터의 키에 포함되지 않으므로 네임스페이스 적용이 필요 없다.

### 기존 파일 최소 수정

**`src/data/mockSegments.js`**
파일 끝의 `export const mockSegments = rawSegments.map(...)` 앞에서 `mockSegments517`의 raw 배열을 import해 `rawSegments`와 concat한다. 기존 1500줄짜리 `rawSegments` 배열 리터럴은 건드리지 않는다.

**`src/data/placeCoordinates.js`**
`placeCoordinates517`를 spread로 병합해 export한다.

**`src/lib/localizeSegment.js`**
기본 인자로 쓰이는 `segmentTranslations` import 지점에서 `segmentTranslations517`을 함께 import해 병합한 객체를 기본값으로 사용하도록 수정한다(함수 시그니처와 조회 로직 자체는 변경하지 않음).

### 영상 링크

517개는 `videoSources.js`에 항목을 추가하지 않는다. 대신 `video_id`(예: `V007_Z7u5SNDq0jw`)에서 정규식(`^V\d+_(.+)$`)으로 유튜브 ID를 추출해 `https://www.youtube.com/watch?v={id}` 링크를 만드는 헬퍼 함수를 추가하고, `Detail.jsx`에서 `videoSources[segment.video_id]`가 없을 때 이 헬퍼로 폴백한다. `source_type`(쇼츠/영상 구분) 필드는 현재 UI 어디에서도 사용되지 않는 것을 확인했으므로 517개용 데이터를 별도로 만들지 않는다.

## 이미지 누락 처리

`ResultCard.jsx`, `DramaSection.jsx`, `Detail.jsx`의 `<img>` 태그에 `onError` 핸들러를 추가해 이미지 로드 실패 시 `visibility: hidden` 처리하고, 컨테이너에 회색(`#e2e8f0`) 배경을 지정한다. 로컬 실험 사이트에서 이미 검증한 패턴을 그대로 적용한다.

## 테스트 계획

- `mockSegments.test.js`의 전체 개수 검증을 45 → 562(45+517)로 갱신
- `segmentTranslations.test.js`의 "모든 세그먼트에 번역 레코드가 있어야 한다" 검증은 517개 모두 번역이 있으므로 예외 처리 없이 통과해야 함
- `place_id` 네임스페이스 충돌이 없는지 확인하는 테스트 추가(기존 30개 + 신규 74개 = 104개 키, 중복 없음을 검증)
- 이미지 `onError` 폴백에 대한 컴포넌트 테스트 추가
- 전체 회귀 테스트(`npm test`) 통과 확인
- 브라우저로 직접 확인: 검색, 테마 필터, 상세 페이지, 지도 핀(특히 겹치는 8개 장소와 네임스페이스 적용된 장소들이 올바른 위치에 찍히는지)
