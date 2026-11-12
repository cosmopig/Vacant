import json
import pathlib
import subprocess
import unittest
import ops.audits.g3_2_fire_summary as fs

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestG3_2FireSummary(unittest.TestCase):
    def test_selftest_success_and_six_controls(self):
        result = subprocess.run(
            ["python3", "ops/audits/g3_2_fire_summary.py", "--selftest"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("VERDICT: G3_2_FIRE_SUMMARY_SELFTEST_OK", result.stdout)
        for ctrl in ("h1_a0_refuted", "h1_pos_met", "h1_b_violated", "h1_b_met",
                     "tokens_empty_guard", "answer_sha_mismatch"):
            self.assertIn(f"PASS {ctrl}", result.stdout)

    def test_module_exports_h1_verdict_and_build(self):
        self.assertTrue( callable(getattr(fs, "h1_verdict", None)) )
        self.assertTrue( callable(getattr(fs, "build", None)) )
        self.assertTrue( callable(getattr(fs, "check_fire_summary", None)) )

    def test_core_denominators_and_check_fire_summary(self):
        summary_path = ROOT / "ops/audits/g3_2_fire_summary.json"
        raw_text = summary_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)

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

        self.assertEqual(fs.check_fire_summary({}, raw_text), [])
        tampered = json.loads(raw_text)
        tampered["claims"]["total"] = 99
        self.assertTrue(fs.check_fire_summary({}, json.dumps(tampered)))


if __name__ == "__main__":
    unittest.main()
