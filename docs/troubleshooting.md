# Troubleshooting

## "No MOZA wheelbase found"

- Check the base has power and USB. In Desktop Mode run `ls /dev/serial/by-id/`: you should see a `Gudsen_MOZA_...` entry.
- Close Boxflat or Pit House.
- Pitwall also looks for any `ttyACM` device with USB vendor `346e`.

## Wheel works but no force feedback in games

**Pre-race checks** shows "Wheel found but no force feedback". MOZA needs the `hid-universal-pidff` kernel driver (mainline since Linux 6.15). Make sure SteamOS is up to date.

## No telemetry

- Run **Pre-race checks** in the game.
- UDP sims: check the game's telemetry output is on with IP `127.0.0.1` and the right port ([Telemetry setup](telemetry.md)).
- Shared-memory sims: check the bridge is running (Pre-race checks) and that you restarted the game after setting it up.
- Another app may already be using the port; the Session panel lists port errors.

## BeamNG laps aren't recorded

Set a start line (Session → **Set start line here**) and make sure MotionSim is enabled; position comes from MotionSim.

## Phone can't open the dashboard

- Phone and Steam Machine must be on the same network.
- Use the exact address shown in the Session panel.
- Some guest or mesh networks isolate devices; try your main network.

## Benchmark says "No MangoHud log found"

Restart the game after arming the benchmark and drive for at least a minute. Logs go to `~/.local/share/pitwall/mangohud`.

## Something else

[Open an issue](../../../issues/new/choose) with the Decky log from `~/homebrew/logs/Pitwall/`.
