#!/usr/bin/env bash
# Installs the scanner's dependencies into a cache dir — never into the project under test.
set -euo pipefail
CACHE="${ACCESS_ATLAS_CACHE:-$HOME/.cache/access-atlas}"
mkdir -p "$CACHE"
cd "$CACHE"
[ -f package.json ] || npm init -y >/dev/null
if ! node -e "require('playwright'); require('axe-core')" 2>/dev/null; then
  npm i playwright axe-core --silent
fi
npx --yes playwright install chromium >/dev/null
node -e "console.log('access-atlas deps ready: axe-core ' + require('axe-core/package.json').version + ', playwright ' + require('playwright/package.json').version)"
