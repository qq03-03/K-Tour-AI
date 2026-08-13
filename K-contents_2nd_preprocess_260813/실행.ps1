param(
    [Parameter(Position=0)]
    [ValidateSet("setup","check","list","run","one","rebuild","fresh")]
    [string]$Mode = "check",

    [string]$SourceSegmentId = "",
    [switch]$RightsConfirmed,
    [switch]$SkipDownload,
    [switch]$Force,
    [string]$CookiesFromBrowser = "",
    [int]$Limit = 0,

    # fresh 실행 시 다운로드된 원본 영상은 기본적으로 보존합니다.
    # 원본까지 모두 삭제하고 다시 받을 때만 사용하세요.
    [switch]$DeleteOriginalVideos
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$OutputDir = Join-Path $Root "preprocessed_output"
$OriginalVideoDir = Join-Path $OutputDir "original_videos"

function Find-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.11 --version *> $null
        if ($LASTEXITCODE -eq 0) { return @("py","-3.11") }

        & py -3 --version *> $null
        if ($LASTEXITCODE -eq 0) { return @("py","-3") }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }

    throw "Python을 찾을 수 없습니다. Python 3.11 설치를 권장합니다."
}

function Clear-PreprocessedOutput {
    param([switch]$DeleteOriginals)

    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Force -Path $OriginalVideoDir | Out-Null
        return
    }

    if ($DeleteOriginals) {
        Write-Host "`n[초기화] preprocessed_output 전체 삭제" -ForegroundColor Yellow
        Remove-Item $OutputDir -Recurse -Force
        New-Item -ItemType Directory -Force -Path $OriginalVideoDir | Out-Null
        return
    }

    # 빠른 재실행을 위해 original_videos만 보존하고
    # 기존 전처리 산출물은 전부 초기화합니다.
    Write-Host "`n[초기화] 기존 전처리 결과 삭제" -ForegroundColor Yellow
    Write-Host "original_videos는 재다운로드 시간을 줄이기 위해 유지합니다." -ForegroundColor DarkYellow

    $targets = @(
        (Join-Path $OutputDir "preprocessed_video"),
        (Join-Path $OutputDir "keyframes"),
        (Join-Path $OutputDir "_internal"),
        (Join-Path $OutputDir "processing_results.json"),
        (Join-Path $OutputDir "preprocessed_segments.json")
    )

    foreach ($target in $targets) {
        if (Test-Path $target) {
            Remove-Item $target -Recurse -Force
        }
    }

    New-Item -ItemType Directory -Force -Path $OriginalVideoDir | Out-Null
}

if ($Mode -eq "setup") {
    if (-not (Test-Path $Python)) {
        $Base = Find-Python

        if ($Base.Count -eq 2) {
            & $Base[0] $Base[1] -m venv ".\.venv"
        }
        else {
            & $Base[0] -m venv ".\.venv"
        }

        if ($LASTEXITCODE -ne 0) {
            throw "가상환경 생성 실패"
        }
    }

    & $Python -m pip install --upgrade pip setuptools wheel
    & $Python -m pip install --no-cache-dir -r ".\requirements.txt"

    if ($LASTEXITCODE -ne 0) {
        throw "패키지 설치 실패"
    }

    New-Item -ItemType Directory -Force -Path $OriginalVideoDir | Out-Null
    Write-Host "`n설치 완료" -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $Python)) {
    throw ".venv가 없습니다. 먼저 .\실행.ps1 setup 을 실행하세요."
}

if ($Mode -eq "rebuild") {
    & $Python ".\build_manifest.py"
    if ($LASTEXITCODE -ne 0) { throw "매니페스트 재생성 실패" }
    exit 0
}

& $Python -c "import numpy,cv2,imageio_ffmpeg; print('numpy',numpy.__version__); print('opencv',cv2.__version__); print('ffmpeg',imageio_ffmpeg.get_ffmpeg_exe())"
if ($LASTEXITCODE -ne 0) { throw "환경 확인 실패" }

$Args2 = @(
    ".\video_preprocess.py",
    "--manifest", ".\preprocessing_manifest.json",
    "--output", ".\preprocessed_output"
)

if ($SkipDownload) { $Args2 += "--skip-download" }
if ($Force) { $Args2 += "--force" }
if ($CookiesFromBrowser) { $Args2 += @("--cookies-from-browser", $CookiesFromBrowser) }
if ($Limit -gt 0) { $Args2 += @("--limit", $Limit) }

switch ($Mode) {
    "check" {
        & $Python ".\video_preprocess.py" `
            --manifest ".\preprocessing_manifest.json" `
            --output ".\preprocessed_output" `
            --dry-run `
            --limit 3
    }

    "list" {
        $Args2 += "--list-only"
        & $Python @Args2
    }

    "run" {
        if (-not $RightsConfirmed) {
            throw "영상 사용 권한을 확인했다면 -RightsConfirmed를 추가하세요."
        }

        Write-Host "`n[전체 전처리] 완료된 것은 이어서 처리합니다." -ForegroundColor Green
        $Args2 += "--rights-confirmed"
        & $Python @Args2
    }

    "fresh" {
        if (-not $RightsConfirmed) {
            throw "영상 사용 권한을 확인했다면 -RightsConfirmed를 추가하세요."
        }

        Clear-PreprocessedOutput -DeleteOriginals:$DeleteOriginalVideos

        $FreshArgs = @(
            ".\video_preprocess.py",
            "--manifest", ".\preprocessing_manifest.json",
            "--output", ".\preprocessed_output",
            "--rights-confirmed",
            "--force"
        )

        if ($SkipDownload) {
            $FreshArgs += "--skip-download"
        }

        if ($CookiesFromBrowser) {
            $FreshArgs += @("--cookies-from-browser", $CookiesFromBrowser)
        }

        Write-Host "`n========================================================" -ForegroundColor Cyan
        Write-Host " 전체 전처리를 처음부터 다시 시작합니다." -ForegroundColor Cyan
        Write-Host " 기존 clip / keyframe / 결과 JSON은 초기화되었습니다." -ForegroundColor Cyan

        if ($DeleteOriginalVideos) {
            Write-Host " 원본 영상도 삭제했으므로 다시 다운로드합니다." -ForegroundColor Yellow
        }
        else {
            Write-Host " original_videos는 유지하여 재다운로드를 최소화합니다." -ForegroundColor Green
        }

        Write-Host "========================================================`n" -ForegroundColor Cyan

        & $Python @FreshArgs
    }

    "one" {
        if (-not $SourceSegmentId) {
            throw "-SourceSegmentId를 입력하세요. 예: V001_P001_S001"
        }

        if (-not $RightsConfirmed) {
            throw "영상 사용 권한을 확인했다면 -RightsConfirmed를 추가하세요."
        }

        $Args2 += @(
            "--source-segment-id", $SourceSegmentId,
            "--rights-confirmed"
        )

        & $Python @Args2
    }
}

if ($LASTEXITCODE -ne 0) {
    throw "실행 실패"
}
