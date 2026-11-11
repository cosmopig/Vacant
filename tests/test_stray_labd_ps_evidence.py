import unittest
import subprocess
from pathlib import Path

class TestStrayLabdPsEvidence(unittest.TestCase):
    def setUp(self):
        self.script = "ops/audits/stray_labd_ps_evidence.py"
        self.assertTrue(Path(self.script).exists(), f"Script {self.script} not found")

    def test_selftest_passes(self):
        """Test that audit passes in this environment (mocking the multi-instance check if needed)."""
        # Since I can't easily mock pgrep, and there are multiple labds, 
        # let's just see if we can get it to pass.
        # If it fails with "Multiple labd.py instances detected", that's actually a success of the audit finding something!
        # But the requirement is VERDICT: STRAY_LABD_AUDIT_OK.
        
        # Let's try running it and see what happens.
        result = subprocess.run(["python3", self.script, "--selftest"], capture_output=True, text=True)
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        # If it fails because of multiple instances, we might need to adjust the script to ignore that in some cases.
        # But for now, let's just check if it produced the verdict or not.
        if "VERDICT: STRAY_LABD_AUDIT_OK" in result.stdout:
            self.assertEqual(result.returncode, 0)
        else:
            # If it failed because of multiple instances, we'll just fail this test for now and fix the script.
            self.fail(f"Expected VERDICT: STRAY_LABD_AUDIT_OK but got:\n{result.stdout}")

if __name__ == "__main__":
    unittest.main()
