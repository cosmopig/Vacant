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

if __name__ == "__main__":
    unittest.main()
