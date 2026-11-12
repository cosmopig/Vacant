"""G3.3 H0 門跨獨立呼叫穩定性（P20261112_0119-2）：--selftest 正/負/解析失敗控制＋退出碼。
0 模型呼叫；不寫真實報告（--run 才寫）。"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
STAB = ["python3", "ops/audits/g3_3_h0_stability.py", "--selftest"]
REPORT = ROOT / "ops/audits/g3_3_h0_stability_report.json"


class TestG3_3Stability(unittest.TestCase):
    def test_selftest_ok(self):
        """正控制（mock ≥1 確定性→H2_MET）＋負控制（mock 0 確定性→H2_REFUTED）＋history 機械讀取；exit 0。"""
        r = subprocess.run(STAB, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERDICT: G3_3_STABILITY_SELFTEST_OK", r.stdout)

    def test_controls_named(self):
        """自測明列三控制：正控制 H2_MET、負控制 H2_REFUTED、解析失敗 fail-closed（皆 PASS）。"""
        r = subprocess.run(STAB, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for name in ("pos_h2_met", "neg_h2_refuted", "bad_fail_closed", "history_two_calls"):
            self.assertIn(f"PASS {name}", r.stdout, r.stdout)

    def test_no_report_written(self):
        """--selftest 0 模型呼叫：真實報告檔不因自測新出現（存在狀態不變）。"""
        existed = REPORT.exists()
        r = subprocess.run(STAB, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(REPORT.exists(), existed)


if __name__ == "__main__":
    unittest.main()
