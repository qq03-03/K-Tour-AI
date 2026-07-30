param(
    [ValidateRange(1, 12)]
    [int]$Limit = 12,
    [ValidateRange(1, 10)]
    [int]$TopK = 5,
    [string]$Model = "gpt-5.6-luna",
    [switch]$EnableMetadataRerank
)

$pythonPath = "D:\K-Tour-AI\.venv\Scripts\python.exe"
$testScript = Join-Path $PSScriptRoot "run_synthetic_search_evaluation.py"
$outputPath = Join-Path $PSScriptRoot "output\synthetic_search_evaluation.json"
$temporaryKey = $false

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python 실행 파일을 찾을 수 없습니다: $pythonPath"
}

if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    $secureKey = Read-Host "OPENAI_API_KEY 입력" -AsSecureString
    $credential = [System.Management.Automation.PSCredential]::new(
        "openai",
        $secureKey
    )
    $env:OPENAI_API_KEY = $credential.GetNetworkCredential().Password
    $temporaryKey = $true
}

try {
    $arguments = @(
        $testScript,
        "--limit", $Limit,
        "--top-k", $TopK,
        "--model", $Model,
        "--output", $outputPath
    )
    if ($EnableMetadataRerank) {
        $arguments += "--enable-metadata-rerank"
    }
    & $pythonPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "검색 평가가 종료 코드 $LASTEXITCODE 로 실패했습니다."
    }
}
finally {
    if ($temporaryKey) {
        Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    }
}
