# K-Tour AI 검색 담당 신규 데이터 자동화

새 VLM/임베딩 결과를 생성하는 도구가 아닙니다. 새 metadata가 전달될 때
검색 담당자가 반복하던 작품명 보호, 필터 카탈로그, 테마 연결, 평가 정답
검사를 한 번에 준비합니다.

## 자동으로 처리하는 범위

- 새 metadata와 기존 기준본의 SCENE/source/place/title 차이 계산
- SCENE 전부가 바뀐 경우에도 source ID의 video/place 재사용 여부 차단
- 변경 필드에 따라 text/image 임베딩·stale 삭제·테마 재검수 영향 분류
- metadata와 표시언어에서 작품명 카탈로그 생성
- metadata와 표시언어에서 장소 별칭 카탈로그 생성
- 같은 장소·작품의 다국어 표기가 SCENE마다 달라진 경우 검수 목록 생성
- 실제 데이터에 존재하는 하드 필터값과 지역권 규칙 생성
- 기존 확정 테마는 유지하고 신규·변경·미분류 source만 검수 대기로 분리
- `approved_empty`/`excluded`와 근거 hash를 다음 실행에서 이어받아 반복 검수 방지
- 빈 테마 매핑은 승인으로 간주하지 않고 반드시 검수 대기로 분리
- 표시언어의 누락·빈 문장·빈 배열 원소와 SCENE별 엔터티 표기 충돌 검사
- 기존 평가 질문의 정답 source/SCENE/keyframe/place 소속관계와 필터 모순 검사
- 전달받은 text/image embedding의 ID·개수·차원·경로·유한값 정합성 확인
- place_id 기준 좌표 누락·stale·불일치·근접 중복 후보 확인
- place_id 기준 다국어 장소 표시 카탈로그 생성 및 주소 번역 대기열 분리
- 주소 번역이 없으면 한국어 도로명 주소로 fallback하고 지역·도시·장소명은 기존 표시언어 사용
- 한국 관광 데이터 범위를 벗어난 비정상 좌표 차단
- 모든 작품명·지역권·계절·시간 표현에 대한 규칙 회귀 사례 자동 생성
- 백엔드 URL이 준비된 뒤 40문항 Hit@K·Recall@K·MRR·nDCG와 응답 계약 검사

## 자동 확정하지 않는 범위

- VLM metadata 또는 embedding 수정·재생성
- 번역명이 충돌할 때 임의로 하나 선택
- 신규 테마의 최종 확정
- 평가 질문의 정답 자동 변경
- DB 적재·삭제
- Git commit/push

같은 번역 별칭이 서로 다른 작품이나 장소를 가리키면 해당 별칭은 활성
카탈로그에서 제외되고 `search_review_queue.json`에 기록됩니다.

## 권장 실행 방식

여러 전달본 중 최신 파일을 수정시간으로 추측하지 않습니다. 사용할 파일을
manifest에 명시합니다. `example_manifest.json`을 복사해 새 전달본 경로만
변경합니다.

테마가 없는 것이 맞다고 검수한 source는
`theme_decision_registry.generated.json`의 상태를 `approved_empty` 또는
`excluded`로 확정해 별도 버전 파일로 보관하고, 다음 manifest의
`theme_decisions`에 그 경로를 지정합니다. 근거 metadata hash가 같을 때만 해당
결정을 재사용하며 내용이 바뀌면 다시 검수 대기로 보냅니다.

```powershell
& 'D:\K-Tour-AI\.venv\Scripts\python.exe' `
  'C:\Users\human\Documents\K-Tour-AI\search_automation\run_search_sync.py' `
  --manifest 'C:\Users\human\Documents\K-Tour-AI\search_automation\example_manifest.json' `
  --overwrite
