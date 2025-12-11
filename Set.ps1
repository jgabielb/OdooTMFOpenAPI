# 1. Stop the background Odoo service (so we can take over the port)
Write-Host "Stopping background Odoo service..."
Stop-Service "odoo-server-19.0" -ErrorAction SilentlyContinue
Stop-Service "odoo-19.0" -ErrorAction SilentlyContinue

# 2. Define your paths

# Odoo install (adjust these if your Odoo version/path changes)
$Py        = "C:\Program Files\Odoo 19.0.20251209\python\python.exe"
$OdooRoot  = "C:\Program Files\Odoo 19.0.20251209\server"
$Bin       = Join-Path $OdooRoot "odoo-bin"
$Conf      = Join-Path $OdooRoot "odoo.conf"
$BaseAddons = Join-Path $OdooRoot "addons"

# Current user profile (no hardcoded username)
$UserProfile = $env:USERPROFILE

# IMPORTANT: custom addons folder under the current user's OneDrive
$MyAddons = Join-Path $UserProfile "OneDrive\work_area\OdooBSS"

Write-Host "Using custom addons folder: $MyAddons"

# 3. Run Odoo
# -c to load config (DB passwords, etc.)
# --addons-path appends your custom folder
# -d TMF_Clean_DB uses that DB
# -u all updates all installed modules
# -i tmf_resource_inventory installs that module (and deps)

Write-Host "Starting Odoo Development Server..."
& $Py $Bin `
    -c $Conf `
    --addons-path="$BaseAddons,$MyAddons" `
    -d TMF_Clean_DB `
    -u all `
    # -i tmf_resource_inventory
