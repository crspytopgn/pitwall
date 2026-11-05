# Day one: Steam Machine to first lap

A checklist for setting up a new Steam Machine (or Steam Deck) for sim racing with Pitwall. Allow about 30 minutes plus game downloads.

## Before it arrives

- [ ] Decide which sims you'll play first and check them in the [compatibility guide](compatibility.md). BeamNG.drive, DiRT Rally 2.0, Forza Horizon and F1 23 are the easiest starts.
- [ ] If your MOZA base needs a firmware update, do it now on a Windows PC with Pit House. Pitwall can't update firmware.
- [ ] Have a USB hub or enough ports: wheel base, pedals (if separate), and a keyboard helps for Desktop Mode.

## 1. Update SteamOS

Settings → System → check for updates. Recent SteamOS versions include the Linux kernel driver MOZA bases need for force feedback (`hid-universal-pidff`, Linux 6.15 and newer).

## 2. Install Decky Loader (5 minutes)

1. Steam button → Power → **Switch to Desktop**.
2. Open a browser, go to [decky.xyz](https://decky.xyz) and download the installer.
3. Run it, choose the recommended install, then use the **Return to Gaming Mode** icon on the desktop.

## 3. Install Pitwall (2 minutes)

1. Download `Pitwall-x.y.z.zip` from the [Releases page](../../../releases) (in Desktop Mode, or put it on a USB stick).
2. Gaming Mode → `...` → plug icon → cog → **Developer mode** on → **Install Plugin from ZIP File**.

## 4. Plug in the wheel and run auto setup (1 minute)

Connect the wheel base and pedals, then open Pitwall. The first time, it offers **Run auto setup**. It:

- recognises your device and wheel (for MOZA, the exact base: R3, R5, R9…)
- applies MOZA's own recommended settings for that base
- sets a 60 FPS performance target (raise it on the Performance page if your TV is 120 Hz)
- switches on telemetry for installed games that support automatic setup

## 5. Install your sims

- **BeamNG.drive** runs natively. Options → Other → Protocols: enable OutGauge (`127.0.0.1:4444`) and MotionSim (`127.0.0.1:4445`).
- **DiRT Rally 2.0**: launch once, then Game guide → DiRT Rally 2.0 → **Do this for me**.
- **Forza Horizon**: Settings → HUD and Gameplay → Data Out on, `127.0.0.1`, port `5300`.
- **F1 23**: Telemetry Settings → UDP on, `127.0.0.1`, port `20777`, format 2023.
- **Assetto Corsa / ACC / AMS2 / rFactor 2 / LMU**: Game guide → the game → **Set up telemetry bridge**, then restart the game.

Each game's page in Pitwall has the full steps and known issues.

## 6. Pre-race checks

Launch a game, open Pitwall → **Pre-race checks**. Everything should be green: wheel, force feedback, telemetry, and the bridge if the game needs one.

## 7. Phone dashboard

Session → **Show QR code**, scan it with your phone (same Wi-Fi), and add it to your home screen. Put the phone on a stand near the wheel.

## 8. First laps

Drive a few laps. In BeamNG, set a start line first. From the second lap, Pitwall shows where you lose time. If the force feedback doesn't feel right, use **Force feedback feel** and change one thing at a time.

## If something doesn't work

Pitwall → **Send diagnostics** creates a bundle you can attach to a GitHub issue in two scans. See [Troubleshooting](troubleshooting.md).
