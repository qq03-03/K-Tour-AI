# 좌표·표시 언어 증분 자동화

새로운 영상 데이터가 들어왔을 때 전처리를 통과한 segment만 기준으로 좌표와
표시용 번역 입력을 준비한다. 원본 metadata와 keyframe은 읽기만 하며 모든
결과는 별도의 출력 폴더에 생성한다.

## 기본 실행: 외부 API 미호출

```powershell
& 'D:\K-Tour-AI\tools\run_frontend_data_automation.ps1' `
  -Metadata 'D:\path\to\metadata.json' `
  -Accepted 'D:\path\to\preprocessed_segments.json' `
  -ExistingCoordinates 'D:\K-Tour-AI\data\places_coordinates_selected.json' `
  -OutputRoot 'D:\K-Tour-AI\output\frontend_data_v1'
```

기본 실행은 카카오·OpenAI API를 호출하지 않는다. 다음 결과를 만든다.

- `accepted_metadata_flat.json`: 전처리 통과 segment만 포함한 평탄화 metadata
- `places_coordinates_review.csv`: 기존 좌표 재사용 및 신규 조회 대상
- `places_coordinates_kakao_candidates.csv`: 카카오 조회 계획
- `display_translation_source.json`: 표시용 번역 입력
- `frontend_data_prepare_report.json`: 처리 수량과 원본 비변경 기록

출력 파일이 이미 존재하면 중단한다. 의도적으로 새 결과를 만들 때만
`-Overwrite`를 사용한다.

## 실제 좌표 조회

같은 PowerShell에서 `KAKAO_REST_API_KEY`를 설정한 후 `-RunCoordinateApi`를
추가한다. 기존 좌표가 있는 place_id는 재조회하지 않는다.

## 실제 표시용 번역

같은 PowerShell에서 `OPENAI_API_KEY`를 설정한 후 `-RunTranslations`를 추가한다.
원문 해시가 같은 번역은 재사용하고 신규·변경 레코드만 API로 전송한다. 현재
metadata에서 삭제된 checkpoint 레코드는 stale 데이터로 정리한다.

번역 의미와 UI 자연스러움까지 OpenAI로 다시 검사하려면
`-RunTranslationQa`도 추가한다.

## 자동 중단 조건

- `segment_id` 중복
- 한 `place_id`에 서로 다른 `place_name` 연결
- 전처리 통과 segment가 metadata에 없음
- 필수 ID 또는 장소명 누락
- 기존 좌표 파일 사이의 위도·경도 충돌
- 번역용 필수 필드 또는 언어 누락

`제주도`처럼 정확한 좌표를 지정하기 어려운 장소명은 자동 확정하지 않고
`장소명 검토 필요` 상태로 분리한다.
