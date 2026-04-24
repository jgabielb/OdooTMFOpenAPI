# Generate a self-signed certificate for local HTTPS testing
# Uses a disposable openssl Docker container (no host dependencies)
# Run from the deploy/ directory

$certDir = Join-Path $PSScriptRoot "certs"
New-Item -ItemType Directory -Force -Path $certDir | Out-Null

Write-Host "Generating self-signed certificate in $certDir..."

# Use forward slashes for the volume mount (Docker on Windows)
$certDirMount = $certDir -replace '\\', '/'

docker run --rm `
    -v "${certDirMount}:/certs" `
    alpine/openssl req -x509 -nodes -days 365 -newkey rsa:2048 `
        -keyout /certs/privkey.pem `
        -out /certs/fullchain.pem `
        -subj "/C=CL/ST=Local/L=Dev/O=TMF/OU=BSS/CN=localhost" `
        -addext "subjectAltName=DNS:localhost,DNS:tmf.local,IP:127.0.0.1"

if ($LASTEXITCODE -eq 0 -and (Test-Path (Join-Path $certDir "fullchain.pem"))) {
    Write-Host ""
    Write-Host "Certificate: $(Join-Path $certDir 'fullchain.pem')"
    Write-Host "Key:         $(Join-Path $certDir 'privkey.pem')"
    Write-Host ""
    Write-Host "Next: docker compose up -d"
} else {
    Write-Error "Certificate generation failed."
    exit 1
}
