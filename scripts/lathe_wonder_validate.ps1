param(
    [string]$Python = "",
    [string]$ExampleDir = "examples/wonder/alchemist_observatory",
    [string]$WorkDir = "",
    [string[]]$PytestArgs = @(
        "-q",
        "tests/unit/test_wonder_brief_lowering.py",
        "tests/unit/test_wonder_contracts.py",
        "tests/unit/test_wonder_memory.py",
        "tests/unit/test_wonder_scene_validation.py",
        "tests/unit/test_wonder_schema_reference_docs.py",
        "tests/unit/test_scene_cli.py",
        "tests/unit/test_scene_ids.py",
        "tests/unit/test_scene_package_manifest.py",
        "tests/unit/test_scene_patch.py",
        "tests/unit/test_scene_planner.py",
        "tests/unit/test_scene_source_roundtrip.py",
        "tests/unit/test_scene_executor.py",
        "tests/unit/test_scene_io.py",
        "tests/unit/test_scene_assembly.py",
        "tests/unit/test_scene_versioning.py",
        "tests/unit/test_scene_repair.py",
        "tests/unit/test_scene_curiosity.py",
        "tests/unit/test_scene_validators.py",
        "tests/unit/test_scene_bench.py",
        "tests/unit/test_scene_roblox.py",
        "tests/unit/test_scene_style_layout.py",
        "tests/unit/test_scene_game_readiness_provenance.py",
        "tests/unit/test_wonder_llm.py"
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

if (-not $WorkDir) {
    if ($env:WONDER_WORK_DIR) {
        $WorkDir = $env:WONDER_WORK_DIR
    } else {
        $RunId = "{0}_{1}" -f (Get-Date -Format "yyyyMMddHHmmssfff"), $PID
        $WorkDir = ".tmp_tests/wonder_validate_$RunId"
    }
}

function Join-WonderWorkPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Child
    )

    return Join-Path $WorkDir $Child
}

function Invoke-WonderValidationStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "== $Title =="
    Write-Host "$Python $($Arguments -join ' ')"
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Assert-ProxyPackageArtifactContract {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PackageDir
    )

    Write-Host ""
    Write-Host "== Validate proxy Scene Package artifact contract =="
    $Manifest = Get-Content -Path (Join-Path $PackageDir "scene_package_manifest.json") -Raw | ConvertFrom-Json
    $ScenePlan = Get-Content -Path (Join-Path $PackageDir "reports/scene_plan.json") -Raw | ConvertFrom-Json
    $ExportReport = Get-Content -Path (Join-Path $PackageDir "reports/scene_export_artifacts.json") -Raw | ConvertFrom-Json
    $RenderEntries = @($Manifest.renders)
    $GlbEntries = @($Manifest.exports | Where-Object { $_.target -eq "glb" })
    $PlannedRenderTasks = @($ScenePlan.render_tasks)
    $PlannedGlbTasks = @($ScenePlan.export_tasks | Where-Object { $_.target -eq "glb" -or $_.format -eq "glb" })
    $GlbArtifacts = @($ExportReport.artifacts | Where-Object { $_.target -eq "glb" })
    if ($RenderEntries.Count -eq 0) {
        throw "Built scene package has no render entries."
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
                throw "Missing planned render artifact: $Key"
            }
        }
    }
    if ($GlbEntries.Count -ne $PlannedGlbTasks.Count -or $GlbArtifacts.Count -ne $PlannedGlbTasks.Count) {
        throw "Built GLB exports do not match planned GLB export tasks."
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
    Write-Host "Proxy artifact contract passed."
}

