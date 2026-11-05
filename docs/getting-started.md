# Getting started

This walks through a first session with any supported sim. The examples use BeamNG.drive because it runs natively and needs no extra software.

## 1. Run auto setup

The first time you open Pitwall it offers **Run auto setup**. It recognises your device and wheel and applies the best starting settings.

## 2. Switch on the sim's telemetry

Open **Game guide**, pick your sim and follow its setup steps. Where Pitwall can do it for you, there's a button: **Do this for me** for sims with a config file, or **Set up telemetry bridge** for Proton sims that publish shared memory. The [telemetry guide](telemetry.md) lists every sim's settings.

For example, in BeamNG: Options → Other → Protocols, then enable OutGauge (`127.0.0.1`, port `4444`) and MotionSim (`127.0.0.1`, port `4445`).

The **Session** panel shows `Telemetry: <sim>` as soon as data arrives.

## 3. Check everything and set a start line if needed

Launch the sim and open **Pre-race checks**: wheel, force feedback, telemetry and (if needed) the bridge should all be OK.

Most sims report laps themselves. If the Session panel says a start line is needed (BeamNG, for example), drive to your start/finish point and press **Set start line here**.

## 4. Open the phone dashboard

The Session panel shows an address like `http://192.168.1.20:8090` and a QR code (switch on **Show QR code**). Scan it with a phone or tablet on the same Wi-Fi. You get:

- shift lights, gear, speed and RPM
- a live delta against your best lap (green: ahead, red: behind)
- current, last and best lap times
- throttle and brake bars
- coaching tips after each lap
- fuel in the tank, laps left and tyre temperatures (when the game sends them)
- a track map drawn from your own driving, with your position
- optional voice callouts (tap **Voice**) for lap times and the top tip

Pick a layout from the bar at the bottom, or swipe left and right:

| Layout | Shows |
|---|---|
| **All** | Everything above |
| **Drive** | Rev lights, a huge gear, speed and RPM, delta |
| **Laps** | A big delta and lap time, last and best, coaching |
| **Track** | A large track map with delta and times |
| **Race** | Fuel, tyres, delta and times, for longer races |

Every layout works in portrait and landscape and scales to the size of the phone. Your choice is remembered. To give a second phone a different layout, add it to the address, for example `http://192.168.1.20:8090/#track`.

Add it to your home screen for a full-screen view: on Android, open the browser menu and choose **Install app** or **Add to Home screen**; on iPhone, tap Share, then **Add to Home Screen**. It works in any current phone browser (Chrome, Samsung Internet, Firefox, Safari). The screen stays on while the dashboard is open; on some phones that starts after your first tap.

## 5. Drive

From your second lap, Pitwall compares every braking zone with your best lap and tells you where the time went. See [Coaching](coaching.md).

## 6. Wheel and force feedback

- **Wheel**: change rotation, FFB strength and effects, and save a profile for the game you're running. It's applied automatically the next time that game starts.
- **Force feedback feel**: pick a starting preset, then tell Pitwall what feels wrong ("too light", "oscillates", "can't feel the road") and it makes a small, explained change you can undo. See [FFB tuning](ffb-tuning.md).

## 7. Full screen

**Open full screen** (under More) gives the same tools with more room, plus your lap history.
