import unittest
import json
import pathlib
import subprocess
from ops.audits.g3_2_fire_summary import check_precheck

class TestG3_2FireSummary(unittest.TestCase):
    def test_selftest_success(self):
        # Verify that running the script with --selftest returns 0 and contains the success message
        result = subprocess.run(["python3", "ops/audits/g3_2_fire_summary.py", "--selftest"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: G3_2_FIRE_SUMMARY_SELFTEST_OK", result.stdout)

    def test_core_denominators(self):
        # Verify the core denominator identity in ops/audits/g3_2_fire_summary.json
        # We need to read the actual file and check its content
        manifest_path = pathlib.Path("ops/audits/g3_2_fire_summary.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        claims = data.get("claims", {})
        total = claims.get("total")
        pass_val = claims.get("pass")
        fail_val = claims.get("fail")
        unknown_val = claims.get("unknown")
        
        self.assertEqual(total, 26)
        self.assertEqual(pass_val + fail_val + unknown_val, total)

        cost = data.get("cost", {})
        answer_tokens_known = cost.get("answer_tokens_known")
        extract_tokens_known = cost.get("extract_tokens_known")
        tokens_total = cost.get("tokens_total")
        
        self.assertEqual(answer_tokens_known + extract_tokens_known, tokens_total)
        self.assertEqual(tokens_total, 128923)

        h1 = data.get("h1", {})
        self.assertEqual(h1.get("verdict"), "H1_REFUTED")

if __name__ == "__main__":
    unittest.main()
