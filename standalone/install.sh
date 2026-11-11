#!/usr/bin/env bash
# Install standalone Pitwall (no Decky needed).
#
#   ./install.sh            install or update for the current user
#   ./install.sh --force    install even if the Pitwall Decky plugin is present
#
# What it does:
#   - copies Pitwall to /var/lib/pitwall/app (owned by root: the service runs
#     as root, so its code must not be writable by your user)
#   - installs and starts the pitwall.service system service
#   - adds "Pitwall" to your desktop's app menu (opens http://127.0.0.1:8091)
#
# On SteamOS /var and /etc survive system updates, so this does too.
# Your settings and laps live in ~/.config/pitwall and ~/.local/share/pitwall.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR=/var/lib/pitwall/app
UNIT=/etc/systemd/system/pitwall.service
FORCE=0
for a in "$@"; do
  case "$a" in
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a" >&2; exit 1 ;;
  esac
done

USER_NAME="${SUDO_USER:-$(id -un)}"
if [ "$USER_NAME" = "root" ]; then
  echo "Run this as your normal user (it asks for your password when it needs it), not as root." >&2
  exit 1
fi
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"

say() { printf '\033[1m%s\033[0m\n' "$*"; }

# ---- checks
command -v python3 >/dev/null || { echo "Python 3 is required." >&2; exit 1; }
python3 - <<'PY' || { echo "Python 3.10 or newer is required." >&2; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY
command -v systemctl >/dev/null || { echo "This installer needs systemd." >&2; exit 1; }
if [ -d "$USER_HOME/homebrew/plugins/Pitwall" ] && [ "$FORCE" = 0 ]; then
  echo "The Pitwall Decky plugin is installed. Use one or the other, as both would control the same wheel."
  echo "Remove it in Decky first, or run ./install.sh --force to install anyway (the service then won't start while Decky runs it)."
  exit 1
fi
[ -f "$HERE/standalone/pitwall_app.py" ] && [ -f "$HERE/main.py" ] || { echo "Run this from the extracted Pitwall folder." >&2; exit 1; }

SUDO=""
if [ "$(id -u)" != 0 ]; then
  SUDO=sudo
  if ! sudo -n true 2>/dev/null; then
    say "Pitwall needs administrator rights to install its service."
    if [ -f /etc/os-release ] && grep -q '^ID=steamos' /etc/os-release && passwd -S "$USER_NAME" 2>/dev/null | grep -q ' NP '; then
      echo "SteamOS: your user has no password yet. Set one first with:  passwd"
      exit 1
    fi
  fi
fi

# ---- copy files
say "Installing Pitwall to $APP_DIR"
$SUDO mkdir -p /var/lib/pitwall
$SUDO rm -rf "$APP_DIR.new"
$SUDO mkdir -p "$APP_DIR.new"
for item in main.py py_modules standalone assets LICENSE CREDITS.md README.md; do
  [ -e "$HERE/$item" ] && $SUDO cp -r "$HERE/$item" "$APP_DIR.new/"
done
$SUDO find "$APP_DIR.new" -name '__pycache__' -prune -exec rm -rf {} +
$SUDO chown -R root:root "$APP_DIR.new"
$SUDO chmod -R u=rwX,go=rX "$APP_DIR.new"
$SUDO rm -rf "$APP_DIR"
$SUDO mv "$APP_DIR.new" "$APP_DIR"

# ---- service
say "Setting up the Pitwall service"
$SUDO tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=Pitwall sim racing companion (standalone)
Documentation=https://github.com/crspytopgn/pitwall
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$(command -v python3) $APP_DIR/standalone/pitwall_app.py --user $USER_NAME
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1

[Install]
WantedBy=multi-user.target
EOF
$SUDO systemctl daemon-reload
$SUDO systemctl enable pitwall.service >/dev/null
$SUDO systemctl restart pitwall.service

# ---- app menu entry (as the user)
ICON_DIR="$USER_HOME/.local/share/icons/hicolor/256x256/apps"
APPS_DIR="$USER_HOME/.local/share/applications"
run_as_user() { if [ "$(id -u)" = 0 ]; then sudo -u "$USER_NAME" "$@"; else "$@"; fi; }
run_as_user mkdir -p "$ICON_DIR" "$APPS_DIR"
run_as_user cp "$HERE/assets/logo.png" "$ICON_DIR/pitwall.png" 2>/dev/null || true
run_as_user tee "$APPS_DIR/pitwall.desktop" >/dev/null <<EOF
[Desktop Entry]
Type=Application
Name=Pitwall
Comment=Sim racing companion: wheel, force feedback, game setup, telemetry
Exec=xdg-open http://127.0.0.1:8091
Icon=pitwall
Terminal=false
Categories=Game;Utility;
EOF
command -v update-desktop-database >/dev/null && run_as_user update-desktop-database "$APPS_DIR" 2>/dev/null || true

# ---- done
for _ in $(seq 1 20); do
  if command -v curl >/dev/null && curl -fs -o /dev/null http://127.0.0.1:8091/; then break; fi
  sleep 0.5
done
if $SUDO systemctl is-active --quiet pitwall.service; then
  say "Pitwall is running."
  echo "  Open it:          Pitwall in your app menu, or http://127.0.0.1:8091"
  echo "  Phone dashboard:  shown on Pitwall's Session page"
  echo "  Logs:             journalctl -u pitwall -f"
  echo "  Uninstall:        $APP_DIR/standalone/uninstall.sh"
else
  echo "The service didn't start. See: journalctl -u pitwall -n 50" >&2
  exit 1
fi
