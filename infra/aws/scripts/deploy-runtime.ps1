param(
    [Parameter(Mandatory = $true)]
    [string]$SourceRevision,
    [string]$ReleaseFile = "$PSScriptRoot/../release.local.json",
    [switch]$AcknowledgeHourlyCost,
    [string]$BudgetName = "portfolio-aws-monthly-budget",
    [string]$Profile = "case-resolution-portfolio",
    [string]$Region = "ap-southeast-1"
)

. "$PSScriptRoot/common.ps1"
$SourceRevision = $SourceRevision.Trim().ToLowerInvariant()
Assert-FullGitSha -SourceRevision $SourceRevision
if (-not $AcknowledgeHourlyCost) {
    throw "Runtime creates ALB, CloudFront, and Fargate charges. Re-run with -AcknowledgeHourlyCost."
}
$identity = Assert-AwsSession -Profile $Profile -Region $Region
Assert-CostBudget -AccountId $identity.Account -BudgetName $BudgetName -Profile $Profile
$infraRoot = Split-Path -Parent $PSScriptRoot
$sessionPath = Join-Path $infraRoot "validation-session.local.json"
$session = Assert-ValidationWindow -SessionFile $sessionPath -MinimumMinutesRemaining 15
$watchdogAt = [string]$session.watchdogAtUtc
if ($watchdogAt -notmatch "^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$") {
    throw "Validation session does not contain a valid AWS watchdog time."
}
$release = Get-Content -LiteralPath (Resolve-Path -LiteralPath $ReleaseFile) -Raw |
    ConvertFrom-Json
if ($release.sourceRevision -ne $SourceRevision) {
    throw "Release record does not match SourceRevision. Publish this exact commit first."
}
$imageDigest = [string]$release.imageDigest
if ($imageDigest -notmatch "^sha256:[0-9a-f]{64}$") {
    throw "Release record does not contain a valid immutable image digest."
}

$foundation = Get-StackOutputs `
    -StackName "CaseResolutionFoundation" `
    -Profile $Profile `
    -Region $Region
$repositoryUri = [string]$foundation["RepositoryUri"]
if ($release.repositoryUri -ne $repositoryUri) {
    throw "Release record belongs to a different ECR repository. Publish again for this Foundation."
}
$repositoryName = ($repositoryUri -split "/", 2)[1]
$imageTags = aws ecr describe-images `
    --repository-name $repositoryName `
    --image-ids "imageDigest=$imageDigest" `
    --profile $Profile `
    --region $Region `
    --query "imageDetails[0].imageTags" `
    --output json | ConvertFrom-Json
if ($imageTags -notcontains $SourceRevision) {
    throw "The recorded digest is not tagged with the requested source revision in ECR."
}
$secretName = $foundation["ApplicationSecretName"]
$secretText = aws secretsmanager get-secret-value `
    --secret-id $secretName `
    --profile $Profile `
    --region $Region `
    --query "SecretString" `
    --output text
$secretPayload = $secretText | ConvertFrom-Json
Assert-ApplicationSecretPayload -Payload $secretPayload
$secretPayload = $null
$secretText = $null

Push-Location $infraRoot
try {
    npx cdk deploy CaseResolutionRuntime `
        --profile $Profile `
        --require-approval never `
        -c includeRuntime=true `
        -c imageDigest=$imageDigest `
        -c sourceRevision=$SourceRevision `
        -c autoDestroyAt=$watchdogAt
}
finally {
    Pop-Location
}
Assert-ValidationWindow -SessionFile $sessionPath -MinimumMinutesRemaining 10 | Out-Null

$runtime = Get-StackOutputs `
    -StackName "CaseResolutionRuntime" `
    -Profile $Profile `
    -Region $Region
$network = "awsvpcConfiguration={subnets=[$($runtime.RuntimeSubnetIds)],securityGroups=[$($runtime.MigrationSecurityGroupId)],assignPublicIp=ENABLED}"
$taskArn = aws ecs run-task `
    --cluster $runtime.ClusterName `
    --task-definition $runtime.MigrationTaskDefinitionArn `
    --launch-type FARGATE `
    --network-configuration $network `
    --profile $Profile `
    --region $Region `
    --query "tasks[0].taskArn" `
    --output text
if (-not $taskArn -or $taskArn -eq "None") {
    throw "Migration task did not start."
}
aws ecs wait tasks-stopped `
    --cluster $runtime.ClusterName `
    --tasks $taskArn `
    --profile $Profile `
    --region $Region
$exitCode = aws ecs describe-tasks `
    --cluster $runtime.ClusterName `
    --tasks $taskArn `
    --profile $Profile `
    --region $Region `
    --query "tasks[0].containers[0].exitCode" `
    --output text
if ($exitCode -ne "0") {
    throw "Migration failed with exit code $exitCode. Services remain scaled to zero."
}

$services = @(
    $runtime.SchedulerServiceName,
    $runtime.WorkerServiceName,
    $runtime.ApiServiceName
)
try {
    foreach ($service in $services) {
        aws ecs update-service `
            --cluster $runtime.ClusterName `
            --service $service `
            --desired-count 1 `
            --profile $Profile `
            --region $Region `
            --query "service.serviceName" `
            --output text | Out-Null
        aws ecs wait services-stable `
            --cluster $runtime.ClusterName `
            --services $service `
            --profile $Profile `
            --region $Region
    }
}
catch {
    foreach ($service in $services) {
        try {
            aws ecs update-service `
                --cluster $runtime.ClusterName `
                --service $service `
                --desired-count 0 `
                --profile $Profile `
                --region $Region `
                --query "service.serviceName" `
                --output text | Out-Null
        }
        catch {
            Write-Warning "Could not scale $service to zero during startup rollback."
        }
    }
    throw
}
[ordered]@{
    sourceRevision = $SourceRevision
    imageDigest = $imageDigest
    apiBaseUrl = $runtime.ApiBaseUrl
    migrationExitCode = 0
    startedAtUtc = $session.startedAtUtc
    watchdogAtUtc = $session.watchdogAtUtc
    destroyByUtc = $session.destroyByUtc
    state = "runtime-stable"
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $infraRoot "runtime-validation.local.json")
Write-Host "Runtime is stable at $($runtime.ApiBaseUrl)."
Write-Host "Destroy deadline (UTC): $($session.destroyByUtc)"