```

외부 API를 호출하지 않으며 원본 metadata·embedding·DB를 수정하지 않습니다.

## 생성 파일

- `search_sync_report.json`: 전체 요약과 신규·변경·삭제 검색 영향
- `change_impact.json`: 재생성·재연결·stale 삭제가 필요한 ID 후보
- `drama_title_catalog.generated.json`: 새 작품명을 포함한 런타임 후보 카탈로그
- `location_alias_catalog.generated.json`: 새 장소를 포함한 런타임 후보 카탈로그
- `filter_catalog.generated.json`: 실제 필터값·정규화·지역권 정책
- `theme_mapping.carried_forward.json`: 현재 metadata에 존재하는 기존 확정 테마
- `theme_decision_registry.generated.json`: 모든 source의 확정/검수 상태
- `theme_review_queue.json`: 신규·변경·미분류 source의 테마 검수 후보
- `evaluation_compatibility.json`: 평가 정답 ID 연결 검사
- `embedding_alignment.json`: metadata와 text/image embedding 1:1 검사
- `coordinate_alignment.json`: metadata 74개 장소와 좌표 연결 검사
- `place_display_catalog.generated.json`: place_id별 표시언어·주소 fallback 카탈로그
- `address_translation_review_queue.json`: 영·일·중 주소 번역 또는 한국어 주소 보완 대상
- `search_rule_regression_cases.generated.json`: 작품명 보호·필터 규칙 회귀 사례
- `search_review_queue.json`: 사람이 확인해야 하는 항목만 모은 파일
- `SUMMARY.md`: 사람이 빠르게 읽는 요약

`blocking_error_count`가 0이고 카탈로그 충돌 검수가 끝나야 생성 카탈로그를
검색 서비스에 반영할 수 있습니다. `safe_to_publish_generated_catalogs`가
`true`인지 확인한 뒤 아래 두 파일을 각각 검색 서비스의 기존 카탈로그와
교체하고 서버를 재시작해야 캐시가 갱신됩니다.

```text
drama_title_catalog.generated.json -> search-service/data/drama_title_catalog.json
location_alias_catalog.generated.json -> search-service/data/location_alias_catalog.json
```

자동화 도구는 이 교체 작업을 직접 수행하지 않습니다.

## 백엔드 API 회귀 평가

백엔드가 외부에서 접근 가능한 URL을 전달한 후 실행합니다. 이 명령은 평가
질문을 실제 백엔드로 전송하며, 백엔드가 OpenAI QueryParser를 사용하면 해당
API 비용이 발생할 수 있으므로 실행 전에 승인이 필요합니다.

검색 요청의 자연어 필드명은 현재 프론트·백엔드 스키마에 맞춰 `query`를 사용합니다. `query`가 비어 있고 theme/region/
season 같은 명시 필터만 있으면 백엔드는 OpenAI를 호출하지 않아야 합니다.

```powershell
& 'D:\K-Tour-AI\.venv\Scripts\python.exe' `
  'C:\Users\human\Documents\K-Tour-AI\search_automation\run_backend_regression.py' `
  --base-url 'https://BACKEND-URL' `
  --evaluation 'C:\path\to\multilingual_theme_evaluation_40.json' `
  --contract-cases 'C:\Users\human\Documents\K-Tour-AI\search_automation\config\backend_contract_cases.json' `
  --baseline 'C:\path\to\previous_backend_regression.json' `
  --output 'C:\Users\human\Documents\K-Tour-AI\search_automation\output\backend_regression.json'
```

인증이 필요하면 키를 파일에 쓰지 않고 환경변수로 전달합니다.

```powershell
$env:KTOUR_API_TOKEN = Read-Host 'Backend API token'
```

## 주소 표시언어 생성

한국어 주소가 있는 place만 OpenAI Responses API로 영·일·중 번역합니다.
`place_id`와 주소 숫자를 검증하고, 같은 한국어 주소를 공유하는 place는 같은
번역으로 통일합니다. 원본 좌표 파일은 수정하지 않습니다.

결과는 `place_display_catalog.translated.json`, 호출·검증 결과는
`address_translation_generation_report.json`, 한국어 원주소가 없는 장소는
`address_translation_review_queue.after_translation.json`에 저장합니다.

## 현재 search-service 로컬 규칙 회귀

OpenAI·DB 없이 실제 검색 코드가 생성된 1,044개 작품명·장소·지역·필터
표현을 처리하는지 검사합니다. 현재 구성은 작품명 216, 장소 별칭 577, 지역
별칭 202, 지역권 6, 계절·시간대 43개 사례입니다. 대상 코드는 읽기만 하고
생성 카탈로그 경로를 실행 중에만 연결합니다.

```powershell
& 'D:\K-Tour-AI\.venv\Scripts\python.exe' `
  'C:\Users\human\Documents\K-Tour-AI\search_automation\run_local_rule_regression.py' `
  --search-service-root 'D:\K-Tour-AI\search-service' `
  --output 'C:\Users\human\Documents\K-Tour-AI\search_automation\output\local_rule_regression.json'
```

## 테스트

```powershell
Set-Location 'C:\Users\human\Documents\K-Tour-AI\search_automation'
& 'D:\K-Tour-AI\.venv\Scripts\python.exe' -m pytest -q tests `
  --basetemp "$env:TEMP\ktour-search-automation-tests"
```

현재 자동화 자체 단위 테스트는 `24 passed`입니다.
