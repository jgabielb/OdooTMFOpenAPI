# 1. Stop the background Odoo service (so we can take over the port)
Write-Host "Stopping background Odoo service..."
Stop-Service "odoo-server-19.0" -ErrorAction SilentlyContinue
Stop-Service "odoo-19.0" -ErrorAction SilentlyContinue

# 2. Define your paths (Based on the info you gave me)
$Py = "C:\Program Files\Odoo 19.0.20251209\python\python.exe"
$OdooRoot = "C:\Program Files\Odoo 19.0.20251209\server"
$Bin = "$OdooRoot\odoo-bin"
$Conf = "$OdooRoot\odoo.conf"
$BaseAddons = "$OdooRoot\addons"
# IMPORTANT: This is your custom folder
$MyAddons = "C:\Users\Joao Gabriel\OneDrive\work_area\OdooBSS"

# 3. Run Odoo
# We use -c to load the database passwords from the config file
# We append your custom folder to the addons-path
# -d TMF_Dev creates a new DB for this project

# -i tmf_base installs your module immediately
Write-Host "Starting Odoo Development Server..."
# & $Py $Bin -c $Conf --addons-path="$BaseAddons,$MyAddons" -d TMF_Clean_DB -i tmf_base,tmf_party,tmf_product_catalog
# & $Py $Bin -c $Conf --addons-path="$BaseAddons,$MyAddons" -d TMF_Clean_DB -u all -i sale,tmf_product_catalog
# & $Py $Bin -c $Conf --addons-path="$BaseAddons,$MyAddons" -d TMF_Clean_DB -u tmf_product_catalog
# & $Py $Bin -c $Conf --addons-path="$BaseAddons,$MyAddons" -d TMF_Clean_DB -i sale_management,tmf_product_catalog
# & $Py $Bin -c $Conf --addons-path="$BaseAddons,$MyAddons" -d TMF_Clean_DB -u all -i tmf_product_ordering0
& $Py $Bin -c $Conf --addons-path="$BaseAddons,$MyAddons" -d TMF_Clean_DB