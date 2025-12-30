$BaseDir = ".\tmf_attachment"

# 1. Create Directories
New-Item -ItemType Directory -Force -Path "$BaseDir\security" | Out-Null
New-Item -ItemType Directory -Force -Path "$BaseDir\views" | Out-Null
New-Item -ItemType Directory -Force -Path "$BaseDir\models" | Out-Null
New-Item -ItemType Directory -Force -Path "$BaseDir\controllers" | Out-Null

# 2. Create Dummy Security File (Header only, so it's valid but empty)
$CsvContent = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink"
Set-Content -Path "$BaseDir\security\ir.model.access.csv" -Value $CsvContent

# 3. Create Dummy View File (Empty Odoo tag)
$XmlContent = "<odoo>`n</odoo>"
Set-Content -Path "$BaseDir\views\generated_views.xml" -Value $XmlContent

# 4. Create Dummy Model (To satisfy init)
$ModelContent = @"
from odoo import models
class TMFAttachment(models.AbstractModel):
    _name = 'tmf.attachment'
    _description = 'TMF Attachment Placeholder'
"@
Set-Content -Path "$BaseDir\models\main_model.py" -Value $ModelContent

# 5. Fix Inits
Set-Content -Path "$BaseDir\models\__init__.py" -Value "from . import main_model"
Set-Content -Path "$BaseDir\controllers\__init__.py" -Value "" # Empty controller is fine

Write-Host "Fixed tmf_attachment structure." -ForegroundColor Green