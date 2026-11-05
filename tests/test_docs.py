"""docs/compatibility.md must match what scripts/gen_docs.py generates from games.json."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gen_docs  # noqa: E402


class TestDocs(unittest.TestCase):
    def test_generated_docs_up_to_date(self):
        for path, fn in gen_docs.OUTPUTS.items():
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), fn(), f"{path} is stale: run python3 scripts/gen_docs.py")

    def test_site_builds(self):
        import tempfile
        import json
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import build_site
        out = build_site.build(os.path.join(tempfile.mkdtemp(), "site"))
        data = json.load(open(os.path.join(out, "data.json")))
        self.assertGreater(len(data["games"]), 20)
        self.assertTrue(os.path.exists(os.path.join(out, "wordmark.svg")))


if __name__ == "__main__":
    unittest.main()
