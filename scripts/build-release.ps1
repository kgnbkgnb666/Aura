$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$buildTemp = Join-Path $root "build\temp"
New-Item -ItemType Directory -Force -Path $buildTemp | Out-Null

$env:TEMP = $buildTemp
$env:TMP = $buildTemp

Push-Location $root
try {
    & npm.cmd run build:sidecar
    if ($LASTEXITCODE -ne 0) {
        throw "Sidecar build failed with exit code $LASTEXITCODE"
    }

    & npx.cmd tauri build
    if ($LASTEXITCODE -ne 0) {
        throw "Tauri build failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}
