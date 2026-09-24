Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw "AWS lifecycle scripts require PowerShell 7 or newer."
}
$PSNativeCommandUseErrorActionPreference = $true

function Assert-AwsSession {
    param(
        [string]$Profile,
        [string]$Region
    )

    $env:AWS_REGION = $Region
    $env:AWS_DEFAULT_REGION = $Region
    $env:CDK_DEFAULT_REGION = $Region
    $identity = aws sts get-caller-identity --profile $Profile --region $Region --output json |
        ConvertFrom-Json
    if (-not $identity.Account) {
        throw "AWS SSO session is unavailable. Run: aws sso login --profile $Profile"
    }
    return $identity
}

function Get-StackOutputs {
    param(
        [string]$StackName,
        [string]$Profile,
        [string]$Region
    )

    $rows = aws cloudformation describe-stacks `
        --stack-name $StackName `
        --profile $Profile `
        --region $Region `
        --query "Stacks[0].Outputs" `
        --output json | ConvertFrom-Json
    $outputs = @{}
    foreach ($row in $rows) {
        $outputs[$row.OutputKey] = $row.OutputValue
    }
    return $outputs
}

function Assert-FullGitSha {
    param([string]$SourceRevision)

    if ($SourceRevision -notmatch "^[0-9a-f]{40}$") {
        throw "SourceRevision must be the full lowercase 40-character Git SHA."
    }
}

function Get-BudgetNotificationThreshold {
    param([psobject]$Notification)

    if ($null -ne $Notification.PSObject.Properties["NotificationThreshold"]) {
        return [decimal]$Notification.NotificationThreshold
    }
    if ($null -ne $Notification.PSObject.Properties["Threshold"]) {
        return [decimal]$Notification.Threshold
    }
    throw "AWS did not return a threshold for a budget notification."
}

function Assert-CostBudget {
    param(
        [string]$AccountId,
        [string]$BudgetName,
        [string]$Profile
    )

    $budget = aws budgets describe-budget `
        --account-id $AccountId `
        --budget-name $BudgetName `
        --profile $Profile `
        --region us-east-1 `
        --output json | ConvertFrom-Json
    if ($budget.Budget.BudgetType -ne "COST" `
        -or $budget.Budget.TimeUnit -ne "MONTHLY" `
        -or $budget.Budget.BudgetLimit.Unit -ne "USD" `
        -or [decimal]$budget.Budget.BudgetLimit.Amount -gt 25) {
        throw "Budget '$BudgetName' must be a monthly USD cost budget of 25 or lower."
    }

    $notifications = aws budgets describe-notifications-for-budget `
        --account-id $AccountId `
        --budget-name $BudgetName `
        --profile $Profile `
        --region us-east-1 `
        --output json | ConvertFrom-Json
    $percentage = @(
        $notifications.Notifications |
            Where-Object {
                $null -eq $_.PSObject.Properties["ThresholdType"] `
                    -or $_.ThresholdType -eq "PERCENTAGE"
            }
    )
    $actualThresholds = @(
        $percentage |
            Where-Object NotificationType -eq "ACTUAL" |
            ForEach-Object { Get-BudgetNotificationThreshold -Notification $_ }
    )
    $forecastThresholds = @(
        $percentage |
            Where-Object NotificationType -eq "FORECASTED" |
            ForEach-Object { Get-BudgetNotificationThreshold -Notification $_ }
    )
    if ($actualThresholds -notcontains 50 `
        -or $actualThresholds -notcontains 80 `
        -or $forecastThresholds -notcontains 100) {
        throw "Budget '$BudgetName' must retain 50%/80% actual and 100% forecast protection."
    }
}

function Get-RequiredApplicationSecretNames {
    return @(
        "SUPPORT_COPILOT_CLERK_SECRET_KEY",
        "SUPPORT_COPILOT_CLERK_JWT_KEY",
        "SUPPORT_COPILOT_OPENAI_API_KEY",
        "SUPPORT_COPILOT_GOOGLE_OAUTH_CLIENT_ID",
        "SUPPORT_COPILOT_GOOGLE_OAUTH_CLIENT_SECRET",
        "SUPPORT_COPILOT_CREDENTIAL_VAULT_KEY",
        "SUPPORT_COPILOT_INBOX_SCHEDULER_SECRET",
        "SUPPORT_COPILOT_POLICY_INDEX_SCHEDULER_SECRET"
    )
}

function Assert-ApplicationSecretPayload {
    param([object]$Payload)

    foreach ($name in Get-RequiredApplicationSecretNames) {
        if ($Payload.PSObject.Properties.Name -notcontains $name) {
            throw "Application secret is missing $name."
        }
        $value = [string]$Payload.$name
        if (-not $value -or $value -like "replace_*") {
            throw "Application secret does not contain a usable value for $name."
        }
    }

    if (-not ([string]$Payload.SUPPORT_COPILOT_CLERK_SECRET_KEY).StartsWith("sk_")) {
        throw "Clerk secret key format is invalid."
    }
    $jwtKey = [string]$Payload.SUPPORT_COPILOT_CLERK_JWT_KEY
    if (-not $jwtKey.Contains("-----BEGIN PUBLIC KEY-----") `
        -or -not $jwtKey.Contains("-----END PUBLIC KEY-----")) {
        throw "Clerk JWT public key must be PEM formatted."
    }
    if (-not ([string]$Payload.SUPPORT_COPILOT_OPENAI_API_KEY).StartsWith("sk-")) {
        throw "OpenAI API key format is invalid."
    }
    foreach ($name in @(
        "SUPPORT_COPILOT_INBOX_SCHEDULER_SECRET",
        "SUPPORT_COPILOT_POLICY_INDEX_SCHEDULER_SECRET"
    )) {
        if (([string]$Payload.$name).Length -lt 32) {
            throw "$name must contain at least 32 characters."
        }
    }
    if (-not (Test-UrlSafeBase64Key -Value ([string]$Payload.SUPPORT_COPILOT_CREDENTIAL_VAULT_KEY))) {
        throw "Credential vault key must decode to exactly 32 bytes."
    }
}

function Test-UrlSafeBase64Key {
    param([string]$Value)

    try {
        $normalized = $Value.Replace("-", "+").Replace("_", "/")
        $normalized += "=" * ((4 - $normalized.Length % 4) % 4)
        return [Convert]::FromBase64String($normalized).Length -eq 32
    }
    catch {
        return $false
    }
}

function Assert-ValidationWindow {
    param(
        [string]$SessionFile,
        [int]$MinimumMinutesRemaining = 10
    )

    $session = Get-Content -LiteralPath (Resolve-Path -LiteralPath $SessionFile) -Raw |
        ConvertFrom-Json
    $deadline = [datetime]::Parse([string]$session.destroyByUtc).ToUniversalTime()
    $remaining = $deadline - (Get-Date).ToUniversalTime()
    if ($remaining.TotalMinutes -lt $MinimumMinutesRemaining) {
        throw "Validation window has only $([math]::Round($remaining.TotalMinutes, 1)) minutes left. Destroy the stacks now."
    }
    return $session
}
