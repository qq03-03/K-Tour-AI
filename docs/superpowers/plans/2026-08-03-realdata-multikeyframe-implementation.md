\# Real Data Multi-Keyframe Embedding Implementation Plan



> \*\*For agentic workers:\*\* Implement task-by-task with tests before implementation.



\*\*Goal:\*\* 실데이터의 다중 keyframe 구조를 지원하면서 검색 결과는 segment\_id 단위로 한 번만 반환한다.



\*\*Architecture:\*\* video\_segments는 기존 segment\_id 단위로 유지하고, keyframe과 이미지 임베딩은 별도 단위로 저장한다. 텍스트 임베딩은 segment 단위, 이미지 임베딩은 keyframe 단위로 관리하며 이미지 검색 시 같은 segment의 최고 유사도 keyframe을 대표값으로 사용한다.



\*\*Tech Stack:\*\* Python, PostgreSQL, pgvector, CLIP ViT-B/32, psycopg, pytest



\## Global Constraints



\- 기존 segment\_id 값은 변경하지 않는다.

\- metadata 42건이 모두 처리되어야 한다.

\- 동일 segment\_id의 여러 keyframe이 덮어쓰기 되면 안 된다.

\- 검색 결과는 segment\_id당 한 번만 반환한다.

\- region과 drama\_title을 DB와 검색 텍스트에 포함한다.

\- metadata에서 사용하지 않는 keyframe 3장은 임베딩하지 않는다.

\- metadata가 참조하는 keyframe 누락은 0이어야 한다.



\---



\### Task 1: 실데이터 검증 테스트



\*\*Files:\*\*

\- Create: `embedding-db/tests/test\_realdata\_metadata.py`

\- Read: `metadata\_vlm\_final.json`

\- Read: `K-contents\_preprocessed/preprocessed\_output/keyframes/`



검증 항목:



\- metadata 42건

\- 모든 keyframe\_path 존재

\- keyframe\_path 42개 고유

\- segment\_id 중복 허용

\- region 존재

\- drama\_title 존재

\- start\_time < end\_time

\- mood, scene\_elements, activity 배열 타입



테스트 실행:



`python -m pytest embedding-db/tests/test\_realdata\_metadata.py -v`



\---



\### Task 2: PostgreSQL schema를 multi-keyframe 구조로 변경



\*\*Files:\*\*

\- Modify: `embedding-db/schema.sql`



구조:



`video\_segments`

\- segment\_id PK

\- segment 단위 정보 저장



`segment\_keyframes`

\- keyframe\_id PK

\- segment\_id FK

\- keyframe\_path

\- metadata



`segment\_embeddings`

\- segment\_id PK/FK

\- text\_embedding vector(512)



`keyframe\_embeddings`

\- keyframe\_id PK/FK

\- image\_embedding vector(512)



region과 drama\_title을 video\_segments에 저장한다.



keyframe\_id는 다음 규칙으로 생성한다.



`{segment\_id}\_\_{keyframe filename stem}`



예:



`V005\_P010\_S001\_\_HCCC\_01\_SCENE\_01`



\---



\### Task 3: 임베딩 생성 코드 변경



\*\*Files:\*\*

\- Modify: `embedding-db/scripts/generate\_embeddings.py`

\- Create or modify tests for embedding generation



변경사항:



\- 실데이터 root:

&#x20; `K-contents\_preprocessed/preprocessed\_output/`

\- metadata의 `keyframe\_path`를 위 root 기준으로 해석

\- region을 search\_text에 포함

\- drama\_title을 search\_text에 포함

\- 동일 segment\_id의 여러 keyframe 허용

\- keyframe\_id 자동 생성

\- segment별 text\_embedding 생성

\- keyframe별 image\_embedding 생성



생성 결과는 중복 segment\_id 때문에 덮어쓰기 되지 않아야 한다.



\---



\### Task 4: DB 적재 코드 변경



\*\*Files:\*\*

