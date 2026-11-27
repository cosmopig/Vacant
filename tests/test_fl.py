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
from ops.fl import DEFAULT_BANK_PATH, DEFAULT_EVALPLUS_DIR, DEFAULT_INDEX_PATH, PLAN_SCHEMA, atomic_write_json, sha256_file
from ops.fl.analyze_fl import analyze_root, format_report
from ops.fl.apps_fetch import ALLOWED_DIFFICULTIES_V2, build_apps_fl_bank, build_v2_from_existing, parse_apps_examples
from ops.fl.bank import (
    load_bank_tasks,
    load_evalplus_tasks,
    parse_stdio_case,
    parse_stdio_cases,
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
    collect_stdio_outputs_in_sandbox,
    evaluate_solution_on_cases,
    evaluate_stdio_on_cases,
    normalize_solution_source,
    normalize_stdio_output,
    run_input_generator_in_sandbox,
    run_stdio_input_generator_in_sandbox,
    score_ct_solutions,
    self_check_xmvh_exam,
    stdio_outputs_equal,
)
from ops.fl.run_fl import (
    FEEDBACK_MAX_BYTES,
    FEEDBACK_PREFIX,
    FLRunner,
    _STDIO_TASK_SUFFIX,
    assert_fl_git_clean,
    build_retry_feedback,
    build_task_prompt,
)


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


