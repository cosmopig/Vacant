import unittest
import subprocess
from pathlib import Path
import sys

# Add the current directory to path so we can import ops.audits
sys.path.append(str(Path(__file__).parent.parent))

class TestG3_1Manifest(unittest.TestCase):
    def test_precheck_success(self):
        """Test that precheck passes with correct files."""
        # This will run the actual check against /home/user1/dev/ops/ref/bm_tasks/dabench/
        # Since we just verified those hashes, it should pass.
        result = subprocess.run(
            ["python3", "ops/audits/g3_1_precheck.py", "--selftest"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: G3_1_PRECHECK_OK", result.stdout)

    def test_g3_1_dry_run_success(self):
        """G3 管線官方乾跑（plan schema＋凍結＋預算）：exit 0、DRY-RUN OK、0 model calls。"""
        result = subprocess.run(
            ["python3", "-m", "vacant_network.reqloop.g3",
             "--manifest", "ops/reqloop/g3_1/manifest.json", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DRY-RUN OK", result.stdout)
        self.assertIn("0 模型呼叫", result.stdout)

if __name__ == "__main__":
    unittest.main()
