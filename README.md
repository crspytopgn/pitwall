<p align="center">
  <img src="assets/banner.png" alt="Pitwall: sim racing companion for SteamOS and Steam Machine" width="100%">
</p>

<p align="center">
  <a href="../../actions/workflows/build.yml"><img src="../../actions/workflows/build.yml/badge.svg" alt="build"></a>
  <img src="https://img.shields.io/badge/version-0.1.0%20preview-orange" alt="version 0.1.0 preview">
  <img src="https://img.shields.io/badge/SteamOS-Decky%20plugin-1a9fff" alt="Decky plugin">
  <img src="https://img.shields.io/badge/licence-GPL--3.0-blue" alt="GPL-3.0">
</p>

**Pitwall makes sim racing on Linux easy.** It's a [Decky Loader](https://decky.xyz) plugin for the Steam Machine, Steam Deck and any SteamOS PC: a sourced guide to which sims run on SteamOS and how to set them up, wheel and force feedback control, live telemetry with lap coaching, and a phone dashboard. Everything happens in Gaming Mode, from the Quick Access Menu.

> **0.1.0 preview.** Pitwall is feature-complete for its first release but **hasn't been tested on real hardware yet**. Reports are very welcome: [open an issue](../../issues/new/choose).

## What it does

### Get set up
| Feature | What it does |
|---|---|
| **Game guide** | Does it run on SteamOS, how to install it, in-game FFB settings and known issues for 27 sims, plus live ratings from Valve, ProtonDB and Are We Anti-Cheat Yet |
| **One-tap setup** | Installs the telemetry bridge for shared-memory sims and switches on DiRT Rally 2.0's telemetry, keeping your launch options |
| **Auto setup** | Recognises your device and wheel (down to the MOZA base model) and applies the best starting settings in one tap |
| **Pre-race checks** | Wheel, force feedback driver, telemetry, bridge and game compatibility at a glance |

### Drive
| Feature | What it does |
|---|---|
| **Wheel control** | MOZA (full Pit House-style settings), Logitech, Fanatec, Thrustmaster; profiles per game and per car, applied automatically |
| **FFB feel tuner** | Sourced presets, then "what feels wrong?" → a small, explained, undoable change |
| **Rev lights** | Drives MOZA wheel RPM LEDs from live telemetry, and Logitech G27/G29/G923 LEDs where the driver exposes them |

### ⏱ Go faster
| Feature | What it does |
|---|---|
| **Live telemetry** | 20+ sims: BeamNG, Forza, F1 2021–23, DiRT Rally 1/2, DiRT 4, Assetto Corsa family, AMS2, rFactor 2, Le Mans Ultimate, Euro Truck Simulator 2 and more |
| **Phone dashboard** | Scan a QR code: shift lights, gear, live delta, laps, fuel, tyres, track map and voice callouts on any phone on your Wi-Fi |
| **Coaching** | Compares every braking zone with your best lap: *"Corner 3: lost 0.31s; braked 18 m earlier, 6 km/h slower at the apex"* |
| **Strategy** | Fuel per lap, laps left, what to add at your stop; tyre temperatures, balance and wear per lap |

### Keep it smooth
| Feature | What it does |
|---|---|
| **Performance check** | 90-second MangoHud benchmark judged on 1% lows and stutters against your TV's refresh rate |
| **Lightweight** | One thread listens for every UDP sim; idle checks every two seconds; shared memory read in place |

### Get help
| Feature | What it does |
|---|---|
| **Engineer debrief** | Session summary and problem corners; optionally written up by Claude with your own API key |
| **Send diagnostics** | One tap bundles everything for a bug report; scan to download it and open a pre-filled GitHub issue |

<p align="center"><img src="docs/images/dashboard.png" alt="Phone dashboard" width="300"></p>

## Quick start

