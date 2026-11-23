# Trading-day routine on the Windows laptop (docs/TESTING.md, step 5):
# Kite login -> last week's candles -> preflight -> live paper run until 15:30 -> paper check.
# The "TRADEMIND daily" scheduled task runs it at 08:45 on weekdays; you can also run it by hand:
#   powershell -ExecutionPolicy Bypass -File deploy\windows\daily.ps1
# Everything is logged to data\logs\YYYY-MM-DD.log.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$tm = Join-Path $root ".venv\Scripts\trademind.exe"
$day = Get-Date -Format "yyyy-MM-dd"
$logDir = Join-Path $root "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path (Join-Path $logDir "$day.log") -Append | Out-Null

. "$PSScriptRoot\common.ps1"

try {
    if (-not (Test-Path $tm)) { throw "No virtual environment: follow docs/TESTING.md step 1 first." }
    if ((Get-Date).DayOfWeek -in @("Saturday", "Sunday")) { Write-Host "Weekend: nothing to do."; return }
    if ((Get-Date).TimeOfDay -gt [TimeSpan]"15:15") { Write-Host "Too late for today's session."; return }

    $envText = if (Test-Path ".env") { Get-Content ".env" -Raw } else { "" }
    $telegram = ($envText -match "(?m)^TELEGRAM_BOT_TOKEN=\S+") -and ($envText -match "(?m)^TELEGRAM_CHAT_ID=\S+")
    $login = if ($telegram) { @("login", "--telegram") } else { @("login") }
    if ((Step "Kite login" $login) -ne 0) { throw "Kite login failed." }

    # Yesterday's official candles become history; live tick bars never do.
    $from = (Get-Date).AddDays(-7).ToString("yyyy-MM-dd")
    $to = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
    if ((Step "Recent candles" @("data", "download", "--start", $from, "--end", $to)) -ne 0) {
        Write-Host "warning: download failed; preflight will say whether history is fresh enough"
    }

    if ((Step "Preflight" @("preflight", "--for", "paper")) -ne 0) {
        throw "Preflight failed: fix the FAIL lines above, then run this script again."
    }
    $null = Step "Paper run" @("paper", "run")
    $code = Step "Paper check" @("paper", "check")
    if ($code -eq 1) { Write-Host "`nPAPER CHECK FAILED: live and replay disagree. Keep data\checks\$day.md for review." }
}
catch {
    Write-Host "`nSTOPPED: $($_.Exception.Message)"
    exit 1
}
finally {
    Stop-Transcript | Out-Null
}
