param([string]$Profile = '')
$ErrorActionPreference = 'Stop'
# Read only. Never signs in, upgrades a plan, or provisions infrastructure.
$awsCommand = Get-Command aws -ErrorAction SilentlyContinue
if (-not $awsCommand) {
    throw 'AWS CLI is missing. Install AWS CLI v2.32.0 or newer before AWS setup.'
}
$awsArgs = @('--region', 'us-east-2', '--no-cli-pager', '--cli-connect-timeout', '10', '--cli-read-timeout', '20')
if ($Profile) { $awsArgs += @('--profile', $Profile) }
$identityJson = & $awsCommand.Source sts get-caller-identity @awsArgs --output json
if ($LASTEXITCODE -ne 0) { throw 'AWS credentials are unavailable. Sign in before continuing.' }
$identity = $identityJson | ConvertFrom-Json
$planJson = & $awsCommand.Source freetier get-account-plan-state @awsArgs --output json
if ($LASTEXITCODE -ne 0) { throw 'Cannot verify Free plan status. No deployment allowed.' }
$plan = $planJson | ConvertFrom-Json
if ($plan.accountId -ne $identity.Account) { throw 'Plan identity does not match the selected project.' }
if ($plan.accountPlanType -ne 'FREE' -or $plan.accountPlanStatus -ne 'ACTIVE') {
    throw 'This project is not on an ACTIVE FREE plan. Stop: zero spending is required.'
}
if (-not $plan.accountPlanExpirationDate) { throw 'Cannot verify Free plan expiration. Stop.' }
$expiry = [DateTimeOffset]::Parse($plan.accountPlanExpirationDate)
if ($expiry -le [DateTimeOffset]::UtcNow) { throw 'Free plan has expired. Stop.' }
$credits = $plan.accountPlanRemainingCredits
if (-not $credits -or $credits.unit -ne 'USD' -or [decimal]$credits.amount -le 0) {
    throw 'No verified remaining USD credits. Stop.'
}
[pscustomobject]@{
    Project = $identity.Account
    Identity = $identity.Arn
    Region = 'us-east-2'
    Plan = $plan.accountPlanType
    Status = $plan.accountPlanStatus
    RemainingCreditsUSD = $credits.amount
    Expires = $expiry.ToString('o')
    ResourcesCreated = $false
}