class TestStdioEvaluatorAndAppsBank(unittest.TestCase):
    def test_stdio_normalization_and_float_tolerance(self) -> None:
        self.assertEqual(normalize_stdio_output("1 2  \r\n3 4 \t\n\n  \n"), "1 2\n3 4")
        self.assertEqual(normalize_stdio_output("a\n\nb\n\n"), "a\n\nb")
        self.assertEqual(normalize_stdio_output("   \n\n"), "")

        # Normalisation & exact matches
        self.assertTrue(stdio_outputs_equal("1 2  \n3 4 \n\n", "1 2\n3 4"))
        self.assertFalse(stdio_outputs_equal("a\n\nb", "a\nb"))
        self.assertFalse(stdio_outputs_equal("YES", "NO"))

        # Float tolerance 1e-6
        self.assertTrue(stdio_outputs_equal("3.1415926\n", "3.1415920\n"))
        self.assertFalse(stdio_outputs_equal("3.141594\n", "3.141592\n"))
        self.assertTrue(stdio_outputs_equal("1.000000", "1"))
        self.assertTrue(stdio_outputs_equal("1e-7", "0.0"))
        self.assertTrue(stdio_outputs_equal("ok 2.0000004\nans -0.0", "ok 2.0\nans 0"))

        # Huge integers differing by 1 MUST NOT falsely match due to float precision loss
        self.assertFalse(
            stdio_outputs_equal("10000000000000000000000001", "10000000000000000000000002")
        )
        # Non-finite tokens
        self.assertFalse(stdio_outputs_equal("nan", "0"))
        self.assertFalse(stdio_outputs_equal("inf", "1e308"))

    def test_stdio_sandbox_evaluator_pass_float_fail_exception_timeout(self) -> None:
        # 1. Passing program with trailing spaces and float tolerance
        sol_ok = (
            "import sys\n"
            "a, b = map(float, sys.stdin.read().split())\n"
            "print(f'{a / b:.7f}   ')\n"
            "print()\n"
        )
        cases = [
            {"input": "1 3\n", "output": "0.3333333"},
            {"input": "10 4\n", "output": "2.5"},
        ]
        ev = evaluate_stdio_on_cases(sol_ok, cases, per_case_timeout_s=2.0, total_timeout_s=15.0)
        self.assertTrue(ev["passed"], ev)
        self.assertEqual(ev["n_passed"], 2)
        self.assertEqual(ev["n_total"], 2)

        # 2. Timeout fails cleanly
        sol_tmo = "import time\ntime.sleep(5)\nprint('42')\n"
        ev_tmo = evaluate_stdio_on_cases(
            sol_tmo,
            [{"input": "1\n", "output": "42"}],
            per_case_timeout_s=0.4,
            total_timeout_s=5.0,
        )
        self.assertFalse(ev_tmo["passed"])
        self.assertEqual(ev_tmo["n_passed"], 0)
        self.assertIn("timeout", ev_tmo["error"] or "")

        # 3. Runtime exception fails cleanly
        sol_exc = "raise ValueError('boom')\n"
        ev_exc = evaluate_stdio_on_cases(
            sol_exc,
            [{"input": "1\n", "output": "1"}],
            per_case_timeout_s=2.0,
            total_timeout_s=10.0,
        )
        self.assertFalse(ev_exc["passed"])
        self.assertEqual(ev_exc["n_passed"], 0)
        self.assertIn("rc=", ev_exc["error"] or "")

        # 4. Empty solution fails
        ev_empty = evaluate_stdio_on_cases("", [{"input": "", "output": ""}], per_case_timeout_s=2.0)
        self.assertFalse(ev_empty["passed"])

    def test_stdio_mv_clustering_err_and_input_gen(self) -> None:
        gen_src = "def gen_inputs():\n    return [f'{i}\\n' for i in range(5)]\n"
        gres = run_stdio_input_generator_in_sandbox(gen_src, max_inputs=3)
        self.assertTrue(gres["ok"])
        self.assertEqual(gres["inputs"], ["0\n", "1\n", "2\n"])

        # Exception and timeout both map to ERR_TAG; literal printed "ERR" must NOT collide
        sol_exc = "x = int(input())\nif x == 0: raise RuntimeError()\nprint(x)\n"
        sol_tmo = "import time\nx = int(input())\nif x == 0: time.sleep(5)\nprint(x)\n"
        sol_str = "x = int(input())\nprint('ERR' if x == 0 else x)\n"
        inputs = ["1\n", "0\n"]
        o_exc = collect_stdio_outputs_in_sandbox(sol_exc, inputs, per_case_timeout_s=0.4, total_timeout_s=5.0)
        o_tmo = collect_stdio_outputs_in_sandbox(sol_tmo, inputs, per_case_timeout_s=0.4, total_timeout_s=5.0)
        o_str = collect_stdio_outputs_in_sandbox(sol_str, inputs, per_case_timeout_s=0.4, total_timeout_s=5.0)
        self.assertEqual(o_exc["tags"][1], ERR_TAG)
        self.assertEqual(o_tmo["tags"][1], ERR_TAG)
        self.assertNotEqual(o_str["tags"][1], ERR_TAG)
        mv = cluster_mv_outputs([o_str["tags"], o_exc["tags"], o_tmo["tags"]])
        self.assertFalse(mv["undetermined"])
        self.assertEqual(mv["winning_cluster"], [1, 2])
        self.assertEqual(mv["delivered_idx"], 1)

    def test_apps_example_parser_on_five_real_statements_and_failures(self) -> None:
        # 5 real APPS test split statements covering the real statement formats
        real_statements: list[tuple[str, str, list[dict[str, str]]]] = [
            # 1. apps_0: -----Examples----- with multiple Input / Output blocks
            (
                "apps_0",
                "An accordion is a string...\n\n-----Input-----\nThe only line contains one string $s$.\n\n"
                "-----Output-----\nPrint maximum length.\n\n"
                "-----Examples-----\nInput\n|[a:b:|]\n\nOutput\n4\n\nInput\n|]:[|:]\n\nOutput\n-1",
                [
                    {"input": "|[a:b:|]\n", "output": "4"},
                    {"input": "|]:[|:]\n", "output": "-1"},
                ],
            ),
            # 2. apps_6: -----Example----- (singular) with multiline I/O + -----Note-----
            (
                "apps_6",
                "Zmei Gorynich...\n\n-----Example-----\nInput\n3\n3 10\n6 3\n8 2\n1 4\n\n"
                "Output\n2\n3\n-1\n\n\n\n-----Note-----\n\nIn the first query you can deal the first blow.",
                [
                    {"input": "3\n3 10\n6 3\n8 2\n1 4\n", "output": "2\n3\n-1"},
                ],
            ),
            # 3. apps_117: AtCoder -----Sample Input----- / -----Sample Output----- + trailing prose
            (
                "apps_117",
                "A cow on a plane...\n\n-----Sample Input-----\n5 6\n1 2 0\n0 1 1\n\n"
                "-----Sample Output-----\n13\n\n"
                "The area of the region the cow can reach is 13\\ \\mathrm{cm^2}.",
                [
                    {"input": "5 6\n1 2 0\n0 1 1\n", "output": "13"},
                ],
            ),
            # 4. apps_2709: -----Examples----- with Sample Input N: / Sample Output N:
            (
                "apps_2709",
                "Solve 6 subtasks...\n\n-----Examples-----\n"
                "Sample Input 1:\n7 1\n1 2 3 4 5 6 7\nSample Output 1:\n7\n\n"
                "Sample Input 2:\n7 2\n1 2 3 4 5 6 7\nSample Output 2:\nSmaller\n\n"
                "Sample Input 3:\n10 6\n7 4 11\nSample Output 3:\nhelloworld",
                [
                    {"input": "7 1\n1 2 3 4 5 6 7\n", "output": "7"},
                    {"input": "7 2\n1 2 3 4 5 6 7\n", "output": "Smaller"},
                    {"input": "10 6\n7 4 11\n", "output": "helloworld"},
                ],
            ),
            # 5. apps_134: -----Examples----- with -----Note-----[Image]
            (
                "apps_134",
                "Pythagorean triple...\n\n-----Examples-----\nInput\n3\n\nOutput\n4 5\n"
                "Input\n6\n\nOutput\n8 10\nInput\n1\n\nOutput\n-1\n\n\n"
                "-----Note-----[Image]\n\nIllustration for the first sample.",
                [
                    {"input": "3\n", "output": "4 5"},
                    {"input": "6\n", "output": "8 10"},
                    {"input": "1\n", "output": "-1"},
                ],
            ),
        ]
        for tid, stmt, expected in real_statements:
            got, err = parse_apps_examples(stmt)
            self.assertIsNone(err, f"{tid} parse failed: {err}")
            self.assertEqual(got, expected, f"{tid} mismatch")

        # Parse failure cases
        for bad_stmt in (
            "",
            "-----Примеры-----\nВходные данные\n1\nВыходные данные\n2\n",
            "-----Examples-----\nInput\n1 2\n",
            "No example section here at all.",
        ):
            got, err = parse_apps_examples(bad_stmt)
            self.assertEqual(got, [])
            self.assertIsNotNone(err)

    def test_plan_bank_sha256_verification_and_stdio_spec_parser(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bank_p = pathlib.Path(td) / "apps_mini.jsonl"
            row = {
                "task_id": "apps_test_1",
                "difficulty": "competition",
                "prompt": "Read an integer x and print 2*x + 1. Note: no penalty for small x.",
                "examples": [{"input": "1\n", "output": "3"}, {"input": "2\n", "output": "5"}],
                "hidden_tests": [{"input": f"{x}\n", "output": f"{2 * x + 1}"} for x in range(3, 11)],
            }
            bank_p.write_text(json.dumps(row) + "\n", encoding="utf-8")
            good_sha = sha256_file(bank_p)

            # Matching plan sha passes
            self.assertEqual(verify_bank_sha256(bank_p, index_path=None, expected_sha256=good_sha), good_sha)
            loaded = load_bank_tasks(
                bank_p,
                index_path=None,
                expected_sha256=good_sha,
                task_format="stdio",
                seed=123,
            )
            self.assertEqual(loaded["bank_sha256"], good_sha)
            self.assertEqual(loaded["task_format"], "stdio")
            self.assertEqual(len(loaded["tasks"]), 1)
            t = loaded["tasks"][0]
            self.assertEqual(t["entry_point"], None)
            self.assertEqual(len(t["visible_tests"]), 2)
            self.assertEqual(len(t["gate_hidden"]), 4)
            self.assertEqual(len(t["eval_hidden"]), 4)

            # Prompt suffix exactness and KS-1 checks harness template only (statement may say "penalty")
            prompt_txt = build_task_prompt(t)
            self.assertTrue(prompt_txt.endswith(_STDIO_TASK_SUFFIX))

            # Mismatched or malformed plan sha raises ValueError
            bad_sha = ("0" if good_sha[0] != "0" else "1") + good_sha[1:]
            with self.assertRaises(ValueError):
                verify_bank_sha256(bank_p, index_path=None, expected_sha256=bad_sha)
            with self.assertRaises(ValueError):
                verify_bank_sha256(bank_p, index_path=None, expected_sha256="not-a-sha")

        # Stdio tests_spec.py literal parsing
        spec_ok = 'TESTS = [{"input": "1\\n", "output": "3"}, {"input": "2\\n", "output": "5"}]\n'
        cases, err = parse_tests_spec_text(spec_ok, task_format="stdio")
        self.assertIsNone(err)
        self.assertEqual(cases, [{"input": "1\n", "output": "3"}, {"input": "2\n", "output": "5"}])
        self.assertEqual(parse_stdio_case({"input": "a", "output": "b"}), {"input": "a", "output": "b"})
        self.assertEqual(len(parse_stdio_cases([{"input": "a", "output": "b"}])), 1)

        for bad in (
            '[{"args": [1], "expected": 3}]',
            '[{"input": 1, "output": "3"}]',
            'import os\nTESTS = [{"input": "1", "output": "3"}]',
        ):
            c_bad, e_bad = parse_tests_spec_text(bad, task_format="stdio")
            self.assertEqual(c_bad, [])
            self.assertIsNotNone(e_bad)

    def test_stdio_all_eight_arms_end_to_end_with_fake_claude(self) -> None:
        fake_stdio_claude = r"""#!/usr/bin/env python3
import json, os, pathlib, sys

role = os.environ.get("FL_ROLE", "")
arm = os.environ.get("FL_ARM", "")
att = int(os.environ.get("FL_ATTEMPT", "1"))
prompt = sys.argv[-1]

CORRECT = "x = int(input().strip())\nprint(x * 2 + 1)\n"
ONLY_EX = "x = int(input().strip())\nprint(3 if x == 1 else (5 if x == 2 else -1))\n"
WRONG = "x = int(input().strip())\nprint(-999)\n"

if role == "tf_test_writer":
    pathlib.Path("/work/tests_spec.py").write_text(
        '[\n'
        '  {"input": "1\\n", "output": "3"},\n'
        '  {"input": "10\\n", "output": "21"},\n'
        ']\n',
        encoding="utf-8",
    )
elif role in ("xm_exam_writer", "ct_exam_writer"):
    pathlib.Path("/work/tests_spec.py").write_text(
        'TESTS = [\n'
        '  {"input": "1\\n", "output": "3"},\n'
        '  {"input": "7\\n", "output": "15"},\n'
        ']\n',
        encoding="utf-8",
    )
elif role == "mv_input_gen":
    pathlib.Path("/work/gen_inputs.py").write_text(
        "def gen_inputs():\n    return [f'{i}\\n' for i in range(3, 13)]\n",
        encoding="utf-8",
    )
elif role == "coder":
    assert "Write a Python 3 program in /work/solution.py that reads from standard input and writes to standard output." in prompt
    sol_p = pathlib.Path("/work/solution.py")
    if arm == "B0":
        sol_p.write_text(WRONG, encoding="utf-8")
    elif arm == "B0x3":
        sol_p.write_text(WRONG, encoding="utf-8")
    elif arm == "GT":
        sol_p.write_text(WRONG if att == 1 else CORRECT, encoding="utf-8")
    elif arm == "EX":
        sol_p.write_text(ONLY_EX, encoding="utf-8")
    elif arm == "TF":
        assert pathlib.Path("/work/tests_spec.py").is_file()
        sol_p.write_text(ONLY_EX if att == 1 else CORRECT, encoding="utf-8")
    elif arm == "XM":
        assert not pathlib.Path("/work/tests_spec.py").exists()
        sol_p.write_text(WRONG if att < 3 else CORRECT, encoding="utf-8")
    elif arm == "MV":
        sol_p.write_text(WRONG if att == 1 else CORRECT, encoding="utf-8")
    else:
        sol_p.write_text(CORRECT, encoding="utf-8")

print(json.dumps({"type": "system", "subtype": "init", "cwd": "/work"}))
print(json.dumps({
    "type": "assistant",
    "message": {"id": f"m_{role}_{arm}_{att}", "model": "claude-haiku-5-5", "usage": {"input_tokens": 50, "output_tokens": 15}},
}))
print(json.dumps({
    "type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
    "total_cost_usd": 0.0005, "usage": {"input_tokens": 50, "output_tokens": 15},
}))
"""
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            bank_p = tp / "stdio_bank.jsonl"
            row = {
                "task_id": "apps_synth_1",
                "difficulty": "competition",
                "prompt": "Read integer x and output 2*x + 1.",
                "examples": [{"input": "1\n", "output": "3"}, {"input": "2\n", "output": "5"}],
                "hidden_tests": [{"input": f"{x}\n", "output": f"{2 * x + 1}"} for x in range(3, 11)],
            }
            bank_p.write_text(json.dumps(row) + "\n", encoding="utf-8")
            bank_sha = sha256_file(bank_p)

            fc = tp / "fake_claude_stdio"
            fc.write_text(fake_stdio_claude, encoding="utf-8")
            fc.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            creds = tp / ".credentials.json"
            creds.write_text('{"claudeAiOauth":{"accessToken":"fake"}}\n', encoding="utf-8")

            plan_p = tp / "plan_stdio.json"
            atomic_write_json(
                plan_p,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "fl_stdio_fake_e2e",
                    "task_format": "stdio",
                    "bank_path": str(bank_p),
                    "bank_sha256": bank_sha,
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
                    "per_case_timeout_s": 2.0,
                },
            )
            root = tp / "run_stdio"
            FLRunner(plan_p, root, allow_uncommitted=True, verify_bank_sha=True).run()

            summ = analyze_root(root)
            self.assertEqual(summ["task_format"], "stdio")
            arms = summ["arms"]
            self.assertEqual(arms["B0"]["success_rate"], 0.0)
            self.assertEqual(arms["B0x3"]["success_rate"], 0.0)
            self.assertEqual(arms["EX"]["success_rate"], 0.0)
            self.assertEqual(arms["EX"]["false_accept_rate"], 1.0)
            for arm in ("GT", "TF", "XM", "MV", "CT"):
                self.assertEqual(arms[arm]["success_rate"], 1.0, f"stdio arm {arm} failed")
            self.assertEqual(arms["CT"]["incremental_cost_usd_total"], 0.0)


