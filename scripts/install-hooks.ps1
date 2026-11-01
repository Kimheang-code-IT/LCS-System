<#
.SYNOPSIS
    Installs the optional Git pre-push hook (runs scripts\ci-fast.ps1 and
    blocks failing pushes). Explicit opt-in only; never silent.

.EXAMPLE
    .\scripts\install-hooks.ps1           # install if absent
    .\scripts\install-hooks.ps1 -Force    # overwrite an existing hook
    .\scripts\uninstall-hooks.ps1         # the removal script reverses it
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot 'scripts/hooks/pre-push'
$target = Join-Path $repoRoot '.git/hooks/pre-push'

if (Test-Path $target) {
    if (-not $Force) {
        Write-Host "A pre-push hook already exists at .git/hooks/pre-push. Pass -Force to overwrite it." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Overwriting the existing pre-push hook." -ForegroundColor Yellow
}
Copy-Item -Path $source -Destination $target -Force
Write-Host "Pre-push hook installed: pushes now run scripts\ci-fast.ps1 and fail when it fails." -ForegroundColor Green
Write-Host "Disable it: .\scripts\uninstall-hooks.ps1 (or pass --no-verify to a single git push)." -ForegroundColor DarkGray