# Coaching and the engineer

## Laps

- Sims that count laps are trusted directly (with their official lap time).
- For BeamNG you set a start line; a lap ends at the closest point to it each time you pass, so the start doesn't drift.
- Live for Speed's OutGauge feed has no car position or lap data, so it gets the live dashboard but no lap timing or coaching.
- Laps shorter than 15 seconds or with too little data are ignored. If the game pauses (no data for over a second), the paused time isn't counted.
- Laps are stored per sim, track and car, so your best lap is always a like-for-like reference.

## Live delta

While driving, Pitwall compares your current lap time with your best lap's time at the same distance. Green means ahead, red behind.

## Braking-zone comparison

After each lap, Pitwall finds every braking zone on your best lap and compares the same zone on the new lap:

- where you started braking (metres earlier or later)
- your minimum (apex) speed
- the time gained or lost from 50 m before the braking point to 50 m after the zone

The three biggest losses become tips, such as *"Corner 3 (1240 m): lost 0.31s; braked 18 m earlier, 6 km/h slower at the apex."*

## Engineer debrief

The debrief summarises the session: lap count, best and average, consistency, and the corners that cost most on average.

If you add an Anthropic API key, the same summary (the sim, track and car names, lap times and corner numbers, nothing else) is sent to Claude, which writes a short spoken-style debrief. Without a key, everything works offline.
