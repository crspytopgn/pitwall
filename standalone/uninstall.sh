#!/usr/bin/env bash
# Uninstall standalone Pitwall.
#
#   uninstall.sh           remove Pitwall, keep your settings and laps
#   uninstall.sh --purge   also delete settings and laps
#
# Like the Decky plugin, this undoes Pitwall's system changes (the wheel
# detection udev rule and any force feedback drivers it installed). The
# telemetry bridge in ~/.local/share/pitwall/bin stays, because games' launch
# options may still use it; remove the bridge from each game in Pitwall first
# if you want it gone.
set -euo pipefail

APP_DIR=/var/lib/pitwall/app
UNIT=/etc/systemd/system/pitwall.service
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

USER_NAME="${SUDO_USER:-$(id -un)}"
[ "$USER_NAME" = "root" ] && { echo "Run this as your normal user." >&2; exit 1; }
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
SUDO=""; [ "$(id -u)" != 0 ] && SUDO=sudo

if [ -f "$UNIT" ]; then
  $SUDO systemctl disable --now pitwall.service 2>/dev/null || true
fi
if [ -f "$APP_DIR/standalone/pitwall_app.py" ]; then
  $SUDO python3 "$APP_DIR/standalone/pitwall_app.py" --user "$USER_NAME" --cleanup || true
fi
$SUDO rm -f "$UNIT"
$SUDO systemctl daemon-reload 2>/dev/null || true
$SUDO rm -rf "$APP_DIR"
$SUDO rmdir /var/lib/pitwall 2>/dev/null || true
rm -f "$USER_HOME/.local/share/applications/pitwall.desktop" "$USER_HOME/.local/share/icons/hicolor/256x256/apps/pitwall.png"

if [ "$PURGE" = 1 ]; then
  rm -rf "$USER_HOME/.config/pitwall" "$USER_HOME/.local/share/pitwall/app" "$USER_HOME/.local/state/pitwall"
  echo "Pitwall removed, including settings and laps."
else
  echo "Pitwall removed. Settings and laps kept in ~/.config/pitwall and ~/.local/share/pitwall (use --purge to delete)."
fi
