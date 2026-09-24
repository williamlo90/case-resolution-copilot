param(
    [string]$Profile = "case-resolution-portfolio",
    [string]$Region = "ap-southeast-1"
)

. "$PSScriptRoot/common.ps1"
Assert-AwsSession -Profile $Profile -Region $Region | Out-Null
$infraRoot = Split-Path -Parent $PSScriptRoot
$sessionPath = Join-Path $infraRoot "validation-session.local.json"
$session = Assert-ValidationWindow -SessionFile $sessionPath -MinimumMinutesRemaining 8
$foundation = Get-StackOutputs `
    -StackName "CaseResolutionFoundation" `
    -Profile $Profile `
    -Region $Region
$runtime = Get-StackOutputs `
    -StackName "CaseResolutionRuntime" `
    -Profile $Profile `
    -Region $Region
$stackStatuses = @(
    "CaseResolutionFoundation",
    "CaseResolutionRuntime"
) | ForEach-Object {
    aws cloudformation describe-stacks `
        --stack-name $_ `
        --profile $Profile `
        --region $Region `
        --query "Stacks[0].StackStatus" `
        --output text
}
if ($stackStatuses | Where-Object { $_ -ne "CREATE_COMPLETE" -and $_ -ne "UPDATE_COMPLETE" }) {
    throw "CloudFormation stacks are not in a completed state."
}

$services = aws ecs describe-services `
    --cluster $runtime.ClusterName `
    --services $runtime.ApiServiceName $runtime.WorkerServiceName $runtime.SchedulerServiceName `
    --profile $Profile `
    --region $Region `
    --query "services[].{name:serviceName,desired:desiredCount,running:runningCount,status:status}" `
    --output json | ConvertFrom-Json
foreach ($service in $services) {
    if ($service.status -ne "ACTIVE" -or $service.desired -ne 1 -or $service.running -ne 1) {
        throw "ECS service $($service.name) is not stable at one task."
    }
}

$health = Invoke-WebRequest `
    -Uri "$($runtime.ApiBaseUrl)/api/health/live" `
    -Method Get `
    -TimeoutSec 20 `
    -UseBasicParsing
if ($health.StatusCode -ne 200) {
    throw "CloudFront API health returned HTTP $($health.StatusCode)."
}

$validationId = "aws-$((Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss'))"
$sourceKey = "validation-input/$validationId.json"
$temporary = New-TemporaryFile
try {
    [ordered]@{
        validation_id = $validationId
        purpose = "ephemeral AWS portfolio validation"
    } | ConvertTo-Json | Set-Content -LiteralPath $temporary.FullName
    $contentHash = (Get-FileHash -LiteralPath $temporary.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifestKey = "validation-output/$contentHash.json"
    aws s3 cp $temporary.FullName "s3://$($foundation.ArtifactBucketName)/$sourceKey" `
        --profile $Profile `
        --region $Region `
        --only-show-errors

    $manifestReady = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try {
            aws s3api head-object `
                --bucket $foundation.ArtifactBucketName `
                --key $manifestKey `
                --profile $Profile `
                --region $Region *> $null
            $manifestReady = $true
            break
        }
        catch {
            Start-Sleep -Seconds 3
        }
    }
    if (-not $manifestReady) {
        throw "Lambda evidence manifest did not appear within 60 seconds."
    }
    $manifest = aws s3api get-object `
        --bucket $foundation.ArtifactBucketName `
        --key $manifestKey `
        "$($temporary.FullName).manifest" `
        --profile $Profile `
        --region $Region `
        --query "{VersionId:VersionId}" `
        --output json | ConvertFrom-Json
    $manifestPayload = Get-Content -LiteralPath "$($temporary.FullName).manifest" -Raw |
        ConvertFrom-Json
    if (
        $manifestPayload.validation_id -ne $validationId -or
        $manifestPayload.sha256 -ne $contentHash -or
        $manifestPayload.source_key -ne $sourceKey
    ) {
        throw "Lambda evidence manifest does not match the uploaded validation payload."
    }
}
finally {
    Remove-Item -LiteralPath $temporary.FullName -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath "$($temporary.FullName).manifest" -Force -ErrorAction SilentlyContinue
}

$deadLetters = aws sqs get-queue-attributes `
    --queue-url $foundation.IngestionDeadLetterQueueUrl `
    --attribute-names ApproximateNumberOfMessages `
    --profile $Profile `
    --region $Region `
    --query "Attributes.ApproximateNumberOfMessages" `
    --output text
if ([int]$deadLetters -ne 0) {
    throw "The SQS dead-letter queue is not empty."
}

$sessionStart = if ($session.startedAtUtc -is [datetime]) {
    $session.startedAtUtc.ToUniversalTime()
}
else {
    [datetimeoffset]::Parse(
        [string]$session.startedAtUtc,
        [cultureinfo]::InvariantCulture
    ).UtcDateTime
}
$startMilliseconds = ([DateTimeOffset]$sessionStart).ToUnixTimeMilliseconds()
$validationLog = $null
for ($attempt = 0; $attempt -lt 18 -and $null -eq $validationLog; $attempt++) {
    $workerMessages = aws logs filter-log-events `
        --log-group-name $foundation.WorkerLogGroupName `
        --start-time $startMilliseconds `
        --profile $Profile `
        --region $Region `
        --query "events[].message" `
        --output json | ConvertFrom-Json
    $validationLog = @($workerMessages | Where-Object {
        $_ -match [regex]::Escape($validationId) -and
        $_ -match "aws_validation_passed" -and
        $_ -match "vector_enabled.*True"
    }) | Select-Object -First 1
    if ($null -eq $validationLog) {
        Start-Sleep -Seconds 5
    }
}
if ($null -eq $validationLog) {
    throw "The connected Celery/RDS validation task was not observed for $validationId."
}
$migrationRevision = [regex]::Match(
    [string]$validationLog,
    'migration_revision[''"\s:]+(?<revision>[a-zA-Z0-9_-]+)'
).Groups["revision"].Value
if (-not $migrationRevision) {
    throw "The validation task did not report the live Alembic revision."
}

$evidence = [ordered]@{
    schemaVersion = "case-resolution-aws-live-validation-v1"
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    sourceRevision = (Get-Content (Join-Path $infraRoot "runtime-validation.local.json") -Raw |
        ConvertFrom-Json).sourceRevision
    checks = [ordered]@{
        cloudFormation = $stackStatuses
        cloudFrontHealth = 200
        ecsServicesStable = $services.Count
        validationId = $validationId
        s3EvidenceManifest = $manifestKey
        s3EvidenceVersion = [string]$manifest.VersionId
        lambdaEvidenceValidation = "passed"
        sqsDeadLetters = [int]$deadLetters
        celeryTask = "aws_validation_passed"
        rdsQuery = "passed"
        rdsVectorExtension = "enabled"
        rdsMigrationRevision = $migrationRevision
        rdsMigrationExitCode = 0
    }
    watchdogAtUtc = $session.watchdogAtUtc
    destroyByUtc = $session.destroyByUtc
}
$evidencePath = Join-Path $infraRoot "aws-validation-evidence.local.json"
$evidence | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $evidencePath
Write-Host "AWS live validation passed. Evidence: $evidencePath"
Write-Host "Begin teardown no later than $($session.destroyByUtc) UTC."
