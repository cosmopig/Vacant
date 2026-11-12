import unittest
from pathlib import Path
from ops.audits.e010_closure_check import selftest

class TestE010ClosureCheck(unittest.TestCase):
    def setUp(self):
        self.runs = Path("/srv/vlab/runs/e010_bigwork_pi_AC")
        self.packet = Path("ops/packets/e010_bigwork.md")
        self.backlog = Path.home() / "dev/ops/BACKLOG.md"

    def test_selftest(self):
        # 驗證 --selftest 返回 0
        result = selftest(self.runs, self.packet, self.backlog)
        self.assertEqual(result, 0, f"selftest failed with exit code {result}")

if __name__ == "__main__":
    unittest.main()
