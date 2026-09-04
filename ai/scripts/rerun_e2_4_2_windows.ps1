param(
    [Parameter(Mandatory = $true)]
    [string]$FixtureManifest,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,

    [string]$PythonExecutable = "",
    [string]$TesseractExecutable = "",
    [switch]$Resume
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Contract = Join-Path `
    $ProjectRoot `
    "config\experiments\e2_4_2_ocr_robustness.json"
$Runner = Join-Path `
    $ProjectRoot `
    "ai\scripts\benchmark_e2_4_price_axis_ocr.py"
$FixtureManifest = (Resolve-Path -LiteralPath $FixtureManifest).Path
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)

if (-not $PythonExecutable) {
    $PythonCandidates = @(
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
        (Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe")
    )
    $PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $PythonCommand) {
        $PythonCandidates += $PythonCommand.Source
    }
    $PythonExecutable = $PythonCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
}

if (-not $TesseractExecutable) {
    $TesseractCandidates = @()
    $TesseractCommand = Get-Command tesseract.exe -ErrorAction SilentlyContinue
    if ($null -ne $TesseractCommand) {
        $TesseractCandidates += $TesseractCommand.Source
    }
    $TesseractCandidates += @(
        "C:\Program Files\Tesseract-OCR\tesseract.exe",
        "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        (Join-Path `
            $env:LOCALAPPDATA `
            "Programs\Tesseract-OCR\tesseract.exe"),
        (Join-Path `
            $env:LOCALAPPDATA `
            "Microsoft\WinGet\Links\tesseract.exe"),
        (Join-Path `
            $env:USERPROFILE `
            "scoop\apps\tesseract\current\tesseract.exe"),
        "C:\ProgramData\chocolatey\bin\tesseract.exe"
    )
    $TesseractExecutable = $TesseractCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
}

foreach ($RequiredPath in @(
    $PythonExecutable,
    $TesseractExecutable,
    $Contract,
    $Runner,
    $FixtureManifest
)) {
    if (-not $RequiredPath -or -not (
        Test-Path -LiteralPath $RequiredPath -PathType Leaf
    )) {
        throw "Required path not found: $RequiredPath"
    }
}

if ((Test-Path -LiteralPath $OutputDirectory) -and -not $Resume) {
    throw (
        "Output directory already exists. Choose a new directory or use " +
        "-Resume: $OutputDirectory"
    )
}

$env:PYTHONPATH = Join-Path $ProjectRoot "backend"
$env:AI_TDSS_TESSERACT_CMD = $TesseractExecutable

& $TesseractExecutable --version | Select-Object -First 1
& $PythonExecutable -c `
    "import pytesseract; print('pytesseract', pytesseract.__version__)"

$BenchmarkArguments = @(
    $Runner,
    "--contract", $Contract,
    "--fixture-manifest", $FixtureManifest,
    "--output-dir", $OutputDirectory,
    "--tesseract-cmd", $TesseractExecutable,
    "--progress-every", "8",
    "--fail-fast"
)
if ($Resume) {
    $BenchmarkArguments += "--resume"
}

& $PythonExecutable @BenchmarkArguments
if ($LASTEXITCODE -ne 0) {
    throw "E2.4.2 benchmark failed with exit code $LASTEXITCODE."
}

$Summary = Join-Path `
    $OutputDirectory `
    "e2_4_2_ocr_benchmark_summary.md"
Get-Content -LiteralPath $Summary -Encoding UTF8 -Raw

$OutputParent = Split-Path -Parent $OutputDirectory
$OutputName = Split-Path -Leaf $OutputDirectory
$ResultsZip = Join-Path `
    $OutputParent `
    "${OutputName}_windows_results.zip"
Compress-Archive `
    -Path (Join-Path $OutputDirectory "*") `
    -DestinationPath $ResultsZip `
    -Force

$Digest = Get-FileHash -LiteralPath $ResultsZip -Algorithm SHA256
"Results ZIP: $ResultsZip"
"SHA256     : $($Digest.Hash)"
