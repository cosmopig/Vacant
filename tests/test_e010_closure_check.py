import unittest
from pathlib import Path
from ops.audits.e010_closure_check import selftest

class TestE010ClosureCheck(unittest.TestCase):
    def test_selftest_success(self):
        # This test relies on the actual files being correct as per the ticket requirements
        # If they are, it should return 0 (success)
        result = selftest(Path("/home/user1/dev/ops/packets/e010_bigwork.md"),
                           Path("/home/user1/dev/ops/BACKLOG.md"))
        self.assertEqual(result, 0, f"Selftest failed with exit code {result}")

if __name__ == "__main__":
    unittest.main()
