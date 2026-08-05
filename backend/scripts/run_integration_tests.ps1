[CmdletBinding()]
param(
    [string]$EnvFile = (Join-Path $PSScriptRoot "..\.env.test.local"),
    [switch]$ConnectionOnly,
    [switch]$ConfirmDestructiveDisposableDatabase,
    [switch]$ShowCapturedOutput,
    [string[]]$TestPath = @("tests\integration")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-SanitizedOutput {
    param(
        [object[]]$Entries,
        [string[]]$Secrets
    )

    foreach ($entry in $Entries) {
        $safe = [string]$entry
        foreach ($secret in $Secrets) {
            if ($secret.Length -ge 4) {
                $safe = $safe.Replace($secret, "<redacted>")
            }
        }
        $safe = [regex]::Replace(
            $safe,
            "npg_[A-Za-z0-9_-]+",
            "<redacted NEON_PASSWORD>"
        )
        $safe = [regex]::Replace(
            $safe,
            "postgresql(?:\+psycopg)?://[^\s]+",
            "<redacted DATABASE_URL>"
        )
        Write-Output $safe
    }
}

if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    Write-Output "Integration env file was not found."
    exit 2
}

try {
    $line = Get-Content -LiteralPath $EnvFile |
        Where-Object { $_ -match "^\s*TEST_DATABASE_URL\s*=" } |
        Select-Object -First 1
    if (-not $line) {
        Write-Output "TEST_DATABASE_URL was not found in the integration env file."
        exit 2
    }
    $scopeLine = Get-Content -LiteralPath $EnvFile |
        Where-Object { $_ -match "^\s*TEST_DATABASE_SCOPE\s*=" } |
        Select-Object -First 1
    $endpointLine = Get-Content -LiteralPath $EnvFile |
        Where-Object { $_ -match "^\s*TEST_DATABASE_ENDPOINT_ID\s*=" } |
        Select-Object -First 1
    if (-not $scopeLine -or -not $endpointLine) {
        Write-Output (
            "Integration tests require TEST_DATABASE_SCOPE=disposable and an explicit " +
            "TEST_DATABASE_ENDPOINT_ID."
        )
        exit 2
    }
    $scope = ($scopeLine -split "=", 2)[1].Trim().Trim('"').Trim("'")
    $expectedEndpointId = ($endpointLine -split "=", 2)[1].Trim().Trim('"').Trim("'")
    if ($scope -ne "disposable") {
        Write-Output "Refusing destructive integration tests outside a disposable database branch."
        exit 2
    }
    if (-not $ConnectionOnly -and -not $ConfirmDestructiveDisposableDatabase) {
        Write-Output (
            "Pass -ConfirmDestructiveDisposableDatabase only after verifying the Neon branch " +
            "is disposable."
        )
        exit 2
    }

    $value = ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
    $secrets = [System.Collections.Generic.List[string]]::new()
    $secrets.Add($value)

    if ($value.StartsWith("postgresql://")) {
        $value = "postgresql+psycopg://" + $value.Substring("postgresql://".Length)
        $secrets.Add($value)
    }
    elseif (-not $value.StartsWith("postgresql+psycopg://")) {
        Write-Output "TEST_DATABASE_URL must be a PostgreSQL connection string."
        exit 2
    }
    if (-not $value.Contains("@ep-")) {
        Write-Output "TEST_DATABASE_URL is missing the @ep- separator before the Neon host."
        Write-Output "Copy the entire direct connection string instead of replacing only its password."
        exit 2
    }

    $match = [regex]::Match(
        $value,
        "^postgresql\+psycopg://(?<username>[^:/?#]+):(?<password>[^@/?#]+)" +
        "@(?<host>[^/?#]+)(?<database>/[^?]+)\?(?<query>.+)$"
    )
    if (-not $match.Success -or $value -match "USERNAME|PASSWORD|@HOST") {
        Write-Output "TEST_DATABASE_URL format is invalid."
        Write-Output "Copy a fresh direct Neon URL and preserve the @ep- host separator."
        exit 2
    }

    $encodedPassword = $match.Groups["password"].Value
    $secrets.Add($encodedPassword)
    $secrets.Add([System.Uri]::UnescapeDataString($encodedPassword))

    $hostName = $match.Groups["host"].Value
    if ($hostName -match "-pooler" -or $hostName -notmatch "^ep-.+\.neon\.tech$") {
        Write-Output "TEST_DATABASE_URL must use a direct Neon endpoint."
        exit 2
    }
    $actualEndpointId = ($hostName -split "\.", 2)[0]
    if (
        $expectedEndpointId -notmatch "^ep-[a-z0-9-]+$" -or
        $actualEndpointId -ne $expectedEndpointId
    ) {
        Write-Output "TEST_DATABASE_ENDPOINT_ID does not match the direct Neon URL."
        exit 2
    }

    $query = $match.Groups["query"].Value
    if ($query -notmatch "(^|&)sslmode=require($|&)") {
        Write-Output "TEST_DATABASE_URL must require TLS."
        exit 2
    }

    $backendRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
    $python = Join-Path $backendRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        Write-Output "Backend Python environment was not found."
        exit 2
    }
    foreach ($path in $TestPath) {
        if ($path -notmatch "^tests[\\/]integration") {
            Write-Output "The redacting runner accepts only backend integration test paths."
            exit 2
        }
    }

    $env:TEST_DATABASE_URL = $value
    $env:SUPPORT_COPILOT_ALLOW_DESTRUCTIVE_TEST_DATABASE = "1"
    try {
        Push-Location $backendRoot
        $nativeErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        if ($ConnectionOnly) {
            $probe = @'
import os
import sys

from sqlalchemy import create_engine, text

engine = create_engine(
    os.environ["TEST_DATABASE_URL"],
    hide_parameters=True,
    pool_pre_ping=True,
)
try:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT current_setting('server_version'), current_database(),
                       EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')
                """
            )
        ).one()
    print("Database connection: ok")
    print(f"PostgreSQL: {row[0]}")
    print(f"Database: {row[1]}")
    print(f"pgvector: {'active' if row[2] else 'missing'}")
except Exception:
    print("Database connection: failed")
    sys.exit(1)
finally:
    engine.dispose()
'@
            $output = $probe | & $python - 2>&1
        }
        else {
            $pytestArguments = @("-m", "pytest", $TestPath, "-q", "--maxfail=1", "--tb=short")
            if ($ShowCapturedOutput) {
                $pytestArguments += "-s"
            }
            $output = & $python @pytestArguments 2>&1
        }
        $testExitCode = $LASTEXITCODE
        $ErrorActionPreference = $nativeErrorPreference
    }
    finally {
        $ErrorActionPreference = "Stop"
        Pop-Location
        Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
        Remove-Item Env:SUPPORT_COPILOT_ALLOW_DESTRUCTIVE_TEST_DATABASE -ErrorAction SilentlyContinue
    }

    Write-SanitizedOutput -Entries $output -Secrets $secrets.ToArray()
    exit $testExitCode
}
catch {
    Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:SUPPORT_COPILOT_ALLOW_DESTRUCTIVE_TEST_DATABASE -ErrorAction SilentlyContinue
    Write-Output "The integration test runner stopped before pytest completed."
    exit 2
}
