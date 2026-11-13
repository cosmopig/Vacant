#!/usr/bin/env python3
"""smoke_opencode 結案複核量具單元測試。
使用 ~/dev/Vacant/.venv/bin/python 執行。
"""
import unittest
from pathlib import Path
import json
import sys

# 使用指定的 Python 環境路徑 (如果可能，這裡會被環境變數或直接呼叫決定)
# 但為了讓 pytest 能跑，我們寫成標準的 unittest 並在外部指定 python 路徑。

sys.path.append(str(Path(__file__).resolve().parents[2]))

from ops.audits.smoke_opencode_closure_check import check

class TestSmokeOpencodeClosureCheck(unittest.TestCase):
    def setUp(self):
        # 基礎資料 (符合要求的正確值)
        self.valid_report = {
            "cells_scored": 2,
            "infra": [],
            "per_arm": {
                "A": {"n": 1, "pass": 0, "rate": 0.0},
                "C": {"n": 1, "pass": 0, "rate": 0.0, "vacant_sha": ["dd2c67464eff9ba2eec478d60cf245bc601b2a57"]}
            },
            "paired": {
                "A_vs_C": {
                    "pairs": 1,
                    "A_only": 0,
                    "C_only": 0,
                    "mcnemar_p_two_sided": 1.0
                }
            }
        }
        # 注意：PACKET_TITLE 在腳本中是 "# smoke_opencode · OpenCode 能不能在格子裡跑——冒煙評測（2026-11-13）"
        self.valid_packet = "# smoke_opencode · OpenCode 能不能在格子裡跑——冒煙評測（2026-11-13）\nContent..."
        # 注意：BACKLOG_KEY 在腳本中是 "smoke_opencode 完賽檢查"
        self.valid_backlog = "Some other stuff\n- [x] **smoke_opencode 完賽檢查）判定 GO\nMore stuff"

    def test_valid_case(self):
        """驗證所有條件正確時通過 (空列表)"""
        report_json = json.dumps(self.valid_report)
        violations = check(report_json, self.valid_packet, self.valid_backlog)
        self.assertEqual(len(violations), 0, f"Expected no violations, got: {violations}")

    def test_invalid_cells_scored(self):
        """驗證 cells_scored 不正確時報錯"""
        report = self.valid_report.copy()
        report["cells_scored"] = 3
        violations = check(json.dumps(report), self.valid_packet, self.valid_backlog)
        self.assertTrue(any("cells_scored" in v for v in violations))

    def test_invalid_infra(self):
        """驗證 infra 不為空時報錯"""
        report = self.valid_report.copy()
        report["infra"] = ["some_error"]
        violations = check(json.dumps(report), self.valid_packet, self.valid_backlog)
        self.assertTrue(any("infra" in v for v in violations))

    def test_invalid_arm_rate(self):
        """驗證 Arm A rate 不正確時報錯"""
        report = self.valid_report.copy()
        report["per_arm"]["A"]["rate"] = 0.5
        violations = check(json.dumps(report), self.valid_packet, self.valid_backlog)
        self.assertTrue(any("per_arm[A]" in v for v in violations))

    def test_invalid_mcnemar(self):
        """驗證 McNemar p 不正確時報錯"""
        report = self.valid_report.copy()
        report["paired"]["A_vs_C"]["mcnemar_p_two_sided"] = 0.5
        violations = check(json.dumps(report), self.valid_packet, self.valid_backlog)
        self.assertTrue(any("mcnemar_p_two_sided" in v for v in violations))

    def test_invalid_vacant_sha(self):
        """驗證 C 臂 vacant_sha 不正確時報錯"""
        report = self.valid_report.copy()
        report["per_arm"]["C"]["vacant_sha"] = ["wrong_sha"]
        violations = check(json.dumps(report), self.valid_packet, self.valid_backlog)
        self.assertTrue(any("vacant_sha" in v for v in violations))

    def test_invalid_packet_title(self):
        """驗證 packet 標題不正確時報錯"""
        violations = check(json.dumps(self.valid_report), "Wrong Title", self.valid_backlog)
        self.assertTrue(any("packet" in v for v in violations))

    def test_invalid_backlog_checkbox(self):
        """驗證 BACKLOG 未勾選時報錯"""
        # 故意把 [x] 改成 [ ]
        bad_backlog = "Line1\n- [ ] **smoke_opencode 完賽檢查）判定 GO\nLine3"
        violations = check(json.dumps(self.valid_report), self.valid_packet, bad_backlog)
        self.assertTrue(any("未勾選 [x]" in v for v in violations))

if __name__ == "__main__":
    unittest.main()
