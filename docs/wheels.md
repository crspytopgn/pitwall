# Wheels

Pitwall has two separate jobs with wheels:

1. **Force feedback in games** comes from the Linux kernel driver. Pitwall doesn't provide it, but **Pre-race checks** tells you whether it's available.
2. **Wheel settings** (rotation, strength, effects, profiles) are what Pitwall controls.

## Support at a glance

| Brand | FFB driver | Pitwall controls | Rev lights |
|---|---|---|---|
| **MOZA** (R3, R5, R9, R12, R16, R21 and others Boxflat supports) | `hid-universal-pidff` (Linux 6.15+, also 6.12.24+, 6.13.12+, 6.14.3+) | Rotation, game FFB strength, torque output, road sensitivity, damper, friction, natural inertia, spring, max wheel speed, speed-dependent damping, FFB on/off, set centre | Yes, from telemetry |
| **Logitech** (G29, G920, G923, older) | `hid-logitech` / `hid-logitech-hidpp` (mainline; G920 and G923 Xbox since 6.3) | Rotation; with [new-lg4ff](https://github.com/berarma/new-lg4ff) also gain, autocenter, spring, damper, friction | G27/G29/G923 where the driver exposes the LEDs |
| **Fanatec** | [hid-fanatecff](https://github.com/gotzl/hid-fanatecff) (community) | Rotation and the base's tuning menu: FF, FOR, SPR, DPR, NDP, NFR, INT | – |
| **Thrustmaster** | [hid-tmff2](https://github.com/Kimplul/hid-tmff2) (community) | Rotation, gain, spring, damper, friction | – |
| Simagic, Cammus, Simucube | varies | Detected in checks only | – |

Pre-race checks identify your wheel model from its USB ID and show its tested support level and the driver it needs (full list: [wheel support table](wheel-support.md)).

Pitwall only offers settings whose driver files actually exist, so the same plugin works with mainline and community drivers.

> **SteamOS note:** community kernel drivers (hid-fanatecff, hid-tmff2, new-lg4ff, simagic-ff) aren't part of SteamOS. Pitwall can install them for you (below), and they need reinstalling after SteamOS updates. MOZA and basic Logitech support are in the mainline kernel.

## Getting force feedback working

Open Pitwall → **Wheel**. The **Force feedback** section shows, for each wheel base:

- whether Linux gives it force feedback, and which effects its driver supports (constant force, spring, damper, friction and so on). Sims mostly need constant force; the others add feel.
- **Test force feedback**: a gentle pull to the left, then the right, through Linux's force feedback interface, the same one games use through Proton. If the wheel moves, the driver and wheel are fine and any remaining problem is in the game's settings or Proton. The strength is adjustable up to 40% and ramps in softly, so it's safe on strong direct drive bases.
- **Install**, when your wheel needs a driver that SteamOS doesn't have.

### Installing a driver on SteamOS

| Driver | For | Project |
|---|---|---|
| hid-universal-pidff | MOZA, Cammus, PXN, VRS, Asetek, Turtle Beach, FFBeast on kernels older than 6.15 (or the 6.12.24+, 6.13.12+, 6.14.3+ updates) | [JacKeTUs/universal-pidff](https://github.com/JacKeTUs/universal-pidff) |
| new-lg4ff | Logitech G25, G27, G29, G923 (PlayStation), DFGT, DFP, MOMO: adds the effects the stock driver lacks, and is required for the G923 PlayStation | [berarma/new-lg4ff](https://github.com/berarma/new-lg4ff) |
| hid-fanatecff | Fanatec bases | [gotzl/hid-fanatecff](https://github.com/gotzl/hid-fanatecff) |
| hid-tmff2 | Thrustmaster T300RS, T248, TX, TS-XW, TS-PC | [Kimplul/hid-tmff2](https://github.com/Kimplul/hid-tmff2) |
| simagic-ff | Simagic Alpha family and EVO on firmware v159 or later | [JacKeTUs/simagic-ff](https://github.com/JacKeTUs/simagic-ff) |

Pitwall only offers the driver your wheel needs. Pressing **Install** does what each project documents for Arch-based systems, for your exact kernel:

1. lifts SteamOS's read-only flag
2. installs the build tools and the headers for your running kernel from SteamOS's own repository (`pacman`)
3. downloads the driver's source from its official GitHub repository
4. builds it and installs it in `/usr/lib/modules/<kernel>/updates/pitwall`, plus the project's udev rules where it has them (Fanatec, Thrustmaster)
5. puts the read-only flag back, loads the driver and reloads udev

It needs internet and takes a few minutes; the log is shown as it runs. Unplug the wheel and plug it back in afterwards, then use **Test force feedback**.

A SteamOS update replaces the system and kernel, which removes the driver. Pitwall remembers what it installed and, after an update, tells you and offers **Reinstall**. When the driver's project publishes a newer version, **More → Updates** says so and offers **Update**. **Remove** takes the driver out again and goes back to the kernel's own.

This changes system files, so it's always your choice: Pitwall never installs a driver without you pressing the button. On other distributions, install the driver with your package manager or from the project's instructions.

## If a game doesn't see your wheel

If **Test force feedback** works but a game shows no wheel or no force feedback, it's a detection problem rather than a driver one. Pre-race checks tell you whether Linux recognises your wheel as a game controller, which Steam and Proton need (Linux calls every wheel, pedal set and shifter a "joystick"; it's just the name of the category). If it doesn't, **Wheel → Fix wheel and pedal detection** adds a udev rule for your wheel and reloads udev (unplug and replug the wheel afterwards). For a single stubborn game, its page in the **Game guide** has **Add wheel ID to launch options**, which tells Steam's input layer to treat your wheel as a wheel in that game. More fixes are in the [wheel support table](wheel-support.md#if-a-game-doesnt-see-your-wheel).

## MOZA

Pitwall talks to MOZA bases with the serial protocol reverse engineered by [Boxflat](https://github.com/Lawstorant/boxflat). Every command Pitwall sends is checked byte for byte against Boxflat's encoder in the test suite.

- **Natural inertia** runs from 100% to 500%, as in Pit House.
- **Set centre** stores the current wheel position as straight ahead. Hold the wheel straight first.
- **Rev lights**: switch on "Rev lights from telemetry" on the Wheel page. Ten LEDs fill from 60% to 97% of max RPM and flash at the shift point. Pitwall restores the wheel's previous LED mode when you stop driving.
- **Firmware updates** aren't supported. MOZA's update process hasn't been reverse engineered and a bad write can brick a base, so use Pit House on Windows for firmware.
- Close Boxflat or Pit House before using Pitwall; two programs talking to the base at once can confuse it.

## Profiles

Wheel settings can be saved per game and per car. With **Apply profiles automatically** on:

- the game's profile is applied when it launches
- a **car profile** is applied whenever that car appears in telemetry, overriding the game profile (car names come from the sim, so this works in AC, ACC, AMS2, rFactor 2, LMU, RaceRoom, LFS and Forza, but not BeamNG)
- your **default** profile is applied when you quit

FFB on/off is never stored in a profile, so a profile can't silently switch force feedback off.
