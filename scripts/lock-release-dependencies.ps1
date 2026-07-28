param(
    [string]$Python = $env:AURA_PYTHON
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not $Python) {
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path -LiteralPath $candidate) {
        $Python = $candidate
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) {
    throw "Set AURA_PYTHON or -Python to a Python 3.12 interpreter."
}

$version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne "3.12") {
    throw "Release lock generation requires Python 3.12; '$Python' reports $version."
}

& $Python -m pip install --disable-pip-version-check "pip-tools==7.6.0"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to install pip-tools (exit code $LASTEXITCODE)."
}

Push-Location $root
try {
    & $Python -m piptools compile `
        --allow-unsafe `
        --resolver=backtracking `
        --strip-extras `
        --output-file=requirements-release.lock `
        requirements-build.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency lock generation failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}

Write-Host "Updated requirements-release.lock with Python 3.12."
