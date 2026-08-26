# K-Tour AI 검색 담당 자동화 인수인계

기준일: 2026-08-25
담당 범위: 검색 로직·다국어·품질 평가

## 목적

새 metadata가 추가될 때 사람이 500여 건을 다시 훑지 않고, 검색에 영향을 주는
변경과 검수 대상을 자동으로 분리합니다. VLM·임베딩을 생성하거나 원본·DB를
수정하는 도구가 아닙니다.

## 자동 처리 순서

```text
입력 manifest와 SHA-256 확정
→ metadata 최종 스키마·ID 검사
→ 이전 기준본과 신규/변경/삭제 비교
→ source ID의 video/place 재사용 및 한국 밖 비정상 좌표 차단
→ 작품명·장소·필터 카탈로그 생성
→ 표시언어 엔터티 표기 충돌 분리
→ 기존 테마 유지, 신규·변경·미분류 source만 검수 대기
→ 빈 테마·빈 번역문 승인 우회 차단
→ 평가 정답 ID 소속관계와 expected_filters 모순 검사
→ text/image embedding 정합성 검사
→ 좌표 place_id 연결 검사
→ 변경 영향 및 사람 검수 목록 출력
```

백엔드 URL을 받은 뒤에는 별도 실행으로 다음을 검사합니다.

```text
40문항 Hit/Recall/MRR/nDCG
+ 명시 필터 우선
+ 같은 필드 OR / 다른 필드 AND
+ 0건 필터 완화 금지
+ 꽃 테마 버튼
+ 경상도/부산/제주·서귀포 지역 처리
+ 겨울연가 작품명 보호
+ source_segment_id 중복 제거
+ 1-based rank/null/RRF/응답 필드
+ 이전 보고서 대비 신규 실패와 순위 하락
```

## 자동 확정하지 않는 항목

- 번역 별칭 충돌 시 어느 표기가 맞는지
- 테마 최종 판정
- 평가 정답 변경
- 같은 좌표를 가진 장소 병합
- keyframe 경로 변경 시 이미지 내용까지 같은지
- stale DB 행 삭제
- Git commit/push

이 항목들은 검수 목록만 만들고 사람이 결정합니다.

## 현재 517건 실행 결과

- SCENE 517 / source 109 / 장소 74 / 작품 42
- metadata 차단 오류 0
- 평가 질문 40개 정답 ID 연결 완료
- text embedding 517 / image embedding 517, 512차원, ID 1:1
- embedding 차단 오류 0
- 이미지 embedding JSON의 복사 metadata에서 7건 경고
  - P011·P026: `제주시`가 남아 있으나 최신 metadata는 `서귀포시`
  - V040 용화산: image JSON에 `theme_category` 복사 필드가 없음
  - 이미지 벡터 재생성 사유는 아니며 DB는 최신 metadata 기준인지 확인 필요
- 좌표 74/74 연결, 차단 오류 0
- 좌표 검수 후보
  - P013/P044: 동일 좌표
  - P069/P070: 약 30.6m
- 기존 작품명 카탈로그 13개에서 최종 42개 후보 생성
- 기존 장소 카탈로그 30개에서 최종 74개 후보 생성
- 작품 별칭 충돌
  - `Autumn in My Heart`: 가을동화/가을로 충돌, 자동 제외
- 주문진 관련 P013/P044 장소 별칭 3개 그룹 충돌, 검수 대기
- 표시언어 엔터티 표기 변형 80그룹 검수 대기
- 테마 매핑 v6에서 101개 source의 테마를 확정했고 최종 보류는 0건
- 작품명·장소·지역·필터 규칙 자동 회귀 사례 1,044개 생성
- 현재 실제 search-service 로컬 규칙 실행: 1,036 통과 / 8 실패
  - 실패: 오전, 오후, day, morning, 저녁, evening, 야간, 야경
  - 수정 제안: `TIME_OF_DAY_FIX_PROPOSAL.md`
- 자동화 자체 단위 테스트: 24 통과

현재 기준본과 신규본을 같은 파일로 지정했으므로 변경 영향 목록은 0건입니다.
다음 전달본부터 manifest의 `metadata`만 새 파일로, `baseline_metadata`는 현재
확정본으로 지정하면 실제 증분 작업이 계산됩니다.

## 실행

```powershell
Set-Location 'C:\Users\human\Documents\K-Tour-AI\search_automation'
& 'D:\K-Tour-AI\.venv\Scripts\python.exe' run_search_sync.py `
  --manifest example_manifest.json `
  --overwrite `
  --strict
```

외부 API 호출은 없으며 원본 metadata·embedding·DB를 수정하지 않습니다.

백엔드 회귀 평가는 URL을 받은 뒤, OpenAI 호출 및 비용 승인을 다시 받은 후에만
실행합니다.

```powershell
& 'D:\K-Tour-AI\.venv\Scripts\python.exe' run_backend_regression.py `
  --base-url 'https://BACKEND-URL' `
  --evaluation '..\outputs\K-Tour_AI_Backend_Handoff_517_Final_v4_Region_20260820\data\multilingual_theme_evaluation_40.json' `
  --contract-cases 'config\backend_contract_cases.json' `
  --strict `
  --output 'output\backend_regression.json'
```

백엔드가 OpenAI QueryParser를 호출한다면 이 실행은 OpenAI API 비용이 발생할 수
있습니다.
