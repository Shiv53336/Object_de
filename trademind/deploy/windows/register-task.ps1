# Registers the "TRADEMIND daily" scheduled task: weekdays at 08:45, runs daily.ps1 in a window while
# you are signed in, and wakes the laptop if it is asleep (wake timers must be allowed in Power Options).
#   powershell -ExecutionPolicy Bypass -File deploy\windows\register-task.ps1
# Remove it with:  Unregister-ScheduledTask -TaskName "TRADEMIND daily"

$script = Join-Path $PSScriptRoot "daily.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Weekly -At 08:45 `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 8)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "TRADEMIND daily" -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Registered 'TRADEMIND daily' for weekdays at 08:45 (local time; set Windows to India Standard Time)."
