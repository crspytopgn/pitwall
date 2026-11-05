# Contributing to Pitwall

Thanks for helping. The most valuable contributions right now are **real-hardware reports**: which sims, wheels and settings work on your Steam Machine, Steam Deck or Linux PC.

## Reporting

- **Bug:** [bug report](../../issues/new?template=bug_report.yml) with the Decky log from `~/homebrew/logs/Pitwall/`.
- **Game status changed / new known issue:** [game report](../../issues/new?template=game_report.yml) with a link to the source.
- **Wheel support:** [wheel report](../../issues/new?template=wheel_support.yml).

## Building

```bash
pnpm install
pnpm run build                              # frontend → dist/index.js
python3 -m unittest discover -s tests       # backend tests (stdlib only)
./scripts/package.sh                        # → out/Pitwall-x.y.z.zip
```

For the MOZA protocol cross-check, clone [Boxflat](https://github.com/Lawstorant/boxflat) and set `BOXFLAT_DIR` (needs PyYAML).

## Ground rules

- **No third-party Python packages.** Decky runs plugins on its bundled Python.
- **Every claim needs a source.** Entries in `py_modules/pitwall/data/games.json` and FFB presets must link where they come from. Prefer developer documentation, then Valve, ProtonDB, Are We Anti-Cheat Yet and GamingOnLinux.
- **Regenerate the docs** after editing `games.json`: `python3 scripts/gen_docs.py`. CI fails if `docs/compatibility.md` is stale.
- **Keep it light.** Pitwall runs alongside games on modest hardware. No busy loops; read only the bytes you need.
- **Never write to hardware you haven't verified.** New wheel commands should be checked against an existing open-source implementation, with a test.

## Adding a UDP sim

1. Add a parser to `py_modules/pitwall/telemetry/parsers.py` returning a `Frame` (positions as horizontal x, horizontal y, height).
2. Route it in `UdpSource.handle` and add a default port in `DEFAULT_PORTS`.
3. Add a packet-level test in `tests/test_core.py`.
4. Add the game to `games.json` and regenerate docs.

## Adding a shared-memory sim

1. Add the struct fields to `tools/shm_offsets.c`, compile against the C header and copy the offsets into `telemetry/shm.py`.
2. Extend `tools/shm_fixtures.c` to write a fixture with known values; add a test in `tests/test_shm.py`.
3. Register it in `READERS`.

## Adding a wheel

Implement the driver interface in `py_modules/pitwall/wheels/` (see the module docstring). For kernel drivers that expose sysfs files, subclass `SysfsDriver` and list the attributes.
