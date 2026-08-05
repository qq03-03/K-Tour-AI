# 검색 결과 표시용 다국어 계약

## 목적

검색 순위와 임베딩은 변경하지 않고, 검색이 끝난 결과 카드의 표시 필드만 요청 언어로 바꾼다.

- 지원 언어: `ko`, `en`, `ja`, `zh`
- 연결 키: `segment_id + keyframe_id`
- `keyframe_id` 형식: 임베딩 DB와 동일한 `segment_id__keyframe_path 파일명`
- 번역 누락 fallback: 요청 언어 → 한국어 → 검색 원문
- 기존 text/image embedding 재생성 불필요

## 전달 파일

- `search-service/data/display_translations.json`: 백엔드 실사용 번역
- `search-service/src/display_localization.py`: 번역 적용 함수
- `search-service/run_validate_display_translations.py`: 최종 metadata 연결 검증
- `search-service/data/display_translation_overrides.json`: 사람 검수 교정 이력

`display_translation_source.json`과 `display_translations.checkpoint.json`은 번역 재생성용이며 백엔드 런타임에는 필요하지 않다.

## 백엔드 적용 순서

```python
import json
from pathlib import Path

from src.display_localization import localize_search_results

catalog = json.loads(
    Path("data/display_translations.json").read_text(encoding="utf-8")
)

# 기존 벡터 검색이 끝난 뒤 한 번 적용한다.
localized_results = localize_search_results(
    search_results,
    lang=request.lang,
    catalog=catalog,
)
```

`lang=ja`인 경우 `drama_title`, `place_name`, `region`, `season`, `time_of_day`, `description`, `mood`, `activity`, `scene_elements`가 일본어로 교체된다.

다음 검색 필드는 그대로 유지된다.

- `rank`
- `segment_id`, `video_id`, `place_id`, `keyframe_id`
- `start_time`, `end_time`, `keyframe_path`
- `text_score`, `image_score`, `final_score`

각 결과에는 실제 적용 상태 확인용으로 다음 값이 추가된다.

- `requested_lang`: 요청 언어
- `display_lang`: 실제 적용 언어 또는 `source`

## 최종 metadata 연결 검증

```powershell
python run_validate_display_translations.py `
  --metadata "path/to/final_metadata.json" `
  --translations "data/display_translations.json"
```

통과 조건:

- metadata와 번역 레코드가 1:1 연결
- ID 누락·중복·stale 데이터 없음
- 45개 레코드에 4개 언어가 모두 존재
- 설명·태그·명칭 필드가 빈 값 없이 존재

## 책임 범위

- 검색 파트: 번역 JSON, ID 연결, fallback, 품질 검증
- 백엔드: 요청 `lang` 전달 및 `localize_search_results()` 호출
- 프론트엔드: 백엔드가 반환한 현지화 결과 표시
