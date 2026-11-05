# Changelog

## 0.1.0 (unreleased preview)

First public preview. Not yet tested on real hardware.

- Telemetry: BeamNG (OutGauge + MotionSim), Live for Speed, Forza Horizon 4/5/6 and Forza Motorsport, DiRT Rally 2.0 (Codemasters UDP), Assetto Corsa / ACC / AC EVO, Automobilista 2, Project CARS 2, rFactor 2, Le Mans Ultimate and RaceRoom (shared memory)
- Lap timing from the sim or a start line, live delta, braking-zone coaching
- Phone dashboard with shift lights, track map and voice callouts; five layouts (All, Drive, Laps, Track, Race) that scale to any phone in portrait or landscape; installable on Android and iPhone
- Wheel control: MOZA (serial), Logitech, Fanatec, Thrustmaster (kernel sysfs); per-game profiles
- MOZA rev lights from telemetry
- FFB presets and feel tuner with undo
- Game guide with live ratings (Valve, ProtonDB, Are We Anti-Cheat Yet) and generated docs
- One-tap winecarte telemetry bridge setup; DiRT Rally 2.0 telemetry auto setup
- Pre-race checks, MangoHud benchmark analysis, engineer debrief (optional Claude)
- Full-screen view
- Fuel and tyre strategy (fuel per lap, fuel to add, tyre temperatures with window, balance and wear)
- Wheel profiles per car, applied when the car appears in telemetry
- QR codes for the phone dashboard and diagnostics
- Send diagnostics: redacted zip, one-time phone download link and a pre-filled GitHub issue
- New wordmark logo
- F1 2021/22/23 telemetry (UDP formats 2021–2023), Euro Truck Simulator 2 / American Truck Simulator (scs-sdk-plugin), DiRT Rally and DiRT 4 entries, AC Rally entry
- iRacing re-checked: runs offline (Test Drive) under Proton; online still blocked by anti-cheat
- GitHub Pages website: game checker, wheel support, MOZA settings finder, fuel calculator, toolbox, day-one checklist
- Wheel identification from USB IDs with tested support levels (linux-steering-wheels); kernel check including backports
- Logitech rev lights (G27/G29/G923 via the driver's LEDs)
- winecarte bridge for AC Rally; Datalink noted for RaceRoom; toolbox of community tools
- Auto setup: detects device and wheel (MOZA base model) and applies MOZA's per-base recommendation; first-run prompt
- Day-one guide for new Steam Machine owners
- One UDP thread for all sims; strategy summary cached for the dashboard
- Fixes: launch options are fetched from Steam when not cached; car profiles re-apply after relaunch; a frozen shared-memory map no longer blocks another sim
- Track position for Assetto Corsa, AC EVO and ACC, so the track map works there
- Credits for every project, data source, library, icon set and font (CREDITS.md)
- Wheel table rebuilt from linux-steering-wheels with every wheel, USB IDs and notes (`scripts/sync_wheels.py`)
- Wheel and pedal detection: checks whether Linux sees them as joysticks, with a one-tap udev fix and a per-game SDL wheel ID launch option
- Logitech mice, keyboards and other non-wheel devices are no longer mistaken for wheels
- Force feedback setup: supported effects per wheel, a gentle left/right FFB test through the Linux input layer, and on SteamOS a one-tap build and install of hid-universal-pidff, new-lg4ff, hid-fanatecff, hid-tmff2 or simagic-ff for the running kernel, with a reinstall prompt after SteamOS updates
- Per game: raw HID access (PROTON_ENABLE_HIDRAW) as a last-resort detection fix
