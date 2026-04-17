# TMF/Odoo Integration Test Runner
# Usage: .\run_tests.ps1 [-Scenario 1] [-Verbose]

param(
    [int]$Scenario = 0,
    [switch]$Verbose,
    [string]$BaseUrl = "http://localhost:8069",
    [string]$OdooDB = "TMF_Odoo_DB"
)

$env:TMF_BASE_URL = $BaseUrl
$env:ODOO_DB = $OdooDB

$pytestArgs = @("-v", "--tb=short")

if ($Verbose) {
    $pytestArgs += "-s"
}

if ($Scenario -gt 0) {
    $testFile = "test_{0:D2}_*.py" -f $Scenario
    Write-Host "Running scenario $Scenario ($testFile)..." -ForegroundColor Cyan
    python -m pytest $pytestArgs $testFile
} else {
    Write-Host "Running ALL scenarios..." -ForegroundColor Cyan
    python -m pytest $pytestArgs
}

Write-Host "`nDone." -ForegroundColor Green
