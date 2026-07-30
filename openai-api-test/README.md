# OpenAI API 격리 테스트

기존 검색 서비스와 분리하여 OpenAI API 연결과 구조화 출력을 확인하는
테스트 환경입니다. 실제 프로젝트의 평가 질문, 메타데이터, DB 데이터는
읽거나 외부 API로 전송하지 않습니다.

## 전송되는 내용

`run_synthetic_api_test.py` 안에 고정된 다음 두 합성 문장만 전송합니다.

1. `Reply with exactly: OK`
2. `Fictional test only: A traveler wants a calm spring morning walk through a flower garden in Example City.`

외부 파일이나 사용자가 입력한 검색 문장을 API 요청으로 받는 기능은
의도적으로 제공하지 않습니다.

## PowerShell 실행

```powershell
Set-Location D:\K-Tour-AI\openai-api-test
.\run_api_test.ps1
```

`OPENAI_API_KEY` 환경변수가 없으면 키를 가려진 입력창으로 요청하며,
실행 후 해당 프로세스에서 키를 제거합니다.

단계별 실행:

```powershell
.\run_api_test.ps1 -Stage ping
.\run_api_test.ps1 -Stage structured
.\run_api_test.ps1 -Stage all
```

결과는 `output\synthetic_api_test.json`에 저장됩니다.

## 합성 질문으로 실제 로컬 검색 평가

12개 합성 질문 중 질문 문자열만 OpenAI API로 보내 구조화합니다.
정답 세그먼트 ID, 메타데이터, 임베딩, DB 행과 검색 결과는 로컬에서만
사용합니다.

먼저 1문항만 확인:

```powershell
.\run_search_test.ps1 -Limit 1
```

전체 12문항 평가:

```powershell
.\run_search_test.ps1 -Limit 12 -TopK 5
```

결과는 `output\synthetic_search_evaluation.json`에 저장됩니다.

메타데이터 재정렬은 기본적으로 꺼져 있습니다. 정합성 검사를 통과한
데이터셋에서만 다음과 같이 명시적으로 켭니다.

```powershell
.\run_search_test.ps1 -Limit 12 -EnableMetadataRerank
```

## 통합 JSON과 DB 메타데이터 정합성 검사

외부 API를 사용하지 않고 `nami_segments_10.json`의 활동·장면·감성 태그와
PostgreSQL에 적재된 검색 메타데이터를 비교합니다.

```powershell
D:\K-Tour-AI\.venv\Scripts\python.exe .\run_metadata_alignment_check.py
```

결과는 `output\metadata_alignment_report.json`에 저장됩니다.

## 저장된 OpenAI 분석 결과 재현 평가

최초 API 평가에 저장된 `search_text`, `filters`, `soft_hints`를 재사용하여
OpenAI를 다시 호출하지 않고 검색 순위 코드만 동일한 조건에서 비교합니다.

```powershell
D:\K-Tour-AI\.venv\Scripts\python.exe .\run_replay_evaluation.py
```

결과는 `output\synthetic_search_evaluation_replay.json`에 저장됩니다.

## 외부 API 없는 단위 테스트

```powershell
D:\K-Tour-AI\.venv\Scripts\python.exe -m pytest -q
```
