# K-Tour AI 백엔드 전달 준비본

기준 데이터는 517 SCENE이며 P063은 완전히 제외했습니다. 임베딩 진행 중인 원본은 수정하지 않았습니다.

## 구성

- data/metadata_517_no_P063.json
- data/display_translations_517_no_P063.json
- data/places_coordinates_517.json, .csv
- data/multilingual_theme_evaluation_40.json
- docs/search_api_contract.md
- examples/ 요청·후보·최종 응답 예시
- scripts/validate_embedding_delivery.py
- scripts/run_post_embedding_checks.ps1
- reports/ 사전 검증 결과

## 연결 키

- 좌표: place_id
- 표시언어: segment_id + keyframe_id + lang
- 검색 중복 제거: source_segment_id
- keyframe_id: segment_id와 동일

## 임베딩 도착 후

PowerShell에서 아래처럼 현재 프로세스에만 실행 정책 예외를 적용해 검사합니다. 실제 임베딩 파일이 오면 `-TextEmbeddings`, `-ImageEmbeddings` 경로를 추가합니다.

`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_post_embedding_checks.ps1`

이후 PostgreSQL 적재 건수와 Top-K/RRF 통합 검색을 확인합니다.