_FAKE_PI_WORKER_PY = r"""#!/usr/bin/env python3
import argparse, json, os, pathlib

ap = argparse.ArgumentParser()
ap.add_argument("--prompt", required=True)
args = ap.parse_args()
prompt = args.prompt

assert os.getcwd() == "/work", f"bad cwd: {os.getcwd()}"
assert os.environ.get("HOME") == "/sandbox_home"

role = os.environ.get("FL_ROLE", "")
arm = os.environ.get("FL_ARM", "")
att = int(os.environ.get("FL_ATTEMPT", "1"))
mode = os.environ.get("FL_FAKE_MODE", "normal")

CORRECT = "x = int(input().strip())\nprint(x * 2 + 1)\n"
ONLY_EX = "x = int(input().strip())\nprint(3 if x == 1 else (5 if x == 2 else -1))\n"
WRONG = "x = int(input().strip())\nprint(-999)\n"

if role == "tf_test_writer":
    pathlib.Path("/work/tests_spec.py").write_text(
        '[\n'
        '  {"input": "1\\n", "output": "3"},\n'
        '  {"input": "10\\n", "output": "21"},\n'
        ']\n',
        encoding="utf-8",
    )
elif role == "coder":
    sol_p = pathlib.Path("/work/solution.py")
    spec_p = pathlib.Path("/work/tests_spec.py")

    if arm == "TF":
        assert spec_p.is_file(), "TF pi coder must see read-only /work/tests_spec.py"
        try:
            spec_p.write_text("[]", encoding="utf-8")
            raise AssertionError("TF tests_spec.py must be read-only in pi sandbox")
        except OSError:
            pass
    elif arm in ("XMH", "XMVH"):
        assert not spec_p.exists(), f"{arm} pi coder must NOT see exam tests_spec.py"

    # Check feedback presence on retry for gated arms (never expected output!)
    if arm in ("GT", "EX", "TF", "XMH", "XMVH") and att >= 2:
        assert "Your previous solution failed on this input:" in prompt, f"{arm} att {att} missing feedback"
        assert "21" not in prompt and "15" not in prompt and "19" not in prompt, f"Expected output leaked in feedback: {prompt}"

    if arm == "B0":
        sol_p.write_text(WRONG, encoding="utf-8")
    elif arm == "B0x3":
        assert "Your previous solution failed on this input:" not in prompt
        sol_p.write_text(WRONG, encoding="utf-8")
    elif arm == "GT":
        sol_p.write_text(WRONG if att == 1 else CORRECT, encoding="utf-8")
    elif arm == "EX":
        sol_p.write_text(WRONG if att == 1 else ONLY_EX, encoding="utf-8")
    elif arm == "TF":
        sol_p.write_text(ONLY_EX if att == 1 else CORRECT, encoding="utf-8")
    elif arm == "XMH":
        sol_p.write_text(WRONG if att == 1 else CORRECT, encoding="utf-8")
    elif arm == "XMVH":
        if mode == "xmvh_undetermined":
            sol_p.write_text(WRONG, encoding="utf-8")
        else:
            sol_p.write_text(WRONG if att == 1 else CORRECT, encoding="utf-8")
    elif arm == "MV":
        assert "Your previous solution failed on this input:" not in prompt
        sol_p.write_text(WRONG if att == 1 else CORRECT, encoding="utf-8")
    else:
        sol_p.write_text(CORRECT, encoding="utf-8")

print(json.dumps({
    "type": "message_end",
    "message": {
        "role": "assistant",
        "stopReason": "stop",
        "usage": {"input": 120, "output": 40},
    },
}))
"""


