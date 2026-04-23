# Bump the Lathe project version in pyproject.toml and CITATION.cff in lockstep.
#
# Usage:
#   scripts\bump_version.ps1 patch
#   scripts\bump_version.ps1 minor
#   scripts\bump_version.ps1 major
#
# Prefers `uv tool run bump-my-version`; falls back to `hatch version`.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("major", "minor", "patch")]
    [string]$Part
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$uv = Get-Command uv -ErrorAction SilentlyContinue
$hatch = Get-Command hatch -ErrorAction SilentlyContinue

if ($uv) {
    & uv tool run bump-my-version bump $Part
    if ($LASTEXITCODE -ne 0) { throw "uv bump-my-version failed ($LASTEXITCODE)" }
} elseif ($hatch) {
    & hatch version $Part
    if ($LASTEXITCODE -ne 0) { throw "hatch version failed ($LASTEXITCODE)" }
} else {
    throw "Neither 'uv' nor 'hatch' found on PATH; install one of them."
}

$newVersion = & python -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version'])"
if ($LASTEXITCODE -ne 0) { throw "failed to read new version from pyproject.toml" }
$newVersion = $newVersion.Trim()

$today = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd")

$citation = Join-Path $repoRoot "CITATION.cff"
if (Test-Path $citation) {
    & python - $newVersion $today @"
import pathlib, re, sys
version, today = sys.argv[1], sys.argv[2]
p = pathlib.Path("CITATION.cff")
text = p.read_text()
text = re.sub(r"^version:.*$", f"version: {version}", text, flags=re.M)
text = re.sub(r"^date-released:.*$", f"date-released: {today}", text, flags=re.M)
p.write_text(text)
"@
    if ($LASTEXITCODE -ne 0) { throw "failed to update CITATION.cff" }
}

Write-Output "bumped to v$newVersion (CITATION.cff updated to $today)"
