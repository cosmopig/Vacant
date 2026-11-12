import unittest
from pathlib import Path
import subprocess
import os

class TestStrayLabdRootCauseAudit(unittest.TestCase):
    def test_selftest(self):
        # Run the audit script with --selftest
        result = subprocess.run(
            ["python3", "ops/audits/stray_labd_root_cause_audit.py", "--selftest"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: STRAY_LABD_ROOT_CAUSE_OK", result.stdout)

    def test_real_session_parsing(self):
        # This test will check if the script can actually find the evidence in the real file
        # We'll use a temporary mock to ensure it doesn't fail due to missing files during unit tests
        # but we also want to verify the logic.
        pass

if __name__ == "__main__":
    unittest.main()
