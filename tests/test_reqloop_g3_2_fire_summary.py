import unittest
import json
import pathlib
from ops.audits.g3_2_fire_summary import check_fire_summary

class TestG3_2FireSummary(unittest.TestCase):
    def test_selftest_success(self):
        # This test is slightly different from the requirement because we want to 
        # verify that running the script with --selftest works as expected.
        # The requirement says: "驗證 python3 ops/audits/g3_2_fire_summary.py --selftest ... 退出碼為 0 且輸出含 VERDICT: G3_2_FIRE_SUMMARY_SELFTEST_OK"
        import subprocess
        result = subprocess.run(
            ["python3", "ops/audits/g3_2_fire_summary.py", "--selftest"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: G3_2_FIRE_SUMMARY_SELFTEST_OK", result.stdout)

    def test_core_denominators(self):
        # 驗證 ops/audits/g3_2_fire_summary.json 的核心分母恆等式：
        # claims["total"] == 26
        # claims["pass"] + claims["fail"] + claims["unknown"] == 26
        # cost["answer_tokens_known"] + cost["extract_tokens_known"] == cost["tokens_total"] == 128923
        # h1["verdict"] == "H1_REFUTED"
        with open("ops/audits/g3_2_fire_summary.json", "r") as f:
            data = json.load(f)
        
        claims = data["claims"]
        cost = data["cost"]
        h1 = data["h1"]

        self.assertEqual(claims["total"], 26)
        self.assertEqual(claims["pass"] + claims["fail"] + claims["unknown"], 26)
        self.assertEqual(cost["answer_tokens_known"] + cost["extract_tokens_known"], cost["tokens_total"])
        self.assertEqual(cost["tokens_total"], 128923)
        self.assertEqual(h1["verdict"], "H1_REFUTED")

if __name__ == "__main__":
    unittest.main()
