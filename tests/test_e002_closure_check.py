import unittest
from pathlib import Path
import subprocess
import json

class TestE002ClosureCheck(unittest.TestCase):
    def setUp(self):
        self.script = Path("ops/audits/e002_closure_check.py")
        self.assert_is_file(self.script)

    def assert_is_file(self, path: Path):
        self.assertTrue(path.exists(), f"Expected file {path} to exist.")
        self.assertTrue(path.is_file(), f"Expected {path} to be a file.")

    def test_script_execution_logic(self):
        """Test that the script correctly identifies violations in a dummy report."""
        # Valid-looking but incorrect data
        dummy_report = {
            "cells_scored": 100,  # Should be 170
            "infra": [1, 2],       # Should be 9
            "per_arm": {
                "A": {"n": 34, "pass": 18, "rate": 0.5294},
                "C": {"n": 34, "pass": 22, "rate": 0.6471},
                "H": {"n": 34, "pass": 15, "rate": 0.4412},
                "M": {"n": 34, "pass": 15, "rate": 0.4412},
                "S": {"n": 34, "pass": 20, "rate": 0.5882}
            },
            "paired": {
                "A_vs_C": {"mcnemar_p_two_sided": 0.99}, # Should be 0.3438
                "A_vs_H": {"mcnemar_p_two_sided": 0.4531},
                "A_vs_M": {"mcnemar_p_two_sided": 0.5078},
                "A_vs_S": {"mcnemar_p_two_sided": 0.7266}
            }
        }
        dummy_report_path = Path("dummy_report.json")
        dummy_report_path.write_text(json.dumps(dummy_report))

        try:
            # We use --report to point to our dummy file
            result = subprocess.run(
                [str(self.script), "--report", str(dummy_report_path)],
                capture_output=True,
                text=True
            )
            # Should have violations (return code 1)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("REPORT cells_scored=100 != 170", result.stdout)
            self.assertIn("REPORT infra 數=2 != 9", result.stdout)
            self.assertIn("REPORT A_vs_C mcnemar_p_two_sided=0.99 != 0.3438", result.stdout)
        finally:
            if dummy_report_path.exists():
                dummy_report_path.unlink()

    def test_script_handles_missing_files(self):
        """Verify script doesn't crash when files are missing (it should just report them)."""
        result = subprocess.run(
            [str(self.script)],
            capture_output=True,
            text=True
        )
        # It should exit with 1 because it can't find the default files
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing file", result.stdout)

if __name__ == "__main__":
    unittest.main()
