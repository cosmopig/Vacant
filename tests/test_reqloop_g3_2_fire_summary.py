import unittest
import json
from pathlib import Path
from ops.audits.g3_2_fire_summary import check_fire_summary

class TestFireSummary(unittest.TestCase):
    def test_h1a_success(self):
        # 4 cells, 1/4 = 1. Need >= 1 confirmed reverify with PASS/FAIL.
        rows = [
            {"task_id": "t1", "content_reverify": True, "status": "PASS"},
            {"task_id": "t2", "content_reverify": False, "status": "PASS"},
            {"task_id": "t3", "content_reverify": False, "status": "FAIL"},
            {"task_id": "t4", "content_reverify": False, "status": "UNKNOWN"},
        ]
        errors = check_fire_summary(rows)
        self.assertEqual(len(errors), 0)

    def test_h1a_failure(self):
        # 4 cells, 0 confirmed reverifies.
        rows = [
            {"task_id": "t1", "content_reverify": False, "status": "PASS"},
            {"task_id": "t2", "content_reverify": False, "status": "FAIL"},
            {"task_id": "t3", "content_reverify": False, "status": "UNKNOWN"},
            {"task_id": "t4", "content_reverify": False, "status": "UNKNOWN"},
        ]
        errors = check_fire_summary(rows)
        self.assertTrue(any("H1(a) failed" in e for e in errors))

    def test_h1b_success(self):
        # Gap is content_reverify=True and status="UNKNOWN"
        # Round 2 must have diff_fixed >= 1 and regressed=False
        rows = [
            {"task_id": "gap1", "content_reverify": True, "status": "UNKNOWN", "diff_fixed": 1, "regressed": False},
            {"task_id": "t2", "content_reverify": False, "status": "PASS"},
            {"task_id": "t3", "content_reverify": False, "status": "FAIL"},
            {"task_id": "t4", "content_reverify": False, "status": "UNKNOWN"},
        ]
        errors = check_fire_summary(rows)
        self.assertEqual(len(errors), 0)

    def test_h1b_failure_diff_fixed(self):
        rows = [
            {"task_id": "gap1", "content_reverify": True, "status": "UNKNOWN", "diff_fixed": 0, "regressed": False},
            {"task_id": "t2", "content_reverify": False, "status": "PASS"},
            {"task_id": "t3", "content_reverify": False, "status": "FAIL"},
            {"task_id": "t4", "content_reverify": False, "status": "UNKNOWN"},
        ]
        errors = check_fire_summary(rows)
        self.assertTrue(any("H1(b) failed" in e and "diff_fixed=0" in e for e in errors))

    def test_h1b_failure_regressed(self):
        rows = [
            {"task_id": "gap1", "content_reverify": True, "status": "UNKNOWN", "diff_fixed": 1, "regressed": True},
            {"task_id": "t2", "content_reverify": False, "status": "PASS"},
            {"task_id": "t3", "content_reverify": False, "status": "FAIL"},
            {"task_id": "t4", "content_reverify": False, "status": "UNKNOWN"},
        ]
        errors = check_fire_summary(rows)
        self.assertTrue(any("H1(b) failed" in e and "regressed=True" in e for e in errors))

    def test_superiority_claim(self):
        rows = [
            {"task_id": "t1", "content_reverify": True, "status": "PASS (Superior to baseline)"},
            {"task_id": "t2", "content_reverify": False, "status": "FAIL"},
            {"task_id": "t3", "content_reverify": False, "status": "UNKNOWN"},
            {"task_id": "t4", "content_reverify": False, "status": "UNKNOWN"},
        ]
        errors = check_fire_summary(rows)
        self.assertTrue(any("Superiority claim detected" in e for e in errors))

    def test_empty_rows(self):
        errors = check_fire_summary([])
        self.assertIn("empty rows", errors)

if __name__ == "__main__":
    unittest.main()
