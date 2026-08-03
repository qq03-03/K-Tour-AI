K-콘텐츠 영상 전처리 실행 방법
============================================================

1. 프로젝트 경로
- 실행.ps1이 있는 폴더를 자동으로 프로젝트 경로로 사용합니다.
- G드라이브와 H드라이브가 바뀌어도 경로를 직접 수정하지 않습니다.

2. 컴퓨터별 실행 환경
- 가상환경:
  %LOCALAPPDATA%\K-contents-preprocessing\.venv
- FFmpeg:
  %LOCALAPPDATA%\K-contents-preprocessing\.tools\ffmpeg.exe
- .venv와 .tools는 GitHub 또는 Slack으로 공유하지 않습니다.

3. 최초 실행
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\실행.ps1 setup
.\실행.ps1 list
.\실행.ps1 test

시험 실행이 정상적이면:
.\실행.ps1 all

4. 특정 영상 다시 실행
.\실행.ps1 one -VideoId "Lovely Runner_01"

- one 명령은 완료된 영상도 기존 결과를 제거한 뒤 다시 처리합니다.
- 해당 영상의 quality_report 행도 교체되므로 다른 영상 결과가 사라지지 않습니다.

5. 로그인이 필요한 영상
Chrome을 완전히 종료한 뒤:
.\실행.ps1 cookie -VideoId "Lovely Runner_01"

6. 전체 결과 초기화
.\실행.ps1 reset

삭제:
- clips
- keyframes
- rejected_keyframes
- contact_sheets
- preprocessed_segments.json
- rejected_candidates.json
- quality_report.csv

유지:
- raw_videos

7. ** 수정된 파일 제목

- raw_videos -> original_videos : 원본 영상
- clips	-> preprocessed_video : 전처리 영상
- keyframes: 전처리 대표 이미지
- rejected_keyframes: 제외 이미지 자료
- contact_sheets: 검수용 이미지 자료
- preprocessed_segments.json: 전처리 결과 메타데이터
- rejected_candidates.json: 제외 장면 메타데이터
- quality_report.csv: 전체 후보 품질 보고서

8. 예상 복구 계획
- V001_P001_S001 | Lovely Runner_01 | 봄 | 기존 선택 0 | 계절만 제외 1 | 복구 예정 1 | 품질 제외 유지 0
- V001_P002_S001 | Lovely Runner_02 | 봄 | 기존 선택 0 | 계절만 제외 6 | 복구 예정 3 | 품질 제외 유지 6
- V001_P003_S001 | Lovely Runner_03 | 봄 | 기존 선택 0 | 계절만 제외 8 | 복구 예정 3 | 품질 제외 유지 1
- V002_P004_S001 | WLGYT_01 | 봄 | 기존 선택 1 | 계절만 제외 0 | 복구 예정 0 | 품질 제외 유지 0
- V002_P004_S002 | WLGYT_02 | 봄 | 기존 선택 1 | 계절만 제외 0 | 복구 예정 0 | 품질 제외 유지 0
- V002_P004_S003 | WLGYT_03 | 봄 | 기존 선택 2 | 계절만 제외 0 | 복구 예정 0 | 품질 제외 유지 0
- V013_P019_S001 | DIVA_01 | 봄 | 기존 선택 0 | 계절만 제외 4 | 복구 예정 2 | 품질 제외 유지 0
- V013_P020_S001 | DIVA_03 | 봄 | 기존 선택 0 | 계절만 제외 1 | 복구 예정 1 | 품질 제외 유지 0
- V004_P008_S001 | TFTO_02 | 여름 | 기존 선택 0 | 계절만 제외 3 | 복구 예정 3 | 품질 제외 유지 0
- V004_P009_S001 | TFTO_07 | 여름 | 기존 선택 3 | 계절만 제외 0 | 복구 예정 0 | 품질 제외 유지 0
- V005_P010_S003 | HCCC_03 | 여름 | 기존 선택 0 | 계절만 제외 0 | 복구 예정 0 | 품질 제외 유지 2
- V008_P013_S002 | GOBLIN_02 | 여름 | 기존 선택 1 | 계절만 제외 0 | 복구 예정 0 | 품질 제외 유지 1
- V006_P011_S002 | OURBLUES_03 | 여름 | 기존 선택 0 | 계절만 제외 1 | 복구 예정 1 | 품질 제외 유지 0
- V009_P022_S001 | hotel_deluna_paradise_01 | 여름 | 기존 선택 2 | 계절만 제외 0 | 복구 예정 0 | 품질 제외 유지 0
- V011_P016_S002 | kingdom_gyeongbok_02 | 여름 | 기존 선택 0 | 계절만 제외 0 | 복구 예정 0 | 품질 제외 유지 0
- V011_P017_S002 | kingdom_changdeok_02 | 여름 | 기존 선택 2 | 계절만 제외 0 | 복구 예정 0 | 품질 제외 유지 0
- V003_P006_S001 | OBS_03 | 가을 | 기존 선택 0 | 계절만 제외 0 | 복구 예정 0 | 품질 제외 유지 1
- V007_P012_S001 | CLOY_01 | 가을 | 기존 선택 0 | 계절만 제외 4 | 복구 예정 2 | 품질 제외 유지 0
- V011_P017_S001 | kingdom_changdeok_01 | 가을 | 기존 선택 3 | 계절만 제외 0 | 복구 예정 0 | 품질 제외 유지 1
- V012_P018_S001 | WTWIF_01 | 가을 | 기존 선택 0 | 계절만 제외 1 | 복구 예정 1 | 품질 제외 유지 0
- V006_P011_S001 | OURBLUES_01 | 겨울 | 기존 선택 0 | 계절만 제외 5 | 복구 예정 3 | 품질 제외 유지 0

예상 추가 클립·대표 이미지: 20개
계절 외 품질 사유로 제외 유지: 12개

실제 복구 수는 현재 로컬 JSON 내용과 원본 영상 파일 존재 여부에 따라 달라질 수 있습니다.
