"""P26 - offline CI gate helpers (poora suite yahan se nahi chalaya jata)."""

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ["JIN_AGENT_DATA"] = tempfile.mkdtemp(prefix="jin-gate-")

from jin_agent import VERSION, ci_gate  # noqa: E402


class TestGateHelpers(unittest.TestCase):
    def test_package_modules_listed(self):
        names = ci_gate.package_modules()
        self.assertGreaterEqual(len(names), 20)
        for expected in ("metrics", "logging_setup", "ci_gate", "orchestrator", "store"):
            self.assertIn(expected, names)

    def test_compile_file_ok(self):
        ok, error = ci_gate.compile_file(Path(ci_gate.__file__))
        self.assertTrue(ok)
        self.assertEqual(error, "")

    def test_compile_file_reports_syntax_error(self):
        folder = Path(tempfile.mkdtemp(prefix="jin-bad-"))
        bad = folder / "bad.py"
        bad.write_text("def broken(:\n    pass\n", encoding="utf-8")
        ok, error = ci_gate.compile_file(bad)
        self.assertFalse(ok)
        self.assertIn("bad.py", error)

    def test_check_imports_green(self):
        res = ci_gate.check_imports()
        self.assertTrue(res["ok"], res.get("errors"))
        self.assertEqual(res["errors"], [])
        self.assertGreater(res["imported"], 20)

    def test_evaluator_quick_offline(self):
        res = ci_gate.check_evaluator_quick(queries=2)
        self.assertTrue(res["ok"])
        self.assertEqual(res["mode"], "offline-fixture")
        self.assertEqual(res["queries"], 2)
        self.assertEqual(res["crashes"], 0)
        self.assertEqual(res["fabricated"], 0)
        self.assertGreaterEqual(res["provenance_pct"], 100.0)
        self.assertGreater(res["items"], 0)

    def test_run_without_unit_suite(self):
        out = ci_gate.run(include_unittests=False, queries=2)
        self.assertTrue(out["ok"])
        self.assertEqual(out["version"], VERSION)
        self.assertIn("imports", out["checks"])
        self.assertIn("evaluator", out["checks"])
        self.assertNotIn("unit_tests", out["checks"])
        json.dumps(out)  # compact verdict JSON-serialisable hai

    def test_verdict_has_no_secrets(self):
        blob = json.dumps(ci_gate.run(include_unittests=False, queries=1))
        self.assertNotIn("sk-", blob)
        self.assertNotRegex(blob, r"bot\d{6,}:")


if __name__ == "__main__":
    unittest.main()
