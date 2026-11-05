<p align="center">
  <img src="assets/banner.png" alt="Pitwall: sim racing companion for SteamOS and Steam Machine" width="100%">
</p>

<p align="center">
  <a href="../../actions/workflows/build.yml"><img src="../../actions/workflows/build.yml/badge.svg" alt="build"></a>
  <img src="https://img.shields.io/badge/version-0.1.0%20preview-orange" alt="version 0.1.0 preview">
  <img src="https://img.shields.io/badge/SteamOS-Decky%20plugin-1a9fff" alt="Decky plugin">
  <img src="https://img.shields.io/badge/licence-GPL--3.0-blue" alt="GPL-3.0">
</p>

**Pitwall makes sim racing on Linux easy.** It's a [Decky Loader](https://decky.xyz) plugin for the Steam Machine, Steam Deck and any SteamOS PC: live telemetry, lap coaching, a phone dashboard, wheel and force feedback control, and a sourced guide to which sims run on SteamOS and how to set them up. Everything happens in Gaming Mode, from the Quick Access Menu.

> **0.1.0 preview.** Pitwall is feature-complete for its first release but **hasn't been tested on real hardware yet**. Reports are very welcome: [open an issue](../../issues/new/choose).

## Features

| | |
|---|---|
| 📡 **Telemetry from 15 sims** | BeamNG, Forza, DiRT Rally 2.0, Live for Speed, Assetto Corsa, ACC, AC EVO, AMS2, Project CARS 2, rFactor 2, Le Mans Ultimate, RaceRoom |
| ⏱️ **Lap timing and live delta** | Uses the sim's own laps, or a start line you set (BeamNG, LFS) |
| 💡 **Coaching** | Compares every braking zone with your best lap: *"Corner 3: lost 0.31s; braked 18 m earlier, 6 km/h slower at the apex"* |
| 📱 **Phone dashboard** | Shift lights, gear, delta, laps, pedals, track map and voice callouts on any phone on your Wi-Fi |
| 🛞 **Wheel control** | MOZA (full Pit House-style settings), Logitech, Fanatec, Thrustmaster; per-game profiles applied at launch |
| 🚥 **Rev lights** | Drives MOZA wheel RPM LEDs from live telemetry |
| 🎚️ **FFB feel tuner** | Sourced presets, then "what feels wrong?" → a small, explained, undoable change |
| 📖 **Game guide** | Status, install steps, in-game FFB settings and known issues per sim, plus live ratings from Valve, ProtonDB and Are We Anti-Cheat Yet |
| 🔌 **One-tap telemetry bridge** | Sets up [winecarte](https://github.com/srounce/winecarte) for shared-memory sims, keeping your launch options |
| ✅ **Pre-race checks** | Wheel, force feedback driver, telemetry, bridge and game compatibility at a glance |
| ⚡ **Performance** | 90-second MangoHud benchmark judged on 1% lows and stutters against your TV's refresh rate |
| 🎧 **Engineer debrief** | Session summary and problem corners; optionally written up by Claude with your own API key |

<p align="center"><img src="docs/images/dashboard.png" alt="Phone dashboard" width="300"></p>

## Quick start

1. Install [Decky Loader](https://decky.xyz).
2. Download `Pitwall-x.y.z.zip` from [Releases](../../releases) (or the latest build under **Actions**).
3. Decky → cog → **Developer mode** on → **Install Plugin from ZIP File**.
4. Open Pitwall from the Quick Access Menu and run **Pre-race checks**.

Then follow [Getting started](docs/getting-started.md).

## Which sims work?

| Sim | Runs on SteamOS | Pitwall telemetry |
|---|---|---|
| BeamNG.drive | ✅ native | ✅ |
| DiRT Rally 2.0 | ✅ | ✅ (auto setup) |
| Forza Horizon 4 / 5 | ✅ | ✅ |
| Live for Speed | ✅ | ✅ |
| Assetto Corsa / ACC | 🛠️ | ✅ via bridge |
| AMS2, Project CARS 2, rFactor 2, Le Mans Ultimate, RaceRoom | 🛠️ / ⚠️ | 🧪 via bridge |
| iRacing, EA SPORTS WRC, F1 24 / 25 | ⛔ anti-cheat | – |

The full, sourced guide is in **[docs/compatibility.md](docs/compatibility.md)** (generated from the same data the app uses).

## Documentation

[Install](docs/install.md) · [Getting started](docs/getting-started.md) · [Compatibility](docs/compatibility.md) · [Telemetry](docs/telemetry.md) · [Wheels](docs/wheels.md) · [FFB tuning](docs/ffb-tuning.md) · [Performance](docs/performance.md) · [Coaching](docs/coaching.md) · [Troubleshooting](docs/troubleshooting.md) · [FAQ](docs/faq.md)

## How it's built

- **No third-party Python dependencies**: everything uses the standard library, so it runs on Decky's bundled Python.
- **Light on the Steam Machine**: idle, it checks for telemetry every two seconds; shared memory is read in place without copying.
- **Verified protocols**: MOZA commands are checked byte for byte against Boxflat; shared-memory readers are checked against fixtures written by C code using the real struct definitions.
- **Sourced knowledge**: every known issue and preset links its source, and the test suite enforces it.

```
main.py                     Decky backend entry point
src/index.tsx               Quick Access Menu and full-screen UI
py_modules/pitwall/
  telemetry/                UDP parsers (OutGauge, MotionSim, Forza, Codemasters) and shared-memory readers
  laps.py, coach.py         lap detection, live delta, braking-zone coaching
  hub.py, store.py          live state, SQLite lap history
  dashboard.py, web/        phone dashboard (HTTP + Server-Sent Events)
  wheels/                   MOZA serial driver; Logitech, Fanatec, Thrustmaster sysfs drivers
  leds.py, ffb.py           rev lights, FFB presets and feel tuner
  compat.py, data/          game guide, live ratings, auto setup
  bridge.py                 winecarte download and launch options
  health.py, perf.py        pre-race checks, MangoHud analysis
  engineer.py               debrief (offline, optional Claude)
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

<sub>Keywords: sim racing Linux, SteamOS sim racing, Steam Machine racing wheel, Steam Deck racing wheel, MOZA Linux, MOZA R3 SteamOS, Boxflat Decky, BeamNG telemetry Linux, Assetto Corsa Proton telemetry, ACC Linux telemetry, SimHub alternative Linux, racing dashboard phone, Decky plugin racing.</sub>
