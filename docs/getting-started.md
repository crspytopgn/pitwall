# Getting started

This walks through a first session in BeamNG.drive. Other sims work the same way once their telemetry is switched on (see [Telemetry setup](telemetry.md)).

## 1. Check everything is ready

Open Pitwall from the Quick Access Menu and choose **Pre-race checks**. It tells you whether:

- your wheel is connected and controllable
- force feedback is available to games
- telemetry is arriving from the game
- a shared-memory bridge is running (for sims that need one)
- the game you're running is known to work on SteamOS

## 2. Switch on telemetry in BeamNG

Options → Other → Protocols:

- **OutGauge**: on, IP `127.0.0.1`, port `4444`
- **MotionSim**: on, IP `127.0.0.1`, port `4445`

Pitwall's **Session** panel shows `📡 Telemetry: beamng` as soon as data arrives.

## 3. Set a start line

BeamNG doesn't report laps, so Pitwall needs to know where your lap starts. Drive to the start/finish point and press **Set start line here**. Each time you pass back through that point, a lap is recorded.

Sims that count laps themselves (Forza, DiRT Rally 2.0, Assetto Corsa, ACC, AMS2, rFactor 2, Le Mans Ultimate, RaceRoom) don't need this.

## 4. Open the phone dashboard

The Session panel shows an address like `http://192.168.1.20:8090`. Open it on a phone or tablet connected to the same Wi-Fi. You get:

- shift lights, gear, speed and RPM
- a live delta against your best lap (green: ahead, red: behind)
- current, last and best lap times
- throttle, brake and fuel bars
- coaching tips after each lap
- a track map with your position
- optional voice callouts (tap **Voice**) for lap times and the top tip

Add it to your home screen for a full-screen view.

## 5. Drive

From your second lap, Pitwall compares every braking zone with your best lap and tells you where the time went. See [Coaching](coaching.md).

## 6. Wheel and force feedback

- **Wheel settings & profiles**: change rotation, FFB strength and effects, and save a profile for the game you're running. It's applied automatically the next time that game starts.
- **Force feedback feel**: pick a starting preset, then tell Pitwall what feels wrong ("too light", "oscillates", "can't feel the road") and it makes a small, explained change you can undo. See [FFB tuning](ffb-tuning.md).

## 7. Full screen

**Open Pitwall full screen** gives the same tools with more room, plus your lap history.
