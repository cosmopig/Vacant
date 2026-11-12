import unittest
import json
import pathlib
import sys
from ops.audits.g3_2_fire_summary import selftest

class TestG3_2FireSummary(unittest.TestCase):
    def test_selftest(self):
        # We want to run the script with --selftest and check output/exit code
        # Since we are in a test, we can just call it or use subprocess
        import subprocess
        result = subprocess.run(["python3", "ops/audits/g3_2_fire_summary.py", "--selftest"], 
                                 capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: G3_2_FIRE_SUMMARY_SELFTEST_OK", result.stdout)

    def test_json_consistency(self):
        # Verify the core denominator identity in ops/audits/g3_2_fire_summary.json
        # Note: This file is frozen, so we just read it and check.
        path = pathlib.Path("ops/audits/g3_2_fire_summary.json")
        if not path.exists():
            self.skipTest(f"Expected {path} to exist")
        
        data = json.loads(path.read_text(encoding="utf-8"))
        claims = data["claims"]
        cost = data["cost"]
        
        self.assertEqual(claims["total"], 26)
        self.assertEqual(claims["pass"] + claims["fail"] + claims["unknown"], 26)
        self.assertEqual(cost["answer_tokens_known"] + cost["extract_tokens_known"], cost["tokens_total"])
        self.assertEqual(cost["tokens_total"], 128923)
        self.assertEqual(data["h1"]["verdict"], "H1_REFUTED")

if __name__ == "__main__":
    unittest.main()
