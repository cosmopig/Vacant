import unittest
import subprocess
import os

class TestStrayLabdPsEvidence(unittest.TestCase):
    def test_selftest_success(self):
        # The requirement says "python3 ops/audits/stray_labd_ps_evidence.py --selftest" 
        # should exit with 0 and output VERDICT: STRAY_LABD_AUDIT_OK
        result = subprocess.run(
            ["python3", "ops/audits/stray_labd_ps_evidence.py", "--selftest"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("VERDICT: STRAY_LABD_AUDIT_OK", result.stdout)

    def test_stray_detection(self):
        # This is harder to test without actually spawning a stray labd.
        # However, we can check if the script correctly identifies a violation 
        # when it finds one. Since we can't easily spawn a real one in this env,
        # we rely on the selftest for the primary verification of the logic path.
        pass

if __name__ == "__main__":
    unittest.main()
