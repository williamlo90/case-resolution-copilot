param(
    [int]$MemoryLimitMb = 700,
    [int]$StartupTimeoutSeconds = 20,
    [int]$RequestTimeoutSeconds = 30,
    [string]$Route = "/sign-in"
)

$ErrorActionPreference = "Stop"

$frontendRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$devRunner = Join-Path $frontendRoot "scripts\dev-safe.mjs"
$stdoutPath = Join-Path $env:TEMP "support-copilot-memory-check.stdout.log"
$stderrPath = Join-Path $env:TEMP "support-copilot-memory-check.stderr.log"
$launcher = $null
$client = $null
$serverProcessId = $null
$previousLocalDevApproval = $env:SUPPORT_COPILOT_ALLOW_LOCAL_DEV
$peakMemoryMb = 0.0
$limitSamples = 0
$limitTriggered = $false
$httpStatus = "not_run"

function Read-ServerMemoryMb {
    param([int]$ProcessId)

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) {
        return 0.0
    }
    return $process.WorkingSet64 / 1MB
}

function Update-MemorySample {
    param([double]$MemoryMb)

    if ($MemoryMb -gt $script:peakMemoryMb) {
        $script:peakMemoryMb = $MemoryMb
    }
    if ($MemoryMb -gt $MemoryLimitMb) {
        $script:limitSamples += 1
    }
    else {
        $script:limitSamples = 0
    }
    if ($script:limitSamples -ge 3) {
        $script:limitTriggered = $true
    }
}

try {
    if (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue) {
        throw "Port 3000 is already in use."
    }
    if (-not (Test-Path -LiteralPath $devRunner)) {
        throw "The low-memory development runner was not found."
    }

    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    $env:SUPPORT_COPILOT_ALLOW_LOCAL_DEV = "1"
    $launcher = Start-Process `
        -FilePath (Get-Command node).Source `
        -ArgumentList @(
            "`"$devRunner`"",
            "--port",
            "3000"
        ) `
        -WorkingDirectory $frontendRoot `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden `
        -PassThru

    $startupDeadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    $listener = $null
    while ((Get-Date) -lt $startupDeadline) {
        $listener = Get-NetTCPConnection `
            -LocalPort 3000 `
            -State Listen `
            -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($listener) {
            break
        }
        if ($launcher.HasExited) {
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $listener) {
        throw "Next.js did not start within $StartupTimeoutSeconds seconds."
    }
    $serverProcessId = $listener.OwningProcess

    Add-Type -AssemblyName System.Net.Http
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.UseProxy = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds($RequestTimeoutSeconds)
    $request = $client.GetAsync("http://localhost:3000$Route")

    while (-not $request.IsCompleted) {
        $memoryMb = Read-ServerMemoryMb -ProcessId $serverProcessId
        Update-MemorySample -MemoryMb $memoryMb
        if ($limitTriggered) {
            break
        }
        Start-Sleep -Milliseconds 250
    }

    if (-not $limitTriggered) {
        try {
            $response = $request.GetAwaiter().GetResult()
            $httpStatus = [int]$response.StatusCode
            $response.Dispose()
        }
        catch {
            $httpStatus = "request_failed"
        }

        for ($sample = 0; $httpStatus -eq 200 -and $sample -lt 10; $sample += 1) {
            $memoryMb = Read-ServerMemoryMb -ProcessId $serverProcessId
            Update-MemorySample -MemoryMb $memoryMb
            if ($limitTriggered) {
                break
            }
            Start-Sleep -Milliseconds 500
        }
    }

    $finalMemoryMb = Read-ServerMemoryMb -ProcessId $serverProcessId
    [pscustomobject]@{
        http_status = $httpStatus
        peak_memory_mb = [math]::Round($peakMemoryMb, 1)
        final_memory_mb = [math]::Round($finalMemoryMb, 1)
        memory_limit_mb = $MemoryLimitMb
        memory_limit_triggered = $limitTriggered
    } | ConvertTo-Json -Compress
}
finally {
    if ($serverProcessId) {
        Stop-Process -Id $serverProcessId -Force -ErrorAction SilentlyContinue
    }
    if ($launcher -and -not $launcher.HasExited) {
        Stop-Process -Id $launcher.Id -Force -ErrorAction SilentlyContinue
    }
    if ($client) {
        $client.Dispose()
    }
    if ($null -eq $previousLocalDevApproval) {
        Remove-Item Env:SUPPORT_COPILOT_ALLOW_LOCAL_DEV -ErrorAction SilentlyContinue
    }
    else {
        $env:SUPPORT_COPILOT_ALLOW_LOCAL_DEV = $previousLocalDevApproval
    }
}
