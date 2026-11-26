"""tests/test_fl.py — Unit and integration tests for ops/fl/ (fast-lane judge comparison).

Covers:
- Bank sha256 verification against runs/INDEX.json (and refusal on mismatch)
- Deterministic 50/50 hidden test split and <4 hidden test skipping
- Safe AST literal parsing (`ast.literal_eval`) for bank cases and `tests_spec.py`
- LeetCode `class Solution` normalization
- MV clustering including `"ERR"` sentinel (and non-collision with string `"ERR"`)
- CT dual-agreement scoring and tie handling
- TF freezing (read-only kernel EROFS/EBUSY bind inside `/work` + host frozen gate + undetermined fallback)
- End-to-end runner across all 8 arms (B0/B0x3/GT/EX/TF/XM/MV/CT) with a fake claude binary
- Calibration mode (`--calibrate N`), resume safety, git-clean guard, analyzer `--json`,
  and reused E1 Claude + eval-sandbox negative controls.
"""
from __future__ import annotations

import json
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops.e1.negative_controls import run_claude_negative_controls
from ops.fl import DEFAULT_BANK_PATH, DEFAULT_INDEX_PATH, PLAN_SCHEMA, atomic_write_json
from ops.fl.analyze_fl import analyze_root, format_report
from ops.fl.bank import (
    load_bank_tasks,
    parse_test_case,
    parse_test_cases,
    parse_tests_spec_text,
    split_hidden_tests,
    verify_bank_sha256,
)
from ops.fl.eval_fl import (
    ERR_TAG,
    cluster_mv_outputs,
    collect_outputs_in_sandbox,
    evaluate_solution_on_cases,
    normalize_solution_source,
    run_input_generator_in_sandbox,
    score_ct_solutions,
)
from ops.fl.run_fl import FLRunner, assert_fl_git_clean


