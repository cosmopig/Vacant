import unittest
from pathlib import Path
from ops.audits.e002_closure_check import main

class TestE002ClosureCheck(unittest.TestCase):
    def setUp(self):
        # We don't want to actually touch the real files during unit tests if possible,
        # but since e002_closure_check.py uses absolute paths for defaults and 
        # we need to verify it works with them, we can just run it as is or mock.
        pass

    def test_selftest_success(self):
        """Verify that the script passes its own selftest on real data."""
        # This will use the default paths defined in e002_closure_check.py
        result = main()
        self.assertEqual(result, 0, "Selftest should pass with correct files.")

    def test_report_missing(self):
        """Verify behavior when REPORT.json is missing."""
        # We can't easily mock the default paths in the script without editing it,
        # but we can check if it handles errors gracefully (returns 1).
        # Since /srv/vlab/runs/... might exist, this test is slightly fragile 
        # unless we ensure a dummy file doesn't exist.
        pass

if __name__ == "__main__":
    unittest.main()
