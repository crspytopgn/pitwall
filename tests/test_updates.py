import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py_modules"))

from pitwall import bridge, drivers, updates  # noqa: E402

NEW = "f00dbabe" + "1" * 32


def fake_fetch(responses):
    def fetch(url, timeout=15):
        for key, body in responses.items():
            if key in url:
                if isinstance(body, Exception):
                    raise body
                return json.dumps(body).encode()
        raise OSError("unexpected " + url)
    return fetch


class TestUpdates(unittest.TestCase):
    def test_repo_path(self):
        self.assertEqual(updates.repo_path("https://github.com/JacKeTUs/universal-pidff"), "JacKeTUs/universal-pidff")
        self.assertEqual(updates.repo_path("https://github.com/a/b.git/"), "a/b")

    def test_driver_and_bridge(self):
        fetch = fake_fetch({
            "universal-pidff/commits": [{"sha": NEW, "commit": {"committer": {"date": "2026-11-01T10:00:00Z"}}}],
            "new-lg4ff/commits": [{"sha": "abc1234" + "0" * 33, "commit": {"committer": {"date": "2025-05-28T00:00:00Z"}}}],
            "winecarte/releases/latest": {"tag_name": "v0.4.0", "published_at": "2026-10-20T00:00:00Z"},
        })
        installed = {"universal-pidff": {"commit": "abc1234", "sha": "abc1234" + "0" * 33},
                     "new-lg4ff": {"commit": "abc1234"}}
        res = updates.check(installed, drivers.DRIVERS, True, "v0.3.0", fetch=fetch, now=lambda: 1000)
        by = {i["id"]: i for i in res["items"]}
        self.assertTrue(by["universal-pidff"]["update"])
        self.assertEqual(by["universal-pidff"]["latest"], "f00dbab")
        self.assertEqual(by["universal-pidff"]["date"], "2026-11-01")
        self.assertFalse(by["new-lg4ff"]["update"])            # same commit, matched by short id
        self.assertTrue(by["winecarte"]["update"])
        self.assertEqual(sorted(res["available"]), ["universal-pidff", "winecarte"])
        self.assertEqual(res["checked"], 1000)

    def test_fail_soft(self):
        fetch = fake_fetch({"commits": OSError("offline"), "releases": OSError("offline")})
        res = updates.check({"hid-tmff2": {"commit": "1234567"}}, drivers.DRIVERS, True, None, fetch=fetch)
        self.assertEqual(res["available"], [])
        self.assertTrue(all(i["error"] for i in res["items"]))

    def test_unknown_bridge_version_counts_as_old(self):
        fetch = fake_fetch({"releases/latest": {"tag_name": "v1"}})
        res = updates.check({}, drivers.DRIVERS, True, None, fetch=fetch)
        self.assertEqual(res["available"], ["winecarte"])
        self.assertEqual(updates.check({}, drivers.DRIVERS, False, None, fetch=fetch)["items"], [])

    def test_due(self):
        self.assertTrue(updates.due(None))
        self.assertFalse(updates.due({"checked": 100}, now=lambda: 100 + 3600))
        self.assertTrue(updates.due({"checked": 100}, now=lambda: 100 + 25 * 3600))

    def test_bridge_records_version(self):
        with tempfile.TemporaryDirectory() as home:
            def fetch(url, timeout=30):
                if url == bridge.API:
                    return json.dumps({"tag_name": "v9", "assets": [
                        {"name": "winecarte-run", "browser_download_url": "x/run"},
                        {"name": "wine2linux.exe", "browser_download_url": "x/exe"}]}).encode()
                return b"bin"
            self.assertIsNone(bridge.installed_version(home))
            self.assertTrue(bridge.install(home, fetch=fetch)["ok"])
            self.assertEqual(bridge.installed_version(home), "v9")


if __name__ == "__main__":
    unittest.main()
