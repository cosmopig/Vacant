import unittest
import json
import pathlib
import subprocess
from ops.audits.g3_2_precheck import check_precheck

REF = pathlib.Path("/home/user1/dev/ops/ref/bm_tasks/dabench")
LOCAL = pathlib.Path("/home/user1/dev/wt/worker/ops/reqloop/g3_2/tasks")

class TestG3_2Precheck(unittest.TestCase):
    def setUp(self):
        # Mock manifest based on ops/reqloop/g3_2/manifest.json
        self.valid_manifest = {
            "schema": "vacant.reqloop.g3gate.plan/1",
            "tasks": [
                {"task_id": "dab_725", "files": {"f1": "sha1"}},
                {"task_id": "dab_587", "files": {"f2": "sha2"}},
                {"task_id": "dab_657", "files": {"f3": "sha3"}},
                {"task_id": "dab_517", "files": {"f4": "sha4"}}
            ],
            "bank": {
                "ordering": ["dab_725", "dab_587", "dab_657", "dab_517"],
                "seen_set": []
            },
            "screening": {
                "output_sha256": "dummy_sha",
                "top4": ["dab_725", "dab_587", "dab_657", "dab_517"]
            },
            "budget": {
                "max_cells": 4,
                "timeout_s_per_round": 300,
                "daily_token_cap": 2000000,
                "quota_fail_closed": True,
                "model_entry": "glm",
                "hard_token_cap": False,
                "cost_missing": "UNKNOWN",
                "arms": ["full_rloop"]
            }
        }

    def test_valid_manifest(self):
        # Mock files in local and ref
        for tid in ["dab_725", "dab_587", "dab_657", "dab_517"]:
            (LOCAL / tid).mkdir(parents=True, exist_ok=True)
            (REF / tid).mkdir(parents=True, exist_ok=True)
            for rel in ["f1", "f2", "f3", "f4"]:
                # We need to make sure we only create files for the correct tids if they were different, 
                # but here all 4 are expected.
                (LOCAL / tid / rel).write_text("content")
                (REF / tid / rel).write_text("content")

        import hashlib
        for tid in ["dab_725", "dab_587", "dab_657", "dab_517"]:
            idx = ["dab_725", "dab_587", "dab_657", "dab_517"].index(tid)
            rel = f"f{idx+1}"
            self.valid_manifest["tasks"][idx]["files"][rel] = hashlib.sha256(b"content").hexdigest()

        dummy_stdout = 'dummy\n{"top4": ["dab_725", "dab_587", "dab_657", "dab_517"]}'
        self.valid_manifest["screening"]["output_sha256"] = hashlib.sha256(dummy_stdout.encode("utf-8")).hexdigest()

        errors = check_precheck(self.valid_manifest, screen_stdout=dummy_stdout, 
                                 ref_dir=REF, local_dir=LOCAL)
        self.assertEqual(errors, [])

    def test_bad_sha(self):
        for tid in ["dab_725", "dab_587", "dab_657", "dab_517"]:
            idx = ["dab_725", "dab_587", "dab_657", "dab_517"].index(tid)
            rel = f"f{idx+1}"
            (LOCAL / tid / rel).write_text("content")
            (REF / tid / rel).write_text("content")
        self.valid_manifest["tasks"][0]["files"]["f1"] = "wrong_sha"
        errors = check_precheck(self.valid_manifest, screen_stdout="dummy\n{\"top4\": [\"dab_725\", \"dab_587\", \"dab_657\", \"dab_517\"]}", 
                                 ref_dir=REF, local_dir=LOCAL)
        self.assertTrue(any("sha mismatch" in e for e in errors))

    def test_bad_order(self):
        # Mock files
        for tid in ["dab_725", "dab_587", "dab_657", "dab_517"]:
            idx = ["dab_725", "dab_587", "dab_657", "dab_517"].index(tid)
            rel = f"f{idx+1}"
            (LOCAL / tid / rel).write_text("content")
            (REF / tid / rel).write_text("content")
        self.valid_manifest["tasks"][0]["task_id"] = "dab_039"
        errors = check_precheck(self.valid_manifest, screen_stdout="dummy\n{\"top4\": [\"dab_725\", \"dab_587\", \"dab_657\", \"dab_517\"]}", 
                                 ref_dir=REF, local_dir=LOCAL)
        self.assertTrue(any("順序不符" in e for e in errors))

    def test_bad_screen_sha(self):
        for tid in ["dab_725", "dab_587", "dab_657", "dab_517"]:
            idx = ["dab_725", "dab_587", "dab_657", "dab_517"].index(tid)
            rel = f"f{idx+1}"
            (LOCAL / tid / rel).write_text("content")
            (REF / tid / rel).write_text("content")
        self.valid_manifest["screening"]["output_sha256"] = "wrong_sha"
        errors = check_precheck(self.valid_manifest, screen_stdout="dummy\n{\"top4\": [\"dab_725\", \"dab_587\", \"dab_657\", \"dab_517\"]}", 
                                 ref_dir=REF, local_dir=LOCAL)
        self.assertTrue(any("screen sha mismatch" in e for e in errors))

    def test_bad_budget(self):
        for tid in ["dab_725", "dab_587", "dab_657", "dab_517"]:
            idx = ["dab_725", "dab_587", "dab_657", "dab_517"].index(tid)
            rel = f"f{idx+1}"
            (LOCAL / tid / rel).write_text("content")
            (REF / tid / rel).write_text("content")
        self.valid_manifest["budget"]["timeout_s_per_round"] = 999
        errors = check_precheck(self.valid_manifest, screen_stdout="dummy\n{\"top4\": [\"dab_725\", \"dab_587\", \"dab_657\", \"dab_517\"]}", 
                                 ref_dir=REF, local_dir=LOCAL)
        self.assertTrue(any("timeout_s_per_round mismatch" in e for e in errors))

    def test_missing_ref_fail_closed(self):
        # Ensure ref_dir is a non-existent path or similar to trigger fail-closed if needed
        # In check_precheck, it checks lp.is_file() and rp.is_file(). 
        # If rp is not a file, it adds an error.
        self.valid_manifest["tasks"][0]["files"]["f1"] = "sha1"
        errors = check_precheck(self.valid_manifest, screen_stdout="dummy\n{\"top4\": [\"dab_725\", \"dab_587\", \"dab_657\", \"dab_517\"]}", 
                                 ref_dir=pathlib.Path("/non/existent"), local_dir=LOCAL)
        self.assertTrue(any("missing ref" in e for e in errors))
