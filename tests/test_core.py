"""Core tests: run with `python3 -m unittest discover -s tests` from the repo root."""

import json
import math
import os
import socket
import struct
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "py_modules"))

from pitwall import coach, compat, engineer, health, perf  # noqa: E402
from pitwall.dashboard import Dashboard  # noqa: E402
from pitwall.hub import Hub  # noqa: E402
from pitwall.laps import LapTracker  # noqa: E402
from pitwall.telemetry import parsers  # noqa: E402
from pitwall.telemetry.frame import Frame  # noqa: E402
from pitwall.telemetry.sources import parse_ac  # noqa: E402


def outgauge_packet(speed=30.0, rpm=5000.0, gear=4, throttle=0.8, brake=0.0, car=b"beam", show=0, with_id=False):
    p = parsers.OUTGAUGE.pack(0, car, 16384, gear, 0, speed, rpm, 0.5, 90.0, 0.6, 0.0, 100.0,
                              0xFFF, show, throttle, brake, 0.0, b"", b"")
    return p + (struct.pack("<i", 7) if with_id else b"")


def motionsim_packet(x, y, z=0.0):
    return struct.pack("<4s21f", b"BNG1", x, y, z, *([0.0] * 18))


class TestParsers(unittest.TestCase):
    def test_outgauge_beamng(self):
        f = parsers.parse_outgauge(outgauge_packet(show=parsers.DL_SHIFT | parsers.DL_ABS))
        self.assertEqual(f.sim, "beamng")
        self.assertEqual(f.gear, 3)            # OutGauge 4 = 3rd
        self.assertAlmostEqual(f.speed, 30.0)
        self.assertTrue(f.shift_light and f.extra["abs"])
        self.assertEqual(parsers.parse_outgauge(outgauge_packet(with_id=True)).sim, "beamng")

    def test_outgauge_lfs_and_reverse(self):
        f = parsers.parse_outgauge(outgauge_packet(car=b"FBM", gear=0))
        self.assertEqual((f.sim, f.car, f.gear), ("lfs", "FBM", -1))

    def test_outgauge_rejects_other_sizes(self):
        self.assertIsNone(parsers.parse_outgauge(b"\0" * 88))

    def test_motionsim(self):
        m = parsers.parse_motionsim(motionsim_packet(1.5, -2.0, 3.0))
        self.assertEqual(m["pos"], (1.5, -2.0, 3.0))
        self.assertIsNone(parsers.parse_motionsim(b"XXXX" + b"\0" * 84))

    def _forza(self, size):
        sled = [1, 1234, 8000.0, 800.0, 6000.0] + [0.0] * 12 + [0.0] * 12 + [0] * 4 + [0.0] * 20 + [42, 1, 700, 1, 6]
        sled_b = struct.pack("<iIfff3f3f3f3f4f4f4f4i4f4f4f4f4f5i", *sled)
        dash = struct.pack("<3f3f4f7fHBBBBBBbbb", 10.0, 20.0, 30.0, 50.0, 0, 0, 212, 212, 176, 176,
                           0, 0.5, 1000.0, 80.0, 82.0, 12.0, 300.0, 3, 1, 255, 0, 0, 0, 4, -64, 0, 0)
        pad = b"\0" * 12 if size == 324 else b""
        tail = b"\0" * (size - len(sled_b) - len(pad) - len(dash))
        return sled_b + pad + dash + tail

    def test_forza_all_layouts(self):
        for size in (311, 324, 331):
            f = parsers.parse_forza(self._forza(size))
            self.assertIsNotNone(f, size)
            self.assertEqual(f.gear, 4)
            self.assertAlmostEqual(f.speed, 50.0)
            self.assertAlmostEqual(f.throttle, 1.0)
            self.assertEqual(f.lap, 3)
            self.assertEqual(f.tyre_temp[0], 100.0)       # 212 °F
            self.assertAlmostEqual(f.steer, -64 / 127)
            self.assertEqual(f.pos, (10.0, 30.0, 20.0))
            self.assertEqual(f.car, "42")
        self.assertIsNone(parsers.parse_forza(b"\0" * 300))

    def test_codemasters(self):
        v = [0.0] * 66
        v[1], v[2], v[7], v[29], v[31], v[33], v[36], v[37], v[61], v[62], v[63] = \
            65.0, 1200.0, 40.0, 1.0, 0.0, 3.0, 2.0, 650.0, 4000.0, 130.5, 800.0
        f = parsers.parse_codemasters(struct.pack("<66f", *v))
        self.assertEqual((f.gear, f.lap, f.rpm, f.max_rpm, f.last_lap), (3, 2, 6500.0, 8000.0, 130.5))
        self.assertAlmostEqual(f.lap_frac, 0.3)
        v[33] = 10.0
        self.assertEqual(parsers.parse_codemasters(struct.pack("<66f", *v)).gear, -1)

    def test_ac_shm(self):
        phys = bytearray(800)
        struct.pack_into("<i3f2i2f", phys, 0, 99, 0.7, 0.1, 40.0, 4, 7200, -0.2, 180.0)
        graph = bytearray(1200)
        struct.pack_into("<i", graph, 4, 2)
        struct.pack_into("<i", graph, 132, 5)
        struct.pack_into("<3i", graph, 140, 45000, 101234, 100987)
        struct.pack_into("<f", graph, 248, 0.42)
        static = bytearray(800)
        static[68:68 + 12] = "ks_bmw".encode("utf-16-le")
        static[134:134 + 8] = "spa".encode("utf-16-le")
        struct.pack_into("<i", static, 412, 8500)
        f = parse_ac(bytes(phys), bytes(graph), bytes(static))
        self.assertEqual((f.gear, f.lap, f.car, f.track, f.max_rpm), (3, 5, "ks_bmw", "spa", 8500))
        self.assertAlmostEqual(f.speed, 50.0)
        self.assertAlmostEqual(f.last_lap, 101.234)
        self.assertTrue(f.active)


