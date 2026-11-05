# FAQ

**Is this official?** No. Pitwall isn't affiliated with Valve, MOZA, any wheel maker or any sim developer.

**Does it work on Steam Deck / desktop Linux?** Yes, anywhere Decky Loader runs. It's designed for the Steam Machine on a TV, hence the phone dashboard.

**Is it a SimHub replacement?** It covers the parts most people use on SteamOS: dashboard, rev lights, lap analysis. It doesn't do bass shakers or custom dash designs.

**Can it update MOZA firmware?** No. The update process isn't reverse engineered and a bad write can brick a base. Use Pit House on Windows.

**Why doesn't iRacing / F1 25 / EA WRC work?** Their anti-cheat blocks Linux. No tool can change that; only the developers can.

**Does it slow my games down?** It's designed not to: idle polling is every two seconds, and telemetry parsing reads only the bytes it needs.

**What data leaves my Steam Machine?**
- Live compatibility ratings are fetched from ProtonDB, Valve and Are We Anti-Cheat Yet (cached for a day).
- The telemetry bridge is downloaded from GitHub when you ask for it.
- Lap summaries go to Anthropic only if you add an API key and open the debrief.
- The phone dashboard is served on your local network only. Don't expose port 8090 to the internet.

**Where's my data?** `~/homebrew/settings/Pitwall` (settings), `~/homebrew/data/Pitwall` (laps, caches), `~/.local/share/pitwall` (benchmark logs, bridge).
