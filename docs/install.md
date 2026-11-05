# Installing Pitwall

Pitwall is a [Decky Loader](https://decky.xyz) plugin. Decky adds a plugin menu to SteamOS's Quick Access Menu (the `...` button) and works in Gaming Mode on the Steam Machine, Steam Deck and other SteamOS or Linux PCs.

> **Status: 0.1.0 preview.** Pitwall hasn't been tested on real hardware yet. Please [report what works and what doesn't](../../../issues/new/choose).

## 1. Install Decky Loader

Follow the instructions at [decky.xyz](https://decky.xyz). In short: switch to Desktop Mode, download the installer from the Decky website, run it, and return to Gaming Mode.

## 2. Install Pitwall

1. Download the latest Pitwall zip from the newest successful run under **Actions → build → Artifacts** (you need to be signed in to GitHub). GitHub wraps it in another zip: extract that once to get `Pitwall-0.1.0.zip`. A Releases page will follow once 0.1 has been tested on hardware.
2. In Gaming Mode press `...`, open Decky (the plug icon) and select the cog.
3. Under **General**, switch on **Developer mode**.
4. Open **Developer → Install Plugin from ZIP File** and pick the zip.
5. Pitwall appears in the Decky menu with a chequered-flag icon.

## Why Pitwall runs as root

Pitwall's backend uses Decky's `_root` flag. That lets it:

- talk to MOZA bases over their serial port without you installing a udev rule
- write wheel settings exposed by kernel drivers under `/sys`
- read telemetry from `/dev/shm`
- install a force feedback driver or the wheel detection rule, only when you press the button

It only touches the files listed in this documentation. Files it creates in your home folder (benchmark logs, the telemetry bridge) are handed back to your user.

## Updating

Install the new zip the same way. Your settings, wheel profiles and lap history are kept: they live outside the plugin folder (`~/homebrew/settings/Pitwall` and `~/homebrew/data/Pitwall`).

### Drivers and the telemetry bridge

Pitwall checks once a day whether the force feedback drivers and the telemetry bridge it installed have newer versions on GitHub, and tells you when they do. **More → Updates** lists each one with its installed and latest version, a **Check now** button and an **Update** button. Nothing updates on its own; switch off **Check daily** there if you'd rather check yourself. The check only reads from GitHub. Game ratings and compatibility data refresh by themselves.

## Removing

Decky → cog → **Plugins** → Pitwall → **Uninstall**. To remove everything, also delete:

- `~/homebrew/settings/Pitwall` (settings, wheel profiles, API key)
- `~/homebrew/data/Pitwall` (lap history, cached ratings)
- `~/.local/share/pitwall` (benchmark logs, downloaded telemetry bridge)

If you set up a telemetry bridge or a benchmark, open the game's **Properties → General → Launch Options** and remove the `winecarte-run` or `MANGOHUD` part.