\- Modify: `embedding-db/scripts/insert\_embeddings.py`



기존 문제 제거:



`metadata\_by\_segment = {segment\_id: item}` 방식 사용 금지.



동일 segment\_id의 여러 metadata를 유지해야 한다.



적재 방식:



\- videos: video\_id 기준

\- video\_segments: segment\_id 기준 1건

\- segment\_keyframes: keyframe\_id 기준 각 keyframe 저장

\- segment\_embeddings: segment\_id 기준 text embedding

\- keyframe\_embeddings: keyframe\_id 기준 image embedding



기존 오류 수정:



`region = metadata.get("place\_name")`



→



`region = metadata.get("region")`



drama\_title도 DB에 저장한다.



\---



\### Task 5: 검색 로직 변경



\*\*Files:\*\*

\- Modify: `embedding-db/scripts/search\_embeddings.py`

\- Modify: `embedding-db/tests/test\_search\_embeddings.py`



텍스트 검색:



\- segment\_embeddings 검색

\- segment\_id당 한 번 반환



이미지 검색:



\- keyframe\_embeddings 전체 검색

\- segment\_id별 최고 similarity만 선택

\- 최종 결과는 segment\_id당 한 번 반환

\- 대표 keyframe\_path도 결과에 포함



예:



같은 segment의 similarity가



\- SCENE\_01 = 0.71

\- SCENE\_02 = 0.87

\- SCENE\_03 = 0.76



이면 최종 결과:



\- segment\_id = 해당 segment

\- similarity = 0.87

\- representative\_keyframe = SCENE\_02



\---



\### Task 6: 회귀 테스트



기존 전체 테스트 실행:



`python -m pytest embedding-db/tests -v`



성공 조건:



\- 기존 검색 기능 정상

\- multi-keyframe 테스트 정상

\- region/drama\_title 검색 텍스트 반영

\- 같은 segment 검색결과 중복 없음



\---



\### Task 7: 최종 metadata 반영



검증 완료 후:



`metadata\_vlm\_final.json`



을



`embedding-db/metadata/metadata.json`



으로 반영한다.



임시 파일 `metadata2.1.json`, `metadata\_vlm\_final.json`은 최종 Git 커밋 대상에서 제외한다.



\---



\### Task 8: 실데이터 임베딩 생성



실제 metadata 42건 및 참조 keyframe 42장으로 CLIP 임베딩을 생성한다.



검증:



\- 처리 실패 0

\- 누락 이미지 0

\- text embedding 512차원

\- image embedding 512차원

\- keyframe별 이미지 embedding 보존



\---



\### Task 9: PostgreSQL/pgvector 적재



실데이터 적재 후 확인:



\- videos 건수

\- video\_segments 고유 segment 건수

\- segment\_keyframes 42건

\- segment\_embeddings = 고유 segment 수

\- keyframe\_embeddings 42건



동일 segment의 여러 keyframe이 모두 보존되어야 한다.



\---



\### Task 10: 실제 검색 검증



텍스트 검색 예:



\- `도깨비 겨울 촬영지`

\- `강원도 드라마 촬영지`

\- `우리들의 블루스 제주 바닷가`

\- `조용하고 평화로운 겨울 여행지`



이미지 검색:



\- 실제 keyframe 한 장을 query로 사용

\- 동일 이미지가 속한 segment가 상위 결과에 나오는지 확인

\- 같은 segment가 여러 줄로 중복되지 않는지 확인



\---



\### Task 11: Git 최종 반영



커밋 대상:



\- schema.sql

\- generate\_embeddings.py

\- insert\_embeddings.py

\- search\_embeddings.py

\- 테스트 코드

\- 최종 metadata.json



커밋 제외:



\- 압축 해제한 keyframes/

\- 임시 metadata2.1.json

\- metadata\_vlm\_final.json

\- 생성된 embedding output

\- PostgreSQL 로컬 DB 데이터



전체 테스트 통과 후 feature branch를 push하고 main에 병합한다.

