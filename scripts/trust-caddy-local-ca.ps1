$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir "..")
$certPath = Join-Path $projectRoot "caddy-local-root.crt"
$tempCertPath = Join-Path $env:TEMP "caddy-local-root.crt"
$containerName = "ai-study-caddy"
$containerCertPath = "/data/caddy/pki/authorities/local/root.crt"

Write-Host "Exporting Caddy local root CA from container '$containerName'..."
docker cp "${containerName}:${containerCertPath}" $tempCertPath
Copy-Item -Path $tempCertPath -Destination $certPath -Force

if (-not (Test-Path $certPath)) {
    throw "Failed to export Caddy local root CA to $certPath"
}

$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($tempCertPath)
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")

try {
    $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    $existing = $store.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }

    if ($existing) {
        Write-Host "Caddy local root CA is already trusted for the current Windows user."
    } else {
        $store.Add($cert)
        Write-Host "Caddy local root CA has been added to Cert:\CurrentUser\Root."
    }
} finally {
    $store.Close()
}

Write-Host ""
Write-Host "Certificate file: $certPath"
Write-Host "Subject: $($cert.Subject)"
Write-Host "Thumbprint: $($cert.Thumbprint)"
Write-Host ""
Write-Host "Restart your browser, then open https://localhost again."
