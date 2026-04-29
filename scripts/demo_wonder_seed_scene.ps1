param(
    [string]$Python = "",
    [string]$ExampleDir = "examples/wonder/alchemist_observatory",
    [string]$OutDir = "",
    [switch]$DryRun,
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
    $OutDir = if ($env:LATHE_WONDER_DEMO_OUT) { $env:LATHE_WONDER_DEMO_OUT } else { "tmp_wonder_seed_demo" }
}

$EvidenceDir = Join-Path $OutDir "_demo_evidence"
$SourceDir = Join-Path $EvidenceDir "source_bridge"
$BriefDir = Join-Path $EvidenceDir "brief_lowering"
$PatchDir = Join-Path $EvidenceDir "patch"
$RepairDir = Join-Path $EvidenceDir "repair"
$CuriosityDir = Join-Path $EvidenceDir "curiosity"
$PreviewBuildRoot = Join-Path $OutDir "preview_build"
$PatchedBuildRoot = Join-Path $OutDir "patched_build"
$ExpandedBuildRoot = Join-Path $OutDir "expanded_build"
$BeforeAfterDir = Join-Path $OutDir "before_after"

if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
    New-Item -ItemType Directory -Force -Path $SourceDir | Out-Null
    New-Item -ItemType Directory -Force -Path $BriefDir | Out-Null
    New-Item -ItemType Directory -Force -Path $PatchDir | Out-Null
    New-Item -ItemType Directory -Force -Path $RepairDir | Out-Null
    New-Item -ItemType Directory -Force -Path $CuriosityDir | Out-Null
}

function Assert-DemoInput {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        throw "Required demo input not found: $Path"
    }
}

