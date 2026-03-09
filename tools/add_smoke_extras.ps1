$ErrorActionPreference = "Stop"

$cfgPath = "OdooTMFOpenAPI/tools/tmf_api_smoke.sample.json"
$cfg = Get-Content -Raw $cfgPath | ConvertFrom-Json

$requested = @(
  "testEnvironmentAllocationExecution","testDataSchema","testResourceAPI","testSuiteExecution","metadataCategory","monitor","device","workSpecification","resourceCatalog","userEquipment","warrantySpecification","taskFlowSpecification","association","cloudApplication","work","cancelResourceReservation","dunningScenario","iotDeviceSpecification","managedEntity","physicalResource","testSuite","testDataInstanceDefinition","testSuiteResult","userEquipmentSpecification","resourcePool","queryWorkQualification","event","nonFunctionalTestExecution","cloudApplicationSpecification","checkWorkQualification","productOffering","iotManagementEvent","metadataCatalogItem","iotDataEvent","concreteEnvironmentMetaModel","dataAccessEndpoint","entity","iotDevice","customer360","entityCatalog","geographicLocation","nonFunctionalTestResultDefinition","resourceInventory","riskAssessment","outage","resourceRole","topic","userinfo","transferBalance","warranty","processFlow","partyPrivacyAgreement","productUsageSpecification","provisioningArtifact","processFlowSpecification","metadataSpecification","productSpecification","dunningRule","productOrderRiskAssessment","productOfferingRiskAssessment","resourceRoleSpecification","serviceUsage","shoppingCartRiskAssessment","taskFlow","testCase","testCaseExecution","testCaseResult"
)

$existingPaths = @{}
foreach ($t in $cfg.tests) {
  if ($t.collection_path) { $existingPaths[$t.collection_path.ToLower()] = $true }
}

$existingNames = @{}
foreach ($t in $cfg.tests) {
  if ($t.name) { $existingNames[$t.name.ToLower()] = $true }
}

$routeLines = rg -n '@http\.route\(\[?\s*f?[''"]/tmf-api/[^''"]+' OdooTMFOpenAPI | Out-String
$routes = @()
foreach ($line in ($routeLines -split "`n")) {
  if ($line -match '/tmf-api/[^''"\],\)]*') {
    $routes += $Matches[0]
  }
}
$routes = $routes | Sort-Object -Unique

function Find-Route([string]$token) {
  $tokenEsc = [regex]::Escape($token)
  $cands = $routes | Where-Object { $_ -match "(?i)/$tokenEsc(\b|/|$)" }
  if (-not $cands) {
    $cands = $routes | Where-Object { $_ -match "(?i)$tokenEsc" }
  }
  if ($cands) {
    $plain = $cands | Where-Object { $_ -notmatch '<string:' }
    if ($plain) { return ($plain | Select-Object -First 1) }
    return ($cands | Select-Object -First 1)
  }
  return $null
}

$added = @()
$missing = @()

foreach ($token in $requested) {
  $route = Find-Route $token
  if (-not $route) {
    $missing += $token
    continue
  }

  $path = $route -replace '/<string:[^>]+>', ''
  $path = $path -replace '/+$', ''
  if ([string]::IsNullOrWhiteSpace($path)) {
    $missing += $token
    continue
  }

  if ($existingPaths.ContainsKey($path.ToLower())) { continue }

  $name = "Extra $token"
  $i = 2
  while ($existingNames.ContainsKey($name.ToLower())) {
    $name = "Extra $token $i"
    $i += 1
  }

  $existingNames[$name.ToLower()] = $true
  $existingPaths[$path.ToLower()] = $true

  $obj = [ordered]@{
    name = $name
    collection_path = $path
    list = [ordered]@{
      expected_status = @(200)
    }
    scenarios = [ordered]@{
      list_fields_enabled = $false
      get_by_id_fields_enabled = $false
      list_by_id_filter_enabled = $false
      not_found_enabled = $false
    }
  }

  $cfg.tests += (New-Object psobject -Property $obj)
  $added += "$token -> $path"
}

$cfg | ConvertTo-Json -Depth 100 | Set-Content -Path $cfgPath

Write-Output ("ADDED={0}" -f $added.Count)
Write-Output ("MISSING={0}" -f $missing.Count)
if ($missing.Count -gt 0) {
  Write-Output ("MISSING_TOKENS={0}" -f ($missing -join ","))
}
if ($added.Count -gt 0) {
  Write-Output "ADDED_SAMPLE:"
  $added | Select-Object -First 50 | ForEach-Object { Write-Output $_ }
}

