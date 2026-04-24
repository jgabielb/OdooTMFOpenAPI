# Generate a locally-trusted certificate using mkcert.
# Browsers will trust this cert with NO warning because mkcert installs
# a local root CA into the Windows (and Firefox) trust stores.
#
# Prerequisite: install mkcert
#   winget install FiloSottile.mkcert
# or via chocolatey:
#   choco install mkcert
#
# Run from the deploy/ directory.

$certDir = Join-Path $PSScriptRoot "certs"
New-Item -ItemType Directory -Force -Path $certDir | Out-Null

$mkcert = Get-Command mkcert -ErrorAction SilentlyContinue
if (-not $mkcert) {
    Write-Error "mkcert not found. Install it first: winget install FiloSottile.mkcert"
    exit 1
}

Write-Host "Installing mkcert local CA (may prompt for admin once)..."
mkcert -install

Write-Host ""
Write-Host "Generating trusted certificate..."
Push-Location $certDir
try {
    mkcert -cert-file fullchain.pem -key-file privkey.pem `
        localhost 127.0.0.1 ::1 tmf.local
} finally {
    Pop-Location
}

if (Test-Path (Join-Path $certDir "fullchain.pem")) {
    Write-Host ""
    Write-Host "Certificate: $(Join-Path $certDir 'fullchain.pem')"
    Write-Host "Key:         $(Join-Path $certDir 'privkey.pem')"
    Write-Host ""
    Write-Host "Browsers will now trust https://localhost with no warning."
    Write-Host "Next: docker compose up -d"
} else {
    Write-Error "Certificate generation failed."
    exit 1
}
