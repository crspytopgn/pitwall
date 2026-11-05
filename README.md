# Pitwall

A sim racing companion for SteamOS (Steam Machine, Steam Deck, any Linux with [Decky Loader](https://decky.xyz)). It lives in the Quick Access Menu, so you never leave Gaming Mode.

- **Live telemetry** from the sims that support it, with lap timing and a live delta to your best lap
- **Coaching**: after each lap, compares every braking zone with your best lap and tells you where the time went ("Corner 3: lost 0.31s; braked 18 m earlier, 6 km/h slower at the apex")
- **Phone dashboard**: open `http://<steam-machine-ip>:8090` on a phone or tablet for gear, shift lights, delta, lap times, pedals and coaching tips
- **Wheel control**: rotation, FFB, damping and more, with per-game profiles applied automatically at launch
- **Game guide**: compatibility status, install steps and known issues for each sim, combined with live ratings from Valve, ProtonDB and Are We Anti-Cheat Yet
- **Pre-race checks**: is the wheel connected, is force feedback available, is telemetry arriving, is the bridge running
- **Performance**: 90-second MangoHud benchmark, judged on 1% lows and stutters against your TV's refresh rate
- **Engineer debrief**: session summary with your problem corners; optionally written up by Claude if you add an Anthropic API key

> Unofficial. Not affiliated with any sim developer or wheel manufacturer.

## Supported sims

| Sim | Runs on SteamOS | Telemetry in Pitwall | How |
|---|---|---|---|
| BeamNG.drive | ✅ native | ✅ | OutGauge + MotionSim UDP; set a start line for laps |
| DiRT Rally 2.0 | ✅ Proton | ✅ | Codemasters UDP; Pitwall can switch it on for you |
| Forza Horizon 4 / 5 | ✅ Proton | ✅ | Forza Data Out |
| Forza Horizon 6 | ✅ | 🧪 untested | Forza Data Out (assumed same format) |
| Forza Motorsport | ⚠️ launch problems reported | ✅ | Forza Data Out |
| Live for Speed | ✅ Proton | ✅ basic | OutGauge |
| Assetto Corsa / ACC / AC EVO | 🛠️ Proton | ✅ | Shared memory via [simshmbridge](https://github.com/Spacefreak18/simshmbridge) or [winecarte](https://github.com/srounce/winecarte) |
| Automobilista 2, rFactor 2, RaceRoom | 🛠️ Proton | 🔜 planned | Shared memory via bridge |
| Le Mans Ultimate | ⚠️ community Proton build only | 🔜 planned | Shared memory via bridge |
| iRacing, EA SPORTS WRC, F1 24 / 25 | ⛔ anti-cheat blocks Linux | – | – |

The full, sourced list (install steps, known issues, links) is in [`py_modules/pitwall/data/games.json`](py_modules/pitwall/data/games.json) and is what the in-app game guide shows.

## Supported wheels

| Wheel | Settings | Notes |
|---|---|---|
| MOZA (all bases) | Full: rotation, FFB strength, torque, road sensitivity, damper, friction, inertia, spring, max speed, FFB on/off, centre | Serial protocol from [Boxflat](https://github.com/Lawstorant/boxflat). FFB in games needs the kernel's `hid-universal-pidff` driver |
| Logitech G29 / G920 / G923 etc. | Rotation | Through the kernel's `hid-logitech` driver |
| Fanatec, Thrustmaster, Simagic, Cammus, Simucube | Detected in checks | Settings drivers planned |

Wheel drivers share one interface (`py_modules/pitwall/wheels/`), so adding a brand is one class.

## Install

1. Install [Decky Loader](https://decky.xyz) on the Steam Machine.
2. Download `Pitwall-x.y.z.zip` from [Releases](../../releases) (or the latest build artifact under Actions).
3. Gaming Mode → `...` → Decky (plug icon) → cog → **General → Developer mode** on.
4. **Developer → Install Plugin from ZIP File**, then pick the zip.

The backend runs as root (Decky's `_root` flag) so it can talk to the wheel's serial port without a udev rule.

### BeamNG quick start

1. In BeamNG: **Options → Other → Protocols**. Enable **OutGauge** (`127.0.0.1`, port `4444`) and **MotionSim** (`127.0.0.1`, port `4445`).
2. Drive to the start/finish point of a loop and press **Set start line here** in Pitwall.
3. Drive laps. Coaching appears from your second lap.

## Where the compatibility data comes from

Pitwall prefers primary sources and says where every claim comes from.

| Source | Used for | Why |
|---|---|---|
| Developer documentation (e.g. BeamNG docs) | Install steps, telemetry formats | Primary source |
| Valve's Steam Deck compatibility rating | Live, per game | Official testing |
| [ProtonDB](https://www.protondb.com) | Live tier, plus known issues and tinkering steps | Largest set of crowd reports with Proton versions |
| [Are We Anti-Cheat Yet](https://areweanticheatyet.com) | Live anti-cheat status | Anti-cheat decides whether online sims run at all |
| [GamingOnLinux](https://www.gamingonlinux.com/anticheat/) | Anti-cheat news and confirmation | Second source |
| [awesome-linux-simracing](https://github.com/LukasLichten/awesome-linux-simracing) | Bridges and drivers | Community index |

Live ratings are cached for 24 hours and fail soft when offline. Curated entries in `games.json` must link a source (the test suite enforces this).

## Privacy

- The dashboard is served on your local network only, with no login. Don't port-forward it.
- Telemetry and laps stay on the device (`~/homebrew/data/Pitwall/laps.sqlite`).
- The engineer debrief sends a lap summary to Anthropic **only** if you add an API key; the key is stored in a file only root can read.

## Development

```bash
pnpm install
pnpm run build                               # frontend → dist/index.js
python3 -m unittest discover -s tests        # backend tests
BOXFLAT_DIR=/path/to/boxflat python3 -m unittest discover -s tests   # + MOZA protocol cross-check
./scripts/package.sh                         # → out/Pitwall-x.y.z.zip
```

Layout:

```
main.py                         Decky backend entry point
src/index.tsx                   Quick Access Menu UI
py_modules/pitwall/
  telemetry/parsers.py          OutGauge, MotionSim, Forza, Codemasters packet parsers
  telemetry/sources.py          UDP listeners, AC/ACC shared-memory reader
  laps.py                       lap detection (sim laps or start line), sampling, live delta
  coach.py                      braking-zone comparison and tips
  store.py                      SQLite lap storage
  hub.py                        ties it together, live state
  dashboard.py, web/            phone dashboard (HTTP + Server-Sent Events)
  wheels/                       MOZA and Logitech drivers
  compat.py, data/games.json    game guide, live ratings, auto-setup
  health.py, perf.py            pre-race checks, MangoHud analysis
  engineer.py                   debrief (offline + optional Claude)
```

No third-party Python dependencies: everything uses the standard library so it runs on Decky's bundled Python.

## Roadmap

- Telemetry for AMS2 / Project CARS 2, rFactor 2 / LMU and RaceRoom via shared-memory bridges
- Wheel drivers for Fanatec (hid-fanatecff), Thrustmaster (hid-tmff2), Simagic
- RPM LEDs on MOZA wheels from telemetry
- Spoken coaching cues during a session
- Track maps on the dashboard from position data

## Credits and licence

GPL-3.0. The MOZA protocol and command table come from [Boxflat](https://github.com/Lawstorant/boxflat) by Tomasz Pakuła, which reverse engineered them. Telemetry formats from the BeamNG documentation and the Forza, Codemasters and Assetto Corsa communities.
