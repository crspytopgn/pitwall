# Credits

Pitwall stands on a lot of other people's work. This page lists everything it uses, learns from or links to, and the licence each one comes under. If something is missing or credited wrongly, please [open an issue](https://github.com/crspytopgn/pitwall/issues) and it'll be fixed quickly.

Pitwall is unofficial. It isn't affiliated with or endorsed by Valve, MOZA Racing, Logitech, Fanatec, Thrustmaster, any sim developer, or any of the projects below.

## Protocols and data layouts

| Project | Author | What Pitwall uses it for | Licence |
|---|---|---|---|
| [Boxflat](https://github.com/Lawstorant/boxflat) | Tomasz Pakuła (Lawstorant) | MOZA serial protocol: frame format, command IDs and value ranges. Pitwall's own implementation is tested byte for byte against Boxflat's command tables | GPL-3.0 |
| [simapi](https://github.com/Spacefreak18/simapi) | Spacefreak18 | C headers for the AC/ACC, AMS2/PC2, rFactor 2, LMU, RaceRoom and SCS shared-memory layouts; Pitwall's offsets and test fixtures are generated from them | LGPL-3.0 |
| [simshmbridge](https://github.com/Spacefreak18/simshmbridge) | Spacefreak18 | Reference for how shared memory is exposed to Linux under Proton | GPL-3.0 |
| [new-lg4ff](https://github.com/berarma/new-lg4ff) | Bernat Arlandis (berarma) | Logitech sysfs controls (range, gain, autocentre, effects, LEDs) | GPL-2.0 |
| [hid-fanatecff](https://github.com/gotzl/hid-fanatecff) | gotzl | Fanatec sysfs controls and tuning menu | GPL-2.0 |
| [hid-tmff2](https://github.com/Kimplul/hid-tmff2) | Kimplul | Thrustmaster sysfs controls | GPL-3.0 |
| [universal-pidff](https://github.com/JacKeTUs/universal-pidff) | JacKeTUs and contributors | Direct-drive force feedback driver (now `hid-universal-pidff` in mainline Linux); kernel version checks | GPL-2.0 |
| [BeamNG protocols](https://documentation.beamng.com/modding/protocols/) | BeamNG GmbH | OutGauge and MotionSim packet formats | Documentation |
| Forza Data Out | Turn 10 / Playground Games | UDP telemetry format | Documentation |
| Codemasters and EA F1 UDP specifications | Codemasters / EA | DiRT "extradata 3" format; F1 2021-2023 packet formats | Documentation |
| [SCS SDK plugin](https://github.com/RenCloud/scs-sdk-plugin) | RenCloud | ETS2/ATS telemetry on native Linux | MIT |
| [rF2SharedMemoryMapPlugin](https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin) | The Iron Wolf | rFactor 2 shared memory | GPL-3.0 |

## Tools Pitwall installs or points you to

| Project | Author | Licence |
|---|---|---|
| [winecarte](https://github.com/srounce/winecarte) | srounce | GPL-2.0 |
| [linux-simracing-utils](https://github.com/srounce/linux-simracing-utils) | srounce | GPL-2.0 |
| [Datalink](https://github.com/LukasLichten/Datalink) | Lukas Lichten and contributors | MIT |
| [Monocoque](https://github.com/Spacefreak18/monocoque) | Spacefreak18 | GPL-3.0 |

Pitwall downloads winecarte from its official GitHub releases; it doesn't redistribute it.

### Force feedback drivers Pitwall can build on SteamOS

When you press **Install**, Pitwall downloads the source from the project's own repository and builds it on your machine; it doesn't ship or modify these drivers.

| Project | Author | Licence |
|---|---|---|
| [universal-pidff](https://github.com/JacKeTUs/universal-pidff) | JacKeTUs and contributors | GPL-2.0 |
| [new-lg4ff](https://github.com/berarma/new-lg4ff) | Bernat Arlandis (berarma) | GPL-2.0 |
| [hid-fanatecff](https://github.com/gotzl/hid-fanatecff) | gotzl | GPL-2.0 |
| [hid-tmff2](https://github.com/Kimplul/hid-tmff2) (with hid-tminit) | Kimplul | GPL-3.0 |
| [simagic-ff](https://github.com/JacKeTUs/simagic-ff) | JacKeTUs | GPL-2.0 |

## Compatibility and community data

| Source | Used for | Licence or terms |
|---|---|---|
| [ProtonDB](https://www.protondb.com) | Live community ratings | ProtonDB terms; read through its public summaries API, cached for a day |
| Valve's Steam Deck compatibility ratings | Live Deck/SteamOS ratings | Steam store data |
| [Are We Anti-Cheat Yet](https://areweanticheatyet.com) | Anti-cheat status | MIT |
| [linux-steering-wheels](https://github.com/JacKeTUs/linux-steering-wheels) | Wheel support table (`data/wheels.json`, rebuilt by `scripts/sync_wheels.py`), and the background for Pitwall's wheel detection fixes | Community project by JacKeTUs and contributors; Pitwall's notes and fixes are its own wording and code |
| [awesome-linux-simracing](https://github.com/LukasLichten/awesome-linux-simracing) | Toolbox list (`data/tools.json`, `docs/toolbox.md`), adapted | CC BY-SA 4.0; the adapted list is shared under the same licence |
| [GamingOnLinux](https://www.gamingonlinux.com), [Box This Lap](https://boxthislap.org), [Sim Racing on Linux](https://simracingonlinux.com) and the game developers' own posts | Notes and known issues in the game guide; every note links to its source | Linked articles |

## Libraries bundled in the plugin

| Library | Author | Licence |
|---|---|---|
| [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader), `@decky/api`, `@decky/ui` | Steam Deck Homebrew | LGPL-2.1 (libraries) |
| `@decky/rollup` | Steam Deck Homebrew | BSD-3-Clause |
| [decky-plugin-template](https://github.com/SteamDeckHomebrew/decky-plugin-template) (build setup, `decky.pyi`) | Steam Deck Homebrew | BSD-3-Clause, notice below |
| [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | Kazuhiko Arase | MIT |
| [react-icons](https://github.com/react-icons/react-icons) | react-icons contributors | MIT |
| Icons from [game-icons.net](https://game-icons.net) (via react-icons) | Lorc, Delapouite and contributors | CC BY 3.0 |

The phone dashboard and website use no third-party code.

## Branding and images

- Typeface: [Inter](https://rsms.me/inter/) by Rasmus Andersson, SIL Open Font License 1.1. The wordmark is drawn from Inter's letterforms.
- The Monza outline in the dashboard screenshot comes from [f1-circuits](https://github.com/bacinger/f1-circuits) by Tomislav Bacinger (MIT). In the plugin itself, track maps are drawn from your own driving, not from any track data.

## Notices

decky-plugin-template:

```
BSD 3-Clause License
Original Copyright (c) 2022-2024, Steam Deck Homebrew
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

Product and game names are trademarks of their owners and are used only to say what Pitwall works with.
