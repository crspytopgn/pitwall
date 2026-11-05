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

> **SteamOS note:** community kernel drivers (hid-fanatecff, hid-tmff2, new-lg4ff) aren't part of SteamOS and its system partition is read-only, so installing them takes extra work and may need redoing after SteamOS updates. MOZA and basic Logitech support are in the mainline kernel.

## MOZA

Pitwall talks to MOZA bases with the serial protocol reverse engineered by [Boxflat](https://github.com/Lawstorant/boxflat). Every command Pitwall sends is checked byte for byte against Boxflat's encoder in the test suite.

- **Natural inertia** runs from 100% to 500%, as in Pit House.
- **Set centre** stores the current wheel position as straight ahead. Hold the wheel straight first.
- **Rev lights**: switch on "Rev lights from telemetry" on the Wheel page. Ten LEDs fill from 60% to 97% of max RPM and flash at the shift point. Pitwall restores the wheel's previous LED mode when you stop driving.
- **Firmware updates** aren't supported. MOZA's update process hasn't been reverse engineered and a bad write can brick a base, so use Pit House on Windows for firmware.
- Close Boxflat or Pit House before using Pitwall; two programs talking to the base at once can confuse it.

## Profiles

Wheel settings can be saved per game and per car. With **Auto-apply per game** on:

- the game's profile is applied when it launches
- a **car profile** is applied whenever that car appears in telemetry, overriding the game profile (car names come from the sim, so this works in AC, ACC, AMS2, rFactor 2, LMU, RaceRoom, LFS and Forza, but not BeamNG)
- your **default** profile is applied when you quit FFB on/off is never stored in a profile, so a profile can't silently switch force feedback off.
