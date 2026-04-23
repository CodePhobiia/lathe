#Requires -Version 5.1
<#
.SYNOPSIS
    Remove transient build roots + parser cache from the Lathe repo.

.DESCRIPTION
    Windows counterpart to scripts/clean_workspace.sh.

    Safety model:
      * Refuses to run outside the repo root (checks for pyproject.toml
        in the current working directory).
      * Requires -Confirm (alias -y) before deleting.
      * Always lists targets first.
      * Idempotent: missing directories are skipped silently.

.PARAMETER Confirm
    Actually delete targets. Without this switch the script prints the
    list and exits (dry run).

.EXAMPLE
    pwsh scripts/clean_workspace.ps1
    pwsh scripts/clean_workspace.ps1 -Confirm
#>

[CmdletBinding()]
param(
    [Alias('y')]
    [switch]$Confirm
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath 'pyproject.toml' -PathType Leaf)) {
    Write-Error "refusing to run: pyproject.toml not found in cwd ($PWD). Run from the repo root."
    exit 2
}

$patterns = @(
    'dist_*',
    'tmp_*',
    'warm_*',
    'v05_*',
    'cache_probe_*'
)

$fixedTargets = @(
    '.lathe_lark_cache',
    '.venv_old_broken'
)

$targets = New-Object System.Collections.Generic.List[string]

foreach ($pat in $patterns) {
    $matches = Get-ChildItem -Path . -Directory -Filter $pat -Force -ErrorAction SilentlyContinue
    foreach ($m in $matches) {
        $targets.Add($m.Name) | Out-Null
    }
}

foreach ($t in $fixedTargets) {
    if (Test-Path -LiteralPath $t) {
        $targets.Add($t) | Out-Null
    }
}

if ($targets.Count -eq 0) {
    Write-Host 'nothing to clean.'
    exit 0
}

Write-Host "targets ($($targets.Count)):"
foreach ($t in $targets) {
    Write-Host "  $t"
}

if (-not $Confirm) {
    Write-Host ''
    Write-Host 'dry run. pass -Confirm (or -y) to delete.'
    exit 0
}

foreach ($t in $targets) {
    Remove-Item -LiteralPath $t -Recurse -Force -Confirm:$false
    Write-Host "removed $t"
}

Write-Host 'done.'
