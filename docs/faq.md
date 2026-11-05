# FAQ

**Is this official?** No. Pitwall isn't affiliated with Valve, MOZA, any wheel maker or any sim developer.

**Does it work on Steam Deck / desktop Linux?** Yes, anywhere Decky Loader runs. It's designed for the Steam Machine on a TV, hence the phone dashboard.

**Is it a SimHub replacement?** It covers the parts most people use on SteamOS: a phone dashboard with several layouts, rev lights and lap analysis. It doesn't do bass shakers or custom dash designs. If you need SimHub or CrewChief themselves, [linux-simracing-utils](https://github.com/srounce/linux-simracing-utils) installs both on Linux; see the [toolbox](toolbox.md).

**Can it update MOZA firmware?** No. The update process isn't reverse engineered and a bad write can brick a base. Use Pit House on Windows.

**Why doesn't iRacing / F1 25 / EA WRC work?** Their anti-cheat isn't enabled for Linux. F1 24, F1 25 and EA WRC won't start; iRacing runs offline in Test Drive only, and Pitwall doesn't read iRacing telemetry. No tool can change that; only the developers can.

**Does it slow my games down?** It's designed not to: idle polling is every two seconds, and telemetry parsing reads only the bytes it needs.

**What data leaves my Steam Machine?**
- Live compatibility ratings are fetched from ProtonDB, Valve and Are We Anti-Cheat Yet (cached for a day).
- The telemetry bridge is downloaded from GitHub when you ask for it.
- Lap summaries go to Anthropic only if you add an API key and open the debrief.
- The phone dashboard is served on your local network only. Don't expose port 8090 to the internet.
- Diagnostics are only saved locally; you choose whether to download and attach them to an issue.
- Installing a force feedback driver downloads it from the project's GitHub repository and build tools from SteamOS's repository, only when you press **Install**.

**Does Pitwall change system files?** Only when you ask it to: the udev rule for wheel detection, and a force feedback driver if you press **Install**. Both are listed in [Wheels](wheels.md) and can be removed from the same page.

**Where's my data?** `~/homebrew/settings/Pitwall` (settings), `~/homebrew/data/Pitwall` (laps, caches), `~/.local/share/pitwall` (benchmark logs, bridge).
