param(
    [string]$FrontendUrl = "https://ai-support-escalation-copilot.vercel.app",
    [string]$BackendUrl = "https://ai-support-escalation-copilot-6s7o.vercel.app",
    [string]$ExpectedRevision = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

if ([string]::IsNullOrWhiteSpace($ExpectedRevision)) {
    $ExpectedRevision = (& git rev-parse HEAD).Trim().ToLowerInvariant()
}
if ($ExpectedRevision -notmatch '^[0-9a-f]{40}$') {
    throw "ExpectedRevision must be a full Git commit SHA."
}

function Get-HeaderValue {
    param(
        [System.Net.Http.HttpResponseMessage]$Response,
        [string]$Name
    )

    $values = $null
    if ($Response.Headers.TryGetValues($Name, [ref]$values)) {
        return ($values -join ", ")
    }
    if ($Response.Content.Headers.TryGetValues($Name, [ref]$values)) {
        return ($values -join ", ")
    }
    return $null
}

function Assert-HeaderEquals {
    param(
        [System.Net.Http.HttpResponseMessage]$Response,
        [string]$Name,
        [string]$Expected
    )

    $actual = Get-HeaderValue -Response $Response -Name $Name
    if ($actual -ne $Expected) {
        throw "$Name expected '$Expected' but received '$actual'."
    }
}

function Assert-HeaderContains {
    param(
        [System.Net.Http.HttpResponseMessage]$Response,
        [string]$Name,
        [string]$ExpectedFragment
    )

    $actual = Get-HeaderValue -Response $Response -Name $Name
    if (-not $actual -or -not $actual.Contains($ExpectedFragment)) {
        throw "$Name does not contain '$ExpectedFragment'."
    }
}

$handler = [System.Net.Http.HttpClientHandler]::new()
$handler.AllowAutoRedirect = $false
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds(20)

try {
    $frontend = $client.GetAsync("$($FrontendUrl.TrimEnd('/'))/cases").GetAwaiter().GetResult()
    if ([int]$frontend.StatusCode -notin @(307, 308)) {
        throw "Frontend /cases expected a single authentication redirect but returned $([int]$frontend.StatusCode)."
    }
    $location = Get-HeaderValue -Response $frontend -Name "Location"
    if ($location -ne "/sign-in") {
        throw "Frontend /cases redirected to '$location' instead of '/sign-in'."
    }
    Assert-HeaderEquals $frontend "X-Content-Type-Options" "nosniff"
    Assert-HeaderEquals $frontend "X-Frame-Options" "DENY"
    Assert-HeaderEquals $frontend "X-Robots-Tag" "noindex, nofollow, noarchive"
    Assert-HeaderContains $frontend "Content-Security-Policy" "'strict-dynamic'"
    Assert-HeaderContains $frontend "Content-Security-Policy" "frame-ancestors 'none'"
    Assert-HeaderEquals $frontend "X-Source-Revision" $ExpectedRevision

    $ready = $client.GetAsync("$($BackendUrl.TrimEnd('/'))/api/health/ready").GetAwaiter().GetResult()
    if ([int]$ready.StatusCode -ne 200) {
        throw "Backend readiness returned $([int]$ready.StatusCode)."
    }
    $readyBody = $ready.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
    if ($readyBody.status -ne "ready" -or $readyBody.dependencies.database.status -ne "healthy") {
        throw "Backend readiness did not report a healthy database."
    }
    Assert-HeaderEquals $ready "Cache-Control" "no-store"
    Assert-HeaderEquals $ready "X-Content-Type-Options" "nosniff"
    Assert-HeaderEquals $ready "X-Frame-Options" "DENY"
    Assert-HeaderEquals $ready "X-Robots-Tag" "noindex, nofollow, noarchive"
    Assert-HeaderContains $ready "Content-Security-Policy" "default-src 'none'"
    Assert-HeaderContains $ready "X-Correlation-ID" "corr_"
    Assert-HeaderEquals $ready "X-Source-Revision" $ExpectedRevision

    $openApi = $client.GetAsync("$($BackendUrl.TrimEnd('/'))/openapi.json").GetAwaiter().GetResult()
    if ([int]$openApi.StatusCode -ne 404) {
        throw "Production OpenAPI endpoint returned $([int]$openApi.StatusCode) instead of 404."
    }

    Write-Output "frontend_auth_boundary=passed"
    Write-Output "frontend_security_headers=passed"
    Write-Output "backend_readiness=passed"
    Write-Output "backend_security_headers=passed"
    Write-Output "production_openapi_closed=passed"
    Write-Output "source_revision=$ExpectedRevision"
}
finally {
    $client.Dispose()
    $handler.Dispose()
}
