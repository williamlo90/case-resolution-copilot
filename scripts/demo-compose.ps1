param(
    [ValidateSet('Config', 'Up', 'Smoke', 'Down')]
    [string]$Action = 'Config',
    [switch]$IsolatedHost
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composeFile = Join-Path $repoRoot 'compose.demo.yaml'
$runtimeDirectory = Join-Path $repoRoot 'local/phase6'
$environmentFile = Join-Path $runtimeDirectory 'demo.env'

if ($Action -in @('Up', 'Smoke') -and -not $IsolatedHost) {
    throw 'Starting or probing the demo requires -IsolatedHost; see RESOURCE_SAFETY_POLICY.md.'
}

if ($Action -eq 'Config') {
    $previousPassword = $env:DEMO_POSTGRES_PASSWORD
    try {
        $env:DEMO_POSTGRES_PASSWORD = 'configuration-check-only'
        & docker compose -f $composeFile config --quiet
        if ($LASTEXITCODE -ne 0) { throw 'Compose config validation failed.' }
    }
    finally {
        if ($null -eq $previousPassword) {
            Remove-Item Env:DEMO_POSTGRES_PASSWORD -ErrorAction SilentlyContinue
        }
        else { $env:DEMO_POSTGRES_PASSWORD = $previousPassword }
    }
    Write-Host 'Demo Compose configuration is valid.'
    return
}

if ($Action -eq 'Up' -and -not (Test-Path -LiteralPath $environmentFile)) {
    New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) }
    finally { $generator.Dispose() }
    $password = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
    [System.IO.File]::WriteAllText($environmentFile, "DEMO_POSTGRES_PASSWORD=$password`n")
}
if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw 'Demo environment file is missing. Run -Action Up on the isolated host first.'
}

$composeArgs = @('compose', '--env-file', $environmentFile, '-f', $composeFile)
switch ($Action) {
    'Up' {
        & docker @composeArgs build postgres
        if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL demo image build failed.' }
        & docker @composeArgs build api
        if ($LASTEXITCODE -ne 0) { throw 'Backend demo image build failed.' }
        & docker @composeArgs build frontend
        if ($LASTEXITCODE -ne 0) { throw 'Frontend demo image build failed.' }
        & docker @composeArgs up --no-build --detach --wait --wait-timeout 180
        if ($LASTEXITCODE -ne 0) { throw 'Demo startup failed. Inspect Compose logs on the isolated host.' }
        Write-Host 'Synthetic demo is ready at http://127.0.0.1:3000/cases.'
    }
    'Smoke' {
        $ready = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health/ready' -TimeoutSec 10
        if ($ready.status -ne 'ready' -or $ready.dependencies.database.status -ne 'healthy') {
            throw 'The API or demo database is not ready.'
        }
        $page = Invoke-WebRequest -Uri 'http://127.0.0.1:3000/cases' -TimeoutSec 15 -UseBasicParsing
        if ($page.StatusCode -ne 200) { throw 'The demo frontend did not return HTTP 200.' }
        Write-Host 'API readiness and frontend case page passed.'
    }
    'Down' {
        & docker @composeArgs down
        if ($LASTEXITCODE -ne 0) { throw 'Demo shutdown failed.' }
        Write-Host 'Demo services stopped. The named database volume is retained.'
    }
}
