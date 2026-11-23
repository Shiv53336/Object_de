# Shared helpers for the Windows scripts. Dot-source it: . "$PSScriptRoot\common.ps1"

# Runs the trademind CLI, shows its output, and returns only its exit code. Without `| Out-Host`
# the printed lines would become part of the function's return value, and a check like
# `(Step ...) -ne 0` would always be true (the bug the 2026-11-23 review found).
function Step([string]$name, [string[]]$arguments) {
    Write-Host "`n=== $name ($(Get-Date -Format HH:mm:ss)) ==="
    & $tm @arguments | Out-Host
    return [int]$LASTEXITCODE
}
