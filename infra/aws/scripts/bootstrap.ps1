param(
    [string]$Profile = "case-resolution-portfolio",
    [string]$Region = "ap-southeast-1"
)

. "$PSScriptRoot/common.ps1"
$identity = Assert-AwsSession -Profile $Profile -Region $Region
$infraRoot = Split-Path -Parent $PSScriptRoot
Push-Location $infraRoot
try {
    npm ci
    npx cdk bootstrap "aws://$($identity.Account)/$Region" --profile $Profile
}
finally {
    Pop-Location
}
