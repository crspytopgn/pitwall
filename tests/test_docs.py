"""docs/compatibility.md must match what scripts/gen_docs.py generates from games.json."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gen_docs  # noqa: E402


class TestDocs(unittest.TestCase):
    def test_compatibility_doc_up_to_date(self):
        with open(gen_docs.OUT, encoding="utf-8") as f:
            self.assertEqual(f.read(), gen_docs.render(),
                             "docs/compatibility.md is stale: run python3 scripts/gen_docs.py")


if __name__ == "__main__":
    unittest.main()
