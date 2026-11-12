import unittest
import json
import pathlib
from ops.audits import g3_2_precheck

class TestG32Precheck(unittest.TestCase):
    def setUp(self):
        # Valid manifest for base tests
        self.valid_manifest = {
            "schema": "vacant.reqloop.g3gate.plan/1",
            "tasks": [
                {"task_id": "dab_725", "files": {"input.txt": "sha1"}},
                {"task_id": "dab_587", "files": {"input.txt": "sha2"}},
                {"task_id": "dab_657", "files": {"input.txt": "sha3"}},
                {"task_id": "dab_517", "files": {"input.txt": "sha4"}},
            ],
            "bank": {
                "seen_set": ["old_1"],
                "ordering": ["dab_725", "dab_587", "dab_657", "dab_517"]
            },
            "screening": {
                "output_sha256": "dummy_sha",
                "top4": ["dab_725", "dab_587", "dab_657", "dab_517"]
            },
            "budget": {
                "arms": ["full_rloop"],
                "max_cells": 4,
                "timeout_s_per_round": 300,
                "daily_token_cap": 2000000,
                "quota_fail_closed": True,
                "model_entry": "glm",
                "hard_token_cap": False,
                "cost_missing": "UNKNOWN"
            }
        }

    def test_schema_mismatch(self):
        manifest = self.valid_manifest.copy()
        manifest["schema"] = "wrong/schema"
        errors = g3_2_precheck.check_precheck(manifest)
        self.assertTrue(any("schema mismatch" in e for e in errors))

    def test_task_order_mismatch(self):
        manifest = self.valid_manifest.copy()
        manifest["tasks"] = [
            {"task_id": "dab_587", "files": {}},
            {"task_id": "dab_725", "files": {}},
            {"task_id": "dab_657", "files": {}},
            {"task_id": "dab_517", "files": {}},
        ]
        errors = g3_2_precheck.check_precheck(manifest)
        self.assertTrue(any("task 順序不符" in e for e in errors))

    def test_unseen_mismatch(self):
        manifest = self.valid_manifest.copy()
        manifest["bank"]["ordering"] = ["wrong_1", "dab_725", "dab_587", "dab_657", "dab_517"]
        errors = g3_2_precheck.check_precheck(manifest)
        self.assertTrue(any("unseen 前 4 ≠ tasks" in e for e in errors))

    def test_budget_mismatch(self):
        manifest = self.valid_manifest.copy()
        manifest["budget"]["max_cells"] = 10
        errors = g3_2_precheck.check_precheck(manifest)
        self.assertTrue(any("max_cells mismatch" in e for e in errors))

    def test_screen_sha_mismatch(self):
        manifest = self.valid_manifest.copy()
        manifest["screening"]["output_sha256"] = "wrong_sha"
        errors = g3_2_precheck.check_precheck(manifest, screen_stdout="dummy output")
        self.assertTrue(any("screen sha mismatch" in e for e in errors))

if __name__ == "__main__":
    unittest.main()
