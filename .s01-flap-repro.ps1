$env:E2E_USERNAME = 's01e2efull@example.com'
$env:E2E_PASSWORD = 'Passw0rd!'
Set-Location 'D:\freelancer\Freight Forwarding\frontend'
for ($i = 1; $i -le 5; $i++) {
    $out = pnpm exec playwright test e2e/page-authorization.spec.ts --grep "every permitted page" --reporter=line 2>&1 | Out-String
    $fail = ($out -split "`n") | Select-String -Pattern 'opened the page anyway|landed on.*instead' | ForEach-Object { $_.Line.Trim() }
    if ($fail) { Write-Output "RUN $i FAIL"; $fail | ForEach-Object { Write-Output $_ } }
    else { Write-Output "RUN $i PASS" }
}