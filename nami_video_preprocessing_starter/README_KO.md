# 남이섬 영상 전처리 시작 프로젝트

## 1. 영상 파일 준비

아래 원본 파일 3개를 `input/videos` 폴더에 복사하고 이름을 변경합니다.

- `260625 핀터맛 여름휴가지 최종_BGM최종.mp4` → `VID_NAMI_01.mp4`
- `260706 Today is your Nami Island.mp4` → `VID_NAMI_02.mp4`
- `260713_출근하는 오리들 남이섬.mp4` → `VID_NAMI_03.mp4`

## 2. VSCode 터미널에서 가상환경 생성

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`python` 명령이 안 되면 `py`를 사용합니다.

## 3. 영상 검사

```powershell
python scripts/check_videos.py
```

## 4. 구간 4개 샘플 전처리

```powershell
python scripts/preprocess.py --config config/segments_sample.json
```

생성 결과:

- `output/segments/SEG_NAMI_01_01.mp4`
- `output/segments/SEG_NAMI_01_02.mp4`
- `output/segments/SEG_NAMI_01_03.mp4`
- `output/segments/SEG_NAMI_01_04.mp4`
- `output/frames/SEG_NAMI_01_01.jpg`
- `output/frames/SEG_NAMI_01_02.jpg`
- `output/frames/SEG_NAMI_01_03.jpg`
- `output/frames/SEG_NAMI_01_04.jpg`
- `output/preprocessing_results.json`

## 5. 시간 구간 검토

`output/segments`의 MP4를 직접 재생합니다.

- 장면 시작이 너무 빠르거나 느리면 `start_time` 수정
- 장면 끝이 잘리거나 다른 장면이 포함되면 `end_time` 수정
- 대표 이미지가 흐리거나 장면 전환 중이면 `representative_frame_time` 수정

수정 후 같은 명령을 다시 실행합니다.

## 6. 9개 전체 실행

샘플이 정상일 때 실행합니다.

```powershell
python scripts/preprocess.py --config config/segments_all_9_template.json
```

`segments_all_9_template.json`의 시간은 1차 초안이므로 실제 영상을 보면서 반드시 조정해야 합니다.

## 7. 검토 완료 표시

출력 파일과 시간을 확인한 후 `output/preprocessing_results.json`에서 해당 구간을 다음처럼 수정합니다.

```json
"time_verified": true,
"review_status": "reviewed",
"notes": "시작·종료 시간 및 대표 프레임 확인 완료"
```

## 8. 폴더 역할
```
input/videos: 원본 영상
config: 영상 구간 시간 정보
output/segments: 구간별로 자른 영상
output/frames: 구간별 대표 이미지
scripts: 영상 전처리 코드
preprocessing_results.json: 전처리 결과 정리 파일
```

## 9. 수정사항

- 동영상은 따로 공유
- start_sec, end_sec, representative_frame_sec -> start_time, end_time, representative_frame_time 명령어 수정
- 샘플 데이터 4개로 다시 수정
- 프레임 SEG_NAMI_01_02 : 3.4 -> 11.7, SEG_NAMI_03_03 : 30.0 -> 31.5 시간 수정 완료
- VID_NAMI_01은 4개 구간으로 다시 나눔
