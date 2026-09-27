#!/usr/bin/env bash
# Symlink the skill into your agent's skills directory. Re-run safely; pass a directory to override.
set -euo pipefail
src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills/access-atlas"
dest="${1:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills}"
mkdir -p "$dest"
if [ -e "$dest/access-atlas" ] && [ ! -L "$dest/access-atlas" ]; then
  echo "$dest/access-atlas exists and is not a symlink; move it aside first." >&2
  exit 1
fi
ln -sfn "$src" "$dest/access-atlas"
echo "installed: $dest/access-atlas -> $src"
echo "next: $src/scripts/ensure-deps.sh"
