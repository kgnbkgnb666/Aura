param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Version
)

$ErrorActionPreference = "Stop"

if ($Version -notmatch '^\d+\.\d+\.\d+([.-][0-9A-Za-z.-]+)?$') {
    throw "Invalid version '$Version'. Use semantic versioning, for example 0.1.3."
}

$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    # npm updates package.json and package-lock.json together.
    & npm.cmd version $Version --no-git-tag-version --allow-same-version
    if ($LASTEXITCODE -ne 0) {
        throw "npm version failed with exit code $LASTEXITCODE"
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $PSScriptRoot "sync-version.ps1") `
        -Version $Version
    if ($LASTEXITCODE -ne 0) {
        throw "Version synchronization failed with exit code $LASTEXITCODE"
    }

    Write-Host "Aura version synchronized to $Version."
} finally {
    Pop-Location
}
