param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"

if ($Version -notmatch '^\d+\.\d+\.\d+([.-][0-9A-Za-z.-]+)?$') {
    throw "Invalid version '$Version'."
}

$root = Split-Path -Parent $PSScriptRoot
$tauriPath = Join-Path $root "src-tauri\tauri.conf.json"
$cargoPath = Join-Path $root "src-tauri\Cargo.toml"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$tauri = Get-Content -Raw -Encoding utf8 $tauriPath
$tauri = [regex]::Replace(
    $tauri,
    '("version"\s*:\s*")[^"]+(")',
    { param($match) $match.Groups[1].Value + $Version + $match.Groups[2].Value },
    1
)
[System.IO.File]::WriteAllText($tauriPath, $tauri, $utf8NoBom)

$cargo = Get-Content -Raw -Encoding utf8 $cargoPath
$cargo = [regex]::Replace(
    $cargo,
    '(?m)^version\s*=\s*"[^"]+"',
    ('version = "' + $Version + '"'),
    1
)
[System.IO.File]::WriteAllText($cargoPath, $cargo, $utf8NoBom)

Write-Host "Synchronized Tauri and Cargo versions to $Version."
