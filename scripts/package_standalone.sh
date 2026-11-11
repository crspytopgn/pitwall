#!/usr/bin/env bash
# Produce the standalone (no Decky) package in out/: a tarball with install.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(python3 -c "import json;print(json.load(open('package.json'))['version'])")
STAGE=$(mktemp -d)
D="$STAGE/pitwall-$VERSION"
mkdir -p "$D/assets"
cp main.py LICENSE CREDITS.md README.md "$D/"
cp -r py_modules standalone "$D/"
cp assets/logo.png assets/mark.svg "$D/assets/"
cp standalone/install.sh "$D/install.sh"
cp docs/standalone.md "$D/STANDALONE.md"
find "$D" -name __pycache__ -prune -exec rm -rf {} +
chmod +x "$D/install.sh" "$D/standalone/install.sh" "$D/standalone/uninstall.sh" "$D/standalone/pitwall_app.py"
mkdir -p out
tar -C "$STAGE" -czf "out/Pitwall-standalone-$VERSION.tar.gz" "pitwall-$VERSION"
rm -rf "$STAGE"
echo "out/Pitwall-standalone-$VERSION.tar.gz"
