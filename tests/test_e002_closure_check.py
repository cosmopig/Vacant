import unittest
from pathlib import Path
from ops.audits.e002_closure_check import check

class TestE002ClosureCheck(unittest.TestCase):
    def test_report_cells_scored(self):
        report = '{"cells_scored": 169, "infra": [1]*9, "per_arm": {}, "paired": {}}'
        packet = "# Packet"
        backlog = "- [x] **e002 完賽收尾"
        violations = check(report, packet, backlog)
        self.assertIn("REPORT cells_scored=169 != 170", violations)

    def test_report_infra_count(self):
        report = '{"cells_scored": 170, "infra": [1], "per_arm": {}, "paired": {}}'
        packet = "# Packet"
        backlog = "- [x] **e002 完賽收尾"
        violations = check(report, packet, backlog)
        self.assertIn("REPORT infra 數=1 != 9", violations)

    def test_report_per_arm(self):
        # Missing C arm
        report = '{"cells_scored": 170, "infra": [1]*9, "per_arm": {"A": {"n":34,"pass":18,"rate":0.5294}}, "paired": {}}'
        packet = "# Packet"
        backlog = "- [x] **e002 完賽收尾"
        violations = check(report, packet, backlog)
        self.assertTrue(any("per_arm[C]" in v for v in violations))

    def test_packet_heading(self):
        report = '{"cells_scored": 170, "infra": [1]*9, "per_arm": {"A":{"n":34,"pass":18,"rate":0.5294},"C":{"n":34,"pass":22,"rate":0.6471},"H":{"n":34,"pass":15,"rate":0.4412},"M":{"n":34,"pass":15,"rate":0.4412},"S":{"n":34,"pass":20,"rate":0.5882}}, "paired": {}}'
        packet = "# Wrong Heading"
        backlog = "- [x] **e002 完賽收尾"
        violations = check(report, packet, backlog)
        self.assertIn("packet 缺標題: '## 4. 預註冊判準（發射前寫死）'", violations)

    def test_backlog_missing(self):
        report = '{"cells_scored": 170, "infra": [1]*9, "per_arm": {"A":{"n":34,"pass":18,"rate":0.5294},"C":{"n":34,"pass":22,"rate":0.6471},"H":{"n":34,"pass":15,"rate":0.4412},"M":{"n":34,"pass":15,"rate":0.4412},"S":{"n":34,"pass":20,"rate":0.5882}}, "paired": {}}'
        packet = "# Packet"
        backlog = ""
        violations = check(report, packet, backlog)
        self.assertIn("BACKLOG 找不到項: '**e002 完賽收尾'", violations)

if __name__ == "__main__":
    unittest.main()
