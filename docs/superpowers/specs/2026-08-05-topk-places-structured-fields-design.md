\# Top-K Segment Deduplication, Places Linking, and Structured Search Fields



\## Goal



리뷰 요청사항을 반영하여 Top-K 검색을 segment 단위로 중복 제거하고,

장소 좌표 연결을 위한 place\_id 관계를 정리하며,

검색에 필요한 구조화 필드를 DB와 검색 결과에 명시적으로 저장한다.



\## 1. Places / Spots relationship



기존 `spots` 테이블을 장소 마스터로 유지한다.



\### spots



\- `place\_id TEXT UNIQUE` 추가

\- 기존 컬럼 유지:

&#x20; - spot\_id

&#x20; - spot\_name

&#x20; - region

&#x20; - address

&#x20; - latitude

&#x20; - longitude

&#x20; - description

&#x20; - source\_url



`place\_id`를 외부 metadata와 downstream 좌표 데이터의 안정적인 연결 키로 사용한다.



\### video\_segments



기존 `spot\_id`는 호환성을 위해 유지한다.



`place\_id`도 유지하고 `spots(place\_id)`와 FK로 연결한다.



Embedding insert 시:



1\. metadata의 place\_id / place\_name / region으로 spots를 upsert한다.

2\. 해당 place\_id의 spot\_id를 조회한다.

3\. video\_segments에 place\_id와 spot\_id를 모두 저장한다.



좌표 데이터가 나중에 추가되더라도 embedding 재생성 없이 spots 테이블만 갱신할 수 있어야 한다.



\## 2. Structured segment fields



`video\_segments`에 다음 컬럼을 추가한다.



\- `description TEXT`

\- `time\_of\_day TEXT`

\- `activity TEXT\[]`

\- `scene\_elements TEXT\[]`



기존 `mood\_tags TEXT\[]`는 mood 저장에 계속 사용한다.



`activity`와 `scene\_elements`는 하나의 tags 컬럼으로 합치지 않는다.



metadata의 구조화 필드를 가능한 그대로 저장한다.



\## 3. Segment-level Top-K



검색 결과의 기본 단위는 keyframe이 아니라 segment이다.



한 segment에 keyframe이 여러 개 존재할 경우:



\- 모든 keyframe의 image similarity를 비교한다.

\- image similarity가 가장 높은 keyframe 한 장을 representative keyframe으로 선택한다.

\- 최종 Top-K에서는 segment당 최대 1개의 결과만 반환한다.



Text search:



\- segment의 text embedding similarity로 순위를 결정한다.

\- 각 segment의 representative keyframe은 query와 image similarity가 가장 높은 keyframe을 사용한다.



Image search:



\- 각 segment의 keyframe 중 image similarity가 가장 높은 keyframe을 선택한다.

\- 그 대표 keyframe의 image similarity로 segment 순위를 결정한다.



\## 4. Top-K result contract



최종 검색 결과는 최소 다음 필드를 반환한다.



\- segment\_id

\- keyframe\_id

\- keyframe\_path

\- place\_id

\- region

\- spot\_name

\- drama\_title

\- description

\- time\_of\_day

\- mood

\- activity

\- scene\_elements

\- video\_id

\- start\_time

\- end\_time

\- text\_score

\- image\_score

\- similarity



`similarity`는 검색 모드에 따라 다음 값을 사용한다.



\- text search: text\_score

\- image search: image\_score



\## 5. Backward compatibility



기존 `spot\_id`, `tags`, `mood\_tags`, `season\_tags`,

`segment\_embeddings` 구조는 이번 변경에서 제거하지 않는다.



새 컬럼과 관계는 기존 DB에도 적용할 수 있도록

`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 형태의 migration을 제공한다.



\## 6. Tests



다음 동작을 테스트한다.



\- spots.place\_id가 UNIQUE인지

\- video\_segments.place\_id가 spots.place\_id와 연결되는지

\- insert 후 spot\_id가 NULL이 아닌지

\- description / time\_of\_day / activity / scene\_elements가 저장되는지

\- 같은 segment에 여러 keyframe이 있어도 Top-K 결과는 한 행인지

\- 대표 keyframe이 가장 높은 image similarity를 가진 keyframe인지

\- Top-K 결과에 모든 구조화 필드가 포함되는지

\- 기존 45 segment / 45 keyframe 데이터가 계속 정상 적재되는지

\- 전체 기존 테스트가 회귀 없이 통과하는지

