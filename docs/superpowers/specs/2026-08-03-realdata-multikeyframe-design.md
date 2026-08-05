\# Real Data Multi-Keyframe Embedding Design



\## 목적



실데이터에서는 하나의 segment\_id에 여러 개의 keyframe 이미지가 연결될 수 있다.



예:



V005\_P010\_S001

\- HCCC\_01\_SCENE\_01.jpg

\- HCCC\_01\_SCENE\_02.jpg

\- HCCC\_01\_SCENE\_03.jpg



검색 결과는 팀 합의에 따라 segment 단위로 한 번만 노출한다.



\## 기본 정책



\- video segment는 기존 segment\_id를 유지한다.

\- 하나의 segment는 여러 keyframe을 가질 수 있다.

\- keyframe마다 이미지 임베딩을 생성한다.

\- segment 검색 결과는 중복 노출하지 않는다.

\- 여러 keyframe 중 가장 높은 이미지 유사도를 해당 segment의 대표 이미지 유사도로 사용한다.

\- 텍스트 검색도 최종 결과는 segment\_id 기준으로 한 번만 반환한다.



\## 데이터 구조



\### video\_segments



기존처럼 segment\_id 기준으로 관리한다.



주요 필드:



\- segment\_id

\- video\_id

\- start\_time

\- end\_time

\- region

\- drama\_title

\- place\_name

\- season

\- metadata



\### segment\_keyframes



새로운 keyframe 단위 테이블을 사용한다.



주요 필드:



\- keyframe\_id

\- segment\_id

\- keyframe\_path

\- metadata



keyframe\_id는 별도의 VLM 필드를 요구하지 않고

segment\_id와 keyframe 파일명을 이용해 내부적으로 생성한다.



예:



V005\_P010\_S001\_\_HCCC\_01\_SCENE\_01



\### keyframe\_embeddings



keyframe별 이미지 임베딩을 저장한다.



주요 필드:



\- keyframe\_id

\- image\_embedding



\### segment\_embeddings



segment 단위 텍스트 임베딩을 저장한다.



주요 필드:



\- segment\_id

\- text\_embedding



\## 검색



\### 텍스트 검색



segment\_embeddings의 text\_embedding을 검색한다.



최종 결과:



\- segment\_id당 한 번만 반환



\### 이미지 검색



모든 keyframe image\_embedding과 query image를 비교한다.



같은 segment\_id의 keyframe이 여러 개 검색되면

가장 높은 유사도의 keyframe만 대표 결과로 선택한다.



예:



V005\_P010\_S001

\- SCENE\_01 similarity 0.71

\- SCENE\_02 similarity 0.87

\- SCENE\_03 similarity 0.76



최종 결과:



V005\_P010\_S001 similarity 0.87

representative\_keyframe = SCENE\_02



\## 신규 메타데이터



실데이터에서 다음 필드가 추가됐다.



\- region

\- drama\_title



두 필드는:



1\. PostgreSQL에 별도 값으로 저장

2\. CLIP 검색 텍스트 생성 시 포함



하도록 한다.



이를 통해 다음과 같은 검색을 지원한다.



\- 도깨비 촬영지 중 겨울 분위기 장소

\- 강원도 드라마 촬영지

\- 우리들의 블루스 제주 바닷가



\## keyframe 실제 경로



metadata의 keyframe\_path:



keyframes/GOBLIN\_03/GOBLIN\_03\_SCENE\_01.jpg



실제 파일 기준 root:



K-contents\_preprocessed/preprocessed\_output/



따라서 실제 이미지:



K-contents\_preprocessed/preprocessed\_output/keyframes/GOBLIN\_03/GOBLIN\_03\_SCENE\_01.jpg



generate\_embeddings.py는 이 실제 데이터 root를 기준으로 이미지를 찾도록 수정한다.



\## 검증된 실데이터 상태



\- metadata: 42건

\- 실제 JPG: 45장

\- metadata에서 참조하지만 존재하지 않는 keyframe: 0장

\- metadata 미사용 keyframe: 3장

\- 동일 segment\_id에 여러 keyframe이 존재하는 구조 확인



미사용 이미지:



\- OBS\_02/OBS\_02\_SCENE\_02.jpg

\- OBS\_02/OBS\_02\_SCENE\_03.jpg

\- WLGYT\_03/WLGYT\_03\_SCENE\_02.jpg



이 3장은 metadata에서 참조하지 않으므로 임베딩 대상에서 제외한다.



\## 수정 대상



\- embedding-db/schema.sql

\- embedding-db/scripts/generate\_embeddings.py

\- embedding-db/scripts/insert\_embeddings.py

\- embedding-db/scripts/search\_embeddings.py

\- 관련 테스트 코드



\## 성공 조건



1\. metadata 42건을 모두 처리할 수 있다.

2\. 동일 segment\_id의 여러 keyframe이 덮어쓰기 되지 않는다.

3\. metadata가 참조하는 keyframe 42장이 모두 임베딩된다.

4\. region과 drama\_title이 검색 텍스트에 포함된다.

5\. 텍스트 검색 결과는 segment\_id당 한 번 나온다.

6\. 이미지 검색 결과는 동일 segment의 최고 유사도 keyframe만 대표한다.

7\. 기존 검색 테스트도 정상 동작한다.

8\. PostgreSQL/pgvector 적재 후 건수 및 관계가 정확하다.