$Brief = "$ExampleDir/dream_brief.json"
$Scene = "$ExampleDir/scene_graph.json"
$Patch = "$ExampleDir/scene_patch_more_sacred.json"
$RenderInspection = "$ExampleDir/render_inspection.example.json"
$WorldMemory = "$ExampleDir/world_memory.json"
$ExpectedSceneManifest = "$ExampleDir/expected/scene_manifest.example.json"
$ExpectedWonderReport = "$ExampleDir/expected/wonder_report.example.json"
$RobloxExampleDir = "examples/wonder/abandoned_roblox_mall"
$RobloxScene = "$RobloxExampleDir/scene_graph.json"
$RobloxProfile = "$RobloxExampleDir/roblox_profile.json"
$RobloxManifest = Join-WonderWorkPath "wonder_roblox_manifest.json"
$RobloxAssetKit = Join-WonderWorkPath "roblox_asset_kit/abandoned_roblox_mall"
$LoweredScene = Join-WonderWorkPath "wonder_lower/alchemist_observatory.scene_graph.json"
$ScenePlan = Join-WonderWorkPath "wonder_scene_plan.json"
$SceneAssembly = Join-WonderWorkPath "wonder_scene_assembly.json"
$SceneBranch = Join-WonderWorkPath "wonder_scene_branch.json"
$SceneDiff = Join-WonderWorkPath "wonder_scene_diff.json"
$RepairReport = Join-WonderWorkPath "wonder_repair_report.json"
$RepairedScene = Join-WonderWorkPath "wonder_repaired_scene.json"
$ExpandedScene = Join-WonderWorkPath "wonder_expanded_scene.json"
$BenchmarkTimings = Join-WonderWorkPath "wonder_benchmark_timings.json"
$BenchmarkScores = Join-WonderWorkPath "wonder_benchmark_scores.json"
$BenchmarkReport = Join-WonderWorkPath "wonder_benchmark_report.json"
$SemanticPatchRequest = Join-WonderWorkPath "wonder_semantic_patch_request.json"
$SemanticPatch = Join-WonderWorkPath "wonder_semantic_patch.json"
$LlmSummary = Join-WonderWorkPath "wonder_llm_diagnostics.json"
$StylePack = Join-WonderWorkPath "wonder_style_pack.json"
$LayoutPlan = Join-WonderWorkPath "wonder_layout_plan.json"
$CameraLightingPlan = Join-WonderWorkPath "wonder_camera_lighting_plan.json"
$GameReadiness = Join-WonderWorkPath "wonder_game_readiness.json"
$AssetProvenance = Join-WonderWorkPath "wonder_asset_provenance.json"
$SceneSource = Join-WonderWorkPath "wonder_source/alchemist_observatory.scene.lth"
$RoundtripScene = Join-WonderWorkPath "wonder_source/alchemist_observatory.roundtrip.scene_graph.json"
$PatchedScene = Join-WonderWorkPath "wonder_patch/alchemist_observatory.patched.scene_graph.json"
$PackageDir = Join-WonderWorkPath "wonder_package"
$BuildDir = Join-WonderWorkPath "wonder_scene_build"
$RenderDir = Join-WonderWorkPath "wonder_scene_render"
$ExportDir = Join-WonderWorkPath "wonder_scene_export"

Write-Host "Lathe Wonder schema and package validation"
Write-Host "Example: $ExampleDir"
Write-Host "Work dir: $WorkDir"

New-Item -ItemType Directory -Force $WorkDir | Out-Null
@'
{
  "stages": {
    "brief": {"duration_ms": 1000},
    "scene_graph": {"duration_ms": 2000},
    "source_generation": {"duration_ms": 1000},
    "check_plan": {"duration_ms": 500},
    "preview_build": {"duration_ms": 5000},
    "preview_render": {"duration_ms": 1000},
    "patch_preview": {"duration_ms": 1000},
    "final_export": {"duration_ms": 1000}
  },
  "cache": {"hits": 1, "misses": 1, "writes": 1}
}
'@ | Set-Content -Path $BenchmarkTimings -Encoding utf8
@'
{
  "metrics": {
    "prompt_to_brief": 0.9,
    "brief_to_scene": 0.9,
    "parse_check": 1.0,
    "build_success": 1.0,
    "scene_validation": 0.9,
    "style_consistency": 0.9,
    "object_count_accuracy": 0.9,
    "render_quality": 0.9,
    "patch_success": 1.0,
    "continuity_preservation": 0.9,
    "export_validity": 1.0
  }
}
'@ | Set-Content -Path $BenchmarkScores -Encoding utf8
@'
{
  "scope": "object",
  "target_id": "obj_astrolabe_table_001",
  "instruction": "Make the table more sacred and less industrial."
}
'@ | Set-Content -Path $SemanticPatchRequest -Encoding utf8
@'
{
  "schema_version": "lathe.game_readiness.v1",
  "scene_id": "alchemist_observatory",
  "target": "generic_game",
  "objects": [
    {
      "object_id": "obj_astrolabe_table_001",
      "mobility": "static",
      "interactable": true,
      "collision": {"type": "box", "required": true},
      "pivot": {"mode": "base_center"}
    }
  ]
}
'@ | Set-Content -Path $GameReadiness -Encoding utf8
@'
{
  "schema_version": "lathe.asset_provenance_scene.v1",
  "scene_id": "alchemist_observatory",
  "objects": [
    {
      "object_id": "obj_astrolabe_table_001",
      "provenance": {
        "source": "deterministic_lathe",
        "commercial_use": true,
        "export_permission": "allowed"
      },
      "content_safety": {"status": "passed", "categories": ["environment_prop"]},
      "brand_ip": {"status": "cleared"},
      "user_upload": {"present": false, "safety_status": "passed"}
    }
  ],
  "exports": [
    {
      "target": "scene_package",
      "path": "exports/alchemist_observatory.lathepkg",
      "permission": "allowed",
      "source_object_ids": ["obj_astrolabe_table_001"]
    }
  ]
}
'@ | Set-Content -Path $AssetProvenance -Encoding utf8

