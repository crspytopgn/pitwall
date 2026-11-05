# Fuel and tyre strategy

Open **Fuel & tyre strategy** in Pitwall, or glance at the fuel and tyre strip on the phone dashboard.

## Fuel

- **Per lap**: the median of your last five clean laps. The lap you joined mid-way and any lap where fuel went up (a pit stop) are ignored.
- **Laps of fuel left**: what's in the tank divided by use per lap.
- **Race remaining**: set either laps or minutes left. With minutes, Pitwall converts using your median lap time.
- **Advice**: how much to add at your stop, including one lap of margin, and how many stops if the total is more than a full tank.

Sims that report litres (AC, ACC, AMS2, Project CARS 2, rFactor 2, Le Mans Ultimate, RaceRoom, DiRT Rally 2.0) show litres. The others (BeamNG, Forza) show percent of the tank.

## Tyres

- **Temperatures** for each corner: core temperature in AC/ACC, tyre temperature in AMS2, carcass temperature in rFactor 2/LMU, centre tread in RaceRoom, and Forza's tyre temperature.
- **Window**: RaceRoom reports each tyre's cold, ideal and hot temperature, so Pitwall colours them blue, green or red. Other sims don't publish a window.
- **Balance**: if the fronts run much hotter than the rears (or the reverse) Pitwall says so, with the usual cause.
- **Wear**: change per lap for each tyre, the worst tyre, and roughly how many laps each 10% takes. Sims count wear in different directions, so Pitwall only uses the change, never the absolute value.

All field layouts come from simapi's C headers and are checked by C-written test fixtures (`tools/shm_fixtures.c`).
