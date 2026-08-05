# 실데이터 검색 평가 실행 절차

이 문서는 최종 임베딩과 PostgreSQL DB가 공유된 직후 실행할 순서를 정리한다.

## 1. PowerShell과 가상환경

VS Code에서 `D:\K-Tour-AI` 폴더를 연 뒤 `터미널 > 새 터미널`을 선택한다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& 'D:\K-Tour-AI\.venv\Scripts\Activate.ps1'
$env:PYTHONIOENCODING = 'utf-8'
$env:HF_HOME = 'D:\K-Tour-AI\.cache\huggingface'
$env:TORCH_HOME = 'D:\K-Tour-AI\.cache\torch'
```

## 2. DB 없이 평가 체인 확인

아래 결과는 합성 정답을 이용하므로 검색 정확도로 해석하지 않는다.

```powershell
& 'D:\K-Tour-AI\.venv\Scripts\python.exe' `
  'D:\K-Tour-AI\search-service\run_production_evaluation_dry_run.py'
```

정상 기준:

- 질문 수 50
- RRF와 normalized 지표 계산 완료
- 실패 보고서 생성 완료
- `execution_mode`가 `dry_run_oracle_not_search_quality`

## 3. PostgreSQL/pgvector 실행

```powershell
Set-Location 'D:\K-Tour-AI\embedding-db'
docker compose up -d
docker compose ps
```

DB 스키마·임베딩 적재는 임베딩 담당자의 최종 PR 안내 명령을 우선 사용한다.

## 4. 실제 DB 사전 점검

```powershell
& 'D:\K-Tour-AI\.venv\Scripts\python.exe' `
  'D:\K-Tour-AI\search-service\run_db_preflight.py' `
  --metadata 'D:\K-Tour-AI\embedding-db\metadata\metadata.json' `
  --output 'D:\K-Tour-AI\search-service\output\db_preflight.json'
```

다음 항목이 모두 `pass`여야 전체 평가를 실행한다.

- 필수 테이블 4개
- segment 45건
- segment text embedding 45건
- keyframe 45건
- keyframe image embedding 45건
- stale·누락·중복 0건
- P030 창경궁 존재
- text/image 벡터 차원이 각 테이블 안에서 일관됨

text embedding과 image embedding의 차원은 서로 달라도 된다. 각각 사용하는 모델 안에서만 일관되면 된다.

## 5. OpenAI API 키 입력

API 키를 코드·JSON·`.env`에 직접 적지 않고 현재 PowerShell 프로세스에만 설정한다.

```powershell
$secureKey = Read-Host 'OpenAI API Key' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
  $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
}
finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
  Remove-Variable keyPointer -ErrorAction SilentlyContinue
  Remove-Variable secureKey -ErrorAction SilentlyContinue
}
```

## 6. 1문항 스모크 테스트

임베딩 담당자의 최종 검색 명령으로 P030 창경궁 또는 주문진 장면 한 건을 먼저 확인한다. 이 단계에서 반환 필드는 다음 계약을 만족해야 한다.

```text
segment_id, keyframe_id, keyframe_path
place_id, region, drama_title
start_time, end_time
description, time_of_day
mood, activity, scene_elements
text_score, image_score
```

같은 `segment_id`가 결과에 두 번 나오면 전체 평가를 시작하지 않는다.

### P030 다국어 QueryParser 4문항 확인

DB 검색 전에 창경궁의 한·영·일·중 질문 분석만 별도로 확인할 수 있다. 이 명령은 OpenAI API 비용이 발생한다.

```powershell
& 'D:\K-Tour-AI\.venv\Scripts\python.exe' `
  'D:\K-Tour-AI\search-service\run_openai_query_parser_evaluation.py' `
  --queries 'D:\K-Tour-AI\search-service\data\p030_query_parser_eval.json' `
  --reasoning-effort none `
  --show-cases `
  --output 'D:\K-Tour-AI\search-service\output\p030_openai_query_parser_evaluation.json'
```

## 7. 실제 50문항 평가

```powershell
& 'D:\K-Tour-AI\.venv\Scripts\python.exe' `
  'D:\K-Tour-AI\search-service\run_multimodal_evaluation.py' `
  --cases 'D:\K-Tour-AI\search-service\data\production_eval_queries_resolved_final.json' `
  --top-k 5 `
  --output 'D:\K-Tour-AI\search-service\output\production_multimodal_evaluation.json'
```

## 8. 실패 사례 분석

```powershell
& 'D:\K-Tour-AI\.venv\Scripts\python.exe' `
  'D:\K-Tour-AI\search-service\run_multimodal_failure_analysis.py' `
  --evaluation 'D:\K-Tour-AI\search-service\output\production_multimodal_evaluation.json' `
  --output 'D:\K-Tour-AI\search-service\output\production_multimodal_failures.json'
```

## 9. 평가 결과 확인 순서

1. `fallback_rate`와 필터 불일치 확인
2. text/image 각 검색 분기의 정답 포함 여부 확인
3. RRF와 normalized의 Hit@5·Recall@5·MRR·nDCG@5 비교
4. 언어별·질문 유형별 점수 비교
5. 대표 keyframe과 정답 앵커 일치 확인
6. 평균·P95 OpenAI 분석시간, 임베딩시간, DB 검색시간 확인

## 10. 종료 후 API 키 제거

```powershell
Remove-Item Env:\OPENAI_API_KEY -ErrorAction SilentlyContinue
```
