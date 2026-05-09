# Extract Claude Code OAuth token from %USERPROFILE%\.claude\.credentials.json
# and export it as $env:CLAUDE_CODE_OAUTH_TOKEN.
#
# Windows-equivalent of scripts/export_oauth_token.sh (which reads the macOS
# Keychain). On Windows, Claude Code stores credentials as plain JSON.
#
# Dot-source this script before running nasde so the env var persists in the
# current PowerShell session:
#
#     . .\scripts\export_oauth_token.ps1
#     nasde run --variant baseline -C my-benchmark
#
# Running without dot-source (.\scripts\export_oauth_token.ps1) sets the var
# only inside the script's child scope and it disappears on return.

$ErrorActionPreference = 'Stop'

$credPath = Join-Path $env:USERPROFILE '.claude\.credentials.json'

if (-not (Test-Path $credPath)) {
    Write-Error "Could not find '$credPath'. Run 'claude' CLI and log in first."
    return
}

try {
    $token = (Get-Content $credPath -Raw | ConvertFrom-Json).claudeAiOauth.accessToken
} catch {
    Write-Error "Failed to parse OAuth token from '$credPath': $_"
    return
}

if ([string]::IsNullOrEmpty($token)) {
    Write-Error "claudeAiOauth.accessToken is empty in '$credPath'."
    return
}

$env:CLAUDE_CODE_OAUTH_TOKEN = $token

$preview = $token.Substring(0, [Math]::Min(20, $token.Length))
Write-Host "OK CLAUDE_CODE_OAUTH_TOKEN exported ($preview...)" -ForegroundColor Green