class TestBankAndSplit(unittest.TestCase):
    def test_verify_real_bank_sha256_and_refuse_mismatch(self) -> None:
        sha = verify_bank_sha256(DEFAULT_BANK_PATH, DEFAULT_INDEX_PATH)
        self.assertEqual(sha, "bd3dffebb1b16bc7c92ead59c82753597a8197f9927d4f758d42e6c28b129293")

        with tempfile.TemporaryDirectory() as td:
            tampered = pathlib.Path(td) / "tampered.jsonl"
            tampered.write_text('{"task_id": "fake"}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_bank_sha256(tampered, DEFAULT_INDEX_PATH)

    def test_split_hidden_determinism_and_skip_under_4(self) -> None:
        cases = [{"args": [i], "expected": i * 2} for i in range(9)]
        s1 = split_hidden_tests(cases, task_id="t1", seed=42)
        s2 = split_hidden_tests(cases, task_id="t1", seed=42)
        s3 = split_hidden_tests(cases, task_id="t1", seed=99)
        s4 = split_hidden_tests(cases, task_id="t2", seed=42)
        assert s1 is not None and s2 is not None and s3 is not None and s4 is not None

        self.assertEqual(s1, s2)
        self.assertEqual(len(s1["gate_hidden"]), 4)
        self.assertEqual(len(s1["eval_hidden"]), 5)
        self.assertEqual(set(s1["gate_indices"]) & set(s1["eval_indices"]), set())
        self.assertEqual(set(s1["gate_indices"]) | set(s1["eval_indices"]), set(range(9)))
        self.assertNotEqual(s1["gate_indices"], s3["gate_indices"])
        self.assertNotEqual(s1["gate_indices"], s4["gate_indices"])

        # < 4 hidden tests -> None (skip)
        self.assertIsNone(split_hidden_tests(cases[:3], task_id="t_small", seed=42))
        self.assertIsNotNone(split_hidden_tests(cases[:4], task_id="t_four", seed=42))

    def test_load_bank_logs_skipped_under_4(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bank_p = pathlib.Path(td) / "mini.jsonl"
            rows = [
                {
                    "task_id": "ok_task",
                    "difficulty": "medium",
                    "entry_point": "double",
                    "prompt": "Double x",
                    "visible_tests": [{"args": [1], "expected": 2}],
                    "hidden_tests": [{"args": [i], "expected": i * 2} for i in range(6)],
                },
                {
                    "task_id": "too_few",
                    "difficulty": "hard",
                    "entry_point": "double",
                    "prompt": "Double x",
                    "visible_tests": [{"args": [1], "expected": 2}],
                    "hidden_tests": [{"args": [i], "expected": i * 2} for i in range(3)],
                },
            ]
            bank_p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            loaded = load_bank_tasks(bank_p, seed=7, verify_sha256=False)
            self.assertEqual([t["task_id"] for t in loaded["tasks"]], ["ok_task"])
            self.assertEqual(len(loaded["skipped"]), 1)
            self.assertEqual(loaded["skipped"][0]["task_id"], "too_few")


class TestLiteralParsing(unittest.TestCase):
    def test_parse_native_and_string_encoded_cases(self) -> None:
        # Native JSON case preserves string return values like "11001"
        c_native = parse_test_case({"args": ["100011001", 3], "expected": "11001"})
        self.assertEqual(c_native, {"args": ["100011001", 3], "expected": "11001"})
        self.assertIsInstance(c_native["expected"], str)

        # String-encoded Python literal case parsed via ast.literal_eval
        c_str = parse_test_case({"args": "([1, 2], 3)", "expected": "6"})
        self.assertEqual(c_str, {"args": [[1, 2], 3], "expected": 6})

        c_str_out = parse_test_case({"args": "('abc',)", "expected": "'cba'"})
        self.assertEqual(c_str_out, {"args": ["abc"], "expected": "cba"})

        # Entire list as Python literal string
        many = parse_test_cases("[{'args': [1, 2], 'expected': 3}, {'args': (4, 5), 'expected': 9}]")
        self.assertEqual(len(many), 2)
        self.assertEqual(many[1], {"args": [4, 5], "expected": 9})

    def test_parse_tests_spec_text_safe_ast_only(self) -> None:
        bare = '[\n  {"args": [1, 2], "expected": 3},\n  {"args": (0, 5), "expected": 5},\n]\n'
        cases, err = parse_tests_spec_text(bare)
        self.assertIsNone(err)
        self.assertEqual(len(cases), 2)

        assigned = '"""doc"""\nTESTS = [{"args": [10], "expected": 20}]\n'
        cases2, err2 = parse_tests_spec_text(assigned)
        self.assertIsNone(err2)
        self.assertEqual(cases2, [{"args": [10], "expected": 20}])

        # Rejects code execution / calls / imports / empty / 0 cases
        for bad in (
            "",
            "[]",
            "import os\nTESTS = [{'args': [1], 'expected': 1}]\n",
            "TESTS = [{'args': [__import__('os').getpid()], 'expected': 1}]\n",
            "def f(): return 1\n",
            "not valid python ((",
            "TESTS = [{'args': 123, 'expected': 1}]\n",
        ):
            c_bad, e_bad = parse_tests_spec_text(bad)
            self.assertEqual(c_bad, [], f"Should reject: {bad!r}")
            self.assertIsNotNone(e_bad)


class TestSolutionNormalizationAndSandboxEval(unittest.TestCase):
    def test_top_level_and_class_solution_normalization(self) -> None:
        cases = [{"args": [[1, 2, 3]], "expected": 6}, {"args": [[10]], "expected": 10}]

        plain_src = "def mySum(nums):\n    return sum(nums)\n"
        self.assertEqual(normalize_solution_source(plain_src, "mySum"), plain_src)
        ev_plain = evaluate_solution_on_cases(plain_src, "mySum", cases)
        self.assertTrue(ev_plain["passed"])

        cls_src = (
            "from typing import List\n"
            "class Solution:\n"
            "    def mySum(self, nums: List[int]) -> int:\n"
            "        return sum(nums)\n"
        )
        norm = normalize_solution_source(cls_src, "mySum")
        self.assertIn("Solution().mySum", norm)
        ev_cls = evaluate_solution_on_cases(cls_src, "mySum", cases)
        self.assertTrue(ev_cls["passed"])
        self.assertEqual(ev_cls["n_passed"], 2)

        static_src = (
            "class Solution:\n"
            "    @staticmethod\n"
            "    def mySum(nums):\n"
            "        return sum(nums)\n"
        )
        ev_static = evaluate_solution_on_cases(static_src, "mySum", cases)
        self.assertTrue(ev_static["passed"])

        # Top-level function takes precedence over class Solution
        both_src = (
            "class Solution:\n"
            "    def mySum(self, nums):\n"
            "        return -999\n"
            "def mySum(nums):\n"
            "    return sum(nums)\n"
        )
        self.assertEqual(normalize_solution_source(both_src, "mySum"), both_src)
        self.assertTrue(evaluate_solution_on_cases(both_src, "mySum", cases)["passed"])

    def test_probe_solution_on_real_bank_eval_hidden(self) -> None:
        loaded = load_bank_tasks(DEFAULT_BANK_PATH, index_path=DEFAULT_INDEX_PATH, seed=123, task_ids=["lcb_2728"])
        probes = json.loads((REPO_ROOT / "ops" / "gain" / "data" / "lcb_v3_probe_solutions.json").read_text(encoding="utf-8"))
        task = loaded["tasks"][0]
        ev = evaluate_solution_on_cases(probes["lcb_2728"], task["entry_point"], task["eval_hidden"])
        self.assertTrue(ev["passed"], f"Probe solution failed: {ev}")


class TestMVClusteringAndCTScoring(unittest.TestCase):
    def test_mv_clustering_including_err_and_string_err_distinction(self) -> None:
        # 2 agreeing solutions (indices 1 & 2) incl. ERR on input 2 -> delivers index 1
        vecs = [
            [{"ok": True, "val": 10}, {"ok": True, "val": 20}],
            [{"ok": True, "val": 10}, {"ok": False, "val": "ERR"}],
            [{"ok": True, "val": 10}, {"ok": False, "val": "ERR"}],
        ]
        res = cluster_mv_outputs(vecs)
        self.assertFalse(res["undetermined"])
        self.assertEqual(res["delivered_idx"], 1)
        self.assertEqual(res["winning_cluster"], [1, 2])
        self.assertEqual(res["agree_counts"], [1, 2, 2])

        # String return value "ERR" MUST NOT collide with exception/timeout ERR sentinel
        vecs_dist = [
            [{"ok": True, "val": "ERR"}],
            [{"ok": False, "val": "ERR"}],
            [{"ok": True, "val": "OTHER"}],
        ]
        res_dist = cluster_mv_outputs(vecs_dist)
        self.assertTrue(res_dist["undetermined"])
        self.assertEqual(res_dist["delivered_idx"], 0)
        self.assertEqual(res_dist["agree_counts"], [1, 1, 1])

        # Sandbox end-to-end: exception and timeout both produce ERR_TAG, string "ERR" produces __FL_OK__:"ERR"
        sol_exc = "def f(x):\n    if x == 0: raise ZeroDivisionError()\n    return x\n"
        sol_tmo = "def f(x):\n    if x == 0:\n        while True: pass\n    return x\n"
        sol_str = "def f(x):\n    return 'ERR' if x == 0 else x\n"
        inputs = [[1], [0]]
        o_exc = collect_outputs_in_sandbox(sol_exc, "f", inputs, per_call_timeout_s=1.0, total_timeout_s=10.0)
        o_tmo = collect_outputs_in_sandbox(sol_tmo, "f", inputs, per_call_timeout_s=1.0, total_timeout_s=10.0)
        o_str = collect_outputs_in_sandbox(sol_str, "f", inputs, per_call_timeout_s=1.0, total_timeout_s=10.0)
        self.assertEqual(o_exc["tags"][1], ERR_TAG)
        self.assertEqual(o_tmo["tags"][1], ERR_TAG)
        self.assertNotEqual(o_str["tags"][1], ERR_TAG)
        mv_sb = cluster_mv_outputs([o_str["tags"], o_exc["tags"], o_tmo["tags"]])
        self.assertFalse(mv_sb["undetermined"])
        self.assertEqual(mv_sb["winning_cluster"], [1, 2])
        self.assertEqual(mv_sb["delivered_idx"], 1)

    def test_gen_inputs_sandbox_execution(self) -> None:
        gen_src = "def gen_inputs():\n    return [(i, i + 1) for i in range(25)]\n"
        res = run_input_generator_in_sandbox(gen_src, max_inputs=20)
        self.assertTrue(res["ok"])
        self.assertEqual(len(res["inputs"]), 20)
        self.assertEqual(res["inputs"][0], [0, 1])

    def test_ct_scoring_and_ties(self) -> None:
        # Cluster {1, 2} agrees (count=2) and passes 4 tests => score 8 vs index 0 (1 * 3 = 3)
        vecs = [[1, 2], [9, 9], [9, 9]]
        ct1 = score_ct_solutions(vecs, [3, 4, 4], n_generated_tests=5)
        self.assertFalse(ct1["undetermined"])
        self.assertEqual(ct1["scores"], [3, 8, 8])
        self.assertEqual(ct1["delivered_idx"], 1)

        # Single strong solution (1 * 5 = 5) beats agreeing weak pair (2 * 2 = 4)
        ct2 = score_ct_solutions(vecs, [5, 2, 2], n_generated_tests=5)
        self.assertEqual(ct2["scores"], [5, 4, 4])
        self.assertEqual(ct2["delivered_idx"], 0)

        # True tie between distinct clusters -> attempt 1 (index 0)
        vecs_diff = [[1], [2], [3]]
        ct_tie = score_ct_solutions(vecs_diff, [1, 4, 4], n_generated_tests=5)
        self.assertFalse(ct_tie["undetermined"])
        self.assertTrue(ct_tie["tie"])
        self.assertEqual(ct_tie["delivered_idx"], 0)

        # Zero generated tests -> undetermined, attempt 1
        ct_zero = score_ct_solutions(vecs, [0, 0, 0], n_generated_tests=0)
        self.assertTrue(ct_zero["undetermined"])
        self.assertEqual(ct_zero["delivered_idx"], 0)


class TestReusedNegativeControlsAndGuards(unittest.TestCase):
    def test_reused_claude_and_eval_sandbox_negative_controls_pass(self) -> None:
        rep = run_claude_negative_controls(hidden_tests_path=DEFAULT_BANK_PATH)
        self.assertTrue(rep["passed"], f"Negative controls failed: {rep}")
        self.assertEqual(rep["leaks"], [])
        self.assertTrue(rep["eval_net_isolated"])

    def test_uncommitted_plan_refused(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "untracked.json"
            p.write_text("{}", encoding="utf-8")
            with self.assertRaises(SystemExit):
                assert_fl_git_clean(p)


_FAKE_CLAUDE_FL_PY = r"""#!/usr/bin/env python3
import json, os, pathlib, sys

assert os.getcwd() == "/work", f"bad cwd: {os.getcwd()}"
assert os.environ.get("HOME") == "/sandbox_home"
assert os.environ.get("NO_PROXY") == ""
assert os.environ.get("HTTP_PROXY", "").startswith("http://127.0.0.1:")

role = os.environ.get("FL_ROLE", "")
arm = os.environ.get("FL_ARM", "")
att = int(os.environ.get("FL_ATTEMPT", "1"))
tid = os.environ.get("FL_TASK_ID", "")
mode = os.environ.get("FL_FAKE_MODE", "normal")
prompt = sys.argv[-1]

# Target task: double_plus(x) = x * 2 + 1
# visible_tests: x=1->3, x=2->5
# gate_hidden: half of x in [3..10]
# eval_hidden: other half of x in [3..10]
CORRECT_SOL = "def double_plus(x):\n    return x * 2 + 1\n"
CLASS_CORRECT_SOL = "class Solution:\n    def double_plus(self, x):\n        return x * 2 + 1\n"
ONLY_VISIBLE_SOL = "def double_plus(x):\n    return 3 if x == 1 else (5 if x == 2 else -1)\n"
WRONG_SOL = "def double_plus(x):\n    return -999\n"

if role == "tf_test_writer":
    if mode == "tf_bad_spec":
        pathlib.Path("/work/tests_spec.py").write_text("import os\nTESTS = []\n", encoding="utf-8")
    else:
        # Strict test spec that rejects WRONG_SOL and ONLY_VISIBLE_SOL, accepts CORRECT_SOL
        pathlib.Path("/work/tests_spec.py").write_text(
            '[\n'
            '  {"args": [1], "expected": 3},\n'
            '  {"args": [10], "expected": 21},\n'
            '  {"args": [7], "expected": 15},\n'
            ']\n',
            encoding="utf-8",
        )
elif role in ("xm_exam_writer", "ct_exam_writer"):
    if mode == "xm_false_reject":
        # Exam has a bogus expected value -> rejects an eval-correct candidate!
        pathlib.Path("/work/tests_spec.py").write_text(
            'TESTS = [{"args": [4], "expected": 99999}]\n',
            encoding="utf-8",
        )
    else:
        pathlib.Path("/work/tests_spec.py").write_text(
            'TESTS = [\n'
            '  {"args": [1], "expected": 3},\n'
            '  {"args": [4], "expected": 9},\n'
            '  {"args": [8], "expected": 17},\n'
            ']\n',
            encoding="utf-8",
        )
elif role == "mv_input_gen":
    pathlib.Path("/work/gen_inputs.py").write_text(
        "def gen_inputs():\n    return [(i,) for i in range(3, 23)]\n",
        encoding="utf-8",
    )
elif role == "coder":
    sol_p = pathlib.Path("/work/solution.py")
    spec_p = pathlib.Path("/work/tests_spec.py")

    if arm == "TF" and mode != "tf_bad_spec":
        # Verify frozen /work/tests_spec.py is visible AND kernel-enforced read-only (cannot write or unlink!)
        assert spec_p.is_file(), "TF coder must see read-only /work/tests_spec.py"
        assert "21" in spec_p.read_text(encoding="utf-8")
        try:
            spec_p.write_text('[{"args": [1], "expected": -999}]\n', encoding="utf-8")
            raise AssertionError("TF /work/tests_spec.py MUST be read-only!")
        except OSError:
            pass
        try:
            spec_p.unlink()
            raise AssertionError("TF /work/tests_spec.py MUST NOT be unlinkable!")
        except OSError:
            pass
    elif arm == "XM":
        # XM coder MUST NOT see tests_spec.py
        assert not spec_p.exists(), "XM coder must NOT see exam tests_spec.py"

    if arm == "B0":
        sol_p.write_text(WRONG_SOL, encoding="utf-8")
    elif arm == "B0x3":
        marker = pathlib.Path("/work/carry_marker.txt")
        if att == 1:
            assert not marker.exists()
            marker.write_text("from_att1", encoding="utf-8")
            sol_p.write_text(WRONG_SOL, encoding="utf-8")
        else:
            assert marker.is_file() and marker.read_text(encoding="utf-8") == "from_att1", "B0x3 must carry workspace"
            assert "Review your solution.py and improve it if needed." in prompt
            sol_p.write_text(WRONG_SOL, encoding="utf-8")
    elif arm == "GT":
        # Attempt 1 wrong, attempt 2 correct (as class Solution!)
        sol_p.write_text(WRONG_SOL if att == 1 else CLASS_CORRECT_SOL, encoding="utf-8")
    elif arm == "EX":
        # Passes visible_tests (examples) but fails eval_hidden -> triggers false_accept!
        sol_p.write_text(ONLY_VISIBLE_SOL, encoding="utf-8")
    elif arm == "TF":
        if mode == "tf_bad_spec":
            sol_p.write_text(CORRECT_SOL, encoding="utf-8")
        else:
            # Attempt 1 fails frozen test (only_visible), attempt 2 passes frozen test & eval
            sol_p.write_text(ONLY_VISIBLE_SOL if att == 1 else CORRECT_SOL, encoding="utf-8")
    elif arm == "XM":
        if mode == "xm_false_reject":
            sol_p.write_text(CORRECT_SOL, encoding="utf-8")
        else:
            sol_p.write_text(WRONG_SOL if att < 3 else CORRECT_SOL, encoding="utf-8")
    elif arm == "MV":
        # Attempt 1 wrong, attempts 2 & 3 agree and are correct -> MV selects attempt 2
        sol_p.write_text(WRONG_SOL if att == 1 else CORRECT_SOL, encoding="utf-8")
    else:
        sol_p.write_text(CORRECT_SOL, encoding="utf-8")

print(json.dumps({"type": "system", "subtype": "init", "cwd": "/work"}))
print(json.dumps({
    "type": "assistant",
    "message": {
        "id": f"msg_{role}_{arm}_{att}",
        "model": "claude-haiku-5-5",
        "usage": {"input_tokens": 100, "output_tokens": 25, "cache_creation_input_tokens": 50, "cache_read_input_tokens": 80},
    },
}))
print(json.dumps({
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "num_turns": 1,
    "total_cost_usd": 0.001,
    "usage": {"input_tokens": 100, "output_tokens": 25, "cache_creation_input_tokens": 50, "cache_read_input_tokens": 80},
}))
"""


class TestEndToEndFakeClaude(unittest.TestCase):
    def _make_mini_bank(self, path: pathlib.Path) -> pathlib.Path:
        rows = [
            {
                "task_id": "synth_med_1",
                "difficulty": "medium",
                "entry_point": "double_plus",
                "prompt": "Given integer x, return 2*x + 1.",
                "visible_tests": [{"args": [1], "expected": 3}, {"args": [2], "expected": 5}],
                "hidden_tests": [{"args": [x], "expected": 2 * x + 1} for x in range(3, 11)],
            },
            {
                "task_id": "synth_hard_1",
                "difficulty": "hard",
                "entry_point": "double_plus",
                "prompt": "Given integer x, return 2*x + 1.",
                "visible_tests": [{"args": [1], "expected": 3}, {"args": [2], "expected": 5}],
                "hidden_tests": [{"args": [x], "expected": 2 * x + 1} for x in range(3, 11)],
            },
        ]
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return path

    def _make_fake_claude(self, td: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
        fc = td / "fake_claude"
        fc.write_text(_FAKE_CLAUDE_FL_PY, encoding="utf-8")
        fc.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        creds = td / ".credentials.json"
        creds.write_text('{"claudeAiOauth":{"accessToken":"fake"}}\n', encoding="utf-8")
        return fc, creds

    def test_all_eight_arms_tf_freeze_ct_reuse_resume_and_analyzer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            bank_p = self._make_mini_bank(tp / "mini_bank.jsonl")
            fc, creds = self._make_fake_claude(tp)
            plan_p = tp / "plan.json"
            atomic_write_json(
                plan_p,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "fl_fake_e2e",
                    "bank_path": str(bank_p),
                    "seed": 42,
                    "arms": ["B0", "B0x3", "GT", "EX", "TF", "XM", "MV", "CT"],
                    "model": {
                        "agent": "claude",
                        "model": "claude-haiku-5-5",
                        "exam_model": "claude-haiku-5-5",
                        "claude_bin": str(fc),
                        "credentials_path": str(creds),
                    },
                    "jobs": 1,
                    "attempt_timeout_s": 30,
                },
            )
            root = tp / "run_root"
            FLRunner(plan_p, root, allow_uncommitted=True, verify_bank_sha=False).run()

            summ = analyze_root(root)
            arms = summ["arms"]
            # B0 & B0x3 wrong (0.0); GT, TF, XM, MV, CT correct (1.0); EX false-accept (0.0)
            self.assertEqual(arms["B0"]["success_rate"], 0.0)
            self.assertEqual(arms["B0x3"]["success_rate"], 0.0)
            self.assertEqual(arms["GT"]["success_rate"], 1.0)
            self.assertEqual(arms["GT"]["false_accept_rate"], 0.0)
            self.assertEqual(arms["EX"]["success_rate"], 0.0)
            self.assertEqual(arms["EX"]["false_accept_rate"], 1.0)
            self.assertFalse(arms["EX"]["qualifies_for_9b"])

            for good_judge in ("TF", "XM", "MV", "CT"):
                self.assertEqual(arms[good_judge]["success_rate"], 1.0, f"{good_judge} failed")
                self.assertEqual(arms[good_judge]["gain_share"], 1.0)
                self.assertEqual(arms[good_judge]["false_accept_rate"], 0.0)
                self.assertTrue(arms[good_judge]["qualifies_for_9b"])

            # Verify CT reused MV & XM with 0 incremental cost, positive standalone cost
            self.assertEqual(arms["CT"]["incremental_cost_usd_total"], 0.0)
            self.assertGreater(arms["CT"]["cost_usd_total"], 0.0)
            ct_rec = json.loads((root / "cells" / "synth_med_1" / "CT" / "record.json").read_text(encoding="utf-8"))
            self.assertEqual(ct_rec["reused_from"], {"mv": True, "xm": True})
            self.assertEqual(ct_rec["delivered_attempt"], 2)

            # Verify TF froze tests_spec.py with sha256 and took 2 attempts
            tf_rec = json.loads((root / "cells" / "synth_med_1" / "TF" / "record.json").read_text(encoding="utf-8"))
            self.assertEqual(tf_rec["attempts_count"], 2)
            self.assertEqual(len(tf_rec["judge_meta"]["frozen_tests_sha256"]), 64)
            self.assertFalse(tf_rec["attempts"][0]["gate_verdict"])
            self.assertTrue(tf_rec["attempts"][1]["gate_verdict"])

            # Verify GT stopped at attempt 2 via class Solution normalization
            gt_rec = json.loads((root / "cells" / "synth_med_1" / "GT" / "record.json").read_text(encoding="utf-8"))
            self.assertEqual(gt_rec["attempts_count"], 2)
            self.assertTrue(gt_rec["delivered_correct"])

            # Verify resume-safe: re-running appends zero new lines
            before_lines = len((root / "results.jsonl").read_text(encoding="utf-8").splitlines())
            FLRunner(plan_p, root, allow_uncommitted=True, verify_bank_sha=False).run()
            after_lines = len((root / "results.jsonl").read_text(encoding="utf-8").splitlines())
            self.assertEqual(before_lines, after_lines)

            # Verify analyzer CLI --json stdout and markdown report
            r_cli = subprocess.run(
                [sys.executable, str(REPO_ROOT / "ops" / "fl" / "analyze_fl.py"), str(root), "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(r_cli.returncode, 0, r_cli.stderr)
            parsed_cli = json.loads(r_cli.stdout)
            self.assertIn("paired_vs_B0x3", parsed_cli)
            self.assertIn("paired_vs_B0", parsed_cli)
            md = format_report(parsed_cli)
            self.assertIn("Paired McNemar vs B0x3", md)

    def test_tf_undetermined_on_unparseable_spec_and_calibrate_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            bank_p = self._make_mini_bank(tp / "mini_bank.jsonl")
            fc, creds = self._make_fake_claude(tp)
            plan_p = tp / "plan_tf_bad.json"
            atomic_write_json(
                plan_p,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "fl_tf_bad_spec",
                    "bank_path": str(bank_p),
                    "seed": 11,
                    "arms": ["TF"],
                    "model": {
                        "agent": "claude",
                        "model": "claude-haiku-5-5",
                        "claude_bin": str(fc),
                        "credentials_path": str(creds),
                        "fake_mode": "tf_bad_spec",
                    },
                    "jobs": 1,
                    "attempt_timeout_s": 30,
                },
            )
            root_tf = tp / "root_tf"
            FLRunner(plan_p, root_tf, allow_uncommitted=True, verify_bank_sha=False).run()
            rec = json.loads((root_tf / "cells" / "synth_med_1" / "TF" / "record.json").read_text(encoding="utf-8"))
            self.assertTrue(rec["undetermined"])
            self.assertEqual(rec["attempts_count"], 1)
            self.assertTrue(rec["delivered_correct"])
            self.assertFalse(rec["false_accept"])

            # Calibration mode runs only B0 on N sampled tasks and reports by difficulty
            root_cal = tp / "root_cal"
            cal_out = FLRunner(plan_p, root_cal, calibrate_n=2, allow_uncommitted=True, verify_bank_sha=False).run()
            self.assertEqual(cal_out["arms"], ["B0"])
            self.assertEqual(cal_out["calibrate"]["by_difficulty"]["medium"]["total"], 1)
            self.assertEqual(cal_out["calibrate"]["by_difficulty"]["hard"]["total"], 1)
            # Refuses resume with mismatched calibrate_n
            with self.assertRaises(SystemExit):
                FLRunner(plan_p, root_cal, calibrate_n=None, allow_uncommitted=True, verify_bank_sha=False).run()

            # False-reject detection: XM exam has wrong expected output -> rejects eval-correct attempts
            plan_fr = tp / "plan_xm_fr.json"
            atomic_write_json(
                plan_fr,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "fl_xm_fr",
                    "bank_path": str(bank_p),
                    "seed": 11,
                    "task_ids": ["synth_med_1"],
                    "arms": ["XM"],
                    "model": {
                        "agent": "claude",
                        "model": "claude-haiku-5-5",
                        "exam_model": "claude-haiku-5-5",
                        "claude_bin": str(fc),
                        "credentials_path": str(creds),
                        "fake_mode": "xm_false_reject",
                    },
                    "jobs": 1,
                    "attempt_timeout_s": 30,
                },
            )
            root_fr = tp / "root_fr"
            FLRunner(plan_fr, root_fr, allow_uncommitted=True, verify_bank_sha=False).run()
            fr_rec = json.loads((root_fr / "cells" / "synth_med_1" / "XM" / "record.json").read_text(encoding="utf-8"))
            self.assertTrue(fr_rec["false_reject"])
            self.assertFalse(fr_rec["false_accept"])
            self.assertEqual(fr_rec["attempt_confusion"]["fn"], 3)
            fr_summ = analyze_root(root_fr)
            self.assertEqual(fr_summ["arms"]["XM"]["false_reject_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
