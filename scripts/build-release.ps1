$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$buildTemp = Join-Path $root "build\temp"
New-Item -ItemType Directory -Force -Path $buildTemp | Out-Null

$package = Get-Content -Raw -Encoding utf8 (Join-Path $root "package.json") | ConvertFrom-Json
$version = [string]$package.version
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
    (Join-Path $PSScriptRoot "sync-version.ps1") `
    -Version $version
if ($LASTEXITCODE -ne 0) {
    throw "Version synchronization failed with exit code $LASTEXITCODE"
}

$env:TEMP = $buildTemp
$env:TMP = $buildTemp

$forbiddenNames = @(
    "config.local.json",
    "history.sqlite",
    "history.sqlite-wal",
    "history.sqlite-shm"
)
$resourceRoots = @(
    (Join-Path $root "src-tauri\resources"),
    (Join-Path $root "src-tauri\binaries")
)

foreach ($resourceRoot in $resourceRoots) {
    if (-not (Test-Path -LiteralPath $resourceRoot)) {
        continue
    }
    $forbidden = Get-ChildItem -LiteralPath $resourceRoot -Recurse -Force | Where-Object {
        $_.Name -in $forbiddenNames -or $_.Name -eq ".aura-local"
    }
    if ($forbidden) {
        $paths = ($forbidden | ForEach-Object { $_.FullName }) -join [Environment]::NewLine
        throw "Refusing to build: private runtime data was found in package resources:$([Environment]::NewLine)$paths"
    }
}

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
