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

# 1. Core / Manual Modules (The "Smart" Logic)
$CoreModules = "tmf_base,tmf_party,tmf_customer,tmf_product_catalog,tmf_product_ordering,tmf_service_inventory,tmf_resource_inventory,tmf_trouble_ticket,tmf_billing_management"

# 2. Generated Modules (The "Data" Layers)
# Note: Excluded tmf_product_order, tmf_service, tmf_resource to avoid conflicts
$GenModules = "tmf_service_activation_configuration,tmf_account,tmf_agreement,tmf_alarm,tmf_appointment,tmf_communication_message,tmf_customer_bill,tmf_device,tmf_document,tmf_entity,tmf_entity_catalog,tmf_event,tmf_general_test_artifact,tmf_geographic_address,tmf_geographic_location,tmf_geographic_site,tmf_medium_characteristic,tmf_party_interaction,tmf_party_privacy_agreement,tmf_party_role,tmf_party_role_product_offering_risk_assessment,tmf_payment,tmf_permission,tmf_process_flow,tmf_product,tmf_product_offering_qualification,tmf_product_ref_or_value,tmf_resource_catalog,tmf_resource_function,tmf_resource_order,tmf_service_catalog,tmf_service_level_objective,tmf_service_order,tmf_service_problem,tmf_service_qualification,tmf_service_test,tmf_shopping_cart,tmf_test_case,tmf_test_execution,tmf_test_scenario,tmf_transfer_balance,tmf_usage,tmf_usage_consumption,tmf_userinfo,tmf_product_inventory"

# Combine them
$ModulesToUpdate = "base,$CoreModules,$GenModules"
# $ModulesToUpdate = "base,tmf_attachment"

# 5. Run Odoo
Write-Host "Starting Odoo Server..." -ForegroundColor Green

& $Py $Bin `
    -c $Conf `
    --addons-path="$BaseAddons,$MyAddons" `
    --db_port=5433 `
    -d TMF_Odoo_DB `
    -u $ModulesToUpdate