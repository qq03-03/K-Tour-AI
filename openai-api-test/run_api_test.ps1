param(
    [ValidateSet("ping", "structured", "all")]
    [string]$Stage = "all",
    [string]$Model = "gpt-5.6-luna"
)

$pythonPath = "D:\K-Tour-AI\.venv\Scripts\python.exe"
$testScript = Join-Path $PSScriptRoot "run_synthetic_api_test.py"
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
    & $pythonPath $testScript --stage $Stage --model $Model
    if ($LASTEXITCODE -ne 0) {
        throw "API 테스트가 종료 코드 $LASTEXITCODE 로 실패했습니다."
    }
}
finally {
    if ($temporaryKey) {
        Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    }
}
