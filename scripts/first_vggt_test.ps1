$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Missing repo-local virtualenv at .venv. Run scripts/bootstrap_local.ps1 first."
}

$RuntimeConfig = "examples\runtime_configs\vggt_local.json"
$OutDir = "dist_vggt_first_test"

Write-Host "Running Lathe doctor with VGGT runtime config..."
& $Python -m lathe.cli doctor --runtime-config $RuntimeConfig

Write-Host ""
Write-Host "Running first strict VGGT build. This can take a while on CPU..."
& $Python -m lathe.cli build examples\reconstruct_courier_from_views.lth reconstruct_courier_from_views --out $OutDir --runtime-config $RuntimeConfig
