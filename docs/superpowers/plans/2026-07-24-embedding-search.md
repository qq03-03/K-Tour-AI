# Embedding Search Implementation Plan

> 구현 시 각 단계의 테스트를 먼저 실행하고, 통과한 뒤 다음 단계로 진행한다.

**Goal:** CLIP 텍스트 또는 이미지 입력을 512차원 벡터로 변환하고 pgvector에서 유사한 영상 구간 TOP K를 검색한다.

**Architecture:** search_embeddings.py 하나에서 명령행 입력 검증, CLIP 임베딩 생성, PostgreSQL 벡터 검색, 결과 출력을 처리한다. 검색 로직의 핵심 함수는 별도로 분리해 테스트할 수 있게 구성한다.

**Tech Stack:** Python, PyTorch, Transformers CLIP, Pillow, NumPy, psycopg 3, pgvector, python-dotenv, pytest

## Global Constraints

- 모델은 openai/clip-vit-base-patch32를 사용한다.
- 텍스트와 이미지 임베딩 차원은 모두 512이다.
- --text와 --image는 둘 중 하나만 입력한다.
- --top-k 기본값은 5이며 1 이상의 정수만 허용한다.
- 텍스트 검색은 text_embedding을 사용한다.
- 이미지 검색은 image_embedding을 사용한다.
- 코사인 유사도는 1 - cosine distance로 계산한다.

---

### Task 1: 검색 유틸리티 테스트 작성

**Files:**
- Create: embedding-db/tests/test_search_embeddings.py
- Create: embedding-db/scripts/search_embeddings.py

**검증 대상:**
- top-k가 1보다 작으면 오류
- 512차원이 아닌 벡터면 오류
- 코사인 거리에서 유사도 변환
- 텍스트와 이미지 옵션의 상호 배타성

**실행 명령:**

python -m pytest embedding-db/tests/test_search_embeddings.py -v

**기대 결과:**

구현 전에는 테스트 실패, 최소 구현 후에는 모든 테스트 통과

---

### Task 2: 명령행 입력 및 환경변수 처리

**Files:**
- Modify: embedding-db/scripts/search_embeddings.py

**구현 인터페이스:**
- parse_arguments() -> argparse.Namespace
- validate_top_k(top_k: int) -> int
- build_connection_string() -> str

**동작:**
- --text와 --image 중 하나만 필수
- --top-k 기본값 5
- .env는 embedding-db/.env에서 로드
- POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB 확인

**검증 명령:**

python embedding-db/scripts/search_embeddings.py --help

**기대 결과:**

--text, --image, --top-k 사용법 표시

---

### Task 3: CLIP 검색 벡터 생성

**Files:**
- Modify: embedding-db/scripts/search_embeddings.py
- Modify: embedding-db/tests/test_search_embeddings.py

**구현 인터페이스:**
- load_clip_model() -> tuple
- encode_text(text, model, processor, device) -> numpy.ndarray
- encode_image(image_path, model, processor, device) -> numpy.ndarray
- validate_query_vector(vector) -> numpy.ndarray

**동작:**
- 텍스트는 CLIP 텍스트 임베딩으로 변환
- 이미지는 RGB로 변환 후 CLIP 이미지 임베딩으로 변환
- L2 정규화 수행
- 결과 차원은 반드시 512
- NaN과 무한대 거부

**검증 명령:**

python -m pytest embedding-db/tests/test_search_embeddings.py -v

**기대 결과:**

모든 단위 테스트 통과

---

### Task 4: pgvector 검색 구현

**Files:**
- Modify: embedding-db/scripts/search_embeddings.py

**구현 인터페이스:**
- search_database(query_vector, search_mode, top_k) -> list[dict]

**텍스트 검색 SQL 개념:**

segment_embeddings.text_embedding <=> query_vector

**이미지 검색 SQL 개념:**

segment_embeddings.image_embedding <=> query_vector

**조인 테이블:**
- segment_embeddings
- video_segments

**반환 항목:**
- segment_id
- spot_name
- video_id
- start_time
- end_time
- similarity
- keyframe_path
- summary

**유사도 계산:**

similarity = 1 - cosine_distance

---

### Task 5: 결과 출력 및 실제 검색 검증

**Files:**
- Modify: embedding-db/scripts/search_embeddings.py

**텍스트 검색 명령:**

python .\embedding-db\scripts\search_embeddings.py --text "가을에 조용히 산책하기 좋은 숲길"

**이미지 검색 명령:**

python .\embedding-db\scripts\search_embeddings.py --image ".\embedding-db\output\frames\<실제 프레임 파일명>"

**TOP 3 검색 명령:**

python .\embedding-db\scripts\search_embeddings.py --text "호숫가 산책" --top-k 3

**완료 기준:**
- 텍스트 검색 결과가 TOP K로 출력됨
- 이미지 검색 결과가 TOP K로 출력됨
- 모든 결과에 장소, 영상, 구간, 유사도, 프레임 경로, 요약이 표시됨
- 저장된 프레임으로 검색했을 때 동일 segment_id가 상위에 표시됨

---

### Task 6: 전체 검증 및 커밋

**검증 명령:**

python -m pytest embedding-db/tests/test_search_embeddings.py -v

python .\embedding-db\scripts\search_embeddings.py --text "가을 숲길" --top-k 5

git status

**커밋 대상:**
- embedding-db/scripts/search_embeddings.py
- embedding-db/tests/test_search_embeddings.py
- docs/superpowers/plans/2026-07-24-embedding-search.md

**커밋 메시지:**

feat: add text and image vector search