1. Install [Decky Loader](https://decky.xyz).
2. Download the latest build: **Actions → build → newest run → Artifacts → Pitwall** (signed in to GitHub), and extract GitHub's outer zip to get `Pitwall-0.1.0.zip`. A Releases page will follow once 0.1 has been tested.
3. Decky → cog → **Developer mode** on → **Install Plugin from ZIP File**.
4. Open Pitwall and press **Run auto setup**: it recognises your device and wheel and applies the best starting settings.

New Steam Machine? Follow the **[day-one guide](docs/day-one.md)** from unboxing to first lap.

## No plugin? Use the website

The **[Pitwall website](https://crspytopgn.github.io/pitwall/)** works in any browser: check whether a sim runs on SteamOS, whether your wheel works on Linux, find MOZA's recommended settings for your base, calculate fuel, and tick off the day-one checklist.

## Which sims work?

| Sim | Runs on SteamOS | Pitwall telemetry |
|---|---|---|
| BeamNG.drive | Yes, native | Yes |
| Euro Truck Simulator 2, American Truck Simulator | Yes, native | Experimental (SDK plugin) |
| DiRT Rally 2.0, DiRT Rally | Yes | Yes (DR2 sets up automatically) |
| Forza Horizon 4 / 5 | Yes | Yes |
| F1 23 (F1 22, F1 2021: check the live rating) | Yes | Experimental |
| Live for Speed | Yes | Yes |
| Assetto Corsa, ACC | With setup | Yes, via one-tap bridge |
| AMS2, Project CARS 2, rFactor 2, Le Mans Ultimate, AC EVO, AC Rally | With setup | Experimental, via one-tap bridge |
| RaceRoom | With setup | Experimental (manual bridge) |
| iRacing | Offline Test Drive only | No |
| EA SPORTS WRC, F1 24, F1 25 | No (anti-cheat) | No |

The full, sourced guide is in **[docs/compatibility.md](docs/compatibility.md)** (generated from the same data the app uses).

## Documentation

[Day one](docs/day-one.md) · [Install](docs/install.md) · [Getting started](docs/getting-started.md) · [Compatibility](docs/compatibility.md) · [Telemetry](docs/telemetry.md) · [Wheels](docs/wheels.md) · [Wheel support table](docs/wheel-support.md) · [Toolbox](docs/toolbox.md) · [FFB tuning](docs/ffb-tuning.md) · [Strategy](docs/strategy.md) · [Performance](docs/performance.md) · [Coaching](docs/coaching.md) · [Troubleshooting](docs/troubleshooting.md) · [FAQ](docs/faq.md)

## How it's built

- **No third-party Python dependencies**: everything uses the standard library, so it runs on Decky's bundled Python.
- **Light on the Steam Machine**: idle, it checks for telemetry every two seconds; shared memory is read in place without copying.
- **Verified protocols**: MOZA commands are checked byte for byte against Boxflat; shared-memory readers are checked against fixtures written by C code using the real struct definitions.
- **Sourced knowledge**: every known issue and preset links its source, and the test suite enforces it.

```
main.py                     Decky backend entry point
src/index.tsx               Quick Access Menu and full-screen UI
py_modules/pitwall/
  telemetry/                UDP parsers (OutGauge, MotionSim, Forza, Codemasters, F1) and shared-memory readers
  laps.py, coach.py         lap detection, live delta, braking-zone coaching
  hub.py, store.py          live state, SQLite lap history
  dashboard.py, web/        phone dashboard (HTTP + Server-Sent Events)
  wheels/                   MOZA serial driver; Logitech, Fanatec, Thrustmaster sysfs drivers
  leds.py, ffb.py           rev lights, FFB presets and feel tuner
  strategy.py               fuel and tyre strategy
  diagnostics.py            bug-report bundle and pre-filled issue
  compat.py, data/          game guide, live ratings, auto setup
  bridge.py                 winecarte download and launch options
  health.py, perf.py        pre-race checks (wheel identification), MangoHud analysis
  device.py                 device detection and auto setup
  data/                     games.json, wheels.json, tools.json: the sourced knowledge base
  engineer.py               debrief (offline, optional Claude)
site/                       the GitHub Pages website (built from the same data)
tools/                      C programs that generate shared-memory offsets and test fixtures
```

See [CONTRIBUTING.md](CONTRIBUTING.md) to build, test or add a sim or wheel.

## Credits

- MOZA protocol: [Boxflat](https://github.com/Lawstorant/boxflat) by Tomasz Pakuła
- Shared-memory layouts: [simapi](https://github.com/Spacefreak18/simapi) by Spacefreak18
- Telemetry bridge: [winecarte](https://github.com/srounce/winecarte)
- Compatibility data: [ProtonDB](https://www.protondb.com), Valve's Steam Deck ratings, [Are We Anti-Cheat Yet](https://areweanticheatyet.com), [GamingOnLinux](https://www.gamingonlinux.com)
- Wheel drivers: [hid-fanatecff](https://github.com/gotzl/hid-fanatecff), [hid-tmff2](https://github.com/Kimplul/hid-tmff2), [new-lg4ff](https://github.com/berarma/new-lg4ff), and `hid-universal-pidff` in mainline Linux

Pitwall is unofficial and not affiliated with Valve, MOZA Racing or any sim developer. Licensed under GPL-3.0.

<sub>Keywords: sim racing Linux, F1 23 Linux telemetry, Euro Truck Simulator 2 wheel Linux, SteamOS sim racing, Steam Machine racing wheel, Steam Deck racing wheel, MOZA Linux, MOZA R3 SteamOS, Boxflat Decky, BeamNG telemetry Linux, Assetto Corsa Proton telemetry, ACC Linux telemetry, SimHub on Linux, racing dashboard phone, Decky plugin racing.</sub>
