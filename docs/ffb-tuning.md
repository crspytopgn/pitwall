# Force feedback tuning

## What makes FFB feel realistic

Sims with full tyre physics (BeamNG, Assetto Corsa, ACC, AMS2, rFactor 2) already calculate the steering forces. Effects the base adds on top (spring, damper, friction, inertia) are filters: they can add weight, but they also hide detail. Three rules cover most problems:

1. **Spring at 0%.** The sim handles centring ([MOZA](https://eu.mozaracing.com/blogs/blog/moza-settings-guide-for-assetto-corsa)).
2. **Avoid clipping.** If big and small forces feel the same, the signal is hitting the base's maximum. Lower the in-game gain until they feel different again.
3. **Change one thing at a time** and drive a few corners before the next change.

## Presets (MOZA)

| Preset | What it does | Source |
|---|---|---|
| Pure (game physics only) | No added spring, damper or friction. Most detail, lightest feel | Built on MOZA's spring-at-0 reasoning |
| MOZA's R3/R5 recommendation | MOZA's published starting point for R3/R5 (written for Assetto Corsa): 900°, road 8, FFB 100%, max speed 120%, damper 60%, natural inertia 140%, friction 25% | [MOZA](https://eu.mozaracing.com/blogs/blog/moza-settings-guide-for-assetto-corsa) |
| Weighted, no damping | Natural inertia and friction at maximum, damper 0, road 4 | Settings a MOZA Creator Program driver shared for an R5, [summarised here](https://simracingcockpit.gg/moza-ffb-settings-for-iracing-r5-r9-r12-r16-and-r21/) |

## The feel tuner

Tell Pitwall what feels wrong. It makes a small change, explains it, and lets you undo it.

| You feel | Pitwall changes | Why |
|---|---|---|
| Light or vague | Natural inertia +50, friction +5 | Adds simulated mass and drag ([source](https://simracingcockpit.gg/f1-24-moza-settings/)) |
| Too heavy in slow corners | FFB strength −10, friction −5 | Less overall force and drag |
| Oscillates on straights | Damper +10, speed damping +10, max wheel speed −20 | MOZA's fix for high-speed oscillation ([source](https://eu.mozaracing.com/blogs/blog/moza-settings-guide-for-assetto-corsa)) |
| Can't feel the road | Road sensitivity +1, damper −10 | More surface detail; damper smothers it ([source](https://simracingsetup.com/f1-23/f1-23-best-moza-wheel-settings/)) |
| Too much rattle | Road sensitivity −1 (and a BeamNG smoothing tip) | ([BeamNG](https://docs.beamng.com/support/hardware/steering_wheel_setup/)) |
| Flat, same in every corner | FFB strength −10, plus "lower in-game gain" | Leaves headroom so peaks aren't clipped |

## In-game settings

The Game guide shows in-game FFB steps for each sim where good sources exist (BeamNG, Assetto Corsa, ACC). The full list is in the [compatibility guide](compatibility.md).
