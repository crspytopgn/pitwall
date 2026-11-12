# Changelog

## Unreleased

- Graphics tuning: each recognised racing game gets a graphics level for the device (Steam Machine, Steam Deck, PC), a frame cap at the target FPS and quiet measuring; the level moves after each session. Assetto Corsa's settings are changed directly (with a backup); other games get the matching in-game preset
- Wheel buttons: a page that shows what each button does in Steam and in the game, live, and on the phone dashboard after each press. Wheel buttons can move around Steam's menus when no game runs (virtual controller, off in games). One automatic in-game layout, changed by pressing the button you want; written into BeamNG.drive's controls, keeping your own bindings
- MOZA: when a base can't be used, Pitwall says why: not on USB, connected in Xbox mode (the R3's default; with how to switch to PC mode), or settings port missing. Shown on the Wheel page, in Pre-race checks and in diagnostics

## 0.1.0 (12 November 2026, preview)

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
- Updates: daily check (switchable) of installed force feedback drivers and the winecarte bridge against their latest GitHub versions, with one-tap update; the bridge now records its installed version
- README: the dashboard screenshots now have a heading and captions
- Robustness: every telemetry frame is cleaned (NaN/infinity removed, values clamped) so a bad packet can't freeze the phone dashboard; malformed UDP packets can no longer stop the listener; strict JSON to the browser
- Phone dashboard: shows 'Connection lost, reconnecting' if updates stop for 3 seconds instead of showing old numbers as live; sends a slow heartbeat when no game is running
- Values from the UI are checked before reaching the wheel or settings (non-numbers, NaN, out-of-range FPS)
- Uninstalling Pitwall removes its wheel detection rule and any drivers it installed
- Website fuel calculator handles a missing or zero lap time; day-one checklist includes the force feedback test
- Standalone version (no Decky): the same backend as a system service with a local web app covering every plugin page; detects the running game from Steam's processes; writes launch options to Steam's settings while Steam is closed (queued while it's open, with a backup); localhost-only control API with host and header checks; install.sh / uninstall.sh; built by CI as Pitwall-standalone
