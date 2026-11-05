# Telemetry setup

Pitwall reads each sim's own data output. Nothing is injected into games.

## UDP sims (no extra software)

| Sim | Where to switch it on | Settings |
|---|---|---|
| BeamNG.drive | Options → Other → Protocols | OutGauge `127.0.0.1:4444`, MotionSim `127.0.0.1:4445` |
| Live for Speed | `cfg.txt` | `OutGauge Mode 1`, `OutGauge IP 127.0.0.1`, `OutGauge Port 4444` |
| Forza Horizon 4 / 5, Forza Motorsport | Settings → HUD and Gameplay → Data Out | On, `127.0.0.1`, port `5300` |
| DiRT Rally 2.0 | `hardware_settings_config.xml` | Pitwall can do it: Game guide → DiRT Rally 2.0 → **Do this for me** |
| DiRT Rally, DiRT 4 | `hardware_settings_config.xml` | `<udp enabled="true" extradata="3" ip="127.0.0.1" port="20777" delay="1" />` |
| F1 23, F1 22, F1 2021 | Settings → Telemetry Settings | UDP Telemetry on, Broadcast off, IP `127.0.0.1`, port `20777`, UDP Format = the game's year |

Pitwall listens on these UDP ports: 4444 (OutGauge), 4445 (MotionSim), 5300 (Forza), 20777 (Codemasters and F1: Pitwall tells them apart by packet shape) and 20778 (F1, optional). One thread handles all of them.

### What each format gives

| Format | Speed/RPM/gear/pedals | Position (track map, start line) | Laps | Tyres |
|---|---|---|---|---|
| OutGauge (BeamNG, LFS) | ✅ | BeamNG via MotionSim | LFS: no (use a start line) | – |
| Forza Data Out | ✅ | ✅ | ✅ | temperatures |
| Codemasters (DR2) | ✅ | ✅ | ✅ | – |
| F1 2021–23 | ✅ | ✅ | ✅ | surface temperatures |

Sources: [BeamNG protocols](https://documentation.beamng.com/modding/protocols), Forza's Data Out documentation, the Codemasters UDP "extradata 3" format.

## Shared-memory sims (need a bridge)

Assetto Corsa, ACC, AC EVO, Automobilista 2, Project CARS 2, rFactor 2, Le Mans Ultimate and RaceRoom publish telemetry as Windows shared memory. Under Proton it stays inside the game's Wine prefix unless a bridge copies it to `/dev/shm`.

**One-tap setup:** Game guide → the game → **Set up telemetry bridge**. Pitwall:

1. downloads the latest [winecarte](https://github.com/srounce/winecarte) release into `~/.local/share/pitwall/bin`
2. adds it in front of `%command%` in the game's launch options, keeping anything you already had

Restart the game afterwards. **Pre-race checks** shows whether the bridge is running. **Remove telemetry bridge** takes it out of the launch options again.

| Sim | Map Pitwall reads | Notes |
|---|---|---|
| Assetto Corsa / ACC / AC EVO | `acpmf_physics`, `acpmf_graphics`, `acpmf_static` | |
| Automobilista 2 / Project CARS 2 | `$pcars2$` | Set Shared Memory to "Project CARS 2" in the game's options |
| rFactor 2 | `$rFactor2SMMP_Telemetry$`, `$rFactor2SMMP_Scoring$` | Needs the Windows rF2SharedMemoryMapPlugin |
| Le Mans Ultimate | `LMU_Data` | |
| RaceRoom | `$R3E` | No automatic bridge yet |
| Euro Truck Simulator 2 / ATS | `SCS/SCSTelemetry` | Native Linux: install the [scs-sdk-plugin](https://github.com/RenCloud/scs-sdk-plugin) `.so` in `bin/linux_x64/plugins`; no bridge needed |

Layouts come from the C headers in [simapi](https://github.com/Spacefreak18/simapi). Pitwall's tests fill those real structs from C and check every field is decoded correctly (`tools/shm_fixtures.c`).

## Position axes

Sims disagree on which axis points up. Pitwall reorders every sim's coordinates to (horizontal, horizontal, height) so maps and start lines work the same everywhere.

## Changing ports

Ports can be overridden in `~/homebrew/settings/Pitwall/settings.json`:

```json
{ "ports": { "outgauge": 4444, "motionsim": 4445, "forza": 5300, "codemasters": 20777 } }
```

Restart Decky (or the Steam Machine) after editing.
