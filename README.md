# K-Tour-AI

K-콘텐츠 촬영지 영상의 SCENE 메타데이터와 대표 프레임 임베딩을 이용해
자연어 질문과 관련된 영상 구간을 찾는 멀티모달 검색 프로젝트입니다.

## 주요 구성

- `embedding-db/`: CLIP 텍스트·이미지 임베딩 생성, PostgreSQL·pgvector 적재 및 후보 검색
- `search_automation/`: 신규 metadata의 ID·스키마·필터·테마·좌표·표시언어·평가 정합성 자동 검증
- `search-service/`: 다국어 QueryParser, 구조화 필터, 텍스트·이미지 RRF 결합 검색 및 40문항 평가
- `search-service/data/`: 통합 검색 카탈로그, 테마 매핑, 장소 좌표·다국어 표시 데이터
- 전처리 폴더: 영상 구간화와 keyframe 생성 결과

검색 자동화 실행 및 백엔드 적용 기준은
[`search_automation/README.md`](search_automation/README.md)와
[`search-service/README.md`](search-service/README.md),
[`docs/backend_search_update_20260827.md`](docs/backend_search_update_20260827.md)를 참고합니다.
