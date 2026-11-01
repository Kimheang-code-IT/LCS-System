<#
.SYNOPSIS
    Smoke-tests the locally built backend image: it must run Alembic against a
    throwaway PostgreSQL container and answer /health before the smoke ends.

.DESCRIPTION
    Isolated Docker network, throwaway containers, no host ports, no volumes,
    full cleanup on success AND failure. Never touches production or the dev
    stack; requires the image from `docker build -t lcs-ci-backend .`.
#>
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

function Remove-Smoke {
    docker rm -f lcs-ci-db 2>$null | Out-Null
    docker network rm lcs-ci-smoke 2>$null | Out-Null
}

$createdNetwork = $false
try {
    if (-not (docker image inspect lcs-ci-backend *> $null)) {
        throw "image lcs-ci-backend not found; run the Docker build step first"
    }
    docker network inspect lcs-ci-smoke *> $null
    if ($LASTEXITCODE -ne 0) {
        docker network create lcs-ci-smoke | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'could not create the smoke network' }
        $createdNetwork = $true
    }

    docker rm -f lcs-ci-db 2>$null | Out-Null
    docker run -d --name lcs-ci-db --network lcs-ci-smoke `
        -e POSTGRES_USER=freight -e POSTGRES_PASSWORD=cismoke -e POSTGRES_DB=freight `
        postgres:16-alpine | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'could not start the smoke postgres' }
    docker exec lcs-ci-db sh -c 'until pg_isready -U freight -d freight >/dev/null 2>&1; do sleep 1; done'
    if ($LASTEXITCODE -ne 0) { throw 'smoke postgres never became ready' }

    # The real image entrypoint path: migrate, boot, and pass /health — the
    # same readiness the production deploy verifies. No host port is used: the
    # health check runs inside the container.
    docker run --rm --network lcs-ci-smoke `
        -e DATABASE_URL=postgresql+asyncpg://freight:cismoke@lcs-ci-db/freight `
        -e JWT_SECRET_KEY=ci-smoke-secret-0123456789abcdef `
        -e CSRF_SECRET_KEY=ci-smoke-csrf-0123456789abcdef `
        -e FIELD_ENCRYPTION_KEY=ci-smoke-field-key-0123456789 `
        -e REDIS_ENABLED=false -e ENVIRONMENT=development -e DEBUG=true `
        lcs-ci-backend sh -c '
            alembic upgrade head || exit 5
            uvicorn app.main:app --host 0.0.0.0 --port 8000 &
            APP=$!
            for i in $(seq 1 30); do
                if python -c "import urllib.request; urllib.request.urlopen(\"http://localhost:8000/health\", timeout=2).read()" 2>/dev/null; then
                    echo "backend /health OK"
                    kill $APP 2>/dev/null
                    exit 0
                fi
                sleep 1
            done
            kill $APP 2>/dev/null
            exit 6
        '
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