def drive_loop(tracker, laps=2, radius=100.0, speed=40.0, brake_zone=(0.45, 0.55), sim="beamng",
               t0=0.0, dt=0.05, slow_factor=1.0):
    """Drive circles around (radius, 0) starting at the origin; braking in one zone per lap."""
    circ = 2 * math.pi * radius
    t = t0
    d = 0.0
    total = circ * laps + 30
    while d < total:
        frac = (d % circ) / circ
        zone = brake_zone[int(d // circ)] if isinstance(brake_zone, list) else brake_zone
        braking = zone[0] <= frac < zone[1]
        v = (speed * 0.5 if braking else speed) * (slow_factor if braking else 1.0)
        ang = frac * 2 * math.pi
        pos = (radius - radius * math.cos(ang), radius * math.sin(ang), 0.0)
        tracker.update(Frame(sim=sim, t=t, speed=v, throttle=0.0 if braking else 1.0,
                             brake=0.9 if braking else 0.0, gear=3, pos=pos))
        t += dt
        d += v * dt
    return t


def f1_packets(fmt, player=3, speed=250, gear=7, lap_num=4, cur_ms=45000, last_ms=91234, dist=1500.0):
    hdr_len, id_at, pl_at = parsers.F1_FORMATS[fmt]

    def header(pid):
        h = bytearray(hdr_len)
        struct.pack_into("<H", h, 0, fmt)
        h[id_at], h[pl_at] = pid, player
        return h
    motion = header(0) + bytearray(22 * 60)
    struct.pack_into("<3f", motion, hdr_len + player * 60, 100.0, 5.0, -200.0)
    session = header(1) + bytearray(600)
    struct.pack_into("<H", session, hdr_len + 4, 5000)
    lap_size = 50 if fmt == 2023 else 43
    lap = header(2) + bytearray(22 * lap_size + 2)
    o = hdr_len + player * lap_size
    struct.pack_into("<2I", lap, o, last_ms, cur_ms)
    d_at, n_at = (18, 31) if fmt == 2023 else (12, 25)
    struct.pack_into("<f", lap, o + d_at, dist)
    lap[o + n_at] = lap_num
    tel = header(6) + bytearray(22 * 60 + 3)
    o = hdr_len + player * 60
    struct.pack_into("<HfffBbH", tel, o, speed, 0.9, -0.1, 0.0, 0, gear, 11000)
    struct.pack_into("<4B", tel, o + 30, 90, 91, 100, 101)     # RL, RR, FL, FR
    return [bytes(motion), bytes(session), bytes(lap), bytes(tel)]


class TestF1(unittest.TestCase):
    def test_all_formats(self):
        for fmt in (2021, 2022, 2023):
            a = parsers.F1Assembler()
            out = [a.feed(p) for p in f1_packets(fmt)]
            f = out[-1]
            self.assertIsNotNone(f, fmt)
            self.assertEqual((f.sim, f.gear, f.lap), ("f1", 7, 3))
            self.assertAlmostEqual(f.speed, 250 / 3.6, places=3)
            self.assertEqual(f.pos, (100.0, -200.0, 5.0))
            self.assertAlmostEqual(f.lap_time, 45.0)
            self.assertAlmostEqual(f.last_lap, 91.234)
            self.assertAlmostEqual(f.lap_frac, 0.3)
            self.assertEqual(f.tyre_temp, [100.0, 101.0, 90.0, 91.0])

    def test_rejects_unknown_formats_and_bad_lap_data(self):
        a = parsers.F1Assembler()
        pk = f1_packets(2023)
        bad = bytearray(pk[0]); struct.pack_into("<H", bad, 0, 2024)
        self.assertIsNone(a.feed(bytes(bad)))
        a.feed(pk[1])
        a.feed(f1_packets(2023, lap_num=0)[2])        # nonsense lap data is ignored
        f = a.feed(pk[3])
        self.assertIsNone(f.lap)


class TestLaps(unittest.TestCase):
    def test_gate_laps_and_delta(self):
        laps = []
        tr = LapTracker(laps.append)
        tr.update(Frame(sim="beamng", t=0, pos=(0, 0, 0)))
        tr.set_gate((0, 0, 0))
        t = drive_loop(tr, laps=2, t0=0.05)
        self.assertEqual(len(laps), 2)
        circ = 2 * math.pi * 100
        self.assertAlmostEqual(laps[0].length, circ, delta=40)
        tr.reference = laps[0]
        drive_loop(tr, laps=1, t0=t + 0.05, slow_factor=0.8)
        live = tr.live()
        self.assertIsNotNone(live["lap_time"])

    def test_pause_gap_not_counted(self):
        laps = []
        tr = LapTracker(laps.append)
        tr.update(Frame(sim="beamng", t=0, pos=(0, 0, 0)))
        tr.set_gate((0, 0, 0))
        tr.update(Frame(sim="beamng", t=0.05, speed=10, pos=(0.5, 0, 0)))
        tr.update(Frame(sim="beamng", t=30.0, speed=10, pos=(0.5, 0, 0)))   # 30 s pause
        self.assertLess(tr.cur.t, 1.0)

    def test_sim_counted_laps(self):
        laps = []
        tr = LapTracker(laps.append)
        t = 0.0
        for lap in range(3):
            for i in range(600):
                tr.update(Frame(sim="forza", t=t, speed=40, lap=lap, last_lap=30.0 if lap else None))
                t += 0.05
        tr.update(Frame(sim="forza", t=t, speed=40, lap=3, last_lap=30.0))
        # first lap was joined mid-way only if not started; laps 1 and 2 complete
        self.assertEqual(len(laps), 2)
        self.assertEqual(laps[0].time, 30.0)


class TestCoach(unittest.TestCase):
    def test_finds_early_braking_and_loss(self):
        laps = []
        tr = LapTracker(laps.append)
        tr.update(Frame(sim="beamng", t=0, pos=(0, 0, 0)))
        tr.set_gate((0, 0, 0))
        drive_loop(tr, laps=2, t0=0.05, brake_zone=[(0.45, 0.55), (0.40, 0.55), (0.45, 0.55)])  # lap 2 brakes earlier
        ref, lap = laps[0], laps[1]
        res = coach.compare(lap.samples, ref.samples)
        self.assertEqual(len(res["corners"]), 1)
        c = res["corners"][0]
        self.assertGreater(c["brake_diff_m"], 20)
        self.assertGreater(c["loss"], 0.3)
        self.assertIn("earlier", res["tips"][0])
        self.assertGreater(res["total_delta"], 0.3)


class TestHubEndToEnd(unittest.TestCase):
    def test_udp_beamng_session(self):
        tmp = tempfile.mkdtemp()
        ports = {"outgauge": 47444, "motionsim": 47445, "forza": 47300, "codemasters": 47777, "f1": 47778}
        hub = Hub(os.path.join(tmp, "laps.sqlite"), ports=ports, enable_shm=False)
        hub.start()
        dash = Dashboard(hub, port=48090)
        dash.start()
        time.sleep(0.3)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for _ in range(5):
            s.sendto(motionsim_packet(0, 0), ("127.0.0.1", 47445))
            s.sendto(outgauge_packet(speed=10), ("127.0.0.1", 47444))
            time.sleep(0.02)
        time.sleep(0.2)
        st = hub.status()
        self.assertTrue(st["receiving"])
        self.assertEqual(st["sim"], "beamng")
        self.assertTrue(st["needs_start_line"])
        self.assertTrue(hub.set_start_line())
        # dashboard serves page and a live event
        html = urllib.request.urlopen("http://127.0.0.1:48090/", timeout=3).read()
        self.assertIn(b"Pitwall", html)
        r = urllib.request.urlopen("http://127.0.0.1:48090/events", timeout=3)
        line = r.readline().decode()
        self.assertTrue(line.startswith("data: "))
        self.assertEqual(json.loads(line[6:])["sim"], "beamng")
        r.close()
        # feed two laps straight into the hub (faster than real time)
        laps_before = len(hub.session_laps)
        tr_feed = []
        hub_tr = hub.tracker

        class Feed:
            def update(self, f):
                hub._on_frame(f)
        drive_loop(Feed(), laps=2, t0=time.monotonic() + 1)
        self.assertEqual(len(hub.session_laps) - laps_before, 2)
        self.assertEqual(len(hub.store.recent()), 2)
        summ = engineer.build_summary(hub.session_summary())
        self.assertEqual(summ["laps"], 2)
        self.assertTrue(engineer.offline_debrief(summ))
        # F1 via the shared Codemasters port
        for p in f1_packets(2022):
            s.sendto(p, ("127.0.0.1", 47777))
        time.sleep(0.2)
        self.assertEqual(hub.status()["sim"], "f1")
        hub.stop()
        dash.stop()
        del tr_feed, hub_tr


class TestPerf(unittest.TestCase):
    def _log(self, frametimes):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "game_2026-11-05_18-00-00.csv")
        with open(p, "w") as f:
            f.write("os,cpu,gpu,ram,kernel,driver,cpuscheduler\nSteamOS,AMD,AMD,16GB,6.16,mesa,\n")
            f.write("fps,frametime,cpu_load,gpu_load,cpu_temp,gpu_temp,elapsed\n")
            for ft in frametimes:
                f.write(f"{1000/ft:.1f},{ft:.3f},50,90,60,70,0\n")
        return d

    def test_great(self):
        r = perf.analyse_latest(self._log([16.6] * 6000), 60)
        self.assertEqual(r["verdict"], "great")

    def test_stutters(self):
        ft = [15.0] * 6000
        for i in range(0, 6000, 50):
            ft[i] = 60.0
        r = perf.analyse_latest(self._log(ft), 60)
        self.assertEqual(r["verdict"], "stutters")

    def test_too_slow(self):
        r = perf.analyse_latest(self._log([25.0] * 6000), 60, ["hint"])
        self.assertEqual(r["verdict"], "too_slow")
        self.assertIn("hint", r["advice"])

    def test_launch_options(self):
        self.assertTrue(perf.benchmark_launch_options("/tmp/x").endswith("%command%"))


class TestCompat(unittest.TestCase):
    def test_games_data_is_valid(self):
        data = compat.load_games()
        ids = set()
        for g in data["games"]:
            self.assertNotIn(g["id"], ids)
            ids.add(g["id"])
            self.assertIn(g["status"], ("works", "setup", "community", "broken"))
            self.assertTrue(g["install"])
            for k in g["known_issues"]:
                self.assertTrue(k["source"].startswith("https://"), k)

    def test_find_and_overview(self):
        home = tempfile.mkdtemp()
        steam = os.path.join(home, ".local/share/Steam/steamapps")
        os.makedirs(steam)
        open(os.path.join(steam, "libraryfolders.vdf"), "w").write('"libraryfolders" { "0" { "path" "%s" } }' % os.path.dirname(steam))
        open(os.path.join(steam, "appmanifest_284160.acf"), "w").write("x")
        c = compat.Compat(home, tempfile.mkdtemp())
        self.assertEqual(c.find(284160)["id"], "beamng")
        self.assertEqual(c.find(None, "Forza Horizon 6 Premium")["id"], "fh6")
        ov = c.overview()
        self.assertEqual(ov[0]["id"], "beamng")
        self.assertTrue(ov[0]["installed"])
        d = c.detail("eawrc", online=False)
        self.assertEqual(d["status"], "broken")

    def test_dr2_auto_setup(self):
        home = tempfile.mkdtemp()
        steam = os.path.join(home, ".local/share/Steam/steamapps")
        cfg_dir = os.path.join(steam, "compatdata/690790/pfx/drive_c/users/steamuser/Documents/My Games/DiRT Rally 2.0/hardwaresettings")
        os.makedirs(cfg_dir)
        open(os.path.join(steam, "libraryfolders.vdf"), "w").write("")
        cfg = os.path.join(cfg_dir, "hardware_settings_config.xml")
        open(cfg, "w").write('<hardware_settings_config>\n\t<motion_platform>\n\t\t<dbox enabled="true" />\n'
                             '\t\t<udp enabled="false" extradata="0" ip="127.0.0.1" port="20777" delay="1" />\n'
                             '\t</motion_platform>\n</hardware_settings_config>\n')
        r = compat.dr2_enable_udp(home)
        self.assertTrue(r["ok"], r)
        xml = open(cfg).read()
        self.assertIn('<udp enabled="true" extradata="3"', xml)
        self.assertIn("<dbox", xml)
        self.assertTrue(os.path.exists(cfg + ".pitwall.bak"))
        self.assertIn("already", compat.dr2_enable_udp(home)["message"])


class TestFfb(unittest.TestCase):
    def setUp(self):
        from pitwall.wheels import MozaDriver
        self.ranges = MozaDriver.__new__(MozaDriver).settings()
        from pitwall import ffb
        self.ffb = ffb

    def test_presets_fit_moza_ranges(self):
        for p in self.ffb.PRESETS:
            self.assertTrue(p["source"].startswith("https://"))
            for k, v in p["values"].items():
                self.assertIn(k, self.ranges, (p["id"], k))
                r = self.ranges[k]
                self.assertTrue(r["min"] <= v <= r["max"], (p["id"], k, v, r))

    def test_nudges_reference_real_settings(self):
        for sid, n in self.ffb.NUDGES.items():
            for key, _d, _why in n["changes"]:
                self.assertIn(key, self.ranges, (sid, key))

    def test_nudge_clamps_and_reports(self):
        cur = {"inertia": 480, "friction": 0, "damper": 0}
        r = self.ffb.nudge("too_light", cur, self.ranges)
        self.assertEqual(r["values"], {"inertia": 500, "friction": 5})
        self.assertEqual(len(r["changes"]), 2)
        r = self.ffb.nudge("too_light", {"inertia": 500, "friction": 100}, self.ranges)
        self.assertEqual(r["values"], {})
        r = self.ffb.nudge("rattly", {"road_sensitivity": 5}, self.ranges, "beamng")
        self.assertIn("Smoothing", r["tip"])
        self.assertIsNone(self.ffb.nudge("nope", {}, self.ranges))


class TestDevice(unittest.TestCase):
    def test_detect_and_plan(self):
        from pitwall import device, ffb
        dev = device.detect()
        self.assertIn(dev["kind"], ("pc", "steam_deck", "steam_machine"))

        class W:
            brand, model = "MOZA", "R5"
        plan = device.plan(dev, W(), [{"id": "dr2", "name": "DiRT Rally 2.0", "status": "works", "installed": True,
                                       "auto_setup": "dr2_udp"}], ffb.preset_for_base)
        self.assertEqual(plan["preset"], "moza_r3_r5")
        self.assertTrue(any(s["id"] == "game:dr2" for s in plan["steps"]))
        self.assertEqual(device.plan(dev, None, [], ffb.preset_for_base)["preset"], None)


class TestHealth(unittest.TestCase):
    def test_runs_without_hardware(self):
        res = health.check(None, None, {"name": "EA SPORTS WRC", "status": "broken", "install": ["x"], "telemetry": {}})
        ids = {r["id"] for r in res}
        self.assertIn("wheel", ids)
        self.assertIn("compat", ids)


if __name__ == "__main__":
    unittest.main()


class TestBridge(unittest.TestCase):
    def test_install_from_tarball_and_launch_options(self):
        import io as _io
        import tarfile as _tar
        from pitwall import bridge
        buf = _io.BytesIO()
        with _tar.open(fileobj=buf, mode="w:gz") as t:
            for n in ("winecarte-run", "wine2linux.exe", "README.md"):
                data = b"x" * 10
                ti = _tar.TarInfo("winecarte-1.0/" + n)
                ti.size = len(data)
                t.addfile(ti, _io.BytesIO(data))
        rel = {"tag_name": "v1.0", "assets": [{"name": "winecarte-1.0.tar.gz", "browser_download_url": "https://x/a"}]}

        def fetch(url):
            return json.dumps(rel).encode() if url == bridge.API else buf.getvalue()
        home = tempfile.mkdtemp()
        r = bridge.install(home, fetch=fetch)
        self.assertTrue(r["ok"], r)
        self.assertTrue(bridge.installed(home))
        self.assertTrue(os.access(os.path.join(bridge.bin_dir(home), "winecarte-run"), os.X_OK))
        pre = bridge.launch_prefix(home)
        self.assertEqual(bridge.merge_launch_options("", pre), f"{pre} %command%")
        self.assertEqual(bridge.merge_launch_options("gamemoderun %command% -vr", pre), f"gamemoderun {pre} %command% -vr")
        merged = bridge.merge_launch_options("gamemoderun %command% -vr", pre)
        self.assertEqual(bridge.merge_launch_options(merged, pre), merged)          # idempotent
        self.assertEqual(bridge.remove_from_launch_options(merged, pre), "gamemoderun %command% -vr")
        self.assertEqual(bridge.remove_from_launch_options(f"{pre} %command%", pre), "")

    def test_install_reports_missing(self):
        from pitwall import bridge
        r = bridge.install(tempfile.mkdtemp(), fetch=lambda u: json.dumps({"assets": []}).encode())
        self.assertFalse(r["ok"])


class TestStrategy(unittest.TestCase):
    def test_fuel_and_tyres(self):
        from pitwall.strategy import Strategy
        st = Strategy()
        fuel, wear = 50.0, [1.0, 1.0, 1.0, 1.0]
        t = 0.0
        for lap in range(4):
            for i in range(10):
                fuel -= 0.25           # 2.5 L per lap
                wear = [w - 0.002 for w in wear]
                wear[1] -= 0.001       # FR wears faster
                st.on_frame(Frame(sim="ac", t=t, fuel_l=fuel, fuel_cap_l=60, tyre_wear=list(wear),
                                  tyre_temp=[95, 96, 80, 81]))
                t += 1
            st.on_lap(90.0)
        st.set_target(laps=20)
        r = st.report()
        self.assertAlmostEqual(r["fuel"]["per_lap"], 2.5, places=2)
        self.assertAlmostEqual(r["fuel"]["laps_left"], 40 / 2.5, places=1)
        self.assertAlmostEqual(r["fuel"]["to_add"], 21 * 2.5 - 40, places=1)
        self.assertEqual(r["tyres"]["worst"], "FR")
        self.assertTrue(any("Fronts" in n for n in r["tyres"]["notes"]))
        st.set_target(minutes=30)       # 30 min at 90 s/lap = 20 laps
        self.assertAlmostEqual(st.report()["fuel"]["to_add"], 21 * 2.5 - 40, places=1)

    def test_refuel_lap_ignored(self):
        from pitwall.strategy import Strategy
        st = Strategy()
        st.on_frame(Frame(sim="ams2", t=0, fuel_l=11, fuel_cap_l=100))
        st.on_lap(80)                                       # joined mid-lap: ignored
        st.on_frame(Frame(sim="ams2", t=1, fuel_l=10))
        st.on_frame(Frame(sim="ams2", t=1.5, fuel_l=8))
        st.on_lap(80)
        st.on_frame(Frame(sim="ams2", t=2, fuel_l=6))
        st.on_frame(Frame(sim="ams2", t=3, fuel_l=60))     # pit stop
        st.on_frame(Frame(sim="ams2", t=4, fuel_l=59))
        st.on_lap(95)
        self.assertEqual(st.fuel_per_lap, [3])


class TestCarChange(unittest.TestCase):
    def test_car_listener_fires_once_per_car(self):
        hub = Hub(os.path.join(tempfile.mkdtemp(), "l.db"), ports={}, enable_shm=False)
        hub.sources = []
        seen = []
        hub.car_listeners.append(lambda sim, car: seen.append((sim, car)))
        t = time.monotonic()
        for i, car in enumerate(["ks_bmw", "ks_bmw", "ks_bmw", "ks_audi"]):
            hub._on_frame(Frame(sim="ac", t=t + i * 0.1, car=car))
        hub._on_frame(Frame(sim="ac", t=t + 1, car="ks_audi", active=False))
        self.assertEqual(seen, [("ac", "ks_bmw"), ("ac", "ks_audi")])


class TestLogitechLeds(unittest.TestCase):
    def test_mask_maps_to_five_leds(self):
        from pitwall.wheels import LogitechDriver
        d = tempfile.mkdtemp()
        for n in range(1, 6):
            os.makedirs(os.path.join(d, f"0003:046D:C24F.0001::RPM{n}"))
            open(os.path.join(d, f"0003:046D:C24F.0001::RPM{n}", "brightness"), "w").close()
        drv = LogitechDriver()
        drv.LED_GLOB = os.path.join(d, "*::RPM{n}", "brightness")
        self.assertTrue(drv.leds_supported and drv.leds_begin())
        drv.leds(0b0000011111)              # 5 of 10 -> 3 of 5
        vals = [open(os.path.join(d, f"0003:046D:C24F.0001::RPM{n}", "brightness")).read() for n in range(1, 6)]
        self.assertEqual(vals, ["1", "1", "1", "0", "0"])
        drv.leds_end()
        vals = [open(os.path.join(d, f"0003:046D:C24F.0001::RPM{n}", "brightness")).read() for n in range(1, 6)]
        self.assertEqual(vals, ["0"] * 5)


class TestWheelDb(unittest.TestCase):
    def test_identify_and_kernel(self):
        self.assertEqual(health.identify("346e", "0005")["model"], "R3")
        self.assertIsNone(health.identify("dead", "beef"))
        for rel, ok in [("6.15.0", True), ("6.16.2-valve1", True), ("6.12.24", True), ("6.12.23", False),
                        ("6.13.12", True), ("6.14.2", False), ("6.11.9", False), ("7.0", True)]:
            self.assertEqual(health.kernel_has_universal_pidff(rel), ok, rel)
