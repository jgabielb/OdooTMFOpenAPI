# 1. Stop background services (Launches a separate mini-window just for this)
Write-Host "Stopping background Odoo services..." -ForegroundColor Yellow
try {
    # This magic line asks for Admin rights JUST to stop the service
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -Command Stop-Service 'odoo-server-19.0' -Force; Stop-Service 'odoo-19.0' -Force" -Wait
} catch {
    Write-Warning "Could not stop service automatically. If Odoo fails to start, stop the service manually."
}

# 2. Define Paths
$OdooVersion = "19.0.20251210"
$Py          = "C:\Program Files\Odoo $OdooVersion\python\python.exe"
$OdooRoot    = "C:\Program Files\Odoo $OdooVersion\server"
$Bin         = Join-Path $OdooRoot "odoo-bin"
$Conf        = Join-Path $OdooRoot "odoo.conf"
$BaseAddons  = Join-Path $OdooRoot "addons"

# 3. Define User Custom Addons Path
$UserProfile = $env:USERPROFILE
$MyAddons    = Join-Path $UserProfile "OneDrive\work_area\OdooBSS"

# Validate paths
if (-not (Test-Path $MyAddons)) {
    Write-Error "CRITICAL: Custom addons path not found: $MyAddons"
    exit
}

Write-Host "------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Odoo Source: $OdooRoot"
Write-Host "Custom Code: $MyAddons"
Write-Host "Database:    TMF_Odoo_DB (Port 5433)"
Write-Host "------------------------------------------------------" -ForegroundColor Cyan

# 4. Define Modules to Update (To fix the 'create' bug)
$ModulesToUpdate = "tmf_billing_management" 

# 5. Run Odoo
Write-Host "Starting Odoo Server..." -ForegroundColor Green

& $Py $Bin `
    -c $Conf `
    --addons-path="$BaseAddons,$MyAddons" `
    --db_port=5433 `
    -d TMF_Odoo_DB `
    -u $ModulesToUpdate