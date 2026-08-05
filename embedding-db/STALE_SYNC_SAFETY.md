# Embedding DB stale 삭제 안전장치

## 기본 적재

기본 실행은 기존 DB 행을 삭제하지 않고 upsert만 수행합니다.

```powershell
python scripts/insert_embeddings.py
```

부분 데이터 또는 단일 데이터셋을 적재할 때는 기본 실행을 사용합니다.

## 전체 동기화

현재 metadata와 embedding 파일이 DB 전체의 기준 데이터임이 확인된 경우에만 `--full-sync`를 사용합니다.

```powershell
python scripts/insert_embeddings.py --full-sync
```

이 옵션은 현재 입력에 없는 기존 `segment_keyframes`와 `video_segments`를 stale 데이터로 삭제합니다. FK cascade에 따라 연결된 embedding도 함께 삭제됩니다.

## 공통 안전장치

- segment 또는 keyframe 입력이 0건이면 DB 접속 전에 실행을 중단합니다.
- `--full-sync`를 생략하면 전역 stale 삭제 SQL을 실행하지 않습니다.
- 향후 여러 데이터셋을 한 DB에 함께 저장한다면 dataset/batch 범위 삭제로 추가 확장해야 합니다.

