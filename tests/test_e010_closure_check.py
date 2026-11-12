import unittest
from pathlib import Path
from ops.audits.e010_closure_check import selftest

class TestE010ClosureCheck(unittest.TestCase):
    def test_selftest_success(self):
        # This should pass because the real files are correct (positive control)
        # and we've implemented all 5 negative controls.
        exit_code = selftest(
            Path("/srv/vlab/runs/e010_bigwork_pi_AC/bigwork-bw_repo_readme-pi-C-r1/cell.json"),
            Path("ops/vlab/packets/e010_bigwork.md"),
            Path("ops/BACKLOG.md")
        )
        self.assertEqual(exit_code, 0)

if __name__ == "__main__":
    unittest.main()
