# 1. Stop background services (Launches a separate mini-window just for this)
Write-Host "Stopping background Odoo services..." -ForegroundColor Yellow
try {
    # This magic line asks for Admin rights JUST to stop the service
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -Command Stop-Service 'odoo-server-19.0' -Force; Stop-Service 'odoo-19.0' -Force" -Wait
} catch {
    Write-Warning "Could not stop service automatically. If Odoo fails to start, stop the service manually."
}

# 2. Define Paths
$OdooVersion = "19.0.20260221"
$Py          = "C:\Program Files\Odoo $OdooVersion\python\python.exe"
$OdooRoot    = "C:\Program Files\Odoo $OdooVersion\server"
$Bin         = Join-Path $OdooRoot "odoo-bin"
$Conf        = Join-Path $OdooRoot "odoo.conf"
$BaseAddons  = Join-Path $OdooRoot "odoo\addons"

# 3. Define User Custom Addons Path
$UserProfile = $env:USERPROFILE
$MyAddons    = Join-Path $UserProfile "OneDrive\work_area\OdooTMFOpenAPI"

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
$CoreModules = "tmf_base,tmf_party,tmf_customer,tmf_product_catalog,tmf_product_ordering,tmf_service_inventory,tmf_resource_inventory,tmf_trouble_ticket,tmf_billing_management,tmfc001_wiring,tmfc027_wiring,tmfc031_wiring"

# 1b. Native Odoo Apps to leverage with TMF data
# Keep this list explicit so environments stay reproducible.
$OdooApps = "contacts,calendar,crm,sale_management,stock,account,purchase,project"

# 2. Generated Modules (The "Data" Layers)
# Note: Excluded tmf_product_order, tmf_service, tmf_resource to avoid conflicts
$GenModules = "tmf_resource_pool_management,tmf_recommendation_management,tmf_customer_bill_management,tmf_user_role_permission,tmf_promotion_management,tmf_payment_method,tmf_partnership_management,tmf_service_quality_management,tmf_change_management,tmf_prepay_balance_management,tmf_quote_management,tmf_service_activation_configuration,tmf_account,tmf_agreement,tmf_alarm,tmf_appointment,tmf_communication_message,tmf_customer_bill,tmf_device,tmf_document,tmf_entity,tmf_entity_catalog,tmf_event,tmf_general_test_artifact,tmf_geographic_address,tmf_geographic_location,tmf_geographic_site,tmf_medium_characteristic,tmf_party_interaction,tmf_party_privacy_agreement,tmf_party_role,tmf_party_role_product_offering_risk_assessment,tmf_payment,tmf_permission,tmf_process_flow,tmf_product,tmf_product_offering_qualification,tmf_product_ref_or_value,tmf_resource_catalog,tmf_resource_function,tmf_resource_activation,tmf_resource_order,tmf_service_catalog,tmf_service_order,tmf_service_problem,tmf_service_qualification,tmf_service_test,tmf_shopping_cart,tmf_test_case,tmf_test_environment,tmf_test_data,tmf_test_result,tmf_test_execution,tmf_test_scenario,tmf_transfer_balance,tmf_usage,tmf_usage_consumption,tmf_userinfo,tmf_product_inventory,tmf_product_stock_relationship,tmf_physical_resource,tmf_managed_entity,tmf_test_data_instance_definition,tmf_non_functional_test_result_definition,tmf_ai_contract_specification,tmf_sales,tmf_shipping_order,tmf_shipment_management,tmf_shipment_tracking_management,tmf_work_management,tmf_work_qualification,tmf_warranty_management,tmf_resource_reservation,tmf_customer360,tmf_digital_identity_management,tmf_incident_management,tmf_metadata_catalog_management,tmf_service_usage_management,tmf_dunning_case_management,tmf_software_compute_management,tmf_cdr_transaction_management,tmf_revenue_sharing_algorithm_management,tmf_revenue_sharing_report_management,tmf_revenue_sharing_model_management,tmf_private_optimized_binding,tmf_cost_management,tmf_resource_role_management,tmf_product_usage_catalog_management,tmf_iot_agent_device_management,tmf_network_as_a_service_management,tmf_self_care_management,tmf_iot_service_management,tmf_ai_management,tmf_intent_management,tmf_5gslice_service_activation,tmf_resource_usage_management,tmf_outage_management,tmf_open_gateway_operate_onboarding_ordering,tmf_open_gateway_operate_product_catalog,tmf_performance_management,tmf_privacy_management"

# Combine them
$ModulesToUpdate = "base,$OdooApps,$CoreModules,$GenModules"
$ModulesToUpgrade = $ModulesToUpdate
# $ModulesToUpdate = "base,tmf_attachment"

# 5. Run Odoo
Write-Host "Starting Odoo Server..." -ForegroundColor Green

& $Py $Bin `
    -c $Conf `
    --addons-path="$BaseAddons,$MyAddons" `
    --log-handler=odoo.addons.rpc.controllers.xmlrpc:ERROR `
    --db_port=5433 `
    -d TMF_Odoo_DB `
    -i $ModulesToUpdate `
    -u $ModulesToUpgrade