_FAKE_CLAUDE_EXAM_PY = r"""#!/usr/bin/env python3
import json, os, pathlib, sys

role = os.environ.get("FL_ROLE", "")
mode = os.environ.get("FL_FAKE_MODE", "normal")
creds_path = pathlib.Path("/sandbox_home/.claude/.credentials.json")
creds_text = creds_path.read_text(encoding="utf-8") if creds_path.is_file() else ""

if mode == "auth_always_fail":
    print(json.dumps({
        "type": "result",
        "subtype": "error",
        "is_error": True,
        "result": "Failed to authenticate: OAuth token revoked (401)",
    }))
    sys.exit(1)

if mode == "auth_stale_until_fresh" and "fresh_token" not in creds_text:
    print(json.dumps({
        "type": "result",
        "subtype": "error",
        "is_error": True,
        "result": "Failed to authenticate: OAuth token revoked (401)",
    }))
    sys.exit(1)

if role in ("xmh_exam_writer", "xm_exam_writer"):
    if mode == "xmvh_one_disagree":
        # 2 statement examples: input "1\n"->3 (agrees), input "2\n"->999 (disagrees, 1/2 = half, NOT > half)
        # Plus extra case "7\n"->15
        pathlib.Path("/work/tests_spec.py").write_text(
            '[\n'
            '  {"input": "1\\n", "output": "3"},\n'
            '  {"input": "2\\n", "output": "999"},\n'
            '  {"input": "7\\n", "output": "15"},\n'
            ']\n',
            encoding="utf-8",
        )
    elif mode == "xmvh_fail_selfcheck":
        # Both statement examples disagree (2/2 > half) -> XMVH self-check fails -> undetermined!
        pathlib.Path("/work/tests_spec.py").write_text(
            '[\n'
            '  {"input": "1\\n", "output": "999"},\n'
            '  {"input": "2\\n", "output": "888"},\n'
            '  {"input": "7\\n", "output": "15"},\n'
            ']\n',
            encoding="utf-8",
        )
    else:
        pathlib.Path("/work/tests_spec.py").write_text(
            '[\n'
            '  {"input": "1\\n", "output": "3"},\n'
            '  {"input": "2\\n", "output": "5"},\n'
            '  {"input": "7\\n", "output": "15"},\n'
            '  {"input": "9\\n", "output": "19"},\n'
            ']\n',
            encoding="utf-8",
        )
elif role == "mv_input_gen":
    pathlib.Path("/work/gen_inputs.py").write_text(
        "def gen_inputs():\n    return [f'{i}\\n' for i in range(3, 13)]\n",
        encoding="utf-8",
    )
elif role == "coder":
    pathlib.Path("/work/solution.py").write_text("x = int(input().strip())\nprint(x * 2 + 1)\n", encoding="utf-8")

print(json.dumps({"type": "system", "subtype": "init", "cwd": "/work"}))
print(json.dumps({
    "type": "assistant",
    "message": {"id": f"ex_{role}", "model": "claude-haiku-5-5", "usage": {"input_tokens": 80, "output_tokens": 30}},
}))
print(json.dumps({
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "num_turns": 1,
    "total_cost_usd": 0.004,
    "usage": {"input_tokens": 80, "output_tokens": 30},
}))
"""


