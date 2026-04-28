param(
    [string]$Python = "",
    [string]$OutDir = "",
    [string[]]$PytestArgs = @(
        "-q",
        "tests/test_lathe.py",
        "tests/test_roundtrip.py",
        "tests/test_doctor.py",
        "tests/unit/test_runtime_config.py",
        "-m",
        "not requires_blender and not requires_xatlas and not requires_torch and not requires_network"
    )
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $Python) {
    $WindowsVenvPython = Join-Path $Root ".venv\Scripts\python.exe"
    $PosixVenvPython = Join-Path $Root ".venv\bin\python"
    if (Test-Path $WindowsVenvPython) {
        $Python = $WindowsVenvPython
    } elseif (Test-Path $PosixVenvPython) {
        $Python = $PosixVenvPython
    } else {
        $Python = "python"
    }
}

if (-not $OutDir) {
    $OutDir = if ($env:LATHE_SMOKE_OUT) { $env:LATHE_SMOKE_OUT } else { "tmp_lathe_smoke" }
}

function Invoke-LatheSmokeStep {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$Quiet
    )

    if ($Quiet) {
        & $Python @Arguments | Out-Null
    } else {
        & $Python @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Invoke-LatheSmokeStep -Arguments @("-m", "lathe.cli", "doctor")
Invoke-LatheSmokeStep -Arguments @("-m", "lathe.cli", "check", "examples/courier_drone.lth")
Invoke-LatheSmokeStep -Arguments @("-m", "lathe.cli", "plan", "examples/courier_drone.lth", "courier_drone") -Quiet
Invoke-LatheSmokeStep -Arguments (@("-m", "pytest") + $PytestArgs)
Invoke-LatheSmokeStep -Arguments @("-m", "lathe.cli", "build", "examples/courier_drone.lth", "courier_drone", "--out", $OutDir)

Write-Host "Lathe smoke passed. Build artifacts written under $OutDir/courier_drone."
