import unittest
import subprocess
import os
import sys

class TestStrayLabdPsEvidence(unittest.TestCase):
    def test_audit_success_no_labd(self):
        # Ensure no labd is running (should be true in clean env)
        result = subprocess.run(
            ["python3", "ops/audits/stray_labd_ps_evidence.py"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: STRAY_LABD_AUDIT_OK", result.stdout)

    def test_audit_selftest(self):
        # The script should output VERDICT: STRAY_LABD_AUDIT_OK if no stray labd is found
        result = subprocess.run(
            ["python3", "ops/audits/stray_labd_ps_evidence.py", "--selftest"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: STRAY_LABD_AUDIT_OK", result.stdout)

if __name__ == "__main__":
    unittest.main()
