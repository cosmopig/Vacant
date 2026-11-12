import unittest
import json
import pathlib
from ops.audits.g3_2_fire_summary import build

# Mock paths for the test environment
REPO = pathlib.Path("/home/user1/dev/wt/worker")
RESULT = REPO / "ops" / "audits" / "g3_2_fire_summary.json"

class TestG3_2FireSummary(unittest.TestCase):
    def test_fire_summary_logic(self):
        # The issue was that _claims() returns an empty list if rounds is missing or empty,
        # and build() expects at least one claim to have a status for the "total" count? 
        # No, it's sum(1 for _, cl in all_claims). If all_claims is empty, total is 0.
        # In my dummy raw, I had rounds: [], so _claims returns [].
        # Let's provide a round with a claim.
        raw = json.dumps({
            "schema": "vacant.reqloop.g3.result/1",
            "cells": [
                {
                    "task": "dab_725",
                    "arm": "full_rloop",
                    "status": "ok",
                    "error": None,
                    "answer": "@x[1]",
                    "answer_sha256": "dummy_sha",
                    "rounds": [{"round": 1, "usages": [{"calls": 1, "tokens": 10}]}],
                    "hidden_after": "UNKNOWN",
                    "content_reverify": {
                        "enabled": True,
                        "rounds": [{"round": 1, "verdict": None, "gap_reason": None, "claims": [{"status": "PASS"}]}],
                        "final_verdict": None,
                        "diff": None,
                        "error": None,
                    },
                }
            ],
            "tasks": [
                {"task_id": "dab_725", "input_sha256": "sha1", "n_requirements": 1, "extract_usages": [], "extract_error": None, "unverified_reasons": []}
            ],
            "totals": {"tokens": 10, "model_calls": 1},
            "quota": {"known_tokens": 10, "daily_token_cap": 2000000},
            "arms": ["full_rloop"],
        }).encode()

        out, problems = build(raw, RESULT)
        self.assertEqual(out["claims"]["total"], 1)
        self.assertEqual(out["cost"]["tokens_total"], 10)
        # Since there is a PASS claim and no gap_reason, it should be H1_MET?
        # Wait, if gap_reason is None, then b = "not_applicable".
        # If a_met (det >= 1) and b == "not_applicable", verdict is H1_REFUTED.
        self.assertEqual(out["h1"]["verdict"], "H1_REFUTED")

if __name__ == "__main__":
    unittest.main()
