# Export Gemini CLI OAuth credentials for subscription-based authentication.
#
# Windows-equivalent of scripts/export_gemini_oauth_token.sh.
#
# Dot-source this script before running nasde to authenticate via your
# Google account instead of GEMINI_API_KEY:
#
#     . .\scripts\export_gemini_oauth_token.ps1
#     nasde run --variant gemini-vanilla -C my-benchmark
#
# Prerequisites: run `gemini login` to authenticate via Google.
# Reads %USERPROFILE%\.gemini\oauth_creds.json and exports the raw JSON as
# $env:GEMINI_OAUTH_CREDS. ConfigurableGemini injects this into the sandbox.

$ErrorActionPreference = 'Stop'

$credPath = Join-Path $env:USERPROFILE '.gemini\oauth_creds.json'

if (-not (Test-Path $credPath)) {
    Write-Error "$credPath not found. Run 'gemini login' to authenticate via Google."
    return
}

try {
    $rawJson = Get-Content $credPath -Raw
    $parsed = $rawJson | ConvertFrom-Json
} catch {
    Write-Error "$credPath does not contain valid JSON credentials: $_"
    return
}

if (-not $parsed) {
    Write-Error "$credPath contains empty credentials."
    return
}

$accessToken = $parsed.access_token
if (-not [string]::IsNullOrEmpty($accessToken)) {
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
        Write-Warning "access_token appears expired. Run 'gemini login' to refresh."
        Write-Warning "Proceeding anyway -- Gemini CLI may auto-refresh via refresh_token."
    }
}

$env:GEMINI_OAUTH_CREDS = $rawJson

$preview = $rawJson.Substring(0, [Math]::Min(20, $rawJson.Length))
Write-Host "OK GEMINI_OAUTH_CREDS exported ($preview...)" -ForegroundColor Green
