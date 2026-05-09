# Validate Codex OAuth auth.json for ChatGPT subscription-based authentication.
#
# Windows-equivalent of scripts/export_codex_oauth_token.sh.
#
# Dot-source this script before running nasde to verify your ChatGPT
# subscription credentials:
#
#     . .\scripts\export_codex_oauth_token.ps1
#     nasde run --variant codex-vanilla -C my-benchmark
#
# Prerequisites: run `codex login` to authenticate via ChatGPT.
# Reads %USERPROFILE%\.codex\auth.json. NASDE injects this file into the
# sandbox automatically — this script only validates it.

$ErrorActionPreference = 'Stop'

$authPath = Join-Path $env:USERPROFILE '.codex\auth.json'

if (-not (Test-Path $authPath)) {
    Write-Error "$authPath not found. Run 'codex login' to authenticate via ChatGPT subscription."
    return
}

try {
    $auth = Get-Content $authPath -Raw | ConvertFrom-Json
} catch {
    Write-Error "Failed to parse $authPath : $_"
    return
}

if ($auth.auth_mode -ne 'chatgpt') {
    Write-Error "auth_mode is '$($auth.auth_mode)', expected 'chatgpt'. Run 'codex login' to authenticate via ChatGPT subscription."
    return
}

$accessToken = $auth.tokens.access_token
if ([string]::IsNullOrEmpty($accessToken)) {
    Write-Error "access_token is empty in $authPath. Run 'codex login' to re-authenticate."
    return
}

# Decode JWT payload (middle segment) to read exp claim. Pad base64url to
# multiple of 4 with '=' before decoding.
try {
    $payloadSegment = $accessToken.Split('.')[1]
    $padded = $payloadSegment.Replace('-', '+').Replace('_', '/')
    switch ($padded.Length % 4) { 2 { $padded += '==' } 3 { $padded += '=' } }
    $payloadJson = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($padded))
    $exp = ($payloadJson | ConvertFrom-Json).exp
} catch {
    $exp = 0
}

$now = [int][double]::Parse((Get-Date -UFormat %s))
if ($exp -gt 0 -and $now -gt $exp) {
    Write-Warning "access_token expired. Run 'codex login' to refresh."
    Write-Warning "Proceeding anyway -- Codex CLI may auto-refresh via refresh_token."
}

$preview = $accessToken.Substring(0, [Math]::Min(20, $accessToken.Length))
Write-Host "OK Codex OAuth validated (auth_mode=chatgpt, token=$preview...)" -ForegroundColor Green
