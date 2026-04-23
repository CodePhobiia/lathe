param(
    [string]$Python = "python",
    [switch]$Dev,
    [switch]$HunyuanHttp,
    [switch]$VGGT,
    [switch]$XAtlas,
    [switch]$Export,
    [switch]$SkipDoctor
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path .venv)) {
    & $Python -m venv .venv
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$VsDevCmd = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
& $VenvPython -m pip install --upgrade pip setuptools wheel

$extras = New-Object System.Collections.Generic.List[string]
if ($Dev) { $extras.Add("dev") }
if ($Export) { $extras.Add("export") }
if ($HunyuanHttp) { $extras.Add("hunyuan_http") }
if ($VGGT) { $extras.Add("vggt") }
if ($XAtlas) {
    if ((Get-Command nmake -ErrorAction SilentlyContinue) -or (Test-Path $VsDevCmd)) {
        $extras.Add("xatlas")
    } else {
        Write-Warning "Skipping xatlas extra because nmake is not available. Install Visual Studio Build Tools (Desktop C++ workload) first."
    }
}

$PackageSpec = if ($extras.Count -gt 0) { ".[{0}]" -f ($extras -join ",") } else { "." }
if ($extras.Contains("xatlas") -and (Test-Path $VsDevCmd)) {
    cmd /c "`"$VsDevCmd`" -host_arch=x64 -arch=x64 && `"$VenvPython`" -m pip install -e $PackageSpec"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    & $VenvPython -m pip install -e $PackageSpec
}

if ($VGGT) {
    Write-Host ""
    Write-Host "VGGT note:"
    Write-Host "  The pip extra installs torch only. The official VGGT package is not currently published on PyPI."
    Write-Host "  Install it manually if needed:"
    Write-Host "    git clone https://github.com/facebookresearch/vggt.git external\vggt"
    Write-Host "    .\.venv\Scripts\python.exe -m pip install -e .\external\vggt"
}

if (-not $SkipDoctor) {
    & $VenvPython -m lathe.cli doctor
}
