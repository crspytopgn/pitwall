# Performance

For sim racing, frame **consistency** matters more than average FPS: a stutter mid-corner costs more than a slightly lower frame rate. Pitwall judges performance on 1% lows and stutters per minute.

## Automatic graphics tuning

Pitwall → **Graphics**. With **Tune every game automatically** on (the default), the first time you start a racing game Pitwall knows, it:

1. Picks a starting level, **Max**, **High**, **Balanced** or **Performance**, for the game on your device. The Steam Machine starts lighter games like Assetto Corsa on Max and heavy Unreal Engine games like ACC on Balanced; a Steam Deck starts lower.
2. Adds a frame cap at your target FPS and quiet MangoHud measuring to the game's launch options (your other options are kept). This takes effect from the game's next start. There's no overlay; measuring starts two minutes in, past menus and loading, and lasts three minutes.
3. When you quit, reads the measurement and moves the level: one down if it was below target or had bad 1% lows, one up if it held the target with the GPU under 70% busy. It never climbs back to a level that was already too slow on your machine, so it settles instead of flip-flopping. Stutters with a good average are usually shaders compiling the first time on a track, so those don't lower anything.

What changes at each level depends on the game:

- **Assetto Corsa:** Pitwall changes the settings itself in `video.ini` (anti-aliasing, anisotropic filtering, shadows, mirrors, reflections, motion blur, depth of field, and the render resolution on Balanced and Performance; the resolution is only ever lowered). It only touches settings already in the file, keeps a backup, and **Stop tuning** puts the original back.
- **Other games:** Pitwall tells you which of the game's own presets matches the level (for example ACC's Epic, High, Mid or Low), and the frame cap and measuring still work, so it tells you when to change it.

You can pick a level yourself at any time; Pitwall then starts learning again from there. Change **Target FPS** on the same page.

## Benchmark a game

1. Pitwall → **Performance check**. Set **Target FPS** to your TV's refresh rate (usually 60 or 120).
2. Launch the game (or open its page) and press **Arm 90 s benchmark**. Pitwall adds MangoHud logging to the game's launch options, keeping your existing options.
3. Restart the game and drive normally for 90 seconds.
4. Press **Analyse latest benchmark**.
5. Press **Restore launch options** when you're done.

You get average FPS, 1% low, stutters per minute and a verdict:

- **Smooth**: holding the target with headroom. Try raising one setting.
- **Stuttering**: average is fine but pacing isn't. Usually shader compilation, streaming or CPU spikes: lower AI count, mirrors, reflections; run the track twice.
- **Below target**: lower resolution scale/upscaling, then shadows and reflections, or cap at half refresh rate for steadier pacing.

Game-specific hints are added where known (for example BeamNG: dynamic reflections, shadows and traffic count).

## Steam Machine tips

- Use the Quick Access Menu's **Performance** tab to set a frame limit matching your target; a steady 60 beats a fluctuating 75.
- The first laps on a new track often stutter while shaders compile. Benchmark the second run.
- Pitwall itself is light: idle, it checks for telemetry every two seconds; while driving, it parses packets as they arrive and streams to the phone dashboard at 15 updates a second.
