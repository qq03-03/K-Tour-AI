[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Metadata,

    [string]$Accepted = "",

    [string[]]$ExistingCoordinates = @(),

    [string]$OutputRoot = "",

    [switch]$RunCoordinateApi,

    [switch]$RunTranslations,

    [switch]$RunTranslationQa,

    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONIOENCODING = "utf-8"
$projectRoot = Split-Path -Parent $PSScriptRoot
$searchService = Join-Path $projectRoot "search-service"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python was not found: $python"
}
if (-not (Test-Path -LiteralPath $Metadata -PathType Leaf)) {
    throw "Metadata file was not found: $Metadata"
}
if ($Accepted -and -not (Test-Path -LiteralPath $Accepted -PathType Leaf)) {
    throw "Accepted-segment file was not found: $Accepted"
}
foreach ($coordinatePath in $ExistingCoordinates) {
    if (-not (Test-Path -LiteralPath $coordinatePath -PathType Leaf)) {
        throw "Existing coordinate file was not found: $coordinatePath"
    }
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $projectRoot "output\frontend_data"
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$coordinateReview = Join-Path $OutputRoot "places_coordinates_review.csv"
$coordinateReport = Join-Path $OutputRoot "frontend_data_prepare_report.json"
$flatMetadata = Join-Path $OutputRoot "accepted_metadata_flat.json"
$coordinateCandidates = Join-Path $OutputRoot "places_coordinates_kakao_candidates.csv"
$translationSource = Join-Path $OutputRoot "display_translation_source.json"
$translations = Join-Path $OutputRoot "display_translations.json"
$translationQa = Join-Path $OutputRoot "display_translation_qa.json"

function Invoke-PythonStep {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    Write-Host ""
    Write-Host "=== $Label ==="
    & $python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed (exit code: $LASTEXITCODE)"
    }
}

$prepareArgs = @(
    (Join-Path $PSScriptRoot "prepare_place_coordinate_input.py"),
    "--metadata", $Metadata,
    "--output", $coordinateReview,
    "--flat-metadata-output", $flatMetadata,
    "--report", $coordinateReport
)
if ($Accepted) {
    $prepareArgs += @("--accepted", $Accepted)
}
foreach ($coordinatePath in $ExistingCoordinates) {
    $prepareArgs += @("--existing", $coordinatePath)
}
if ($Overwrite) {
    $prepareArgs += "--overwrite"
}
Invoke-PythonStep -Label "Prepare accepted places and coordinate input" -Arguments $prepareArgs

$coordinateArgs = @(
    (Join-Path $PSScriptRoot "lookup_kakao_coordinates.py"),
    "--input", $coordinateReview,
    "--output", $coordinateCandidates,
    "--max-results", "5"
)
if (-not $RunCoordinateApi) {
    $coordinateArgs += "--plan-only"
}
if ($Overwrite) {
    $coordinateArgs += "--overwrite"
}
Invoke-PythonStep -Label "Prepare Kakao coordinate candidates" -Arguments $coordinateArgs

$translationPrepareArgs = @(
    (Join-Path $searchService "run_prepare_display_translations.py"),
    "--metadata", $flatMetadata,
    "--output", $translationSource
)
if ($Overwrite) {
    $translationPrepareArgs += "--overwrite"
}
Invoke-PythonStep -Label "Prepare display-translation input" -Arguments $translationPrepareArgs

if ($RunTranslations) {
    if (-not $env:OPENAI_API_KEY) {
        throw "RunTranslations requires the OPENAI_API_KEY environment variable."
    }
    $translationArgs = @(
        (Join-Path $searchService "run_translate_display_metadata.py"),
        "--source", $translationSource,
        "--output", $translations
    )
    if ($Overwrite) {
        $translationArgs += "--overwrite"
    }
    Invoke-PythonStep -Label "Generate OpenAI display translations" -Arguments $translationArgs

    Invoke-PythonStep -Label "Validate display-translation IDs and fields" -Arguments @(
        (Join-Path $searchService "run_validate_display_translations.py"),
        "--metadata", $flatMetadata,
        "--translations", $translations
    )
}

if ($RunTranslationQa) {
    if (-not $RunTranslations -and -not (Test-Path -LiteralPath $translations -PathType Leaf)) {
        throw "Translation QA requires an existing translation file."
    }
    if (-not $env:OPENAI_API_KEY) {
        throw "RunTranslationQa requires the OPENAI_API_KEY environment variable."
    }
    Invoke-PythonStep -Label "Run OpenAI display-translation QA" -Arguments @(
        (Join-Path $searchService "run_display_translation_qa.py"),
        "--source", $translationSource,
        "--translations", $translations,
        "--output", $translationQa
    )
}

Write-Host ""
Write-Host "=== Frontend data automation complete ==="
Write-Host "Output directory: $OutputRoot"
Write-Host "Source metadata/keyframes modified: no"
if (-not $RunCoordinateApi) {
    Write-Host "Kakao API: not called (plan-only)"
}
if (-not $RunTranslations) {
    Write-Host "OpenAI translation API: not called"
}
