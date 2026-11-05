# Changelog

## 0.1.0 (unreleased preview)

First public preview. Not yet tested on real hardware.

- Telemetry: BeamNG (OutGauge + MotionSim), Live for Speed, Forza Horizon 4/5/6 and Forza Motorsport, DiRT Rally 2.0 (Codemasters UDP), Assetto Corsa / ACC / AC EVO, Automobilista 2, Project CARS 2, rFactor 2, Le Mans Ultimate and RaceRoom (shared memory)
- Lap timing from the sim or a start line, live delta, braking-zone coaching
- Phone dashboard with shift lights, track map and voice callouts
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
- Auto setup: detects device and wheel (MOZA base model) and applies MOZA's per-base recommendation; first-run prompt
- Day-one guide for new Steam Machine owners
- One UDP thread for all sims; strategy summary cached for the dashboard
- Fixes: launch options are fetched from Steam when not cached; car profiles re-apply after relaunch; a frozen shared-memory map no longer blocks another sim
