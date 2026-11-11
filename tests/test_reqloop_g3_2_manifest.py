import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
MANIFEST = "ops/reqloop/g3_2/manifest.json"
DRY = ["python3", "-m", "vacant_network.reqloop.g3", "--manifest", MANIFEST, "--dry-run"]

class TestG3_2Manifest(unittest.TestCase):
    def test_precheck_success(self):
        """G3.2 預檢查：sha256 雙核（local==ref==manifest）＋選題一致＋screen hash；VERDICT OK。"""
        r = subprocess.run(["python3", "ops/audits/g3_2_precheck.py", "--selftest"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERDICT: G3_2_PRECHECK_OK", r.stdout)

    def test_dry_run_success(self):
        """G3 管線官方乾跑（plan schema＋凍結＋預算）：exit 0、DRY-RUN OK、0 model calls。"""
        r = subprocess.run(DRY, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("DRY-RUN OK", r.stdout)
        self.assertIn("0 模型呼叫", r.stdout)

    def test_cell_order_frozen(self):
        """乾跑 4 格順序＝凍結選題清單（725→587→657→517），full_rloop 臂、content_reverify 開。"""
        r = subprocess.run(DRY, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        pos = [r.stdout.index(f"CELL dab_{t}/full_rloop:") for t in ("725", "587", "657", "517")]
        self.assertEqual(pos, sorted(pos))
        self.assertIn("content_reverify=True", r.stdout)

if __name__ == "__main__":
    unittest.main()
