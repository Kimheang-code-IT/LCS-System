<#
.SYNOPSIS
    Removes the pre-push hook installed by install-hooks.ps1 (only that hook).
#>
$repoRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $repoRoot '.git/hooks/pre-push'
if (Test-Path $target) {
    Remove-Item $target -Force
    Write-Host "Pre-push hook removed; pushes no longer run the local CI." -ForegroundColor Green
}
else {
    Write-Host "No pre-push hook present; nothing to remove." -ForegroundColor Yellow
}