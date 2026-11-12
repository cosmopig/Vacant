import unittest
import json
import pathlib
from ops.audits import g3_2_fire_summary

class TestG3_2FireSummary(unittest.TestCase):
    def setUp(self):
        # Valid result for base tests (H1 MET, 4 cells)
        self.valid_result = {
            "schema": "vacant.reqloop.g3.result/1",
            "cells": [
                {
                    "task": "dab_725", "arm": "full_rloop", "status": "ok", "error": None, "answer": "@x[1]",
                    "answer_sha256": hashlib.sha256(b"@x[1]").hexdigest(),
                    "rounds": [{"round": 1, "usages": [{"calls": 1, "tokens": 10}]}],
                    "content_reverify": {"enabled": True, "rounds": [], "final_verdict": None, "diff": None}
                },
                {
                    "task": "dab_587", "arm": "full_rloop", "status": "ok", "error": None, "answer": "@x[1]",
                    "answer_sha256": hashlib.sha256(b"@x[1]").hexdigest(),
                    "rounds": [{"round": 1, "usages": [{"calls": 1, "tokens": 10}]}],
                    "content_reverify": {"enabled": True, "rounds": [], "final_verdict": None, "diff": None}
                },
                {
                    "task": "dab_657", "arm": "full_rloop", "status": "ok", "error": None, "answer": "@x[1]",
                    "answer_sha256": hashlib.sha256(b"@x[1]").hexdigest(),
                    "rounds": [{"round": 1, "usages": [{"calls": 1, "tokens": 10}]}],
                    "content_reverify": {"enabled": True, "rounds": [], "final_verdict": None, "diff": None}
                },
                {
                    "task": "dab_517", "arm": "full_rloop", "status": "ok", "error": None, "answer": "@x[1]",
                    "answer_sha256": hashlib.sha256(b"@x[1]").hexdigest(),
                    "rounds": [{"round": 1, "usages": [{"calls": 1, "tokens": 10}]}],
                    "content_reverify": {"enabled": True, "rounds": [], "final_verdict": None, "diff": None}
                },
            ],
            "tasks": [
                {"task_id": "dab_725", "n_requirements": 1},
                {"task_id": "dab_587", "n_requirements": 1},
                {"task_id": "dab_657", "n_requirements": 1},
                {"task_id": "dab_517", "n_requirements": 1},
            ],
            "totals": {"tokens": 40, "model_calls": 0},
            "quota": {"known_tokens": 40, "daily_token_cap": 2000000}
        }

    def test_build_success(self):
        """Valid result produces H1_MET and correct claim counts."""
        raw = json.dumps(self.valid_result).encode()
        out, problems = g3_2_fire_summary.build(raw, pathlib.Path("dummy"))
        self.assertEqual(len(problems), 0)
        self.assertEqual(out["claims"]["total"], 4)
        self.assertEqual(out["h1"]["verdict"], "H1_MET")

    def test_schema_mismatch(self):
        res = self.valid_result.copy()
        res["schema"] = "wrong/schema"
        raw = json.dumps(res).encode()
        _, problems = g3_2_fire_summary.build(raw, pathlib.Path("dummy"))
        self.assertTrue(any("schema 漂移" in p for p in problems))

    def test_cell_order_mismatch(self):
        res = self.valid_result.copy()
        # Swap first two cells
        res["cells"] = res["cells"][1:] + res["cells"][:1]
        raw = json.dumps(res).encode()
        _, problems = g3_2_fire_summary.build(raw, pathlib.Path("dummy"))
        self.assertTrue(any("cells 順序/集合漂移" in p for p in problems))

    def test_tokens_empty_guard(self):
        res = self.valid_result.copy()
        res["cells"] = []
        res["totals"] = {"tokens": 0}
        raw = json.dumps(res).encode()
        _, problems = g3_2_fire_summary.build(raw, pathlib.Path("dummy"))
        self.assertTrue(any("tokens 重算空集" in p for p in problems))

    def test_answer_sha_mismatch(self):
        res = self.valid_result.copy()
        res["cells"][0]["answer"] = "new_answer"
        # Keep old sha
        raw = json.dumps(res).encode()
        _, problems = g3_2_fire_summary.build(raw, pathlib.Path("dummy"))
        self.assertTrue(any("answer_sha256 重算不符" in p for p in problems))

    def test_selftest(self):
        """Verify the --selftest mode passes all 6 controls."""
        r = subprocess.run(["python3", "ops/audits/g3_2_fire_summary.py", "--selftest"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VERDICT: G3_2_FIRE_SUMMARY_SELFTEST_OK", r.stdout)

if __name__ == "__main__":
    unittest.main()
