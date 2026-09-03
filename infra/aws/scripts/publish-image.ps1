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
aws ecr wait image-scan-complete `
    --repository-name $repositoryName `
    --image-id "imageTag=$SourceRevision" `
    --profile $Profile `
    --region $Region
$blockingFindings = aws ecr describe-image-scan-findings `
    --repository-name $repositoryName `
    --image-id "imageTag=$SourceRevision" `
    --profile $Profile `
    --region $Region `
    --query "imageScanFindings.findingSeverityCounts.[CRITICAL,HIGH]" `
    --output json | ConvertFrom-Json
$critical = if ($null -eq $blockingFindings[0]) { 0 } else { [int]$blockingFindings[0] }
$high = if ($null -eq $blockingFindings[1]) { 0 } else { [int]$blockingFindings[1] }
if ($critical -gt 0 -or $high -gt 0) {
    throw "ECR scan rejected the image: $critical critical and $high high findings."
}
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
}
$releaseRecord | ConvertTo-Json | Set-Content -LiteralPath "$infraRoot/release.local.json"
Write-Host "Published and scanned immutable backend image for $SourceRevision."
