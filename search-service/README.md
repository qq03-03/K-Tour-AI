# K-Tour AI 검색 서비스

K-콘텐츠 촬영지 영상의 구간별 메타데이터와 대표 프레임 임베딩을 이용해 자연어 질문과 관련된 **영상 구간**을 찾는 검색 파트입니다.

검색 결과는 영상 전체가 아니라 다음 정보를 가진 특정 구간으로 반환합니다.

- `segment_id`, `video_id`
- `start_time`, `end_time`
- 장소, 설명, 태그
- 대표 프레임 경로
- 텍스트·이미지 검색 점수와 최종 순위

## 구현된 기능

- 규칙 기반 및 OpenAI API 기반 자연어 QueryParser
- 한국어·영어·일본어·중국어 검색어 구조화
- 작품명과 계절 표현의 혼동 방지
- 지역·계절·시간대의 확실한 조건만 하드 필터로 적용
- 감성·활동·장면 요소를 검색 후보 제거가 아닌 소프트 힌트로 사용
- CLIP 텍스트 질의 임베딩 생성과 모델 1회 로딩·재사용
- PostgreSQL/pgvector의 텍스트·이미지 임베딩 검색
- 텍스트·이미지 순위의 RRF 결합
- 유사도 분포를 반영한 정규화 점수 결합
- Hit@K, Recall@K, MRR, nDCG@K 및 단계별 응답시간 측정
- 실제 구간 JSON과 VLM 메타데이터의 스키마·ID·시간·경로 검증
- 검색 실패 사례 기록과 원인 분류

## 실행 환경

- 권장 Python: 3.11 이상
- 실제 검증 환경: Python 3.12.10
- 설치 패키지: `requirements.txt` 참고
- 실제 멀티모달 검색: OpenAI API 키, CLIP 모델, PostgreSQL/pgvector DB 필요
- 규칙 기반 검색과 단위 테스트: OpenAI API 없이 실행 가능
- Ollama와 로컬 LLM: 선택 기능이며 별도 설치 필요

Windows PowerShell 기준 설치 방법입니다.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

API 키는 코드나 Git에 저장하지 않고 `OPENAI_API_KEY` 환경변수로 전달합니다. 기본 QueryParser 모델은 `gpt-5.6-luna`이며 `OPENAI_QUERY_MODEL` 환경변수 또는 실행 시 `--model`로 변경할 수 있습니다.

## 전체 테스트

Windows 임시 폴더 권한 문제를 피하려면 D 드라이브 프로젝트 내부의 별도 폴더를 사용합니다.

```powershell
New-Item -ItemType Directory -Force output | Out-Null
python -m pytest -q --basetemp output/pytest
```

2026-07-24 기준 전체 테스트 결과:

```text
159 passed
```

## 기준선 검색

더미 임베더와 로컬 JSON을 이용해 검색 로직만 확인합니다. 아래 결과를 실제 임베딩 모델 성능으로 해석하면 안 됩니다.

```powershell
python run_search.py --query "서울 봄 궁궐" --top-k 3
python run_search.py --data data/nami_segments_10.json --query "여름 남이섬 숲 산책" --top-k 3
```

## 실제 DB 멀티모달 검색

사전 준비 사항:

1. 저장소 루트의 `embedding-db`에서 Docker PostgreSQL/pgvector 실행
2. DB 스키마 적용 및 텍스트·이미지 임베딩 적재
3. `embedding-db/.env`에 PostgreSQL 접속정보 설정
4. `openai/clip-vit-base-patch32` 모델을 로컬 캐시에 준비
5. `OPENAI_API_KEY` 환경변수 설정

RRF 결합 검색:

```powershell
python run_multimodal_search.py "여름 남이섬에서 토끼를 보는 장면" --top-k 5 --method rrf
```

정규화 점수 결합 검색:

```powershell
python run_multimodal_search.py "A peaceful forest path on Nami Island" --top-k 5 --method normalized
```

실행 결과에는 구조화된 검색어·필터, 최종 구간 순위, 텍스트·이미지 원점수, 결합 점수, 단계별 응답시간과 CLIP 로딩 횟수가 포함됩니다.

## 실제 DB 멀티모달 평가

한국어·영어·일본어·중국어 평가 질문을 대상으로 RRF와 정규화 점수 결합을 함께 비교합니다.

```powershell
python run_multimodal_evaluation.py --top-k 5
```

평가 보고서는 기본적으로 `output/multimodal_evaluation.json`에 저장됩니다.

남이섬 10개 구간과 수동 정답 12개 질문으로 실행한 현재 샘플 결과:

| 방식 | Hit@5 | MRR | nDCG@5 |
|---|---:|---:|---:|
| RRF | 1.0000 | 1.0000 | 0.9799 |
| 정규화 점수 결합 | 1.0000 | 1.0000 | 0.9933 |

- API fallback: 0/12
- 평균 전체 응답시간: 약 1.98초
- p95 전체 응답시간: 약 2.90초
- 평균 QueryParser 응답시간: 약 1.87초
- 한 평가 실행에서 CLIP 모델 로딩 횟수: 1회

> 위 수치는 남이섬 10개 구간과 12개 수동 평가 질문으로 측정한 소규모 통합 테스트 결과입니다. 실제 서비스 성능이나 일반화 성능으로 해석하면 안 됩니다.

## 기존 검색 품질 평가

더미 질문으로 Hit@5, Recall@5, MRR, nDCG@5를 계산합니다.

```powershell
python run_evaluation.py --k 5
```

실패 사례와 원인을 `reports/failure_cases.json`에 기록합니다.

```powershell
python run_failure_analysis.py --k 5
```

## QueryParser 평가

API나 모델 설치가 필요 없는 규칙 기반 기준선:

```powershell
python run_query_parser_evaluation.py --parser rule
```

Ollama와 모델이 별도로 준비된 경우의 로컬 LLM 평가:

```powershell
python run_query_parser_evaluation.py --parser ollama --model qwen3:4b-instruct --timeout 120
```

로컬 LLM은 GPU 환경, 정확도, 응답시간을 OpenAI API와 비교한 뒤 선택합니다.

## 실제 데이터 검증

통합 구간 JSON 검증:

```powershell
python -c "from src.data_loader import load_segments; print(len(load_segments('data/nami_segments_10.json', require_contiguous=True)))"
```

VLM 메타데이터와 영상 전처리 결과의 ID·시간·대표 프레임 연결 검증:

```powershell
python run_vlm_validation.py --metadata path/to/vlm_metadata.json --preprocessing path/to/preprocessing_results.json
```

## 주요 데이터

- `data/dummy_segments.json`: 검색 로직 확인용 더미 구간
- `data/nami_segments_10.json`: 남이섬 10개 구간 통합 테스트 자료
- `data/eval_queries.json`: 기준선 검색 순위 평가 질문과 정답
- `data/query_parser_eval.json`: 4개 언어 QueryParser 평가 질문
- `data/nami_multimodal_eval.json`: 실제 DB 멀티모달 검색용 4개 언어 평가 질문과 정답

## 현재 제한사항

- 남이섬 샘플은 데이터 수가 10개 구간으로 작습니다.
- 실제 지역 필드가 없는 남이섬 메타데이터에는 임시 지역 보정이 적용됩니다.
- VLM의 감성·활동·장면 태그 품질에 따라 검색 결과가 달라질 수 있습니다.
- 실제 데이터가 확대되면 RRF와 정규화 결합 가중치를 다시 비교·조정해야 합니다.
