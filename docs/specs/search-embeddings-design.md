# Search Embeddings Design

## 목적

CLIP ViT-B/32로 생성한 텍스트·이미지 임베딩이 PostgreSQL pgvector에서 정상적으로 검색되는지 검증한다.

## 실행 방식

텍스트 검색 명령:

python .\embedding-db\scripts\search_embeddings.py --text "가을에 조용히 산책하기 좋은 숲길"

이미지 검색 명령:

python .\embedding-db\scripts\search_embeddings.py --image ".\embedding-db\output\frames\sample.jpg"

검색 결과 개수 변경:

python .\embedding-db\scripts\search_embeddings.py --text "호숫가 산책" --top-k 3

## 입력 규칙

- --text 또는 --image 중 하나만 필수로 입력한다.
- 두 옵션은 동시에 사용할 수 없다.
- --top-k 기본값은 5이며 1 이상의 정수만 허용한다.

## 처리 흐름

1. 명령행 인자를 검증한다.
2. .env에서 PostgreSQL 접속 정보를 읽는다.
3. openai/clip-vit-base-patch32 모델과 프로세서를 불러온다.
4. 텍스트 또는 이미지를 512차원 정규화 벡터로 변환한다.
5. pgvector 코사인 거리 연산자로 유사한 영상 구간을 검색한다.
6. 코사인 유사도를 1 - 거리로 계산한다.
7. 상위 결과를 터미널에 출력한다.

## 검색 기준

- 텍스트 검색: segment_embeddings.text_embedding
- 이미지 검색: segment_embeddings.image_embedding
- segment_id를 기준으로 segment_embeddings와 video_segments를 조인한다.

## 출력 항목

- 순위
- segment_id
- spot_name
- video_id
- start_time
- end_time
- similarity
- keyframe_path
- summary

## 오류 처리

- 텍스트와 이미지를 동시에 입력한 경우
- 이미지 경로가 존재하지 않는 경우
- top-k가 1보다 작은 경우
- DB 환경변수가 누락된 경우
- PostgreSQL 연결에 실패한 경우
- 검색할 임베딩이 없는 경우
- 검색 벡터가 512차원이 아닌 경우

## 완료 기준

- 텍스트 검색이 TOP K 결과를 반환한다.
- 이미지 검색이 TOP K 결과를 반환한다.
- 저장된 프레임 검색 시 동일 장면이 상위 결과에 나타난다.
