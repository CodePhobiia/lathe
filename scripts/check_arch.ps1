# Plan 03 Phase 3: run the import-linter layering contracts defined in
# .importlinter.  Exit non-zero if any contract is broken.
#
# Usage:
#   scripts\check_arch.ps1
#
# Requires ``import-linter`` from the [dev] extra:
#   pip install -e ".[dev]"

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$tool = Get-Command lint-imports -ErrorAction SilentlyContinue
if (-not $tool) {
    Write-Error "'lint-imports' not on PATH. Install it with: pip install -e `".[dev]`""
    exit 2
}

& lint-imports --config .importlinter @Args
exit $LASTEXITCODE
