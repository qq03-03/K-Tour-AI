# K-Tour AI 임베딩 파이프라인 설계

## 1. 목적

Qwen2.5-VL-3B 모델이 생성한 영상 구간별 메타데이터와 키프레임 이미지를 이용하여 텍스트 및 이미지 임베딩을 생성하고 PostgreSQL pgvector에 저장한다.

최종적으로 사용자의 검색어와 유사한 영상 구간을 검색하여 video_id, segment_id, spot_name, start_time, end_time 정보를 반환한다.

## 2. 입력 데이터

입력 메타데이터는 JSON 배열 형식이다.

주요 필드:

- segment_id
- video_id
- place_name
- spot_name
- season
- time_of_day
- mood
- scene_elements
- activity
- description
- start_time
- end_time
- keyframe_path

## 3. 임베딩 모델

모델:

openai/clip-vit-base-patch32

임베딩 차원:

512

생성할 벡터:

- text_embedding vector(512)
- image_embedding vector(512)

## 4. 텍스트 임베딩 구성

description만 단독으로 사용하지 않고 다음 필드를 짧게 조합한다.

- spot_name
- place_name
- season
- time_of_day
- mood
- scene_elements
- activity
- description

예시:

연꽃 정원과 연못의 오리. Nami Island in summer daytime. A serene pond with lotus blossoms and ducks. Peaceful, calm and relaxing. Swimming and bird watching.

unknown 값은 텍스트 구성에서 제외한다.

중복된 배열 값은 제거한다.

## 5. 이미지 임베딩

metadata.json의 keyframe_path를 기준으로 이미지를 불러온다.

예시:

output/frames/SEG_NAMI_01_01.jpg

이미지 파일이 없으면 해당 항목을 오류로 기록하고 전체 작업을 중단할지 또는 건너뛸지 선택할 수 있도록 한다.

초기 구현에서는 누락 이미지를 건너뛰지 않고 오류로 처리한다.

## 6. 처리 흐름

1. metadata.json 읽기
2. 필수 필드 검증
3. segment_id 중복 검사
4. keyframe 이미지 존재 여부 검사
5. 텍스트 입력 문장 생성
6. CLIP 텍스트 임베딩 생성
7. CLIP 이미지 임베딩 생성
8. 벡터 정규화
9. PostgreSQL pgvector 저장
10. 검색어 기반 유사도 검색

## 7. 폴더 구조

embedding-db/
- metadata.json
- output/
  - frames/
- scripts/
  - validate_metadata.py
  - generate_embeddings.py
  - insert_embeddings.py
  - search_similar.py
- requirements.txt
- schema.sql
- test_clip.py
- README.md

## 8. 데이터베이스 저장 정책

segment_id를 고유 키로 사용한다.

같은 segment_id가 다시 입력되면 중복 행을 만들지 않고 기존 데이터를 갱신한다.

저장 대상:

- 원본 메타데이터
- 임베딩에 사용한 검색용 텍스트
- text_embedding
- image_embedding
- 임베딩 모델명
- 생성 시각

## 9. 검색 방식

사용자의 검색어를 CLIP 텍스트 임베딩으로 변환한다.

초기 검색은 다음 두 방식을 각각 테스트한다.

- 검색어와 text_embedding 비교
- 검색어와 image_embedding 비교

코사인 거리를 사용하고 상위 결과를 반환한다.

## 10. 검증 기준

- JSON 10개 항목 정상 로드
- segment_id 중복 없음
- 이미지 파일 수와 keyframe_path 일치
- 텍스트 임베딩 shape: 512
- 이미지 임베딩 shape: 512
- NaN 및 무한대 값 없음
- 벡터 DB 저장 성공
- 연꽃, 오리, 숲길 등 테스트 검색어에 관련 영상 구간 반환
