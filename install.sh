#!/usr/bin/env bash
# Install the Access Atlas skills for an agent that reads a skills folder (not needed for the
# Claude Code plugin). Symlinks each skill as access-atlas-<name> and records the repo root.
# Re-run safely. Usage: ./install.sh [skills-dir]   (default: ~/.claude/skills)
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dest="${1:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills}"
mkdir -p "$dest"
for dir in "$root"/skills/*/; do
  name="access-atlas-$(basename "$dir")"
  if [ -e "$dest/$name" ] && [ ! -L "$dest/$name" ]; then
    echo "$dest/$name exists and is not a symlink; move it aside first." >&2
    exit 1
  fi
  ln -sfn "${dir%/}" "$dest/$name"
  echo "installed: $dest/$name"
done
echo
echo "Skills refer to \${CLAUDE_PLUGIN_ROOT}. Outside the Claude Code plugin, add this to your shell profile:"
echo "  export CLAUDE_PLUGIN_ROOT=\"$root\""
echo "Then, once: $root/engine/ensure-deps.sh"
