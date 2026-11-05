#!/usr/bin/env bash
# Build the frontend and produce an installable Decky zip in out/.
set -euo pipefail
cd "$(dirname "$0")/.."
pnpm install --frozen-lockfile
pnpm run build
VERSION=$(python3 -c "import json;print(json.load(open('package.json'))['version'])")
STAGE=$(mktemp -d)
mkdir -p "$STAGE/Pitwall"
mkdir -p "$STAGE/Pitwall/dist" && cp dist/index.js "$STAGE/Pitwall/dist/" && cp main.py plugin.json package.json LICENSE CREDITS.md README.md "$STAGE/Pitwall/"
cp -r py_modules "$STAGE/Pitwall/" && find "$STAGE" -name __pycache__ -prune -exec rm -rf {} +
mkdir -p out
(cd "$STAGE" && zip -qr "$OLDPWD/out/Pitwall-$VERSION.zip" Pitwall)
echo "out/Pitwall-$VERSION.zip"
