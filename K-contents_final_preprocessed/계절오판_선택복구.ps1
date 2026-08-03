param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

$LocalPython = Join-Path $env:LOCALAPPDATA "K-contents-preprocessing\.venv\Scripts\python.exe"
$ProjectPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (Test-Path $LocalPython) {
    $PythonPath = $LocalPython
} elseif (Test-Path $ProjectPython) {
    $PythonPath = $ProjectPython
} else {
    throw "Python 가상환경을 찾을 수 없습니다. 기존 .venv 또는 실행.ps1 setup을 확인하세요."
}

$Arguments = @(
    ".\계절오판_선택복구.py",
    "--project-root",
    "."
)

if ($DryRun) {
    $Arguments += "--dry-run"
}

& $PythonPath @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "계절 오판 선택 복구에 실패했습니다."
}
