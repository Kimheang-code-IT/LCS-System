<#
.SYNOPSIS
    Smoke-tests the locally built frontend image: nginx serving the generated
    SPA must answer HTTP 200 on a temporary high port.

.DESCRIPTION
    Uses port 18080 on the loopback only; throws-away container is always
    removed. Never touches production or the dev stack (which owns port 80).
    Requires the image from `docker build -t lcs-ci-frontend .`.
#>
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

function Remove-Smoke {
    docker rm -f lcs-ci-fe 2>$null | Out-Null
}

try {
    if (-not (docker image inspect lcs-ci-frontend *> $null)) {
        throw "image lcs-ci-frontend not found; run the Docker build step first"
    }
    Remove-Smoke
    docker run -d --name lcs-ci-fe -p 127.0.0.1:18080:80 lcs-ci-frontend | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'could not start the smoke frontend container' }

    $ok = $false
    for ($i = 0; $i -lt 15; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri http://127.0.0.1:18080/ -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -eq 200) { $ok = $true; break }
        }
        catch { Start-Sleep -Seconds 1 }
    }
    Remove-Smoke
    if (-not $ok) { throw 'the frontend image did not serve the SPA on 127.0.0.1:18080' }
    Write-Host '        SPA served HTTP 200 from lcs-ci-frontend' -ForegroundColor DarkGray
}
catch {
    Remove-Smoke
    throw
}