#!/usr/bin/env sh
# Bump the Lathe project version in pyproject.toml and CITATION.cff in lockstep.
#
# Usage:
#   scripts/bump_version.sh patch
#   scripts/bump_version.sh minor
#   scripts/bump_version.sh major
#
# Prefers `uv tool run bump-my-version`; falls back to `hatch version` if uv is
# unavailable. CITATION.cff is updated via sed to match the new pyproject version.
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <major|minor|patch>" >&2
  exit 2
fi

part="$1"
case "$part" in
  major|minor|patch) ;;
  *)
    echo "error: first arg must be one of major|minor|patch (got '$part')" >&2
    exit 2
    ;;
esac

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

if command -v uv >/dev/null 2>&1; then
  uv tool run bump-my-version bump "$part"
elif command -v hatch >/dev/null 2>&1; then
  case "$part" in
    patch) hatch version patch ;;
    minor) hatch version minor ;;
    major) hatch version major ;;
  esac
else
  echo "error: neither 'uv' nor 'hatch' found on PATH; install one of them" >&2
  exit 1
fi

new_version="$(python - <<'PY'
import tomllib, pathlib
print(tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"])
PY
)"

today="$(date -u +%Y-%m-%d)"

if [ -f CITATION.cff ]; then
  # Update `version:` and `date-released:` lines in CITATION.cff.
  python - "$new_version" "$today" <<'PY'
import pathlib, re, sys
version, today = sys.argv[1], sys.argv[2]
p = pathlib.Path("CITATION.cff")
text = p.read_text()
text = re.sub(r"^version:.*$", f"version: {version}", text, flags=re.M)
text = re.sub(r"^date-released:.*$", f"date-released: {today}", text, flags=re.M)
p.write_text(text)
PY
fi

echo "bumped to v${new_version} (CITATION.cff updated to ${today})"
