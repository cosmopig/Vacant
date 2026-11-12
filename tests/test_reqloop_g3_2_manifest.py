import unittest
import json
import pathlib
import hashlib
from ops.audits.g3_2_precheck import check_precheck

REF = pathlib.Path("/home/user1/dev/ops/ref/bm_tasks/dabench")
LOCAL = pathlib.Path("/home/user1/dev/wt/worker/ops/reqloop/g3_2/tasks")

class TestG3_2Precheck(unittest.TestCase):
    def setUp(self):
        # Base valid manifest
        self.valid_manifest = {
            "schema": "vacant.reqloop.g3gate.plan/1",
            "tasks": [
                {"task_id": "dab_725", "files": {"f1": "sha1"}},
                {"task_id": "dab_587", "files": {"f2": "sha2"}},
                {"task_id": "dab_657", "files": {"f3": "sha3"}},
                {"task_id": "dab_517", "files": {"f4": "sha4"}},
            ],
            "bank": {
                "ordering": ["dab_725", "dab_587", "dab_657", "dab_517"],
                "seen_set": [],
            },
            "screening": {
                "output_sha256": "dummy_sha",
            },
            "budget": {
                "max_cells": 4,
                "timeout_s_per_round": 300,
                "daily_token_cap": 2000000,
                "quota_fail_closed": True,
                "model_entry": "glm",
                "hard_token_cap": False,
                "cost_missing": "UNKNOWN",
            },
            "arms": ["full_rloop"],
        }

    def test_valid_manifest_passes(self):
        # Create real files and update manifest with their hashes
        for tid in ["dab_725", "dab_587", "dab_657", "dab_517"]:
            (LOCAL / tid).mkdir(parents=True, exist_ok=True)
            (REF / tid).mkdir(parents=True, exist_ok=True)
            content = b"fixed_content"
            h = hashlib.sha256(content).hexdigest()
            (LOCAL / tid / "f1").write_bytes(content)
            (REF / tid / "f1").write_bytes(content)
            # Update manifest to match this hash for all 4 tasks
            for i, t in enumerate(self.valid_manifest["tasks"]):
                t["files"] = {"f1": h}

        # Mock screen_stdout to be valid
        dummy_screen = json.dumps({"top4": ["dab_725", "dab_587", "dab_657", "dab_517"]})
        dummy_sha = hashlib.sha256(dummy_screen.encode()).hexdigest()
        self.valid_manifest["screening"]["output_sha256"] = dummy_sha

        errors = check_precheck(self.valid_manifest, screen_stdout=dummy_screen)
        self.assertEqual(errors, [], f"Expected no errors, got {errors}")

    def test_n1_bad_sha(self):
        # Setup valid files first
        for tid in ["dab_725", "dab_587", "dab_657", "dab_517"]:
            (LOCAL / tid).mkdir(parents=True, exist_ok=True)
            (REF / tid).mkdir(parents=True, exist_ok=True)
            content = b"fixed_content"
            h = hashlib.sha256(content).hexdigest()
            (LOCAL / tid / "f1").write_bytes(content)
            (REF / tid / "f1").write_bytes(content)
        
        # Set manifest with correct hashes except for one
        for i, t in enumerate(self.valid_manifest["tasks"]):
            h = hashlib.sha256(b"fixed_content").hexdigest()
            t["files"] = {"f1": h}
        
        # Tamper with first task's sha
        self.valid_manifest["tasks"][0]["files"]["f1"] = "0" * 64
        
        errors = check_precheck(self.valid_manifest)
        self.assertTrue(any("local sha mismatch" in e or "ref sha mismatch" in e for e in errors))

    def test_n2_bad_order(self):
        # Setup valid files first
        for tid in ["dab_725", "dab_587", "dab_657", "dab_517"]:
            (LOCAL / tid).mkdir(parents=True, exist_ok=True)
            (REF / tid).mkdir(parents=True, exist_ok=True)
            content = b"fixed_content"
            h = hashlib.sha256(content).hexdigest()
            (LOCAL / tid / "f1").write_bytes(content)
            (REF / tid / "f1").write_bytes(content)

        # Set manifest with correct hashes
        for i, t in enumerate(self.valid_manifest["tasks"]):
            h = hashlib.sha256(b"fixed_content").hexdigest()
            t["files"] = {"f1": h}
        
        # Tamper with task order
        self.valid_manifest["tasks"][0]["task_id"] = "dab_039"
        errors = check_precheck(self.valid_manifest)
        self.assertTrue(any("task 順序不符" in e for e in errors))

    def test_n3_bad_screen_sha(self):
        # Setup valid files first
        for tid in ["dab_725", "dab_587", "dab_657", "dab_517"]:
            (LOCAL / tid).mkdir(parents=True, exist_ok=True)
            (REF / tid).mkdir(parents=True, exist_ok=True)
            content = b"fixed_content"
            h = hashlib.sha256(content).hexdigest()
            (LOCAL / tid / "f1").write_bytes(content)
            (REF / tid / "f1").write_bytes(content)

        # Set manifest with correct hashes
        for i, t in enumerate(self.valid_manifest["tasks"]):
            h = hashlib.sha256(b"fixed_content").hexdigest()
            t["files"] = {"f1": h}
        
        dummy_screen = json.dumps({"top4": ["dab_725", "dab_587", "dab_657", "dab_517"]})
        self.valid_manifest["screening"]["output_sha256"] = "0" * 64
        
        errors = check_precheck(self.valid_manifest, screen_stdout=dummy_screen)
        self.assertTrue(any("screen sha mismatch" in e for e in errors))

    def test_n4_bad_budget(self):
        # Setup valid files first
        for tid in ["dab_725", "dab_587", "dab_657", "dab_517"]:
            (LOCAL / tid).mkdir(parents=True, exist_ok=True)
            (REF / tid).mkdir(parents=True, exist_ok=True)
            content = b"fixed_content"
            h = hashlib.sha256(content).hexdigest()
            (LOCAL / tid / "f1").write_bytes(content)
            (REF / tid / "f1").write_bytes(content)

        # Set manifest with correct hashes
        for i, t in enumerate(self.valid_manifest["tasks"]):
            h = hashlib.sha256(b"fixed_content").hexdigest()
            t["files"] = {"f1": h}
        
        # Tamper with budget
        self.valid_manifest["budget"]["timeout_s_per_round"] = 999
        errors = check_precheck(self.valid_manifest)
        self.assertTrue(any("timeout_s_per_round mismatch" in e for e in errors))

if __name__ == "__main__":
    unittest.main()
