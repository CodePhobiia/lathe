param(
    [string]$Python = "",
    [string]$Source = "examples/courier_drone.lth",
    [string]$Asset = "courier_drone",
    [string]$OutDir = "",
    [switch]$DryRun,
    [switch]$SkipBuild,
    [switch]$VerboseOutput
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
    $OutDir = if ($env:LATHE_DEMO_OUT) { $env:LATHE_DEMO_OUT } else { "tmp_lathe_demo" }
}

$DemoDir = Join-Path $OutDir "_demo_workflow"
if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $DemoDir | Out-Null
}

function Invoke-DemoStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [string]$Artifact = ""
    )

    Write-Host ""
    Write-Host "== $Title =="
    Write-Host "$Python $($Arguments -join ' ')"
    if ($DryRun) {
        return
    }
    if ($Artifact) {
        $ArtifactPath = Join-Path $DemoDir $Artifact
        $ArtifactParent = Split-Path -Parent $ArtifactPath
        if ($ArtifactParent) {
            New-Item -ItemType Directory -Force -Path $ArtifactParent | Out-Null
        }
        $CommandOutput = & $Python @Arguments 2>&1
        $CommandStatus = $LASTEXITCODE
        $Utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
        if ($null -eq $CommandOutput) {
            $OutputText = ""
        } elseif ($CommandOutput -is [array]) {
            $OutputText = [string]::Join([Environment]::NewLine, [string[]]$CommandOutput) + [Environment]::NewLine
        } else {
            $OutputText = [string]$CommandOutput + [Environment]::NewLine
        }
        [System.IO.File]::WriteAllText($ArtifactPath, $OutputText, $Utf8NoBom)
        if ($VerboseOutput) {
            $CommandOutput | Write-Output
        }
        if ($CommandStatus -eq 0) {
            Write-Host "Saved output: $ArtifactPath"
        }
    } else {
        & $Python @Arguments
        $CommandStatus = $LASTEXITCODE
    }
    if ($CommandStatus -ne 0) {
        if ($Artifact) {
            Write-Host "Command failed. See $ArtifactPath for details."
        }
        exit $CommandStatus
    }
}

Write-Host "Lathe core workflow demo"
Write-Host "Source: $Source"
Write-Host "Asset:  $Asset"
Write-Host "Output: $OutDir\$Asset"

Invoke-DemoStep -Title "Check local environment" -Arguments @("-m", "lathe.cli", "doctor") -Artifact "doctor.txt"
Invoke-DemoStep -Title "Normalize source" -Arguments @("-m", "lathe.cli", "normalize", $Source) -Artifact "normalized_program.json"
Invoke-DemoStep -Title "Run semantic checks" -Arguments @("-m", "lathe.cli", "check", $Source) -Artifact "check.txt"
Invoke-DemoStep -Title "Show build plan" -Arguments @("-m", "lathe.cli", "plan", $Source, $Asset) -Artifact "plan.json"
Invoke-DemoStep -Title "Materialize asset" -Arguments @("-m", "lathe.cli", "materialize", $Source, $Asset) -Artifact "materialized_asset.json"

if (-not $SkipBuild) {
    Invoke-DemoStep -Title "Build certified package" -Arguments @(
        "-m", "lathe.cli", "build", $Source, $Asset, "--out", $OutDir, "--report", "json"
    ) -Artifact "build_report_cli.json"
    Invoke-DemoStep -Title "Inspect build report" -Arguments @("-m", "lathe.cli", "inspect", (Join-Path $OutDir $Asset), "--json") -Artifact "inspect.json"
}

Write-Host ""
if ($DryRun) {
    Write-Host "Dry run complete. Re-run without -DryRun to execute the demo."
} elseif ($SkipBuild) {
    Write-Host "Demo commands passed through materialization. Outputs are in $DemoDir."
    Write-Host "Re-run without -SkipBuild to create packaged artifacts."
} else {
    Write-Host "Demo complete. Outputs are in $DemoDir."
    Write-Host "Open $OutDir\$Asset\stages\package\package_manifest.json for packaged artifacts."
}
