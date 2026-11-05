# Troubleshooting

## "No MOZA wheelbase found"

- Check the base has power and USB. In Desktop Mode run `ls /dev/serial/by-id/`: you should see a `Gudsen_MOZA_...` entry.
- Close Boxflat or Pit House.
- Pitwall also looks for any `ttyACM` device with USB vendor `346e`.

## Wheel works but no force feedback in games

**Pre-race checks** shows "Wheel found but no force feedback". MOZA, Cammus, PXN, Asetek, VRS and several other bases need the `hid-universal-pidff` kernel driver, which is in Linux 6.15 or newer, or the 6.12.24+, 6.13.12+ and 6.14.3+ updates. Pre-race checks name your wheel and the driver it needs, and look for the driver itself, so a hand-installed one counts. Update SteamOS first. If the driver still isn't there, open Pitwall → **Wheel** → **Force feedback** and press **Install** (see [Getting force feedback working](wheels.md#getting-force-feedback-working)); Logitech, Fanatec, Thrustmaster and Simagic drivers install the same way. Then use **Test force feedback**: if the wheel moves there but not in a game, the problem is the game's detection, not the driver. See the [wheel support table](wheel-support.md).

## Force feedback stopped after a SteamOS update

SteamOS updates replace the kernel, which removes drivers Pitwall installed. Pitwall says so when it starts; press **Reinstall** in Wheel → Force feedback.

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

## Phone screen turns off

Tap the dashboard once. Phones only allow a web page to keep the screen on after you've touched it, and the dashboard runs over your home network rather than HTTPS, so the first tap starts it. Adding the dashboard to your home screen also helps.

## Benchmark says "No MangoHud log found"

Restart the game after arming the benchmark and drive for at least a minute. Logs go to `~/.local/share/pitwall/mangohud`.

## Something else: send diagnostics

Pitwall → **Send diagnostics** → **Create diagnostics**. It collects your OS and kernel, wheel and force feedback status, telemetry sources, check results, settings (API key removed) and recent logs into a zip in your home folder. Then:

1. Scan the first QR code with your phone to download the zip (the link works once, for 10 minutes, on your local network).
2. Scan the second QR code to open a pre-filled bug report on GitHub, and attach the zip.

Nothing is sent anywhere automatically.
