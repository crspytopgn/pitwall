# Performance

For sim racing, frame **consistency** matters more than average FPS: a stutter mid-corner costs more than a slightly lower frame rate. Pitwall judges performance on 1% lows and stutters per minute.

## Automatic graphics tuning

Pitwall → **Graphics**. With **Tune every game automatically** on (the default), the first time you start a racing game Pitwall knows, it:

1. Picks a starting level, **Max**, **High**, **Balanced** or **Performance**, for the game on your device. The Steam Machine starts lighter games like Assetto Corsa on Max and heavy Unreal Engine games like ACC on Balanced; a Steam Deck starts lower.
2. Adds a frame cap at your target FPS and quiet MangoHud measuring to the game's launch options (your other options are kept). This takes effect from the game's next start. There's no overlay.
3. **Measures only while you're racing.** The game's own telemetry tells Pitwall when you're on track, not paused, and moving; menus, loading screens, replays, the garage and the first seconds after leaving the pits don't count. A game without telemetry has its first two minutes skipped instead. Pitwall needs at least two minutes of driving before it judges a session.
4. When you quit, moves the level: one down if it was below target or had bad 1% lows, one up if it held the target with the GPU under 70% busy. It never climbs back to a level that was already too slow on your machine, so it settles instead of flip-flopping. Stutters with a good average are usually shaders compiling the first time on a track, so those don't lower anything.
5. **Changes the game's own settings** for the new level, then and there (games save their settings when they close, so Pitwall writes them after).

### Which games Pitwall changes itself

Pitwall recognises the settings files whole engines use, and looks for them where each game keeps its files, however you run it on Linux: the Windows version under Proton, the native Linux version, and Steam installed as a Flatpak on desktop Linux:

| Format | Games | What changes |
|---|---|---|
| BeamNG.drive `settings.json` | BeamNG.drive | Mesh, shadow, terrain, lighting and texture quality, dynamic reflections (the heaviest setting), grass density, anisotropic filtering, motion blur, depth of field, render resolution; switches BeamNG to its Custom preset so the settings stick |
| Assetto Corsa `video.ini` | Assetto Corsa | Anti-aliasing, anisotropic filtering, shadows, mirrors, reflections, motion blur, depth of field, render resolution |
| Unreal Engine `GameUserSettings.ini` | Unreal Engine games such as EA SPORTS WRC and Assetto Corsa Rally | The engine's quality levels (view distance, anti-aliasing, shadows, lighting, reflections, post-processing, effects, foliage, shading, textures) and render scale |
| Codemasters `hardware_settings_config.xml` | F1 2021 to F1 25, DiRT Rally 2.0 | Render resolution; ray tracing off below Max |
| Madness `graphicsconfigdx11.xml` | Automobilista 2, Project CARS 2 | Car, track, shadow, reflection and effects detail, motion blur, supersampling, render resolution |
| SCS `config.cfg` | Euro Truck Simulator 2, American Truck Simulator | Render scale, sun shadows, mirror distance, ambient occlusion, depth of field |

For every format: only settings already in the file are changed, nothing is added; the file is backed up once and **Stop tuning** puts the original back; render resolution is only ever lowered, never raised past yours. Where the change is relative (BeamNG, Madness and SCS files), **Max is the settings you chose in the game** and each level below turns detail down from there. If you change a setting yourself in the game, Pitwall notices and takes your new settings as the starting point.

A game only gets its settings file the first time it runs, so Pitwall can change it from the second session on.

**Other games** (ACC, AC EVO, Le Mans Ultimate, rFactor 2, RaceRoom, Forza, iRacing and others): their settings formats aren't documented, so Pitwall tells you which of the game's presets matches the level, for example ACC's Epic, High, Mid or Low. The frame cap and measuring still work, so it tells you when to change it. Some Unreal Engine games, ACC possibly among them, apply their own menu settings over the engine file; there the preset advice is what counts.

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
