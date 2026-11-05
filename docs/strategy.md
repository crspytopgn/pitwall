# Fuel and tyre strategy

Open **Fuel and tyres** in Pitwall, or look at the fuel and tyre tiles on the phone dashboard (the **Race** layout shows them largest).

## Fuel

- **Per lap**: the median of your last five clean laps. The lap you joined mid-way and any lap where fuel went up (a pit stop) are ignored.
- **Laps of fuel left**: what's in the tank divided by use per lap.
- **Race laps remaining** (or minutes remaining): set either one. With minutes, Pitwall converts using your median lap time.
- **Advice**: how much to add at your stop, including one lap of margin, and how many stops if the total is more than a full tank.

Sims that report litres (AC, ACC, AMS2, Project CARS 2, rFactor 2, Le Mans Ultimate, RaceRoom, DiRT Rally 2.0) show litres. BeamNG, Live for Speed and Forza report a fraction of the tank, so they show percent. F1 doesn't send fuel through the packets Pitwall reads.

## Tyres

- **Temperatures** for each corner: core temperature in AC/ACC, tyre temperature in AMS2, carcass temperature in rFactor 2/LMU, centre tread in RaceRoom, Forza's tyre temperature and F1's tyre surface temperature.
- **Window**: RaceRoom reports each tyre's cold, ideal and hot temperature, so Pitwall colours them blue, green or red. Other sims don't publish a window.
- **Balance**: if the fronts run much hotter than the rears (or the reverse) Pitwall says so, with the usual cause.
- **Wear**: change per lap for each tyre, the worst tyre, and roughly how many laps each 10% takes. Sims count wear in different directions, so Pitwall only uses the change, never the absolute value.

Shared-memory field layouts come from simapi's C headers and are checked by C-written test fixtures (`tools/shm_fixtures.c`).
