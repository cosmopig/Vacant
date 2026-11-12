import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
MANIFEST = "ops/reqloop/g3_3/manifest.json"
DRY = ["python3", "-m", "vacant_network.reqloop.g3", "--manifest", MANIFEST, "--dry-run"]

class TestG3_3Manifest(unittest.TestCase):
    def test_precheck_success(self):
        """G3.3 預檢查：sha256 雙核（local==ref==manifest）＋選題一致＋選題規則機械核；VERDICT OK。"""
        r = subprocess.run(["python3", "ops/audits/g3_3_precheck.py", "--selftest"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERDICT: G3_3_PRECHECK_OK", r.stdout)

    def test_dry_run_success(self):
        """G3 管線官方乾跑（plan schema＋凍結＋預算）：exit 0、DRY-RUN OK、0 model calls。"""
        r = subprocess.run(DRY, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("DRY-RUN OK", r.stdout)
        self.assertIn("0 模型呼叫", r.stdout)

    def test_cell_frozen_single(self):
        """1 格＝dab_725×full_rloop（唯一目標題）；content_reverify 開；其餘 3 題不在格單。"""
        r = subprocess.run(DRY, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CELL dab_725/full_rloop:", r.stdout)
        self.assertIn("content_reverify=True", r.stdout)
        self.assertNotIn("CELL dab_587/full_rloop:", r.stdout)
        self.assertNotIn("CELL dab_657/full_rloop:", r.stdout)
        self.assertNotIn("CELL dab_517/full_rloop:", r.stdout)

if __name__ == "__main__":
    unittest.main()
