# K-Tour AI — Frontend

AI 기반 서울 K-관광 영상 자동 메타데이터 생성 및 다국어 검색 시스템의 프론트엔드입니다.

영상을 AI로 분석해 만든 메타데이터(장소·장면 설명·감정 태그 등)를 자연어로 검색하고, 결과를 지도·타임스탬프와 함께 보여주는 서비스의 웹 UI를 담당합니다.

- 팀 프로젝트 본체(영상 전처리, 임베딩/검색 파이프라인): [K-Tour-AI](https://github.com/qq03-03/K-Tour-AI)
- 이 저장소는 그중 웹/프론트엔드 & 통합 파트를 독립적으로 개발하기 위해 분리했습니다.

## 실행 방법

```bash
npm install
npm run dev
```

## 테스트

```bash
npm test
```

## 화면 구성

- **홈** — 검색바, 계절/테마 필터, 인기 콘텐츠
- **검색 결과** — 자연어 검색 결과 리스트 (지도 보기 토글)
- **상세** — 장면 상세 정보, 원본 영상 정보
- **About** — 영상 처리 · 검색 파이프라인 진행 상태

## 데이터

현재는 팀의 실제 파이프라인 산출물(`embedding-db/metadata/metadata.json`, 10개 세그먼트)을 그대로 복사한 mock 데이터로 동작합니다. 실제 검색 API가 완성되면 `src/lib/searchSegments.js`의 인터페이스를 유지한 채 내부 구현만 교체할 예정입니다.

## 기술 스택

Vite · React (JavaScript) · react-router-dom · Vitest · React Testing Library
