import unittest
import subprocess
from pathlib import Path
import json

class TestE010ClosureCheck(unittest.TestCase):
    def setUp(self):
        self.packet = Path("/home/user1/dev/wt/worker/ops/vlab/packets/e010_bigwork.md")
        self.report = Path("/srv/vlab/runs/e010_bigwork_pi_AC/REPORT.json")
        self.cell_c = Path("/srv/vlab/runs/e010_bigwork_pi_AC/bigwork-bw_repo_readme-pi-C-r1/cell.json")

    def test_selftest(self):
        # Run the script with --selftest and check for success
        result = subprocess.run(
            ["python3", "/home/user1/dev/wt/worker/ops/audits/e010_closure_check.py", "--selftest"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: E010_CLOSURE_OK", result.stdout)

    def test_actual_closure(self):
        # Run the script without --selftest and check for success
        result = subprocess.run(
            ["python3", "/home/user1/dev/wt/worker/ops/audits/e010_closure_check.py"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: E010_CLOSURE_OK", result.stdout)

if __name__ == "__main__":
    unittest.main()
