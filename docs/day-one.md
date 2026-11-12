# Day one: Steam Machine to first lap

A checklist for setting up a new Steam Machine (or Steam Deck) for sim racing with Pitwall. Allow about 30 minutes plus game downloads.

## Before it arrives

- [ ] Decide which sims you'll play first and check them in the [compatibility guide](compatibility.md) or on the [website](https://crspytopgn.github.io/pitwall/). BeamNG.drive, DiRT Rally 2.0, Forza Horizon and F1 23 are the easiest starts.
- [ ] If your MOZA base needs a firmware update, do it now on a Windows PC with Pit House. Pitwall can't update firmware.
- [ ] Have a USB hub or enough ports: wheel base, pedals (if separate), and a keyboard helps for Desktop Mode.

## 1. Update SteamOS

Settings → System → check for updates. MOZA bases need the `hid-universal-pidff` kernel driver for force feedback, which is in Linux 6.15 or newer, or the 6.12.24+, 6.13.12+ and 6.14.3+ updates. Pitwall's Pre-race checks look for the driver itself and tell you if it's missing. If SteamOS doesn't have it yet, Pitwall can install it in step 4.

> **Not using Decky?** Skip steps 2 and 3: in Desktop Mode, install [standalone Pitwall](standalone.md) with `./install.sh`, then open Pitwall from the app menu and carry on at step 4. The rest of this guide is the same, except that Pitwall's pages are in its web app rather than the Quick Access Menu.

## 2. Install Decky Loader (5 minutes)

1. Steam button → Power → **Switch to Desktop**.
2. Open a browser, go to [decky.xyz](https://decky.xyz) and download the installer.
3. Run it, choose the recommended install, then use the **Return to Gaming Mode** icon on the desktop.

## 3. Install Pitwall (2 minutes)

1. Download `Pitwall-0.1.0.zip` from the [latest release](https://github.com/crspytopgn/pitwall/releases/latest) (in Desktop Mode, or put it on a USB stick).
2. Gaming Mode → `...` → plug icon → cog → **Developer mode** on → **Install Plugin from ZIP File**.

## 4. Plug in the wheel and run auto setup (1 minute)

Connect the wheel base and pedals, then open Pitwall. The first time, it offers **Run auto setup**. It:

- recognises your device and wheel (for MOZA, the exact base: R3, R5, R9…)
- applies MOZA's own recommended settings for that base
- sets a 60 FPS performance target (raise it on the Performance page if your TV is 120 Hz)
- switches on telemetry for installed sims where it can do so automatically

Then open **Wheel** and look at **Force feedback**. If it offers to install a driver, press **Install** (a few minutes, needs internet), then unplug and replug the wheel. Press **Test force feedback**: the wheel should pull gently left, then right.

## 5. Install your sims

Install each sim from Steam, launch it once, then open its page in Pitwall's **Game guide** and follow the setup steps. Where possible Pitwall does the work for you:

- **Do this for me** switches on telemetry in sims that use a config file.
- **Set up telemetry bridge** installs the bridge Proton sims need for shared memory, keeping your launch options.
- Sims with an in-game telemetry menu show the exact settings to enter.

Each game's page also lists in-game force feedback settings and known issues.

## 6. Pre-race checks

Launch a game, open Pitwall → **Pre-race checks**. Everything should show **OK**: wheel, force feedback, telemetry, and the bridge if the game needs one. Anything marked **FIX** says what to do.

## 7. Phone dashboard

Session → **Show QR code**, scan it with your phone (same Wi-Fi), and add it to your home screen. Put the phone on a stand near the wheel.

## 8. First laps

Drive a few laps. If the Session panel asks for a start line, set one first. From the second lap, Pitwall shows where you lose time. If the force feedback doesn't feel right, use **Force feedback feel** and change one thing at a time.

## If something doesn't work

Pitwall → **Send diagnostics** creates a bundle you can attach to a GitHub issue in two scans. See [Troubleshooting](troubleshooting.md).
