param(
    [ValidateSet("menu", "setup", "list", "test", "one", "all", "cookie", "reset")]
    [string]$Mode = "menu",
    [string]$VideoId = "Lovely Runner_01"
)

$ErrorActionPreference = "Stop"

# USB 드라이브 문자가 바뀌어도 실행.ps1 위치를 자동 인식합니다.
$ProjectRoot = $PSScriptRoot
$LocalEnvironmentRoot = Join-Path $env:LOCALAPPDATA "K-contents-preprocessing"
$VenvRoot = Join-Path $LocalEnvironmentRoot ".venv"
$ToolsDir = Join-Path $LocalEnvironmentRoot ".tools"
$LocalFfmpeg = Join-Path $ToolsDir "ffmpeg.exe"

if (Test-Path $LocalFfmpeg) {
    $env:Path = "$ToolsDir;$env:Path"
}

function Move-ToProject {
    if (-not (Test-Path $ProjectRoot)) {
        throw "프로젝트 폴더를 찾을 수 없습니다: $ProjectRoot"
    }
    Set-Location $ProjectRoot
    Write-Host "현재 프로젝트: $(Get-Location)"
    Write-Host "컴퓨터별 실행환경: $LocalEnvironmentRoot"
}

function Get-ProjectPython {
    return Join-Path $VenvRoot "Scripts\python.exe"
}

function Test-VirtualEnvironment {
    $PythonPath = Get-ProjectPython
    if (-not (Test-Path $PythonPath)) {
        throw "이 컴퓨터의 가상환경이 없습니다. 먼저 .\실행.ps1 setup 을 실행하세요."
    }
}

function Test-Ffmpeg {
    if (-not (Test-Path $LocalFfmpeg)) {
        throw "이 컴퓨터의 FFmpeg가 준비되지 않았습니다. 먼저 .\실행.ps1 setup 을 실행하세요."
    }
    $env:Path = "$ToolsDir;$env:Path"
}

function Initialize-Environment {
    Move-ToProject
    New-Item -ItemType Directory -Path $LocalEnvironmentRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $ToolsDir -Force | Out-Null

    $PythonPath = Get-ProjectPython
    if (-not (Test-Path $PythonPath)) {
        Write-Host "현재 컴퓨터에 가상환경을 생성합니다."
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -m venv $VenvRoot
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv $VenvRoot
        } else {
            throw "Python을 찾을 수 없습니다. Python 설치 후 다시 실행하세요."
        }
        if ($LASTEXITCODE -ne 0) { throw "가상환경 생성에 실패했습니다." }
    } else {
        Write-Host "현재 컴퓨터의 기존 가상환경을 사용합니다."
    }

    & $PythonPath -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip 업데이트에 실패했습니다." }
    & $PythonPath -m pip install -r (Join-Path $ProjectRoot "requirements_scene.txt")
    if ($LASTEXITCODE -ne 0) { throw "필수 패키지 설치에 실패했습니다." }

    $env:KCONTENTS_FFMPEG_DEST = $LocalFfmpeg
    & $PythonPath -c "import os, shutil; from pathlib import Path; import imageio_ffmpeg; src=Path(imageio_ffmpeg.get_ffmpeg_exe()); dst=Path(os.environ['KCONTENTS_FFMPEG_DEST']); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst); print('FFmpeg 준비:', dst)"
    Remove-Item Env:KCONTENTS_FFMPEG_DEST -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -ne 0) { throw "FFmpeg 준비에 실패했습니다." }

    $env:Path = "$ToolsDir;$env:Path"
    & $PythonPath -c "import cv2, numpy, yt_dlp, imageio_ffmpeg; print('cv2:', cv2.__version__); print('numpy:', numpy.__version__); print('yt-dlp:', yt_dlp.version.__version__); print('패키지 확인 완료')"
    if ($LASTEXITCODE -ne 0) { throw "Python 패키지 확인에 실패했습니다." }

    & $LocalFfmpeg -version | Select-Object -First 1
    if ($LASTEXITCODE -ne 0) { throw "FFmpeg 실행 확인에 실패했습니다." }

    Write-Host ""
    Write-Host "환경설정 완료"
    Write-Host "Python: $PythonPath"
    Write-Host "FFmpeg: $LocalFfmpeg"
}

