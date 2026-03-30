param(
    [Parameter(Mandatory = $false)]
    [string]$Target = ".",

    [Parameter(Mandatory = $false)]
    [string]$GeneratorCommand = "",

    [Parameter(Mandatory = $false)]
    [switch]$Validate,

    [Parameter(Mandatory = $false)]
    [string]$Database = "TMF_Odoo_DB",

    [Parameter(Mandatory = $false)]
    [string]$Modules = "",

    [Parameter(Mandatory = $false)]
    [int]$DbPort = 5433,

    [Parameter(Mandatory = $false)]
    [string]$OdooConf = "C:\Program Files\Odoo 19.0.20260221\server\odoo.conf",

    [Parameter(Mandatory = $false)]
    [string]$OdooPython = "C:\Program Files\Odoo 19.0.20260221\python\python.exe",

    [Parameter(Mandatory = $false)]
    [string]$OdooBin = "C:\Program Files\Odoo 19.0.20260221\server\odoo-bin",

    [Parameter(Mandatory = $false)]
    [string]$AddonsPath = "C:\Program Files\Odoo 19.0.20260221\server\odoo\addons,C:\Users\Joao Gabriel\OneDrive\work_area\OdooTMFOpenAPI"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$enhancer = Join-Path $PSScriptRoot "apply_ui_generator_defaults.py"

Write-Host "== OdooTMFOpenAPI UI regeneration wrapper ==" -ForegroundColor Cyan
Write-Host "Repo root: $repoRoot"
Write-Host "Target:    $Target"

if ($GeneratorCommand -and $GeneratorCommand.Trim()) {
    Write-Host "\n[1/3] Running generator command..." -ForegroundColor Yellow
    Write-Host "Command: $GeneratorCommand"
    Push-Location $repoRoot
    try {
        Invoke-Expression $GeneratorCommand
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "\n[1/3] No generator command provided. Skipping generation step." -ForegroundColor DarkYellow
}

Write-Host "\n[2/3] Applying UI post-generation defaults..." -ForegroundColor Yellow
& python $enhancer $Target --write
if ($LASTEXITCODE -ne 0) {
    throw "UI post-generation enhancer failed with exit code $LASTEXITCODE"
}

if ($Validate) {
    Write-Host "\n[3/3] Running Odoo validation..." -ForegroundColor Yellow
    if (-not $Modules.Trim()) {
        throw "-Validate was requested but no -Modules value was provided."
    }
    & $OdooPython $OdooBin -c $OdooConf "--addons-path=$AddonsPath" --db_port=$DbPort -d $Database -u $Modules --stop-after-init
    if ($LASTEXITCODE -ne 0) {
        throw "Odoo validation failed with exit code $LASTEXITCODE"
    }
}
else {
    Write-Host "\n[3/3] Validation skipped." -ForegroundColor DarkYellow
}

Write-Host "\nDone." -ForegroundColor Green
