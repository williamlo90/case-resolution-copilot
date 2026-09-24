param(
    [switch]$AcknowledgeHourlyCost,
    [string]$BudgetName = "portfolio-aws-monthly-budget",
    [string]$Profile = "case-resolution-portfolio",
    [string]$Region = "ap-southeast-1"
)

. "$PSScriptRoot/common.ps1"
if (-not $AcknowledgeHourlyCost) {
    throw "Foundation creates hourly RDS charges. Re-run with -AcknowledgeHourlyCost."
}

$identity = Assert-AwsSession -Profile $Profile -Region $Region
Assert-CostBudget -AccountId $identity.Account -BudgetName $BudgetName -Profile $Profile
$infraRoot = Split-Path -Parent $PSScriptRoot
$sessionPath = Join-Path $infraRoot "validation-session.local.json"
$startedAt = (Get-Date).ToUniversalTime()
$operatorTeardownAt = $startedAt.AddMinutes(35)
$watchdogAt = $startedAt.AddMinutes(45)
$watchdogAtText = $watchdogAt.ToString("yyyy-MM-ddTHH:mm:ssZ")
[ordered]@{
    startedAtUtc = $startedAt.ToString("o")
    operatorTeardownAtUtc = $operatorTeardownAt.ToString("o")
    watchdogAtUtc = $watchdogAtText
    destroyByUtc = $watchdogAt.ToString("o")
    profile = $Profile
    region = $Region
    state = "foundation-started"
} | ConvertTo-Json | Set-Content -LiteralPath $sessionPath
Push-Location $infraRoot
try {
    npm ci
    npx cdk deploy CaseResolutionFoundation `
        --profile $Profile `
        --require-approval never `
        -c autoDestroyAt=$watchdogAtText
}
finally {
    Pop-Location
}
Write-Host "Operator teardown target: $($operatorTeardownAt.ToString('o'))."
Write-Host "AWS-side teardown watchdog is armed for $watchdogAtText."