function Invoke-WonderDemoStep {
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
        $ArtifactPath = Join-Path $EvidenceDir $Artifact
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

$Brief = "$ExampleDir/dream_brief.json"
$Scene = "$ExampleDir/scene_graph.json"
$Patch = "$ExampleDir/scene_patch_more_sacred.json"
$RenderInspection = "$ExampleDir/render_inspection.example.json"
$WorldMemory = "$ExampleDir/world_memory.json"
$SceneSource = Join-Path $SourceDir "alchemist_observatory.scene.lth"
$RoundtripScene = Join-Path $SourceDir "alchemist_observatory.roundtrip.scene_graph.json"
$LoweredScene = Join-Path $BriefDir "alchemist_observatory.lowered.scene_graph.json"
$ScenePlan = Join-Path $EvidenceDir "scene_plan.json"
$SceneAssembly = Join-Path $EvidenceDir "scene_assembly.json"
$PatchedScene = Join-Path $PatchDir "alchemist_observatory.more_sacred.scene_graph.json"
$RepairReport = Join-Path $RepairDir "scene_repair_report.json"
$RepairedScene = Join-Path $RepairDir "alchemist_observatory.repaired.scene_graph.json"
$ExpandedScene = Join-Path $CuriosityDir "alchemist_observatory.opened_archive.scene_graph.json"

Assert-DemoInput -Path $Brief
Assert-DemoInput -Path $Scene
Assert-DemoInput -Path $Patch
Assert-DemoInput -Path $RenderInspection
Assert-DemoInput -Path $WorldMemory

Write-Host "Lathe Wonder seed scene demo"
Write-Host "Example: $ExampleDir"
Write-Host "Output:  $OutDir"
Write-Host "Mode:    deterministic proxy package path"

Invoke-WonderDemoStep -Title "Emit Wonder capabilities" -Arguments @("-m", "lathe.cli", "wonder", "capabilities") -Artifact "00_capabilities.json"
Invoke-WonderDemoStep -Title "Validate Dream Brief schema" -Arguments @("-m", "lathe.cli", "wonder", "validate-brief", $Brief) -Artifact "01_validate_brief.json"
Invoke-WonderDemoStep -Title "Decompose Dream Brief" -Arguments @("-m", "lathe.cli", "wonder", "decompose-brief", $Brief) -Artifact "02_decompose_brief.json"
Invoke-WonderDemoStep -Title "Lower Dream Brief to fallback Scene Graph" -Arguments @("-m", "lathe.cli", "wonder", "lower-brief", $Brief, "--out", $LoweredScene) -Artifact "03_lower_brief.json"
Invoke-WonderDemoStep -Title "Check lowered fallback Scene Graph" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $LoweredScene) -Artifact "04_check_lowered_scene.json"
Invoke-WonderDemoStep -Title "Validate authored Scene Graph schema" -Arguments @("-m", "lathe.cli", "wonder", "validate-scene", $Scene) -Artifact "05_validate_scene.json"
Invoke-WonderDemoStep -Title "Check authored Scene Graph semantics" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $Scene) -Artifact "06_check_scene_graph.json"
Invoke-WonderDemoStep -Title "Check Dream Brief and Scene Graph consistency" -Arguments @("-m", "lathe.cli", "wonder", "check-brief-scene", $Brief, $Scene) -Artifact "07_check_brief_scene.json"
Invoke-WonderDemoStep -Title "Generate JSON-first scene source bridge" -Arguments @("-m", "lathe.cli", "scene", "scene-graph-to-source", $Scene, "--out", $SceneSource) -Artifact "08_scene_graph_to_source.txt"
Invoke-WonderDemoStep -Title "Roundtrip scene source bridge to Scene Graph" -Arguments @("-m", "lathe.cli", "scene", "source-to-scene-graph", $SceneSource, "--out", $RoundtripScene) -Artifact "09_source_to_scene_graph.txt"
Invoke-WonderDemoStep -Title "Check roundtripped Scene Graph" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $RoundtripScene) -Artifact "10_check_roundtrip_scene.json"
Invoke-WonderDemoStep -Title "Plan preview scene build" -Arguments @("-m", "lathe.cli", "scene", "plan", $Scene, "--mode", "preview", "--out", $ScenePlan) -Artifact "11_scene_plan_cli.txt"
Invoke-WonderDemoStep -Title "Validate preview Scene Plan" -Arguments @("-m", "lathe.cli", "wonder", "validate-plan", $ScenePlan) -Artifact "12_validate_scene_plan.json"
Invoke-WonderDemoStep -Title "Assemble scene IR" -Arguments @("-m", "lathe.cli", "scene", "assemble", $Scene, "--out", $SceneAssembly) -Artifact "13_scene_assembly_cli.txt"
Invoke-WonderDemoStep -Title "Validate scene assembly IR" -Arguments @("-m", "lathe.cli", "wonder", "validate-scene-assembly", $SceneAssembly) -Artifact "14_validate_scene_assembly.json"
Invoke-WonderDemoStep -Title "Validate authored World Memory" -Arguments @("-m", "lathe.cli", "wonder", "validate-world-memory", $WorldMemory, "--scene-graph", $Scene) -Artifact "15_validate_world_memory.json"
Invoke-WonderDemoStep -Title "Run scene quality validators" -Arguments @("-m", "lathe.cli", "scene", "validate", $Scene) -Artifact "16_scene_quality_report.json"
Invoke-WonderDemoStep -Title "Build proxy preview Scene Package" -Arguments @("-m", "lathe.cli", "scene", "build", $Scene, "--out", $PreviewBuildRoot, "--mode", "preview") -Artifact "17_preview_build.txt"
Invoke-WonderDemoStep -Title "Validate proxy preview Scene Package" -Arguments @("-m", "lathe.cli", "scene", "package", "validate", "$PreviewBuildRoot/alchemist_observatory") -Artifact "18_validate_preview_package.json"
Invoke-WonderDemoStep -Title "Validate Render Inspection contract" -Arguments @("-m", "lathe.cli", "wonder", "validate-render-inspection", $RenderInspection) -Artifact "19_validate_render_inspection.json"
Invoke-WonderDemoStep -Title "Inspect Render Inspection against scene" -Arguments @("-m", "lathe.cli", "scene", "inspect-render", $Scene, $RenderInspection) -Artifact "20_inspect_render.json"
Invoke-WonderDemoStep -Title "Propose deterministic offline repairs" -Arguments @("-m", "lathe.cli", "scene", "propose-repairs", $Scene, $RenderInspection, "--out", $RepairReport) -Artifact "21_propose_repairs.txt"
Invoke-WonderDemoStep -Title "Validate repair report" -Arguments @("-m", "lathe.cli", "wonder", "validate-scene-repair-report", $RepairReport) -Artifact "22_validate_repair_report.json"
Invoke-WonderDemoStep -Title "Run deterministic offline repair" -Arguments @("-m", "lathe.cli", "scene", "repair", $Scene, $RenderInspection, "--out", $RepairedScene, "--report-out", $RepairReport) -Artifact "23_repair_scene.txt"
Invoke-WonderDemoStep -Title "Check repaired Scene Graph" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $RepairedScene) -Artifact "24_check_repaired_scene.json"
Invoke-WonderDemoStep -Title "Apply more_sacred Scene Patch" -Arguments @("-m", "lathe.cli", "scene", "patch", $Scene, $Patch, "--out", $PatchedScene) -Artifact "25_apply_more_sacred_patch.json"
Invoke-WonderDemoStep -Title "Check patched Scene Graph" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $PatchedScene) -Artifact "26_check_patched_scene.json"
Invoke-WonderDemoStep -Title "Build patched proxy preview Scene Package" -Arguments @("-m", "lathe.cli", "scene", "build", $PatchedScene, "--out", $PatchedBuildRoot, "--mode", "preview") -Artifact "27_patched_build.txt"
Invoke-WonderDemoStep -Title "Validate patched proxy Scene Package" -Arguments @("-m", "lathe.cli", "scene", "package", "validate", "$PatchedBuildRoot/alchemist_observatory") -Artifact "28_validate_patched_package.json"
Invoke-WonderDemoStep -Title "Render before/after proxy comparison" -Arguments @("-m", "lathe.cli", "wonder", "demo-before-after", $ExampleDir, "--out", $BeforeAfterDir, "--patch", $Patch, "--camera-id", "camera_reveal") -Artifact "28b_before_after_demo.json"
Invoke-WonderDemoStep -Title "Validate before/after render comparison" -Arguments @("-m", "lathe.cli", "wonder", "validate-render-comparison", "$BeforeAfterDir/comparisons/render_comparison.json") -Artifact "28c_validate_before_after_comparison.json"
Invoke-WonderDemoStep -Title "Summarize curiosity anchors" -Arguments @("-m", "lathe.cli", "scene", "curiosity", $Scene) -Artifact "29_curiosity_cards.json"
Invoke-WonderDemoStep -Title "Expand opened_archive curiosity anchor" -Arguments @("-m", "lathe.cli", "scene", "expand-anchor", $Scene, "curiosity_warm_lens", "--option", "opened_archive", "--out", $ExpandedScene) -Artifact "30_expand_opened_archive.txt"
Invoke-WonderDemoStep -Title "Check expanded Scene Graph" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $ExpandedScene) -Artifact "31_check_expanded_scene.json"
Invoke-WonderDemoStep -Title "Build expanded proxy preview Scene Package" -Arguments @("-m", "lathe.cli", "scene", "build", $ExpandedScene, "--out", $ExpandedBuildRoot, "--mode", "preview") -Artifact "32_expanded_build.txt"
Invoke-WonderDemoStep -Title "Validate expanded proxy Scene Package" -Arguments @("-m", "lathe.cli", "scene", "package", "validate", "$ExpandedBuildRoot/alchemist_observatory") -Artifact "33_validate_expanded_package.json"

