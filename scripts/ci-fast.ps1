<#
.SYNOPSIS
    Fast local CI for the LCS Freight Forwarding System.

.DESCRIPTION
    Mirrors the required `Dev CI` GitHub Actions gate on a Windows machine:
    lockfile consistency, backend Ruff + tests, frontend lint + typecheck +
    unit tests. It never touches Docker, production, or the network.
    Exits 0 only when every required check passed.

.EXAMPLE
    .\scripts\ci-fast.ps1
    .\scripts\ci-fast.ps1 -SkipBackendTests -Serial
#>
[CmdletBinding()]
param(
    [switch]$SkipBackendTests,
    [switch]$Serial
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$script:results = [System.Collections.Generic.List[object]]::new()
$script:swatch = [System.Diagnostics.Stopwatch]::StartNew()
$script:failures = 0

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command,
        [string]$WorkingDirectory = $repoRoot
    )
    Write-Host "- $Name" -ForegroundColor Cyan
    Set-Location $WorkingDirectory
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $code = 0
    try {
        & $Command
        # A native command's exit code survives in $LASTEXITCODE; a cmdlet
        # failure already threw and was caught below.
        $code = $LASTEXITCODE
    }
    catch {
        Write-Host $_.Exception.Message -ForegroundColor Red
        $code = 1
    }
    finally {
        Set-Location $repoRoot
        $sw.Stop()
    }
    $result = if ($code -eq 0) { 'PASS' } else { 'FAIL' }
    if ($result -eq 'FAIL') {
        Write-Host "FAIL  $Name (exit $code after $([math]::Round($sw.Elapsed.TotalSeconds,1))s)" -ForegroundColor Red
        $script:failures += 1
    }
    else {
        Write-Host ("PASS  {0} ({1:n1}s)" -f $Name, $sw.Elapsed.TotalSeconds) -ForegroundColor Green
    }
    $script:results.Add([pscustomobject]@{ Name = $Name; Result = $result; Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1) })
}

# --- Tool inventory ----------------------------------------------------------
Write-Host "LOCAL CI (fast) - start $((Get-Date).ToString('HH:mm:ss'))" -ForegroundColor White
$missing = @('git', 'node', 'pnpm', 'uv') | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) }
if ($missing) {
    Write-Host "MISSING TOOLS: $($missing -join ', '). Install them and make sure they are on PATH." -ForegroundColor Red
    exit 1
}

$backendDir = Join-Path $repoRoot 'backend'
$frontendDir = Join-Path $repoRoot 'frontend'

# --- Backend -----------------------------------------------------------------
if ($SkipBackendTests) {
    Write-Host 'SKIP  backend stage (-SkipBackendTests)' -ForegroundColor Yellow
}
else {
    # 1. A forgotten dependency update must fail here, not on GitHub.
    Invoke-Step 'Backend Lockfile (uv.lock)' -Command { uv lock --check } -WorkingDirectory $backendDir

    # 2. Reuse backend/.venv; create it once on a fresh checkout.
    if (-not (Test-Path (Join-Path $backendDir '.venv/Scripts/python.exe'))) {
        Invoke-Step 'Backend Env (uv sync)' -Command { uv sync --extra dev } -WorkingDirectory $backendDir
    }

    Invoke-Step 'Backend Ruff' -Command { uv run ruff check . } -WorkingDirectory $backendDir

    # 3. Tests, sharded across CPU cores exactly like the Dev CI gate.
    $pytestArgs = @('run', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider')
    if (-not $Serial) { $pytestArgs += '-n', 'auto' }
    Invoke-Step 'Backend Tests (pytest)' -Command { uv @pytestArgs } -WorkingDirectory $backendDir
}

# --- Frontend -----------------------------------------------------------------
if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
    Invoke-Step 'Frontend Install' -Command { pnpm install --frozen-lockfile } -WorkingDirectory $frontendDir
}
Invoke-Step 'Frontend Lint' -Command { pnpm lint } -WorkingDirectory $frontendDir
Invoke-Step 'Frontend Typecheck' -Command { pnpm typecheck } -WorkingDirectory $frontendDir
Invoke-Step 'Frontend Tests (vitest)' -Command { pnpm exec vitest run } -WorkingDirectory $frontendDir

# --- Summary --------------------------------------------------------------------
$script:swatch.Stop()
$totalSeconds = [int]$script:swatch.Elapsed.TotalSeconds
$totalLabel = '{0}:{1:d2}' -f [int][math]::Floor($totalSeconds / 60), ($totalSeconds % 60)

Write-Host ''
Write-Host 'LOCAL CI RESULTS' -ForegroundColor White
foreach ($result in $script:results) {
    $color = switch ($result.Result) {
        'PASS' { 'Green' } 'FAIL' { 'Red' } default { 'Yellow' }
    }
    Write-Host ("{0}  {1} ({2}s)" -f $result.Name.PadRight(28), $result.Result.PadRight(4), $result.Seconds) -ForegroundColor $color
}
Write-Host ("Total elapsed: {0}" -f $totalLabel) -ForegroundColor DarkGray

if ($script:failures -gt 0) {
    Write-Host "RESULT: BLOCKED ($($script:failures) check(s) failed) - do not push" -ForegroundColor Red
    exit 1
}
Write-Host 'RESULT: READY TO PUSH' -ForegroundColor Green