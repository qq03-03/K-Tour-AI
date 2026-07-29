K-콘텐츠 영상 전처리 실행 방법

==================================================
1. 프로젝트 구성
==================================================

이 프로젝트는 실행.ps1이 있는 폴더를 자동으로 프로젝트 경로로 사용합니다.

가상환경과 FFmpeg는 프로젝트 폴더가 아니라 각 컴퓨터의 LOCALAPPDATA에 설치됩니다.

- 가상환경:
  %LOCALAPPDATA%\K-contents-preprocessing\.venv

- FFmpeg:
  %LOCALAPPDATA%\K-contents-preprocessing\.tools\ffmpeg.exe


==================================================
2. 현재 반영된 데이터
==================================================

- 호텔델루나 표기를 호텔 델루나로 수정
- 변경된 영상 URL, 시간, 계절, 분위기, 장면 요소 반영
- preprocessing_manifest.json과 원본 데이터 동기화
- 기존 전처리 결과는 새 데이터 기준으로 다시 생성 권장


==================================================
3. GitHub
==================================================

1. 압축을 푼 프로젝트 폴더를 VSCode로 엽니다.
2. VSCode 터미널을 PowerShell로 엽니다.
3. 아래 명령을 실행합니다.

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\실행.ps1 setup
.\실행.ps1 list
.\실행.ps1 test

시험 실행이 정상적으로 끝나면:

.\실행.ps1 all

주의:
- 저장소에 포함된 .venv를 사용하지 않습니다.
- 각 팀원 컴퓨터에서 setup을 실행해 자신의 가상환경을 생성해야 합니다.
- Python이 설치되어 있어야 합니다.
- 프로젝트 경로나 드라이브 문자는 직접 수정하지 않습니다.


==================================================
4. Slack
==================================================

1. 받은 ZIP 파일의 압축을 풉니다.
2. 압축을 푼 K-contents_preprocessing 폴더를 VSCode로 엽니다.
3. PowerShell에서 아래 명령을 실행합니다.

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\실행.ps1 setup
.\실행.ps1 list
.\실행.ps1 test

정상적으로 실행되면:

.\실행.ps1 all

ZIP 파일을 다른 폴더로 이동해도 실행.ps1이 현재 위치를 자동으로 인식합니다.


==================================================
5. requirements_scene.txt
==================================================

필수 예시:

numpy
opencv-python
yt-dlp
imageio-ffmpeg
youtube-transcript-api

패키지를 추가했다면 팀원은 다시 아래 명령을 실행합니다.

.\실행.ps1 setup

Python 코드에서 가져올 때:

import imageio_ffmpeg
from youtube_transcript_api import YouTubeTranscriptApi

설치 파일 이름과 import 이름이 다를 수 있습니다.

- 설치 이름: imageio-ffmpeg
- import 이름: imageio_ffmpeg

- 설치 이름: youtube-transcript-api
- import 이름: youtube_transcript_api


==================================================
6. 특정 영상만 실행
==================================================

.\실행.ps1 one -VideoId "Lovely Runner_01"


==================================================
7. 로그인이 필요한 유튜브 영상
==================================================

Chrome을 완전히 종료한 뒤 실행합니다.

.\실행.ps1 cookie -VideoId "Lovely Runner_01"

==================================================
8. 이전 결과 초기화
==================================================

원본 데이터나 매니페스트가 변경되었다면 이전 전처리 결과를 초기화합니다.

.\실행.ps1 reset

reset으로 삭제되는 항목:

- preprocessed_segments.json
- rejected_candidates.json
- quality_report.csv
- clips
- keyframes
- rejected_keyframes
- contact_sheets

삭제되지 않는 항목:

- preprocessed_output\raw_videos


==================================================
9. 시간 수정이 필요한 영상
==================================================

CLOY_02
- start_time: 0.0
- end_time: 0.0

DIVA_03
- start_time: 30.0
- end_time: 30.0

종료 시간이 시작 시간보다 커지기 전까지 위 영상은 자동으로 건너뜁니다.


==================================================
10. 권장 실행 순서
==================================================

처음 받은 팀원:

1. .\실행.ps1 setup
2. .\실행.ps1 list
3. .\실행.ps1 test
4. .\실행.ps1 all

원본 데이터가 수정된 경우:

1. 수정된 파일 덮어쓰기
2. .\실행.ps1 setup
3. .\실행.ps1 reset
4. .\실행.ps1 list
5. .\실행.ps1 test
6. .\실행.ps1 all


==================================================
11. 오류 확인
==================================================

imageio_ffmpeg 가져오기 오류:

.\실행.ps1 setup

설치 확인:

& "$env:LOCALAPPDATA\K-contents-preprocessing\.venv\Scripts\python.exe" -c "import imageio_ffmpeg; print(imageio_ffmpeg.__version__)"

youtube_transcript_api 가져오기 오류:

& "$env:LOCALAPPDATA\K-contents-preprocessing\.venv\Scripts\python.exe" -m pip install youtube-transcript-api

VSCode에서 빨간 밑줄만 표시되는 경우:

1. Ctrl + Shift + P
2. Python: Select Interpreter
3. 아래 Python 선택

%LOCALAPPDATA%\K-contents-preprocessing\.venv\Scripts\python.exe

4. Developer: Reload Window 실행


==================================================
12. 중요
==================================================

- .venv와 .tools를 GitHub 또는 Slack으로 공유하지 않습니다.
- 팀원마다 자신의 컴퓨터에서 setup을 한 번 실행합니다.
- 대용량 원본 영상과 코드 저장소는 분리해서 관리할 수 있습니다.
- 영상 URL, 시간, 계절 등이 수정되면 preprocessing_manifest.json도 함께 수정해야 합니다.