function Invoke-Preprocess {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)
    Move-ToProject
    Test-VirtualEnvironment
    Test-Ffmpeg
    $PythonPath = Get-ProjectPython
    & $PythonPath (Join-Path $ProjectRoot "youtube_scene_preprocess.py") @Arguments
    if ($LASTEXITCODE -ne 0) { throw "영상 전처리 명령이 실패했습니다. 위쪽의 오류 내용을 확인하세요." }
}

function Show-Targets {
    Move-ToProject
    Test-VirtualEnvironment
    $PythonPath = Get-ProjectPython
    & $PythonPath ".\youtube_scene_preprocess.py" --manifest ".\preprocessing_manifest.json" --list-only
    if ($LASTEXITCODE -ne 0) { throw "처리 대상 확인에 실패했습니다." }
}

function Invoke-TestRun {
    Invoke-Preprocess -Arguments @("--manifest", ".\preprocessing_manifest.json", "--output", ".\preprocessed_output", "--rights-confirmed", "--limit", "3")
}

function Invoke-OneVideo {
    Invoke-Preprocess -Arguments @("--manifest", ".\preprocessing_manifest.json", "--output", ".\preprocessed_output", "--rights-confirmed", "--video-id", $VideoId)
}

function Invoke-AllVideos {
    Invoke-Preprocess -Arguments @("--manifest", ".\preprocessing_manifest.json", "--output", ".\preprocessed_output", "--rights-confirmed")
}

function Invoke-WithChromeCookie {
    Invoke-Preprocess -Arguments @("--manifest", ".\preprocessing_manifest.json", "--output", ".\preprocessed_output", "--rights-confirmed", "--video-id", $VideoId, "--cookies-from-browser", "chrome")
}

function Reset-ProcessingResults {
    Move-ToProject
    $OutputRoot = Join-Path $ProjectRoot "preprocessed_output"
    $Targets = @(
        (Join-Path $OutputRoot "preprocessed_segments.json"),
        (Join-Path $OutputRoot "rejected_candidates.json"),
        (Join-Path $OutputRoot "quality_report.csv"),
        (Join-Path $OutputRoot "clips"),
        (Join-Path $OutputRoot "keyframes"),
        (Join-Path $OutputRoot "rejected_keyframes"),
        (Join-Path $OutputRoot "contact_sheets")
    )
    foreach ($Target in $Targets) {
        if (Test-Path $Target) { Remove-Item $Target -Recurse -Force; Write-Host "삭제: $Target" }
    }
    Write-Host "이전 전처리 결과를 초기화했습니다. raw_videos는 유지됩니다."
}

function Show-Menu {
    Write-Host ""
    Write-Host "K-콘텐츠 영상 전처리"
    Write-Host "1. 이 컴퓨터 환경설정"
    Write-Host "2. 처리 대상 확인"
    Write-Host "3. 처음 3개 시험 실행"
    Write-Host "4. 영상 1개 실행"
    Write-Host "5. 전체 영상 실행"
    Write-Host "6. Chrome 쿠키로 영상 1개 실행"
    Write-Host "7. 이전 전처리 결과 초기화"
    Write-Host "0. 종료"
    $Choice = Read-Host "번호를 입력하세요"
    switch ($Choice) {
        "1" { Initialize-Environment }
        "2" { Show-Targets }
        "3" { Invoke-TestRun }
        "4" { $InputVideoId=Read-Host "video_id를 입력하세요"; if ($InputVideoId) {$script:VideoId=$InputVideoId}; Invoke-OneVideo }
        "5" { Invoke-AllVideos }
        "6" { $InputVideoId=Read-Host "video_id를 입력하세요"; if ($InputVideoId) {$script:VideoId=$InputVideoId}; Invoke-WithChromeCookie }
        "7" { Reset-ProcessingResults }
        "0" { return }
        default { throw "올바른 번호를 입력하세요." }
    }
}

switch ($Mode) {
    "setup"  { Initialize-Environment }
    "list"   { Show-Targets }
    "test"   { Invoke-TestRun }
    "one"    { Invoke-OneVideo }
    "all"    { Invoke-AllVideos }
    "cookie" { Invoke-WithChromeCookie }
    "reset"  { Reset-ProcessingResults }
    default   { Show-Menu }
}