function Assert-ArtifactMagic {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [byte[]]$Magic
    )

    if (-not (Test-Path $Path)) {
        throw "Expected artifact not found: $Path"
    }
    $Bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $Path).Path)
    if ($Bytes.Length -lt $Magic.Length) {
        throw "Artifact is too small to validate: $Path"
    }
    for ($Index = 0; $Index -lt $Magic.Length; $Index++) {
        if ($Bytes[$Index] -ne $Magic[$Index]) {
            throw "Artifact magic bytes did not match for: $Path"
        }
    }
}

$ArtifactEvidencePath = Join-Path $EvidenceDir "34_proxy_artifact_evidence.json"
$PreviewPackageDir = Join-Path $PreviewBuildRoot "alchemist_observatory"
$PreviewManifestPath = Join-Path $PreviewPackageDir "scene_package_manifest.json"

if (-not $DryRun) {
    $PreviewManifest = Get-Content -Path $PreviewManifestPath -Raw | ConvertFrom-Json
    $ScenePlanPath = Join-Path $PreviewPackageDir "reports/scene_plan.json"
    $ExportReportPath = Join-Path $PreviewPackageDir "reports/scene_export_artifacts.json"
    $ScenePlan = Get-Content -Path $ScenePlanPath -Raw | ConvertFrom-Json
    $ExportReport = Get-Content -Path $ExportReportPath -Raw | ConvertFrom-Json
    $RenderEntries = @($PreviewManifest.renders)
    $GlbEntries = @($PreviewManifest.exports | Where-Object { $_.target -eq "glb" })
    $PlannedRenderTasks = @($ScenePlan.render_tasks)
    $PlannedGlbTasks = @($ScenePlan.export_tasks | Where-Object { $_.target -eq "glb" -or $_.format -eq "glb" })
    $GlbArtifacts = @($ExportReport.artifacts | Where-Object { $_.target -eq "glb" })
    if ($RenderEntries.Count -eq 0) {
        throw "Preview package manifest has no render artifacts: $PreviewManifestPath"
    }
    if ($GlbEntries.Count -eq 0) {
        throw "Preview package manifest has no GLB export artifact: $PreviewManifestPath"
    }
    $ActualRenderPairs = @{}
    foreach ($Entry in $RenderEntries) {
        foreach ($Pass in @($Entry.passes)) {
            $ActualRenderPairs["$($Entry.camera_id)|$Pass"] = $true
        }
    }
    foreach ($Task in $PlannedRenderTasks) {
        foreach ($Pass in @($Task.passes)) {
            $Key = "$($Task.camera_id)|$Pass"
            if (-not $ActualRenderPairs.ContainsKey($Key)) {
                throw "Preview package is missing planned render artifact: $Key"
            }
        }
    }
    if ($GlbArtifacts.Count -ne $PlannedGlbTasks.Count) {
        throw "Built GLB artifact count $($GlbArtifacts.Count) does not match planned GLB export task count $($PlannedGlbTasks.Count)"
    }
    foreach ($Entry in $RenderEntries) {
        Assert-ArtifactMagic -Path (Join-Path $PreviewPackageDir $Entry.path) -Magic ([byte[]](0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A))
    }
    foreach ($Entry in $GlbEntries) {
        Assert-ArtifactMagic -Path (Join-Path $PreviewPackageDir $Entry.path) -Magic ([byte[]](0x67, 0x6C, 0x54, 0x46))
    }
    foreach ($Artifact in $GlbArtifacts) {
        if ($Artifact.status -ne "built") {
            throw "GLB artifact is not built: $($Artifact.path)"
        }
        if ($Artifact.identity.status -ne "passed") {
            throw "GLB identity validation failed for: $($Artifact.path)"
        }
        if (@($GlbEntries | Where-Object { $_.path -eq $Artifact.path }).Count -eq 0) {
            throw "GLB artifact is missing from package manifest exports: $($Artifact.path)"
        }
        if (@($PlannedGlbTasks | Where-Object { $_.task_id -eq $Artifact.task_id }).Count -eq 0) {
            throw "GLB artifact does not match a planned export task: $($Artifact.task_id)"
        }
    }
    $Evidence = [ordered]@{
        schema_version = "lathe.wonder_proxy_artifact_evidence.v1"
        package = "$PreviewBuildRoot/alchemist_observatory"
        planned_render_task_count = $PlannedRenderTasks.Count
        planned_glb_export_task_count = $PlannedGlbTasks.Count
        render_count = $RenderEntries.Count
        glb_export_count = $GlbEntries.Count
        render_paths = @($RenderEntries | ForEach-Object { $_.path })
        glb_export_paths = @($GlbEntries | ForEach-Object { $_.path })
        glb_identity_statuses = @($GlbArtifacts | ForEach-Object { $_.identity.status })
        glb_task_ids = @($GlbArtifacts | ForEach-Object { $_.task_id })
        status = "passed"
    }
    $Utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
    [System.IO.File]::WriteAllText($ArtifactEvidencePath, ($Evidence | ConvertTo-Json -Depth 8) + [Environment]::NewLine, $Utf8NoBom)
    Write-Host ""
    Write-Host "Saved output: $ArtifactEvidencePath"
}

Write-Host ""
if ($DryRun) {
    Write-Host "Dry run complete. Re-run without -DryRun to execute the Wonder seed scene demo."
} else {
    Write-Host "Wonder seed scene demo complete."
    Write-Host "Evidence:         $EvidenceDir"
    Write-Host "Preview package:  $PreviewBuildRoot\alchemist_observatory"
    Write-Host "Patched package:  $PatchedBuildRoot\alchemist_observatory"
    Write-Host "Expanded package: $ExpandedBuildRoot\alchemist_observatory"
    Write-Host "Before/after:     $BeforeAfterDir"
    Write-Host "Proxy artifacts:  $ArtifactEvidencePath"
}