class TestPiWorkerHaikuExamAuthFeedbackAndBanks(unittest.TestCase):
    def test_retry_feedback_format_cap_and_no_expected_leak(self) -> None:
        stdio_task = {"task_format": "stdio", "entry_point": None}
        cases_s = [
            {"input": "10 20\n", "output": "SECRET_EXPECTED_999"},
            {"input": "30 40\n", "output": "SECRET_EXPECTED_888"},
        ]
        fb = build_retry_feedback(stdio_task, cases_s, {"passed": False, "first_failed_idx": 1})
        self.assertTrue(fb.startswith(FEEDBACK_PREFIX))
        self.assertIn("30 40", fb)
        self.assertNotIn("SECRET_EXPECTED", fb)
        self.assertLessEqual(len(fb.encode("utf-8")), FEEDBACK_MAX_BYTES)

        # Truncation <= 400 bytes even with long UTF-8 input
        long_cases = [{"input": "あ" * 500 + "\n", "output": "NEVER_SHOWN"}]
        fb_long = build_retry_feedback(stdio_task, long_cases, {"passed": False, "first_failed_idx": 0})
        self.assertTrue(fb_long.startswith(FEEDBACK_PREFIX))
        self.assertLessEqual(len(fb_long.encode("utf-8")), FEEDBACK_MAX_BYTES)
        self.assertNotIn("NEVER_SHOWN", fb_long)

        # Function task feedback includes entry_point(*args) only, never expected
        fn_task = {"task_format": "function", "entry_point": "solve"}
        cases_f = [{"args": [[1, 2, 3], "abc"], "expected": "HIDDEN_ANSWER_42"}]
        fb_fn = build_retry_feedback(fn_task, cases_f, {"passed": False, "first_failed_idx": 0})
        self.assertIn("solve([1, 2, 3], 'abc')", fb_fn)
        self.assertNotIn("HIDDEN_ANSWER_42", fb_fn)
        self.assertLessEqual(len(fb_fn.encode("utf-8")), FEEDBACK_MAX_BYTES)

    def test_xmvh_self_check_logic(self) -> None:
        examples = [
            {"input": "1\n", "output": "3"},
            {"input": "2\n", "output": "5"},
            {"input": "3\n", "output": "7"},
        ]
        # 1) All 3 agree
        exam_ok = [
            {"input": "1\n", "output": "3"},
            {"input": "2\n", "output": "5"},
            {"input": "3\n", "output": "7"},
            {"input": "10\n", "output": "21"},
        ]
        sc_ok = self_check_xmvh_exam(exam_ok, examples, task_format="stdio")
        self.assertFalse(sc_ok["self_check_failed"])
        self.assertEqual(sc_ok["n_discarded"], 0)
        self.assertEqual(sc_ok["n_gate_cases"], 4)

        # 2) 1 of 3 disagrees (<= half): discard disagreeing case, union with statement examples restores true output
        exam_one_bad = [
            {"input": "1\n", "output": "3"},
            {"input": "2\n", "output": "WRONG"},
            {"input": "3\n", "output": "7"},
            {"input": "10\n", "output": "21"},
        ]
        sc_one = self_check_xmvh_exam(exam_one_bad, examples, task_format="stdio")
        self.assertFalse(sc_one["self_check_failed"])
        self.assertEqual(sc_one["n_discarded"], 1)
        self.assertEqual(sc_one["n_disagreed"], 1)
        self.assertEqual(sc_one["n_gate_cases"], 4)
        out_for_2 = [c["output"] for c in sc_one["gate_cases"] if c["input"].strip() == "2"]
        self.assertEqual(out_for_2, ["5"])

        # 3) 2 of 3 disagree (> half): self-check failed -> whole exam discarded
        exam_two_bad = [
            {"input": "1\n", "output": "WRONG1"},
            {"input": "2\n", "output": "WRONG2"},
            {"input": "3\n", "output": "7"},
            {"input": "10\n", "output": "21"},
        ]
        sc_two = self_check_xmvh_exam(exam_two_bad, examples, task_format="stdio")
        self.assertTrue(sc_two["self_check_failed"])
        self.assertEqual(sc_two["n_disagreed"], 2)
        self.assertEqual(sc_two["gate_cases"], [])

        # 4) 1 of 2 disagrees (exactly half, NOT more than half): discard 1, keep rest U examples
        sc_half = self_check_xmvh_exam(
            [{"input": "1\n", "output": "3"}, {"input": "2\n", "output": "WRONG"}, {"input": "8\n", "output": "17"}],
            examples[:2],
            task_format="stdio",
        )
        self.assertFalse(sc_half["self_check_failed"])
        self.assertEqual(sc_half["n_discarded"], 1)
        self.assertEqual(sc_half["n_gate_cases"], 3)

    def test_claude_credential_refresh_and_auth_retry_and_infra_void(self) -> None:
        from unittest import mock

        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            bank_p = tp / "mini_stdio.jsonl"
            row = {
                "task_id": "apps_auth_1",
                "difficulty": "introductory",
                "prompt": "Read integer x and output 2*x + 1.",
                "examples": [{"input": "1\n", "output": "3"}, {"input": "2\n", "output": "5"}],
                "hidden_tests": [{"input": f"{x}\n", "output": f"{2 * x + 1}"} for x in range(3, 11)],
            }
            bank_p.write_text(json.dumps(row) + "\n", encoding="utf-8")
            bank_sha = sha256_file(bank_p)

            fc = tp / "fake_claude_auth"
            fc.write_text(_FAKE_CLAUDE_EXAM_PY, encoding="utf-8")
            fc.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

            creds = tp / ".credentials.json"
            creds.write_text('{"claudeAiOauth":{"accessToken":"stale_token"}}\n', encoding="utf-8")

            # Case A: stale token fails attempt 1, wait 60s called, host token rotates -> retry succeeds!
            plan_ok = tp / "plan_auth_ok.json"
            atomic_write_json(
                plan_ok,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "fl_auth_retry_ok",
                    "task_format": "stdio",
                    "bank_path": str(bank_p),
                    "bank_sha256": bank_sha,
                    "seed": 7,
                    "arms": ["B0"],
                    "model": {
                        "agent": "claude",
                        "model": "claude-haiku-5-5",
                        "claude_bin": str(fc),
                        "credentials_path": str(creds),
                        "fake_mode": "auth_stale_until_fresh",
                    },
                    "attempt_timeout_s": 20,
                },
            )

            import time as _time
            real_sleep = _time.sleep
            sleeps_ok: list[float] = []

            def _fake_sleep_rotate(secs: float) -> None:
                if secs < 10.0:
                    real_sleep(secs)
                    return
                sleeps_ok.append(secs)
                creds.write_text('{"claudeAiOauth":{"accessToken":"fresh_token"}}\n', encoding="utf-8")

            root_ok = tp / "root_auth_ok"
            with mock.patch("ops.fl.run_fl.time.sleep", side_effect=_fake_sleep_rotate):
                FLRunner(plan_ok, root_ok, allow_uncommitted=True, verify_bank_sha=True).run()

            rec_ok = json.loads((root_ok / "cells" / "apps_auth_1" / "B0" / "record.json").read_text(encoding="utf-8"))
            self.assertFalse(rec_ok["infra_void"])
            self.assertTrue(rec_ok["delivered_correct"])
            self.assertEqual(rec_ok["attempts"][0]["auth_retries"], 1)
            self.assertEqual(sleeps_ok, [60.0])
            self.assertFalse(rec_ok["attempts"][0]["auth_error"])

            # Case B: persistent auth failure -> retries 2 times (waiting 60s each) then marks infra_void
            plan_fail = tp / "plan_auth_fail.json"
            atomic_write_json(
                plan_fail,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "fl_auth_retry_fail",
                    "task_format": "stdio",
                    "bank_path": str(bank_p),
                    "bank_sha256": bank_sha,
                    "seed": 7,
                    "arms": ["B0"],
                    "model": {
                        "agent": "claude",
                        "model": "claude-haiku-5-5",
                        "claude_bin": str(fc),
                        "credentials_path": str(creds),
                        "fake_mode": "auth_always_fail",
                    },
                    "attempt_timeout_s": 20,
                },
            )
            sleeps_fail: list[float] = []

            def _fake_sleep_fail(secs: float) -> None:
                if secs < 10.0:
                    real_sleep(secs)
                    return
                sleeps_fail.append(secs)

            root_fail = tp / "root_auth_fail"
            with mock.patch("ops.fl.run_fl.time.sleep", side_effect=_fake_sleep_fail):
                FLRunner(plan_fail, root_fail, allow_uncommitted=True, verify_bank_sha=True).run()
            rec_fail = json.loads((root_fail / "cells" / "apps_auth_1" / "B0" / "record.json").read_text(encoding="utf-8"))
            self.assertTrue(rec_fail["infra_void"])
            self.assertEqual(rec_fail["attempts"][0]["auth_retries"], 2)
            self.assertEqual(sleeps_fail, [60.0, 60.0])
            self.assertTrue(rec_fail["attempts"][0]["auth_error"])

            summ_fail = analyze_root(root_fail)
            self.assertEqual(summ_fail["arms"]["B0"]["n_tasks"], 0)
            self.assertEqual(summ_fail["arms"]["B0"]["n_infra_void_tasks"], 1)
            self.assertEqual(summ_fail["arms"]["B0"]["infra_void_tasks"], ["apps_auth_1"])

    def test_pi_worker_and_haiku_exam_all_arms_feedback_cache_and_analyzer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            bank_p = tp / "apps_v2_mini.jsonl"
            row = {
                "task_id": "apps_intro_1",
                "difficulty": "introductory",
                "prompt": "Read integer x and output 2*x + 1.",
                "examples": [{"input": "1\n", "output": "3"}, {"input": "2\n", "output": "5"}],
                "hidden_tests": [{"input": f"{x}\n", "output": f"{2 * x + 1}"} for x in range(3, 11)],
            }
            bank_p.write_text(json.dumps(row) + "\n", encoding="utf-8")
            bank_sha = sha256_file(bank_p)

            fpi = tp / "fake_pi.py"
            fpi.write_text(_FAKE_PI_WORKER_PY, encoding="utf-8")
            fc = tp / "fake_claude_exam"
            fc.write_text(_FAKE_CLAUDE_EXAM_PY, encoding="utf-8")
            fc.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            creds = tp / ".credentials.json"
            creds.write_text('{"claudeAiOauth":{"accessToken":"fresh_token"}}\n', encoding="utf-8")

            # Run 1: full mixed pi + claude across B0, B0x3, GT, EX, TF, XMH, XMVH, MV
            plan_p = tp / "plan_pi_haiku.json"
            atomic_write_json(
                plan_p,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "fl_pi_haiku_e2e",
                    "task_format": "stdio",
                    "gt_source": "gate_hidden",
                    "bank_path": str(bank_p),
                    "bank_sha256": bank_sha,
                    "seed": 42,
                    "arms": ["B0", "B0x3", "GT", "EX", "TF", "XMH", "XMVH", "MV"],
                    "model": {
                        "agent": "pi",
                        "providers": ["fake_lms1004q9"],
                        "model": "qwen/qwen3.5-9b",
                        "fake_agent": str(fpi),
                        "ctx": 131072,
                    },
                    "exam": {
                        "agent": "claude",
                        "model": "claude-haiku-5-5",
                        "claude_bin": str(fc),
                        "credentials_path": str(creds),
                        "fake_mode": "xmvh_one_disagree",
                    },
                    "jobs": 1,
                    "attempt_timeout_s": 30,
                },
            )
            root = tp / "root_pi_haiku"
            FLRunner(plan_p, root, allow_uncommitted=True, verify_bank_sha=True).run()

            # Verify XMH cached the exam once and XMVH reused it (0 incremental exam cost) + dropped the 1 disagreeing example
            xmh_rec = json.loads((root / "cells" / "apps_intro_1" / "XMH" / "record.json").read_text(encoding="utf-8"))
            xmvh_rec = json.loads((root / "cells" / "apps_intro_1" / "XMVH" / "record.json").read_text(encoding="utf-8"))
            self.assertFalse(xmh_rec["judge_meta"]["exam_cached_reused"])
            self.assertTrue(xmvh_rec["judge_meta"]["exam_cached_reused"])
            self.assertEqual(xmh_rec["incremental_cost_usd"], 0.004)
            self.assertEqual(xmvh_rec["incremental_cost_usd"], 0.0)
            self.assertEqual(xmvh_rec["cost_usd"], 0.004)
            self.assertEqual(xmvh_rec["judge_meta"]["self_check"]["n_discarded"], 1)
            self.assertFalse(xmvh_rec["judge_meta"]["self_check"]["self_check_failed"])
            self.assertTrue(xmvh_rec["delivered_correct"])

            # XMH kept the bogus exam case ("2\n"->"999") -> false-rejected CORRECT on att 2 & 3 (3 attempts, gate=False)
            # whereas XMVH dropped the disagreeing case & restored true example -> passed gate on attempt 2!
            self.assertEqual(xmh_rec["attempts_count"], 3)
            self.assertTrue(xmh_rec["false_reject"])
            self.assertFalse(xmh_rec["gate_passed"])
            self.assertEqual(xmvh_rec["attempts_count"], 2)
            self.assertFalse(xmvh_rec["false_reject"])
            self.assertTrue(xmvh_rec["gate_passed"])

            # Verify feedback was sent & recorded on retry for GT, EX, TF, XMH, XMVH (and 0 for B0, B0x3, MV)
            for gated_arm in ("GT", "EX", "TF", "XMH", "XMVH"):
                rec = json.loads((root / "cells" / "apps_intro_1" / gated_arm / "record.json").read_text(encoding="utf-8"))
                self.assertGreaterEqual(rec["attempts_count"], 2, f"{gated_arm} expected >=2 attempts")
                self.assertIsNone(rec["attempts"][0]["feedback_sent"])
                self.assertEqual(rec["attempts"][0]["feedback_bytes"], 0)
                fb2 = rec["attempts"][1]["feedback_sent"]
                self.assertIsNotNone(fb2)
                self.assertTrue(fb2.startswith(FEEDBACK_PREFIX))
                self.assertGreater(rec["feedback_bytes_total"], 0)
                self.assertLessEqual(rec["attempts"][1]["feedback_bytes"], FEEDBACK_MAX_BYTES)
            for ungated_arm in ("B0", "B0x3", "MV"):
                rec = json.loads((root / "cells" / "apps_intro_1" / ungated_arm / "record.json").read_text(encoding="utf-8"))
                self.assertEqual(rec["feedback_bytes_total"], 0)

            # Verify analyzer: gt_gain, haiku_exam_cost, feedback bytes, and report formatting
            summ = analyze_root(root)
            self.assertEqual(summ["gt_gain"]["abs_diff"], 1.0)
            self.assertEqual(summ["gt_gain"]["abs_diff_pp"], 100.0)
            self.assertFalse(summ["gt_gain"]["indistinguishable"])
            self.assertEqual(summ["haiku_exam_cost"]["n_tasks"], 1)
            self.assertEqual(summ["haiku_exam_cost"]["per_task_mean_usd"], 0.004)
            self.assertGreater(summ["arms"]["GT"]["feedback_bytes_per_task_mean"], 0)
            md = format_report(summ)
            self.assertIn("GT gain (GT - B0x3)", md)
            self.assertNotIn("題組無法區分", md)
            self.assertIn("Haiku exam cost/task", md)
            self.assertIn("Fb(B)/Task", md)

            # Run 2: XMVH self-check failure (> half disagree -> whole exam discarded -> undetermined -> deliver attempt 1)
            plan_sc_fail = tp / "plan_xmvh_fail.json"
            atomic_write_json(
                plan_sc_fail,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "fl_xmvh_sc_fail",
                    "task_format": "stdio",
                    "bank_path": str(bank_p),
                    "bank_sha256": bank_sha,
                    "seed": 42,
                    "arms": ["B0x3", "GT", "XMVH"],
                    "model": {
                        "agent": "pi",
                        "providers": ["fake_lms1004q9"],
                        "model": "qwen/qwen3.5-9b",
                        "fake_agent": str(fpi),
                        "fake_mode": "xmvh_undetermined",
                    },
                    "exam": {
                        "agent": "claude",
                        "model": "claude-haiku-5-5",
                        "claude_bin": str(fc),
                        "credentials_path": str(creds),
                        "fake_mode": "xmvh_fail_selfcheck",
                    },
                    "jobs": 1,
                    "attempt_timeout_s": 30,
                },
            )
            root_sc = tp / "root_xmvh_fail"
            FLRunner(plan_sc_fail, root_sc, allow_uncommitted=True, verify_bank_sha=True).run()
            sc_rec = json.loads((root_sc / "cells" / "apps_intro_1" / "XMVH" / "record.json").read_text(encoding="utf-8"))
            self.assertTrue(sc_rec["undetermined"])
            self.assertEqual(sc_rec["undetermined_reason"], "exam_self_check_failed")
            self.assertEqual(sc_rec["attempts_count"], 1)
            self.assertEqual(sc_rec["delivered_attempt"], 1)
            self.assertTrue(sc_rec["judge_meta"]["self_check"]["self_check_failed"])

            # Verify analyzer prints "題組無法區分" when GT - B0x3 < 10pp
            summ_ind = analyze_root(root_sc)
            # In root_sc, B0x3=0.0 and GT=1.0 -> let's also check synthetic <10pp directly on format_report
            summ_low = dict(summ_ind)
            summ_low["gt_gain"] = {
                "gt_rate": 0.55,
                "b0x3_rate": 0.50,
                "abs_diff": 0.05,
                "abs_diff_pp": 5.0,
                "paired_mcnemar": {"n_paired_tasks": 20, "arm_only_pass": 1, "b0x3_only_pass": 0, "mcnemar_exact_p": 1.0},
                "indistinguishable": True,
            }
            self.assertIn("題組無法區分", format_report(summ_low))

    def test_apps_v2_filter_and_evalplus_bank_and_gt_source_visible(self) -> None:
        # 1) APPS v2 filter keeps introductory + interview + competition without downloading
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            raw_p = tp / "test.jsonl"
            sample_q = "Solve.\n\n-----Examples-----\nInput\n1\n\nOutput\n2\n"
            io_str = json.dumps({"inputs": [f"{i}\n" for i in range(6)], "outputs": [f"{i + 1}" for i in range(6)]})
            raw_rows = [
                {"problem_id": 1, "difficulty": "introductory", "question": sample_q, "input_output": io_str},
                {"problem_id": 2, "difficulty": "interview", "question": sample_q, "input_output": io_str},
                {"problem_id": 3, "difficulty": "competition", "question": sample_q, "input_output": io_str},
            ]
            raw_p.write_text("\n".join(json.dumps(r) for r in raw_rows) + "\n", encoding="utf-8")

            v2_entry = build_v2_from_existing(tp)
            self.assertEqual(v2_entry["counts"]["kept"], 3)
            self.assertEqual(v2_entry["by_difficulty"], {"competition": 1, "interview": 1, "introductory": 1})
            self.assertTrue((tp / "apps_fl_bank_v2.jsonl").is_file())
            manifest = json.loads((tp / "MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["v2"]["filtered_bank_sha256"], sha256_file(tp / "apps_fl_bank_v2.jsonl"))

        # 2) EvalPlus HumanEval+/MBPP+ bank loader (pinned sha256, base=visible, plus=hidden)
        if DEFAULT_EVALPLUS_DIR.is_dir():
            loaded_ep = load_bank_tasks(
                DEFAULT_EVALPLUS_DIR,
                task_format="function",
                bank_type="evalplus",
                gt_source="visible",
                seed=42,
                n_tasks=2,
                verify_sha256=True,
            )
            self.assertEqual(loaded_ep["bank_type"], "evalplus")
            self.assertEqual(loaded_ep["gt_source"], "visible")
            self.assertEqual(len(loaded_ep["tasks"]), 2)
            for t in loaded_ep["tasks"]:
                self.assertEqual(t["task_format"], "function")
                self.assertIn(t["difficulty"], ("humanevalplus", "mbppplus"))
                self.assertGreater(len(t["visible_tests"]), 0)
                self.assertGreater(len(t["eval_hidden"]), 0)
                self.assertEqual(len(t["eval_hidden"]), t["n_hidden_total"])

            # Verify gt_source="gate_hidden" splits plus tests 50/50
            loaded_split = load_evalplus_tasks(
                DEFAULT_EVALPLUS_DIR,
                seed=42,
                task_ids=[loaded_ep["tasks"][0]["task_id"]],
                gt_source="gate_hidden",
                verify_sha256=True,
            )
            t_sp = loaded_split["tasks"][0]
            self.assertGreater(len(t_sp["gate_hidden"]), 0)
            self.assertEqual(len(t_sp["gate_hidden"]) + len(t_sp["eval_hidden"]), t_sp["n_hidden_total"])


if __name__ == "__main__":
    unittest.main()
