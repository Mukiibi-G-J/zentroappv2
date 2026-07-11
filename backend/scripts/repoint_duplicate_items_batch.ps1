# Batch repoint wrong item numbers to canonical items (same tenant + branch).
# Production uses core.settingsprod (set below). Override for local dev, e.g.:
#   $env:DJANGO_SETTINGS_MODULE = "core.settings"
# Edit SCHEMA and LOCATION_CODE for production, then run from zentro-backend:
#   .\scripts\repoint_duplicate_items_batch.ps1
# Dry-run first (default); commit with -Apply:
#   .\scripts\repoint_duplicate_items_batch.ps1 -Apply

param(
    [string] $Schema = "primewise",
    [string] $LocationCode = "MWANJARI",
    [switch] $Apply
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Resolve-Path (Join-Path $here "..")
Set-Location $backend

if (-not $env:DJANGO_SETTINGS_MODULE) {
    $env:DJANGO_SETTINGS_MODULE = "core.settingsprod"
}

$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

$pairs = @(
    @("ITM-000829", "ITM-000145"),
    @("ITM-000836", "ITM-000402"),
    @("ITM-000844", "ITM-000565"),
    @("ITM-000854", "ITM-000689"),
    @("ITM-000848", "ITM-000620"),
    @("ITM-000853", "ITM-000667"),
    @("ITM-000838", "ITM-000250"),
    @("ITM-000826", "ITM-000050"),
    @("ITM-000832", "ITM-000218"),
    @("ITM-000835", "ITM-000377"),
    @("ITM-000857", "ITM-000858")
)

$applyArg = @()
if ($Apply) { $applyArg = @("--apply") }

Write-Host "DJANGO_SETTINGS_MODULE=$($env:DJANGO_SETTINGS_MODULE)" -ForegroundColor DarkGray
Write-Host "Schema=$Schema  Location=$LocationCode  Apply=$($Apply.IsPresent)" -ForegroundColor Cyan

foreach ($p in $pairs) {
    $from = $p[0]
    $to = $p[1]
    Write-Host "`n=== $from -> $to ===" -ForegroundColor Yellow
    & $python manage.py repoint_item_ledger_item `
        --schema=$Schema `
        --from-item-no=$from `
        --to-item-no=$to `
        --location-code=$LocationCode `
        @applyArg
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED (exit $LASTEXITCODE) on $from -> $to" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "`nAll $($pairs.Count) repoint(s) finished OK." -ForegroundColor Green
