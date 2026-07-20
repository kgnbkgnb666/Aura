$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$candidates = @()

if ($env:AURA_PYTHON) {
    $candidates += $env:AURA_PYTHON
}
$candidates += Join-Path $root ".venv\Scripts\python.exe"
if ($env:USERPROFILE) {
    $candidates += Join-Path $env:USERPROFILE ".conda\envs\aura\python.exe"
}
if ($env:CONDA_PREFIX) {
    if ((Split-Path $env:CONDA_PREFIX -Leaf) -eq "aura") {
        $candidates += Join-Path $env:CONDA_PREFIX "python.exe"
    } else {
        $candidates += Join-Path $env:CONDA_PREFIX "envs\aura\python.exe"
    }
}

$python = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $python) {
    throw "Aura Python environment not found. Set AURA_PYTHON or create .venv / Conda env named aura."
}

Write-Host "Building Aura sidecar with $python"
Push-Location $root
try {
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath "src-tauri/binaries" `
        --workpath "build/pyinstaller" `
        "aura-sidecar.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}
