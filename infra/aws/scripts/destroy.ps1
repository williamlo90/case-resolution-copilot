param(
    [switch]$AcknowledgeDestroy,
    [string]$SourceRevision = (git rev-parse HEAD),
    [string]$Profile = "case-resolution-portfolio",
    [string]$Region = "ap-southeast-1"
)

. "$PSScriptRoot/common.ps1"
if (-not $AcknowledgeDestroy) {
    throw "This removes the validation environment. Re-run with -AcknowledgeDestroy."
}
$SourceRevision = $SourceRevision.Trim().ToLowerInvariant()
Assert-FullGitSha -SourceRevision $SourceRevision
Assert-AwsSession -Profile $Profile -Region $Region | Out-Null

$infraRoot = Split-Path -Parent $PSScriptRoot
Push-Location $infraRoot
try {
    npx cdk destroy CaseResolutionRuntime `
        --force `
        --profile $Profile `
        -c includeRuntime=true `
        -c imageDigest="sha256:$('0' * 64)" `
        -c sourceRevision=$SourceRevision
    npx cdk destroy CaseResolutionFoundation --force --profile $Profile
}
finally {
    Pop-Location
}

$remainingStacks = aws cloudformation list-stacks `
    --profile $Profile `
    --region $Region `
    --query "StackSummaries[?(StackName=='CaseResolutionFoundation' || StackName=='CaseResolutionRuntime') && StackStatus!='DELETE_COMPLETE'].StackName" `
    --output json | ConvertFrom-Json
if (@($remainingStacks).Count -ne 0) {
    throw "AWS teardown is incomplete: $($remainingStacks -join ', ')."
}

$sessionPath = Join-Path $infraRoot "validation-session.local.json"
$session = if (Test-Path -LiteralPath $sessionPath) {
    Get-Content -LiteralPath $sessionPath -Raw | ConvertFrom-Json
} else {
    $null
}
[ordered]@{
    schemaVersion = "case-resolution-aws-teardown-v1"
    completedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    startedAtUtc = if ($null -ne $session) { $session.startedAtUtc } else { $null }
    stacksRemaining = 0
    status = "destroyed"
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $infraRoot "aws-teardown-evidence.local.json")
Remove-Item -LiteralPath $sessionPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $infraRoot "runtime-validation.local.json") `
    -Force -ErrorAction SilentlyContinue
Write-Host "AWS validation stacks are destroyed. Local teardown evidence was recorded."
