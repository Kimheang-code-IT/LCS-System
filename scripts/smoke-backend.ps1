<#
.SYNOPSIS
    Smoke-tests the locally built backend image: it must run Alembic against a
    throwaway PostgreSQL container and answer /health before the smoke ends.

.DESCRIPTION
    Isolated Docker network, throwaway containers, no host ports, no volumes,
    full cleanup on success AND failure. Never touches production or the dev
    stack; requires the image from `docker build -t lcs-ci-backend .`.

    The boot script travels as a bind-mounted file (a PowerShell 5.1 argument
    with quotes/newlines is rewritten by CreateProcess and would arrive mangled).
#>
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

# 5.1 turns native-stderr redirects into error records that EAP=Stop can throw
# on; cmd absorbs everything natively instead.
function Remove-Smoke {
    cmd /c "docker rm -f lcs-ci-db >nul 2>&1"
    cmd /c "docker network rm lcs-ci-smoke >nul 2>&1"
}

# Boot: migrate, serve, self-check /health (exit 5 = migration, 6 = health).
# ASCII on purpose: a UTF-8 BOM would confuse /bin/sh.
$boot = Join-Path ([System.IO.Path]::GetTempPath()) 'lcs-backend-boot.sh'
@"
#!/bin/sh
set -u
alembic upgrade head || exit 5
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
APP=`$!
for i in `$(seq 1 30); do
    if python -c "import sys,urllib.request; urllib.request.urlopen(sys.argv[1],timeout=2).read()" "http://localhost:8000/health" 2>/dev/null; then
        echo "backend /health OK"
        kill `$APP
        exit 0
    fi
    sleep 1
done
kill `$APP
exit 6
"@ | Set-Content -Path $boot -Encoding ASCII

try {
    $null = docker image inspect lcs-ci-backend 2>&1
    if ($LASTEXITCODE -ne 0) { throw "image lcs-ci-backend not found; run the Docker build step first" }

    Remove-Smoke
    $null = docker network create lcs-ci-smoke 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'could not create the smoke network' }

    $null = docker run -d --name lcs-ci-db --network lcs-ci-smoke `
        -e POSTGRES_USER=freight -e POSTGRES_PASSWORD=cismoke -e POSTGRES_DB=freight `
        postgres:16-alpine 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'could not start the smoke postgres' }
    $null = docker exec lcs-ci-db sh -c 'until pg_isready -U freight -d freight >/dev/null 2>&1; do sleep 1; done' 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'smoke postgres never became ready' }

    docker run --rm --network lcs-ci-smoke -v "${boot}:/lcs-boot.sh:ro" `
        -e DATABASE_URL=postgresql+asyncpg://freight:cismoke@lcs-ci-db/freight `
        -e JWT_SECRET_KEY=ci-smoke-secret-0123456789abcdef `
        -e CSRF_SECRET_KEY=ci-smoke-csrf-0123456789abcdef `
        -e FIELD_ENCRYPTION_KEY=ci-smoke-field-key-0123456789 `
        -e REDIS_ENABLED=false -e ENVIRONMENT=development -e DEBUG=true `
        lcs-ci-backend sh /lcs-boot.sh
    $code = $LASTEXITCODE
    Remove-Smoke
    if ($code -eq 5) { throw 'alembic migration failed in the built backend image' }
    if ($code -eq 6) { throw 'backend /health never answered in the built backend image' }
    if ($code -ne 0) { throw "backend smoke container exited with $code" }
    Write-Host '        migrations + /health OK in lcs-ci-backend' -ForegroundColor DarkGray
}
catch {
    Remove-Smoke
    throw
}
finally {
    Remove-Item $boot -ErrorAction SilentlyContinue
}