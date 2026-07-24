# K-Tour AI 검색 서비스

K-콘텐츠 촬영지 영상의 구간별 메타데이터를 이용해 자연어 질문과 관련된 영상 구간을 찾는 검색 파트입니다.

현재 저장소에는 다음 기능이 포함되어 있습니다.

- 자연어 검색어 구조화와 안전한 필터 변환
- 지역·계절·시간대·감성·활동·장면 요소 필터
- 텍스트 구간 검색 기준선
- 텍스트·이미지 검색 결과의 RRF 및 정규화 점수 결합
- 한국어·영어·일본어·중국어 QueryParser 평가
- Hit@K, Recall@K, MRR, nDCG@K 평가
- 실제 구간 JSON과 VLM 메타데이터 검증

> 현재 검색 점수는 더미 임베더와 테스트용 메타데이터를 사용한 결과입니다. 실제 모델 성능으로 해석하면 안 됩니다.

## 실행 환경

- 권장 Python: 3.11 이상
- 실제 검증 환경: Python 3.12.10
- 필수 Python 패키지: `numpy`, `pytest`
- Ollama와 로컬 LLM은 선택 기능이며 기본 테스트에는 필요하지 않습니다.

Windows PowerShell 기준 설치 방법입니다.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 전체 테스트

```powershell
python -m pytest -p no:cacheprovider -q
```

`-p no:cacheprovider`는 pytest 캐시 폴더를 만들지 않도록 하는 옵션입니다.

## 검색 실행

기본 더미 데이터 검색:

```powershell
python run_search.py --query "서울 봄 궁궐" --top-k 3
```

최신 남이섬 10개 테스트 데이터 검색:

```powershell
python run_search.py --data data/nami_segments_10.json --query "여름 남이섬 숲 산책" --top-k 3
```

검색 결과에는 `segment_id`, `video_id`, 시작·종료 시간, 장소, 설명, 대표 프레임 경로가 포함됩니다.

## 검색 품질 평가

더미 질문으로 Hit@5, Recall@5, MRR, nDCG@5를 계산합니다.

```powershell
python run_evaluation.py --k 5
```

실패 사례와 원인을 분석합니다. 기본 실행 시 `reports/failure_cases.json`이 생성 또는 갱신됩니다.

```powershell
python run_failure_analysis.py --k 5
```

## QueryParser 평가

설치가 필요 없는 규칙 기반 기준선:

```powershell
python run_query_parser_evaluation.py --parser rule
```

Ollama가 별도로 설치되어 있고 모델이 준비된 경우에만 로컬 LLM 평가를 실행합니다.

```powershell
python run_query_parser_evaluation.py --parser ollama --model qwen3:4b-instruct --timeout 120
```

Ollama와 모델은 `requirements.txt`로 설치되지 않습니다. 사용할 모델은 GPU 환경과 정확도·속도 비교 후 결정합니다.

## 실제 데이터 검증

통합 구간 JSON은 다음과 같이 Python에서 검증할 수 있습니다.

```powershell
python -c "from src.data_loader import load_segments; print(len(load_segments('data/nami_segments_10.json', require_contiguous=True)))"
```

VLM 결과가 도착하면 전처리 결과와 함께 검증합니다.

```powershell
python run_vlm_validation.py --metadata path/to/vlm_metadata.json --preprocessing path/to/preprocessing_results.json
```

## 주요 테스트 데이터

- `data/dummy_segments.json`: 검색 로직 확인용 더미 구간
- `data/nami_segments.json`: 기존 남이섬 겨울 구간 초안
- `data/nami_segments_10.json`: 최신 남이섬 10개 전처리 결과 기반 테스트 자료
- `data/eval_queries.json`: 검색 순위 평가 질문과 정답
- `data/query_parser_eval.json`: 4개 언어 QueryParser 평가 질문

실제 VLM 메타데이터와 텍스트·이미지 임베딩 점수가 전달되면 더미 자료와 분리해 평가해야 합니다.
