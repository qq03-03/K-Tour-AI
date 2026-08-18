param(
    [string]$TextEmbeddings = "",
    [string]$ImageEmbeddings = ""
)

$bundleRoot = Split-Path -Parent $PSScriptRoot
$python = "D:\K-Tour-AI\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

$argsList = @(
    (Join-Path $PSScriptRoot "validate_embedding_delivery.py"),
    "--metadata", (Join-Path $bundleRoot "data\metadata_517_no_P063.json"),
    "--translations", (Join-Path $bundleRoot "data\display_translations_517_no_P063.json"),
    "--coordinates", (Join-Path $bundleRoot "data\places_coordinates_517.json"),
    "--keyframes-zip", "C:\Users\human\Documents\K-Tour-AI\codex_staging\no_p063_517\keyframes_517_no_P063.zip",
    "--expected-count", "517",
    "--report", (Join-Path $bundleRoot "reports\post_embedding_validation.json")
)

if ($TextEmbeddings) {
    $argsList += @("--text-embeddings", $TextEmbeddings)
}
if ($ImageEmbeddings) {
    $argsList += @("--image-embeddings", $ImageEmbeddings)
}

& $python @argsList
exit $LASTEXITCODE
