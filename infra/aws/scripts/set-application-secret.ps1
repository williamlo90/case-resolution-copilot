param(
    [Parameter(Mandatory = $true)]
    [string]$SecretFile,
    [string]$Profile = "case-resolution-portfolio",
    [string]$Region = "ap-southeast-1"
)

. "$PSScriptRoot/common.ps1"
Assert-AwsSession -Profile $Profile -Region $Region | Out-Null

$resolved = (Resolve-Path -LiteralPath $SecretFile).Path
$payload = Get-Content -LiteralPath $resolved -Raw | ConvertFrom-Json
Assert-ApplicationSecretPayload -Payload $payload

$outputs = Get-StackOutputs `
    -StackName "CaseResolutionFoundation" `
    -Profile $Profile `
    -Region $Region
$secretName = $outputs["ApplicationSecretName"]
if (-not $secretName) {
    throw "ApplicationSecretName output was not found. Deploy Foundation first."
}

aws secretsmanager put-secret-value `
    --secret-id $secretName `
    --secret-string "file://$resolved" `
    --profile $Profile `
    --region $Region `
    --query "VersionId" `
    --output text | Out-Null
Write-Host "Application secret updated without printing credential values."
