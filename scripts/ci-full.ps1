<#
.SYNOPSIS
    Full local CI for the LCS Freight Forwarding System: everything the GitHub
    Actions gates run, plus dependency/security audits, a production-equivalent
    frontend build, Docker image builds and an isolated container smoke test.

.DESCRIPTION
    Production is never contacted. The smoke test bootstraps throwaway
    containers on an isolated Docker network (and one temporary high host port
    for the frontend image) and always cleans them up; named volumes and the
    developer stack are untouched.

.EXAMPLE
    .\scripts\ci-full.ps1
    .\scripts\ci-full.ps1 -SkipDocker
    .\scripts\ci-full.ps1 -Serial          # pytest without the CPU sharding
#>
[CmdletBinding()]
param(
    [switch]$SkipDocker,
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

# --- Tools --------------------------------------------------------------------
Write-Host "LOCAL CI (full) - start $((Get-Date).ToString('HH:mm:ss'))" -ForegroundColor White
foreach ($tool in @('git', 'node', 'pnpm', 'uv', 'docker')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "MISSING TOOL: '$tool'. Install it and make sure it is on PATH." -ForegroundColor Red
        exit 1
    }
}

$backendDir = Join-Path $repoRoot 'backend'
$frontendDir = Join-Path $repoRoot 'frontend'

# The credential pattern gate used by Dev CI and the Security audit workflow.
$secretPattern = 'AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-(proj-)?[A-Za-z0-9_-]{20,}'

# --- 1. Repository validation -------------------------------------------------------
Write-Host "`n=== Stage 1: repository validation ===" -ForegroundColor White
$dirty = @(git status --porcelain | Where-Object { $_.Trim() })
if ($dirty.Count -gt 0) {
    # A dirty tree is expected between commits and never blocks; it is only
    # reported so a push later cannot surprise you.
    Write-Host ("NOTE  working tree has {0} uncommitted change(s); latest state is what these checks validated." -f $dirty.Count) -ForegroundColor Yellow
}

Invoke-Step 'Secret Patterns (tree)' -Command {
    $hits = (git grep -n -I -E $secretPattern -- . 2>$null)
    if ($hits) {
        Write-Host ($hits | Select-Object -First 10) -ForegroundColor Red
        throw 'A likely credential or private key is committed in the current tree.'
    }
}

Invoke-Step 'Secret Patterns (history)' -Command {
    $hits = (git log --all -p --no-ext-diff 2>$null | Select-String -Pattern $secretPattern -List | Select-Object -First 3)
    if ($hits) {
        Write-Host 'A likely credential or private key exists in Git history. Rotate it and purge the history.' -ForegroundColor Red
        throw 'secret pattern found in git history'
    }
}

# --- 2. Backend -----------------------------------------------------------------------
Write-Host "`n=== Stage 2: backend ===" -ForegroundColor White
Invoke-Step 'Backend Lockfile (uv.lock)' -Command { uv lock --check } -WorkingDirectory $backendDir
Invoke-Step 'Backend Env (uv sync --frozen)' -Command { uv sync --frozen --extra dev } -WorkingDirectory $backendDir
Invoke-Step 'Backend Ruff' -Command { uv run ruff check . } -WorkingDirectory $backendDir
Invoke-Step 'Backend Bandit' -Command { uv run bandit -r app -q --severity-level medium } -WorkingDirectory $backendDir
Invoke-Step 'Backend pip-audit' -Command {
    uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements-audit.txt
    if ($LASTEXITCODE -ne 0) { throw 'uv export failed' }
    uv run pip-audit -r requirements-audit.txt
    if ($LASTEXITCODE -ne 0) {
        throw 'pip-audit reported a vulnerability (e.g. a pyasn1 < 0.6.5 class finding). Raise it to the fixed version and re-lock.'
    }
} -WorkingDirectory $backendDir

Write-Host '  Running the full backend suite exactly like Dev CI (pytest -n auto)...' -ForegroundColor DarkGray
$pytestArgs = @('run', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider')
if (-not $Serial) { $pytestArgs += '-n', 'auto' }
Invoke-Step 'Backend Tests (pytest full)' -Command { uv @pytestArgs } -WorkingDirectory $backendDir

# --- 3. Frontend -----------------------------------------------------------------------
Write-Host "`n=== Stage 3: frontend ===" -ForegroundColor White
Invoke-Step 'Frontend Install (frozen)' -Command { pnpm install --frozen-lockfile } -WorkingDirectory $frontendDir
Invoke-Step 'Frontend pnpm audit' -Command { pnpm audit:security } -WorkingDirectory $frontendDir
Invoke-Step 'Frontend Lint' -Command { pnpm lint } -WorkingDirectory $frontendDir
Invoke-Step 'Frontend Typecheck' -Command { pnpm typecheck } -WorkingDirectory $frontendDir
Invoke-Step 'Frontend Tests (vitest)' -Command { pnpm exec vitest run } -WorkingDirectory $frontendDir
Invoke-Step 'Frontend Production Build' -Command { pnpm generate } -WorkingDirectory $frontendDir

# --- 4. Docker ---------------------------------------------------------------------------
if ($SkipDocker) {
    Write-Host "`n=== Stage 4: Docker SKIPPED (-SkipDocker) ===" -ForegroundColor Yellow
}
else {
    Write-Host "`n=== Stage 4: Docker ===" -ForegroundColor White
    Invoke-Step 'Compose Config (dev + prod)' -Command {
        docker compose -f infrastructure/docker-compose.yml config --quiet
        if ($LASTEXITCODE -ne 0) { throw 'dev compose config invalid' }
        docker compose -f infrastructure/docker-compose.prod.yml config --quiet
        if ($LASTEXITCODE -ne 0) { throw 'prod compose config invalid' }
    }

    Invoke-Step 'Docker Build: backend' -Command { docker build -q -t lcs-ci-backend ./backend } -WorkingDirectory $repoRoot
    Invoke-Step 'Docker Build: frontend' -Command { docker build -q -t lcs-ci-frontend ./frontend } -WorkingDirectory $repoRoot

    Invoke-Step 'Container Smoke: backend' -Command { & (Join-Path $PSScriptRoot 'smoke-backend.ps1') }
    Invoke-Step 'Container Smoke: frontend' -Command { & (Join-Path $PSScriptRoot 'smoke-frontend.ps1') }
}

# --- Summary ------------------------------------------------------------------------------
$script:swatch.Stop()
$totalSeconds = [int]$script:swatch.Elapsed.TotalSeconds
$totalLabel = '{0}:{1:d2}' -f [int][math]::Floor($totalSeconds / 60), ($totalSeconds % 60)

Write-Host ''
Write-Host 'LOCAL CI RESULTS' -ForegroundColor White
foreach ($result in $script:results) {
    $color = switch ($result.Result) {
        'PASS' { 'Green' } 'FAIL' { 'Red' } default { 'Yellow' }
    }
    Write-Host ("{0}  {1} ({2}s)" -f $result.Name.PadRight(34), $result.Result.PadRight(4), $result.Seconds) -ForegroundColor $color
}
Write-Host ("Total elapsed: {0}" -f $totalLabel) -ForegroundColor DarkGray

if ($script:failures -gt 0) {
    Write-Host "RESULT: BLOCKED ($($script:failures) check(s) failed) - do not push" -ForegroundColor Red
    exit 1
}
Write-Host 'RESULT: READY TO PUSH' -ForegroundColor Green
Write-Host 'Note: GitHub Actions remains authoritative; these scripts mirror its gates locally.' -ForegroundColor DarkGray