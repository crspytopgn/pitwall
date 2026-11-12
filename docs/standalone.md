# Standalone Pitwall (without Decky)

Pitwall also runs on its own, without Decky Loader. It's the same Pitwall: wheel settings and profiles, force feedback setup and tuning, the game guide, telemetry, coaching, fuel and tyre strategy, the phone dashboard and the update checks. Only the interface is different: instead of the Quick Access menu, you use a web app on the same machine.

This version targets **SteamOS in Desktop Mode** first. It also works on other Linux distributions with systemd and Python 3.10 or newer, but those haven't been tried yet. Like the rest of Pitwall at 0.1, it hasn't been tested on real hardware yet.

## Decky or standalone?

| | Decky plugin | Standalone |
|---|---|---|
| Interface | Quick Access menu and a full-screen page in Gaming Mode | Web app on the same machine (Desktop Mode) |
| Needs | Decky Loader | Nothing extra; a password for your user to install |
| Running game | Read from Steam directly | Read from Steam's processes |
| Launch options (telemetry bridge, wheel fixes, benchmark) | Set instantly | Written to Steam's settings while Steam is closed; changes made while it's open are applied as soon as you exit Steam |
| Phone dashboard | Yes | Yes |

Use one or the other, not both: they would control the same wheel. The installer stops if the Decky plugin is installed.

## Install

1. Download `Pitwall-standalone-0.1.0.tar.gz` from the [latest release](https://github.com/crspytopgn/pitwall/releases/latest).
2. Extract it, open a terminal in the extracted `pitwall-0.1.0` folder, and run:

   ```
   ./install.sh
   ```

   On SteamOS, your user needs a password for this. If you've never set one, run `passwd` first.
3. Open **Pitwall** from your app menu, or go to http://127.0.0.1:8091 in a browser.

The installer:

- copies Pitwall to `/var/lib/pitwall/app`, owned by root. The service runs as root (like Decky runs plugins: wheel settings, udev rules and driver installs need it), so its code must not be writable by your user.
- installs and starts the `pitwall` system service, which starts at boot
- adds Pitwall to your app menu

On SteamOS, `/var` and `/etc` survive system updates, so Pitwall does too. Your settings and laps live in `~/.config/pitwall` and `~/.local/share/pitwall/app`.

To update, extract a newer package and run `./install.sh` again. Your settings are kept.

## Using it

Everything from the Decky plugin is in the web app's sidebar: Session, Laps, Auto setup, Game guide, Pre-race checks, Wheel, Force feedback feel, Fuel and tyres, Performance check, Engineer debrief, Updates and Send diagnostics. The top of the page shows the game Steam is running, whether Steam is open, and any launch option changes waiting for Steam to close.

### Launch options and Steam

Steam keeps its settings in memory and overwrites its settings file when it exits, so standalone Pitwall only edits launch options while Steam is closed:

- **Steam closed:** the change is written straight away (Pitwall keeps a backup of Steam's file next to it, ending `.pitwall-backup`).
- **Steam open:** the change is saved and applied the moment you exit Steam (Steam menu → Exit). The top of the page shows it as waiting. If you'd rather not close Steam, the game's page shows the launch options so you can paste them into **Properties → Launch options** yourself.

This affects the telemetry bridge, the wheel detection fixes and the performance benchmark. Everything else works with Steam open.

### Profiles per game

Pitwall sees which game is running from Steam's processes and applies that game's wheel profile automatically, as the plugin does. Start the game from Steam, then use **Wheel → Save profile for <game>**.

## Security

The web app can change system settings, so:

- it listens on this machine only (127.0.0.1), never on your network
- it only answers requests addressed to `127.0.0.1` or `localhost`, which stops websites from reaching it through DNS tricks
- every action needs a custom request header that other websites open in your browser can't send

The phone dashboard is separate and read-only, on your network at port 8090 as with the plugin.

## Logs and troubleshooting

- Logs: `journalctl -u pitwall -f`
- Restart: `sudo systemctl restart pitwall`
- "Pitwall service not responding" at the top of the web app: the service isn't running; check the logs above.
- The service won't start while Decky is running the Pitwall plugin. Remove the plugin in Decky, or remove standalone Pitwall.

## Uninstall

```
/var/lib/pitwall/app/standalone/uninstall.sh
```

Like uninstalling the plugin, this removes the wheel detection rule and any force feedback drivers Pitwall installed. Settings and laps are kept unless you add `--purge`. The telemetry bridge in `~/.local/share/pitwall/bin` stays, because games' launch options may still use it; remove the bridge from each game in Pitwall first if you want it gone.
