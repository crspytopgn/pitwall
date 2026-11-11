import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "standalone"))

import steam  # noqa: E402

LOCALCONFIG = '''"UserLocalConfigStore"
{
	"Software"
	{
		"Valve"
		{
			"Steam"
			{
				"apps"
				{
					"244210"
					{
						"LastPlayed"		"1700000000"
						"LaunchOptions"		"-dx11 %command%"
					}
					"805550"
					{
						"LastPlayed"		"1700000001"
					}
				}
				"Language"		"english"
			}
		}
	}
	// a comment Steam doesn't write but other tools might
	"friends"
	{
		"PersonaName"		"Mi\\"chael"
	}
}
'''


def fake_steam(home: str, account: int = 123):
    root = os.path.join(home, ".local/share/Steam")
    os.makedirs(os.path.join(root, "steamapps"))
    os.makedirs(os.path.join(root, "config"))
    os.makedirs(os.path.join(root, f"userdata/{account}/config"))
    lib2 = os.path.join(home, "games")
    os.makedirs(os.path.join(lib2, "steamapps"))
    with open(os.path.join(root, "steamapps/libraryfolders.vdf"), "w") as f:
        f.write(f'"libraryfolders"\n{{\n\t"0"\n\t{{\n\t\t"path"\t\t"{root}"\n\t}}\n\t"1"\n\t{{\n\t\t"path"\t\t"{lib2}"\n\t}}\n}}\n')
    with open(os.path.join(lib2, "steamapps/appmanifest_805550.acf"), "w") as f:
        f.write('"AppState"\n{\n\t"appid"\t\t"805550"\n\t"name"\t\t"Assetto Corsa Competizione"\n}\n')
    with open(os.path.join(root, "steamapps/appmanifest_244210.acf"), "w") as f:
        f.write('"AppState"\n{\n\t"appid"\t\t"244210"\n\t"name"\t\t"Assetto Corsa"\n}\n')
    with open(os.path.join(root, "config/loginusers.vdf"), "w") as f:
        f.write(f'"users"\n{{\n\t"{steam.STEAMID64_BASE + account}"\n\t{{\n\t\t"AccountName"\t\t"x"\n\t\t"MostRecent"\t\t"1"\n\t}}\n}}\n')
    path = os.path.join(root, f"userdata/{account}/config/localconfig.vdf")
    with open(path, "w") as f:
        f.write(LOCALCONFIG)
    return path


def fake_proc(base: str, procs: dict):
    """procs: pid -> (comm, [args])"""
    for pid, (comm, args) in procs.items():
        d = os.path.join(base, str(pid))
        os.makedirs(d)
        with open(os.path.join(d, "comm"), "w") as f:
            f.write(comm + "\n")
        with open(os.path.join(d, "cmdline"), "wb") as f:
            f.write(b"\0".join(a.encode() for a in args) + b"\0")
    os.makedirs(os.path.join(base, "self"), exist_ok=True)


class TestVdf(unittest.TestCase):
    def test_roundtrip_keeps_everything(self):
        tree = steam.loads(LOCALCONFIG)
        again = steam.loads(steam.dumps(tree))
        self.assertEqual(tree, again)
        self.assertEqual(steam.value(steam.get(tree, "UserLocalConfigStore", "friends"), "PersonaName"), 'Mi"chael')
        apps = steam.get(tree, "userlocalconfigstore", "software", "valve", "steam", "apps")
        self.assertEqual([k for k, _ in apps], ["244210", "805550"])

    def test_errors(self):
        for bad in ('"a"\n{\n"b" "c"\n', '"a" "b" }', '"a"', '"unterminated'):
            with self.assertRaises(steam.VdfError):
                steam.loads(bad)

    def test_conditionals_and_unquoted(self):
        tree = steam.loads('"x" { key value [$WIN32] "y" "z" }')
        self.assertEqual(tree, [["x", [["key", "value"], ["y", "z"]]]])


class TestSteamFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.cfg = fake_steam(self.home)
        self.proc = os.path.join(self.home, "proc")

    def tearDown(self):
        self.tmp.cleanup()

    def test_names_and_paths(self):
        self.assertEqual(steam.app_name(self.home, "244210"), "Assetto Corsa")
        self.assertEqual(steam.app_name(self.home, "805550"), "Assetto Corsa Competizione")   # second library
        self.assertIsNone(steam.app_name(self.home, "1"))
        self.assertIsNone(steam.app_name(self.home, "../../etc"))
        self.assertEqual(steam.localconfig_path(self.home), os.path.realpath(self.cfg))

    def test_running_game_and_steam(self):
        fake_proc(self.proc, {10: ("steam", ["/usr/bin/steam"]),
                              20: ("reaper", ["reaper", "SteamLaunch", "AppId=805550", "--", "proton", "run", "acc.exe"]),
                              30: ("bash", ["bash", "-c", "echo AppId=1"])})
        self.assertEqual(steam.running_game(self.proc), "805550")
        self.assertTrue(steam.steam_running(self.proc))
        empty = os.path.join(self.home, "proc2")
        fake_proc(empty, {5: ("bash", ["bash"])})
        self.assertIsNone(steam.running_game(empty))
        self.assertFalse(steam.steam_running(empty))

    def test_launch_options_written_when_steam_closed(self):
        fake_proc(self.proc, {5: ("bash", ["bash"])})
        lo = steam.LaunchOptions(self.home, os.path.join(self.home, "q.json"), proc=self.proc)
        self.assertEqual(lo.get("244210"), "-dx11 %command%")
        self.assertEqual(lo.get("805550"), "")
        r = lo.set("805550", "WINECARTE=1 winecarte-run %command%")
        self.assertTrue(r["applied"])
        self.assertEqual(lo.get("805550"), "WINECARTE=1 winecarte-run %command%")
        self.assertEqual(lo.pending(), {})
        tree = steam.loads(open(self.cfg).read())
        app = steam.get(tree, "UserLocalConfigStore", "Software", "Valve", "Steam", "apps", "805550")
        self.assertEqual(steam.value(app, "LastPlayed"), "1700000001")      # untouched neighbours
        self.assertEqual(steam.value(steam.get(tree, "UserLocalConfigStore", "friends"), "PersonaName"), 'Mi"chael')
        self.assertTrue(os.path.exists(self.cfg + ".pitwall-backup"))
        self.assertEqual(open(self.cfg + ".pitwall-backup").read(), LOCALCONFIG)
        # a game Steam hasn't recorded settings for yet gets its own block
        self.assertTrue(lo.set("1066890", "%command% -fast")["applied"])
        self.assertEqual(lo.get("1066890"), "%command% -fast")

    def test_launch_options_queued_while_steam_open(self):
        fake_proc(self.proc, {10: ("steamwebhelper", ["steamwebhelper"])})
        lo = steam.LaunchOptions(self.home, os.path.join(self.home, "q.json"), proc=self.proc)
        r = lo.set("244210", "SDL_JOYSTICK_WHEEL_DEVICES=0x346e/0x0004 -dx11 %command%")
        self.assertTrue(r["ok"])
        self.assertFalse(r["applied"])
        self.assertIn("exit Steam", r["message"])
        self.assertEqual(open(self.cfg).read(), LOCALCONFIG)                # file untouched
        self.assertEqual(lo.get("244210"), "SDL_JOYSTICK_WHEEL_DEVICES=0x346e/0x0004 -dx11 %command%")   # pending wins
        self.assertEqual(lo.flush()["applied"], False)
        # Steam exits
        import shutil
        shutil.rmtree(self.proc)
        fake_proc(self.proc, {5: ("bash", ["bash"])})
        self.assertTrue(lo.flush()["applied"])
        self.assertEqual(lo.pending(), {})
        self.assertIn("SDL_JOYSTICK_WHEEL_DEVICES", open(self.cfg).read())

    def test_unreadable_config_changes_nothing(self):
        fake_proc(self.proc, {5: ("bash", ["bash"])})
        with open(self.cfg, "w") as f:
            f.write('"UserLocalConfigStore" { "broken" ')
        lo = steam.LaunchOptions(self.home, os.path.join(self.home, "q.json"), proc=self.proc)
        self.assertIsNone(lo.get("244210"))
        r = lo.set("244210", "%command%")
        self.assertFalse(r["ok"])
        self.assertEqual(open(self.cfg).read(), '"UserLocalConfigStore" { "broken" ')
        self.assertFalse(lo.set("abc", "%command%")["ok"])


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@unittest.skipUnless(os.geteuid() == 0 or os.environ.get("CI"), "starts the full app")
class TestControlServer(unittest.TestCase):
    """The control API: localhost only, custom header required, plugin's public methods only."""

    @classmethod
    def setUpClass(cls):
        import pwd
        import pitwall_app
        cls.user = pwd.getpwuid(os.getuid()).pw_name
        os.environ["PITWALL_MOZA_TTY"] = "/nonexistent"
        cls.app = pitwall_app.App(cls.user, free_port())
        cls.app.main.DEFAULTS["dashboard_port"] = free_port()
        cls.app.run()
        cls.base = f"http://127.0.0.1:{cls.app.port}"

    @classmethod
    def tearDownClass(cls):
        cls.app.shutdown()

    def post(self, name, args=None, headers=None):
        h = {"X-Pitwall": "1", "Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(f"{self.base}/api/call/{name}", data=json.dumps({"args": args or []}).encode(), headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def test_calls(self):
        code, body = self.post("app_info")
        self.assertEqual(code, 200)
        self.assertTrue(body["result"]["standalone"])
        self.assertEqual(self.post("get_settings")[0], 200)
        self.assertEqual(self.post("compat_detail", ["ac"])[1]["result"]["name"], "Assetto Corsa")

    def test_refusals(self):
        self.assertEqual(self.post("app_info", headers={"X-Pitwall": "0"})[0], 403)
        self.assertEqual(self.post("app_info", headers={"Host": "evil.example:8091"})[0], 403)
        for name in ("_uninstall", "_main", "__init__", "settings", "nope", "../x"):
            self.assertEqual(self.post(name)[0], 404, name)
        self.assertEqual(self.post("compat_detail", ["a", "b", "c"])[0], 400)
        req = urllib.request.Request(f"{self.base}/", headers={"Host": "attacker.test"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(cm.exception.code, 403)

    def test_page_and_assets(self):
        with urllib.request.urlopen(self.base + "/", timeout=10) as r:
            self.assertIn(b"Pitwall", r.read())
            self.assertIn("default-src 'self'", r.headers["Content-Security-Policy"])
        with urllib.request.urlopen(self.base + "/qrcode.js", timeout=10) as r:
            self.assertIn(b"qrcode", r.read())

    def test_listens_on_localhost_only(self):
        self.assertEqual(self.app.server.server_address[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
