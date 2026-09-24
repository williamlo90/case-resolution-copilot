param(
    [string]$SourceRevision = (git rev-parse HEAD),
    [string]$Profile = "case-resolution-portfolio",
    [string]$Region = "ap-southeast-1"
)

. "$PSScriptRoot/common.ps1"
$SourceRevision = $SourceRevision.Trim().ToLowerInvariant()
Assert-FullGitSha -SourceRevision $SourceRevision
Assert-AwsSession -Profile $Profile -Region $Region | Out-Null
$infraRoot = Split-Path -Parent $PSScriptRoot
$repositoryRoot = (Resolve-Path "$PSScriptRoot/../../..").Path
$headRevision = (git -C $repositoryRoot rev-parse HEAD).Trim().ToLowerInvariant()
if ($headRevision -ne $SourceRevision) {
    throw "SourceRevision must exactly match the current Git HEAD ($headRevision)."
}
$worktreeStatus = git -C $repositoryRoot status --porcelain
if ($worktreeStatus) {
    throw "The Git worktree must be clean before publishing an immutable image."
}

$outputs = Get-StackOutputs `
    -StackName "CaseResolutionFoundation" `
    -Profile $Profile `
    -Region $Region
$repositoryUri = $outputs["RepositoryUri"]
if (-not $repositoryUri) {
    throw "RepositoryUri output was not found. Deploy Foundation first."
}
$registry = $repositoryUri.Split("/")[0]
$repositoryName = ($repositoryUri -split "/", 2)[1]

aws ecr get-login-password --profile $Profile --region $Region |
    docker login --username AWS --password-stdin $registry | Out-Null
docker build `
    --file "$repositoryRoot/backend/Containerfile" `
    --tag "${repositoryUri}:$SourceRevision" `
    "$repositoryRoot/backend"
docker push "${repositoryUri}:$SourceRevision"
# ECR can accept the manifest a few seconds before the scan record becomes queryable.
Start-Sleep -Seconds 15
aws ecr wait image-scan-complete `
    --repository-name $repositoryName `
    --image-id "imageTag=$SourceRevision" `
    --profile $Profile `
    --region $Region
$scanFindings = aws ecr describe-image-scan-findings `
    --repository-name $repositoryName `
    --image-id "imageTag=$SourceRevision" `
    --profile $Profile `
    --region $Region `
    --query "imageScanFindings.findings" `
    --output json | ConvertFrom-Json
$approvedHighFindings = @(
    "CVE-2026-82560", # Perl Pod::Text is not invoked by the application.
    "CVE-2026-85091"  # The application does not use non-blocking native gzwrite operations.
)
$critical = @($scanFindings | Where-Object severity -eq "CRITICAL").Count
$unapprovedHigh = @(
    $scanFindings |
        Where-Object severity -eq "HIGH" |
        Where-Object { $approvedHighFindings -notcontains $_.name }
)
$high = $unapprovedHigh.Count
if ($critical -gt 0 -or $high -gt 0) {
    throw "ECR scan rejected the image: $critical critical and $high unapproved high findings."
}
$approvedHighPresent = @(
    $scanFindings |
        Where-Object severity -eq "HIGH" |
        Where-Object { $approvedHighFindings -contains $_.name } |
        ForEach-Object name
)
$imageDigest = aws ecr describe-images `
    --repository-name $repositoryName `
    --image-ids "imageTag=$SourceRevision" `
    --profile $Profile `
    --region $Region `
    --query "imageDetails[0].imageDigest" `
    --output text
if ($imageDigest -notmatch "^sha256:[0-9a-f]{64}$") {
    throw "ECR did not return a valid immutable image digest."
}
$releaseRecord = [ordered]@{
    sourceRevision = $SourceRevision
    imageDigest = $imageDigest
    repositoryUri = $repositoryUri
    scannedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    approvedHighFindings = $approvedHighPresent
}
$releaseRecord | ConvertTo-Json | Set-Content -LiteralPath "$infraRoot/release.local.json"
Write-Host "Published and scanned immutable backend image for $SourceRevision."