Invoke-WonderValidationStep -Title "Run Wonder contract and scene validation tests" -Arguments (@("-m", "pytest") + $PytestArgs)
Invoke-WonderValidationStep -Title "Regenerate Wonder schema reference" -Arguments @("scripts/generate_wonder_schema_reference.py")
Invoke-WonderValidationStep -Title "Emit Wonder capabilities" -Arguments @("-m", "lathe.cli", "wonder", "capabilities")
Invoke-WonderValidationStep -Title "Emit Wonder readiness status" -Arguments @("-m", "lathe.cli", "wonder", "status")
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Dream Brief" -Arguments @("-m", "lathe.cli", "wonder", "validate-brief", $Brief)
Invoke-WonderValidationStep -Title "Decompose Alchemist Observatory Dream Brief" -Arguments @("-m", "lathe.cli", "wonder", "decompose-brief", $Brief)
Invoke-WonderValidationStep -Title "Lower Alchemist Observatory Dream Brief" -Arguments @("-m", "lathe.cli", "wonder", "lower-brief", $Brief, "--out", $LoweredScene)
Invoke-WonderValidationStep -Title "Check Lowered Alchemist Observatory Scene Graph semantics" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $LoweredScene)
Invoke-WonderValidationStep -Title "Check Brief and Scene consistency" -Arguments @("-m", "lathe.cli", "wonder", "check-brief-scene", $Brief, $Scene)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Scene Graph schema" -Arguments @("-m", "lathe.cli", "wonder", "validate-scene", $Scene)
Invoke-WonderValidationStep -Title "Check Alchemist Observatory Scene Graph semantics" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $Scene)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory expected Scene Manifest" -Arguments @("-m", "lathe.cli", "wonder", "validate-scene-manifest", $ExpectedSceneManifest)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory expected Wonder Report" -Arguments @("-m", "lathe.cli", "wonder", "validate-wonder-report", $ExpectedWonderReport)
Invoke-WonderValidationStep -Title "Check Alchemist Observatory scene through scene CLI" -Arguments @("-m", "lathe.cli", "scene", "check", $Scene)
Invoke-WonderValidationStep -Title "Plan Alchemist Observatory scene" -Arguments @("-m", "lathe.cli", "scene", "plan", $Scene, "--mode", "preview", "--out", $ScenePlan)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Scene Plan" -Arguments @("-m", "lathe.cli", "wonder", "validate-plan", $ScenePlan)
Invoke-WonderValidationStep -Title "Benchmark Alchemist Observatory Wonder path" -Arguments @("-m", "lathe.cli", "scene", "bench", $Scene, "--timings", $BenchmarkTimings, "--scores", $BenchmarkScores, "--out", $BenchmarkReport)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Benchmark Report" -Arguments @("-m", "lathe.cli", "wonder", "validate-scene-benchmark-report", $BenchmarkReport)
Invoke-WonderValidationStep -Title "Extract Alchemist Observatory Style Pack" -Arguments @("-m", "lathe.cli", "scene", "style-pack", $Scene, "--out", $StylePack)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Style Pack" -Arguments @("-m", "lathe.cli", "wonder", "validate-style-pack", $StylePack)
Invoke-WonderValidationStep -Title "Plan Alchemist Observatory Layout" -Arguments @("-m", "lathe.cli", "scene", "layout", $Scene, "--style-pack", $StylePack, "--out", $LayoutPlan)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Layout Plan" -Arguments @("-m", "lathe.cli", "wonder", "validate-layout-plan", $LayoutPlan)
Invoke-WonderValidationStep -Title "Plan Alchemist Observatory Camera and Lighting" -Arguments @("-m", "lathe.cli", "scene", "camera-lighting", $Scene, "--layout-plan", $LayoutPlan, "--out", $CameraLightingPlan)
Invoke-WonderValidationStep -Title "Validate Game Readiness metadata" -Arguments @("-m", "lathe.cli", "wonder", "validate-game-readiness", $GameReadiness)
Invoke-WonderValidationStep -Title "Validate Asset Provenance metadata" -Arguments @("-m", "lathe.cli", "wonder", "validate-asset-provenance-scene", $AssetProvenance)
Invoke-WonderValidationStep -Title "Assemble Alchemist Observatory scene IR" -Arguments @("-m", "lathe.cli", "scene", "assemble", $Scene, "--out", $SceneAssembly)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Scene Assembly IR" -Arguments @("-m", "lathe.cli", "wonder", "validate-scene-assembly", $SceneAssembly)
Invoke-WonderValidationStep -Title "Branch Alchemist Observatory scene" -Arguments @("-m", "lathe.cli", "scene", "branch", $Scene, "--name", "archive_expansion", "--out", $SceneBranch)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Scene Branch" -Arguments @("-m", "lathe.cli", "wonder", "validate-scene-branch", $SceneBranch)
Invoke-WonderValidationStep -Title "Diff Alchemist Observatory scene against itself" -Arguments @("-m", "lathe.cli", "scene", "diff", $Scene, $Scene, "--out", $SceneDiff)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Scene Diff" -Arguments @("-m", "lathe.cli", "wonder", "validate-scene-diff", $SceneDiff)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory scene quality" -Arguments @("-m", "lathe.cli", "scene", "validate", $Scene)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Scene Patch" -Arguments @("-m", "lathe.cli", "wonder", "validate-patch", $Patch)
Invoke-WonderValidationStep -Title "Diagnose Alchemist Observatory Scene Patch for LLM" -Arguments @("-m", "lathe.cli", "wonder", "diagnose-for-llm", $Patch, "--contract", "scene_patch", "--out", $LlmSummary)
Invoke-WonderValidationStep -Title "Apply Semantic Patch Request for LLM" -Arguments @("-m", "lathe.cli", "wonder", "apply-semantic-patch", $SemanticPatchRequest, "--scene-graph", $Scene, "--out", $SemanticPatch)
Invoke-WonderValidationStep -Title "Validate LLM-authored Semantic Scene Patch" -Arguments @("-m", "lathe.cli", "wonder", "validate-patch", $SemanticPatch)
Invoke-WonderValidationStep -Title "Preview Alchemist Observatory Scene Patch" -Arguments @("-m", "lathe.cli", "scene", "patch", $Scene, $Patch, "--out", $PatchedScene, "--preview")
Invoke-WonderValidationStep -Title "Apply Alchemist Observatory Scene Patch" -Arguments @("-m", "lathe.cli", "scene", "patch", $Scene, $Patch, "--out", $PatchedScene)
Invoke-WonderValidationStep -Title "Validate Patched Alchemist Observatory Scene Graph" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $PatchedScene)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Render Inspection" -Arguments @("-m", "lathe.cli", "wonder", "validate-render-inspection", $RenderInspection)
Invoke-WonderValidationStep -Title "Inspect Alchemist Observatory Render Inspection semantically" -Arguments @("-m", "lathe.cli", "scene", "inspect-render", $Scene, $RenderInspection)
Invoke-WonderValidationStep -Title "Propose Alchemist Observatory repairs" -Arguments @("-m", "lathe.cli", "scene", "propose-repairs", $Scene, $RenderInspection, "--out", $RepairReport)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory Repair Report" -Arguments @("-m", "lathe.cli", "wonder", "validate-scene-repair-report", $RepairReport)
Invoke-WonderValidationStep -Title "Repair Alchemist Observatory offline" -Arguments @("-m", "lathe.cli", "scene", "repair", $Scene, $RenderInspection, "--out", $RepairedScene, "--report-out", $RepairReport)
Invoke-WonderValidationStep -Title "Validate Repaired Alchemist Observatory Scene Graph" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $RepairedScene)
Invoke-WonderValidationStep -Title "Validate Alchemist Observatory World Memory" -Arguments @("-m", "lathe.cli", "wonder", "validate-world-memory", $WorldMemory, "--scene-graph", $Scene)
Invoke-WonderValidationStep -Title "Summarize Alchemist Observatory curiosity anchors" -Arguments @("-m", "lathe.cli", "scene", "curiosity", $Scene)
Invoke-WonderValidationStep -Title "Expand Alchemist Observatory curiosity anchor" -Arguments @("-m", "lathe.cli", "scene", "expand-anchor", $Scene, "curiosity_warm_lens", "--option", "opened_archive", "--out", $ExpandedScene)
Invoke-WonderValidationStep -Title "Validate Expanded Alchemist Observatory Scene Graph" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $ExpandedScene)
Invoke-WonderValidationStep -Title "Generate Alchemist Observatory scene source bridge" -Arguments @("-m", "lathe.cli", "scene", "scene-graph-to-source", $Scene, "--out", $SceneSource)
Invoke-WonderValidationStep -Title "Roundtrip Alchemist Observatory scene source bridge" -Arguments @("-m", "lathe.cli", "scene", "source-to-scene-graph", $SceneSource, "--out", $RoundtripScene)
Invoke-WonderValidationStep -Title "Validate Roundtripped Alchemist Observatory Scene Graph" -Arguments @("-m", "lathe.cli", "wonder", "check-scene-graph", $RoundtripScene)
Invoke-WonderValidationStep -Title "Initialize Scene Package skeleton" -Arguments @("-m", "lathe.cli", "scene", "package", "init", $PackageDir, "--scene-id", "alchemist_observatory", "--force")
Invoke-WonderValidationStep -Title "Inspect Scene Package skeleton" -Arguments @("-m", "lathe.cli", "scene", "package", "inspect", $PackageDir)
Invoke-WonderValidationStep -Title "Validate Scene Package Manifest" -Arguments @("-m", "lathe.cli", "scene", "package", "validate", $PackageDir)
Invoke-WonderValidationStep -Title "Render Alchemist Observatory proxy PNG passes" -Arguments @("-m", "lathe.cli", "scene", "render", $Scene, "--out", $RenderDir, "--camera", "camera_reveal", "--passes", "beauty,object_id", "--width", "640", "--height", "360")
Invoke-WonderValidationStep -Title "Export Alchemist Observatory proxy GLB" -Arguments @("-m", "lathe.cli", "scene", "export", $Scene, "--out", $ExportDir, "--target", "glb")
Invoke-WonderValidationStep -Title "Build Alchemist Observatory proxy Scene Package" -Arguments @("-m", "lathe.cli", "scene", "build", $Scene, "--out", $BuildDir, "--mode", "preview")
Invoke-WonderValidationStep -Title "Validate Built Alchemist Observatory Scene Package" -Arguments @("-m", "lathe.cli", "scene", "package", "validate", "$BuildDir/alchemist_observatory")
Assert-ProxyPackageArtifactContract -PackageDir "$BuildDir/alchemist_observatory"
Invoke-WonderValidationStep -Title "Validate Roblox low-poly profile" -Arguments @("-m", "lathe.cli", "wonder", "validate-roblox-profile", $RobloxProfile)
Invoke-WonderValidationStep -Title "Build Roblox manifest" -Arguments @("-m", "lathe.cli", "scene", "roblox-manifest", $RobloxScene, "--profile", $RobloxProfile, "--out", $RobloxManifest)
Invoke-WonderValidationStep -Title "Validate Roblox manifest" -Arguments @("-m", "lathe.cli", "wonder", "validate-roblox-manifest", $RobloxManifest)
Invoke-WonderValidationStep -Title "Export Roblox asset-kit bundle" -Arguments @("-m", "lathe.cli", "scene", "roblox-export", $RobloxScene, "--profile", $RobloxProfile, "--out", $RobloxAssetKit)

Write-Host ""
Write-Host "Lathe Wonder schema and package validation passed."
