$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$candidates = @()

if ($env:AURA_PYTHON) {
    $candidates += $env:AURA_PYTHON
}
$candidates += Join-Path $root ".venv\Scripts\python.exe"
$candidates += Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
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

$bootstrapPython = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $bootstrapPython) {
    throw "Python 3.12 was not found. Set AURA_PYTHON to a Python 3.12 interpreter."
}

$bootstrapVersion = & $bootstrapPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $bootstrapVersion.Trim() -ne "3.12") {
    throw "Release builds require Python 3.12; '$bootstrapPython' reports $bootstrapVersion."
}

$releaseEnv = Join-Path $root ".venv-release"
$python = Join-Path $releaseEnv "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creating isolated Python 3.12 release environment at $releaseEnv"
    & $bootstrapPython -m venv $releaseEnv
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create the release environment (exit code $LASTEXITCODE)."
    }
}

$lockFile = Join-Path $root "requirements-release.lock"
if (-not (Test-Path -LiteralPath $lockFile)) {
    throw "Missing release dependency lock: $lockFile"
}

Write-Host "Synchronizing locked release dependencies"
& $python -m pip install --disable-pip-version-check --no-deps --requirement $lockFile
if ($LASTEXITCODE -ne 0) {
    throw "Locked dependency installation failed with exit code $LASTEXITCODE"
}

Write-Host "Building Aura sidecar with isolated environment $python"
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
