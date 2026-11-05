# Performance

For sim racing, frame **consistency** matters more than average FPS: a stutter mid-corner costs more than a slightly lower frame rate. Pitwall judges performance on 1% lows and stutters per minute.

## Benchmark a game

1. Pitwall → **Performance**. Set **Target FPS** to your TV's refresh rate (usually 60 or 120).
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
