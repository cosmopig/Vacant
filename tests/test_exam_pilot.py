"""Unit and local-smoke tests for the external-exam pilot (exam37).

Covers:
  - acceptance_source ("gate_visible" and fake "exam:*", unittest + pytest-style functions)
    without ever mutating or leaving tests in the worker workspace;
  - failing_tests_noexpect stripping expected values while keeping failing test names & inputs;
  - N3 workspace carry-over across 3 attempts, fixed review prompt, no early stop, deliver last;
  - cell-level and attempt-level false_accept / false_reject computation;
  - ops/redo/banks/import_exams.py (copy, MANIFEST sha256 check, refusal on missing tasks/kinds);
  - ops/redo/analysis/exam_metrics.py (gain share, "題組無法區分", McNemar vs N3 & A, FA/FR, tok/s, timeouts);
  - ops/redo/plans/exam37_colab_e4b.json schema/consistency check;
  - local end-to-end smoke: 1 task × all 7 arms [A, N3, GT, XM, XMV, PB, EX] with a fake agent.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REDO_PY = ROOT / "ops" / "redo" / "redo.py"
IMPORTER_PY = ROOT / "ops" / "redo" / "banks" / "import_exams.py"
METRICS_PY = ROOT / "ops" / "redo" / "analysis" / "exam_metrics.py"
PLAN_EXAM37 = ROOT / "ops" / "redo" / "plans" / "exam37_colab_e4b.json"
PLAN_EXAM37_PART1 = ROOT / "ops" / "redo" / "plans" / "exam37_colab_e4b_part1.json"
PLAN_EXAM37_PART2 = ROOT / "ops" / "redo" / "plans" / "exam37_colab_e4b_part2.json"
REF_OK_JSON = ROOT / "ops" / "redo" / "analysis" / "exam37_xm_reference_ok.json"
PLAN_CTL12 = ROOT / "ops" / "redo" / "plans" / "ctl12_colab_e4b.json"


def _load_mod(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_TOY_SCORER = r'''#!/usr/bin/env python3
import json, os, shutil, subprocess, sys, tempfile
hidden, ws = sys.argv[1], sys.argv[2]
d = tempfile.mkdtemp()
try:
    for f in os.listdir(ws):
        sp = os.path.join(ws, f)
        if os.path.isfile(sp):
            shutil.copy2(sp, os.path.join(d, f))
    for f in os.listdir(hidden):
        sp = os.path.join(hidden, f)
        if os.path.isfile(sp):
            shutil.copy2(sp, os.path.join(d, f))
    r = subprocess.run([sys.executable, "-B", "-m", "unittest", "sol_test"], cwd=d, capture_output=True, text=True)
    ok = (r.returncode == 0)
    print(json.dumps({"pass": ok, "tests_passed": 2 if ok else 0, "tests_total": 2, "status": "ok"}))
finally:
    shutil.rmtree(d, ignore_errors=True)
'''

_GATE_VISIBLE_TEST = (
    "import unittest\nfrom sol import solve\n\n"
    "class SolTest(unittest.TestCase):\n"
    "    def test_alpha(self):\n"
    "        self.assertEqual(solve(10), 101)\n"
    "    def test_beta(self):\n"
    "        self.assertEqual(solve(20), 202)\n"
)

_HIDDEN_TEST = (
    "import unittest\nfrom sol import solve\n\n"
    "class HiddenTest(unittest.TestCase):\n"
    "    def test_h1(self):\n"
    "        self.assertEqual(solve(10), 101)\n"
    "    def test_h2(self):\n"
    "        self.assertEqual(solve(99), 999)\n"
)


def _make_toy_exam_task(bank: pathlib.Path, task: str) -> pathlib.Path:
    tdir = bank / task
    (tdir / "workspace").mkdir(parents=True)
    (tdir / "gate_visible").mkdir(parents=True)
    (tdir / "hidden").mkdir(parents=True)
    for k in ("XM", "XMV", "PB", "EX"):
        (tdir / "exams" / k).mkdir(parents=True)
    (tdir / "workspace" / "goal.md").write_text("Write sol.py implementing solve(x).\n", encoding="utf-8")
    (tdir / "workspace" / "contract.md").write_text("Write your solution to `sol.py`.\n", encoding="utf-8")
    (tdir / "gate_visible" / "sol_test.py").write_text(_GATE_VISIBLE_TEST, encoding="utf-8")
    (tdir / "hidden" / "sol_test.py").write_text(_HIDDEN_TEST, encoding="utf-8")
    (tdir / "scorer.py").write_text(_TOY_SCORER, encoding="utf-8")
    return tdir


class TestExamPilot(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.redo = _load_mod("redo_exam_test", REDO_PY)
        cls.importer = _load_mod("import_exams_test", IMPORTER_PY)
        cls.metrics = _load_mod("exam_metrics_test", METRICS_PY)

    def test_acceptance_source_gate_visible_and_fake_exam_leave_ws_clean(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            bank = pathlib.Path(td) / "bank"
            tdir = _make_toy_exam_task(bank, "t1")
            # Put a pytest-style top-level function exam in exams/XM
            (tdir / "exams" / "XM" / "test_xm.py").write_text(
                "from sol import solve\n\n"
                "def test_xm_case1():\n"
                "    assert solve(10) == 101\n\n"
                "def test_xm_case2():\n"
                "    assert solve(20) == 202\n",
                encoding="utf-8",
            )
            ws = pathlib.Path(td) / "cand_ws"
            ws.mkdir()
            (ws / "sol.py").write_text("def solve(x):\n    return 101 if x == 10 else 0\n", encoding="utf-8")
            before = sorted(p.name for p in ws.iterdir())

            # 1) gate_visible (partial pass -> accept=False, per-test dict populated)
            acc_gv = self.redo.acceptance(tdir / "workspace", ws, {}, tdir=tdir, source="gate_visible")
            self.assertEqual(acc_gv["acceptance_source"], "gate_visible")
            self.assertEqual(acc_gv["status"], "ok")
            self.assertFalse(acc_gv["accept"])
            self.assertEqual(acc_gv["run"], 2)
            self.assertEqual(acc_gv["passed"], 1)
            self.assertEqual(
                acc_gv["test_results"],
                {"sol_test.SolTest.test_alpha": True, "sol_test.SolTest.test_beta": False},
            )
            self.assertEqual(sorted(p.name for p in ws.iterdir()), before)

            # 2) exam:XM (pytest-style functions -> per-test dict populated, ws untouched)
            acc_xm = self.redo.acceptance(tdir / "workspace", ws, {}, tdir=tdir, source="exam:XM")
            self.assertEqual(acc_xm["acceptance_source"], "exam:XM")
            self.assertEqual(acc_xm["status"], "ok")
            self.assertFalse(acc_xm["accept"])
            self.assertEqual(acc_xm["run"], 2)
            self.assertEqual(acc_xm["passed"], 1)
            self.assertTrue(acc_xm["test_results"]["test_xm.test_xm_case1"])
            self.assertFalse(acc_xm["test_results"]["test_xm.test_xm_case2"])
            self.assertEqual(sorted(p.name for p in ws.iterdir()), before)

            # 3) passing candidate passes both gate_visible and exam:XM
            (ws / "sol.py").write_text(
                "def solve(x):\n    return {10: 101, 20: 202, 99: 999}.get(x, 0)\n",
                encoding="utf-8",
            )
            self.assertTrue(self.redo.acceptance(tdir / "workspace", ws, {}, tdir=tdir, source="gate_visible")["accept"])
            self.assertTrue(self.redo.acceptance(tdir / "workspace", ws, {}, tdir=tdir, source="exam:XM")["accept"])
            self.assertEqual(sorted(p.name for p in ws.iterdir()), before)

            # 4) missing/empty exam source fails closed (I-4)
            acc_empty = self.redo.acceptance(tdir / "workspace", ws, {}, tdir=tdir, source="exam:PB")
            self.assertFalse(acc_empty["accept"])
            self.assertEqual(acc_empty["status"], "no_tests_in_source")

    def test_failing_tests_noexpect_strips_expected_values(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            bank = pathlib.Path(td) / "bank"
            tdir = _make_toy_exam_task(bank, "t_ne")
            (tdir / "gate_visible" / "sol_test.py").write_text(
                "import unittest\nfrom sol import solve\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_secret_case(self):\n"
                "        inp = 'MY_INPUT_77'\n"
                "        expected = 'SECRET_EXPECTED_999'\n"
                "        self.assertEqual(solve(inp), expected)\n",
                encoding="utf-8",
            )
            ws = pathlib.Path(td) / "ws"
            ws.mkdir()
            (ws / "sol.py").write_text("def solve(x):\n    return 'WRONG'\n", encoding="utf-8")
            acc = self.redo.acceptance(tdir / "workspace", ws, {}, tdir=tdir, source="gate_visible")
            self.assertFalse(acc["accept"])
            hint = self.redo.make_hint_failing_tests_noexpect(acc)
            self.assertIn("test_secret_case", hint)
            self.assertIn("MY_INPUT_77", hint)
            self.assertIn("solve(inp)", hint)
            self.assertNotIn("SECRET_EXPECTED_999", hint)
            self.assertLessEqual(len(hint.encode("utf-8")), 400)
            self.assertIsNone(self.redo._KS1_BANNED.search(hint))

            # Direct text-only fallback stripping (without first_input)
            raw_prob = (
                "test_direct (t.T)\n"
                "Traceback (most recent call last):\n"
                '  File "t.py", line 5, in test_direct\n'
                "    self.assertEqual(f('INPUT_ABC'), 'EXPECTED_XYZ')\n"
                "AssertionError: 'BAD' != 'EXPECTED_XYZ'\n"
            )
            san = self.redo.strip_expected_from_problem(raw_prob)
            assert san is not None
            self.assertIn("f('INPUT_ABC')", san)
            self.assertNotIn("EXPECTED_XYZ", san)

    def test_n3_workspace_carry_and_deliver_last(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            bank, state = tmp / "bank", tmp / "state"
            _make_toy_exam_task(bank, "t_n3")
            stub = tmp / "n3_stub.py"
            stub.write_text(
                "import json, os, pathlib, sys\n"
                "state = pathlib.Path(os.environ['STUB_STATE']); state.mkdir(exist_ok=True)\n"
                "cell = os.environ['REDO_CELL']\n"
                "cf = state / (cell.replace('/', '__') + '.n')\n"
                "n = int(cf.read_text()) + 1 if cf.exists() else 1; cf.write_text(str(n))\n"
                "(state / (cell.replace('/', '__') + f'.prompt{n}')).write_text(sys.argv[1])\n"
                "hist_f = pathlib.Path('carry.txt')\n"
                "prev = hist_f.read_text() if hist_f.is_file() else ''\n"
                "(state / (cell.replace('/', '__') + f'.seen{n}')).write_text(prev or '<NONE>')\n"
                "hist_f.write_text(prev + f'att{n};')\n"
                # Attempt 1 writes a hidden-passing sol, attempt 2 breaks it, attempt 3 fixes it -> deliver last = att3
                "if n in (1, 3):\n"
                "    pathlib.Path('sol.py').write_text('def solve(x):\\n    return {10: 101, 20: 202, 99: 999}.get(x, 0)\\n')\n"
                "else:\n"
                "    pathlib.Path('sol.py').write_text('def solve(x):\\n    return 0\\n')\n"
                "print(json.dumps({'type': 'message_end', 'message': {'role': 'assistant', 'usage': {'input': 40, 'output': 15}}}))\n",
                encoding="utf-8",
            )
            plan = {
                "schema": self.redo.SCHEMA, "id": "test_n3", "seed": 1, "bank": str(bank),
                "tasks": ["t_n3"], "reps": 1,
                "arms": {
                    "A": {"policy": "single", "attempt_timeout_s": 10},
                    "N3": {"policy": "continue", "max_attempts": 3, "attempt_timeout_s": 5,
                           "budget_s": 15, "min_attempt_s": 0.5, "hint": "review", "deliver": "last"},
                    "GT": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5,
                           "budget_s": 15, "min_attempt_s": 0.5, "acceptance_source": "gate_visible",
                           "hint": "failing_tests_noexpect"},
                },
                "pair": ["N3", "GT"], "attempt_timeout_s": 5, "backoff_scale": 0.0,
                "agent": {"argv": [sys.executable, str(stub), "{prompt}"],
                          "env": {"STUB_STATE": str(state)},
                          "export_cell_env": True, "usage": "pi_json"},
                "providers": [{"name": "stub", "provider": "p", "model": "m", "jobs": 1}],
                "acceptance": {"kind": "workspace_tests", "timeout_s": 30},
                "grader": {"timeout_s": 30, "visible_equals_grader": False},
            }
            pf = tmp / "plan.json"
            self.redo.write_json(pf, plan)
            root = tmp / "root"
            ns = argparse.Namespace(plan=str(pf), root=str(root), bank=None, only_tasks=None,
                                    only_reps=None, max_pairs=None, only_providers=None,
                                    allow_uncommitted_plan=True)
            self.assertEqual(self.redo.cmd_run(ns), 0)
            c_n3 = self.redo.read_json(root / "cells" / "t_n3" / "r1" / "N3" / "cell.json")
            self.assertEqual(c_n3["n_attempts"], 3)
            self.assertEqual(c_n3["delivered_attempt"], 3)
            self.assertTrue(c_n3["pass"])
            self.assertIsNone(c_n3["false_accept"])
            self.assertIsNone(c_n3["false_reject"])
            # Workspace carried across all 3 attempts:
            self.assertEqual((state / "t_n3__r1__N3.seen1").read_text(), "<NONE>")
            self.assertEqual((state / "t_n3__r1__N3.seen2").read_text(), "att1;")
            self.assertEqual((state / "t_n3__r1__N3.seen3").read_text(), "att1;att2;")
            # Prompts 2 and 3 get the exact fixed review prompt with NO test/check info:
            p2 = (state / "t_n3__r1__N3.prompt2").read_text()
            p3 = (state / "t_n3__r1__N3.prompt3").read_text()
            self.assertTrue(p2.endswith("\n\n---\n" + self.redo.REVIEW_HINT))
            self.assertEqual(p2, p3)
            self.assertNotIn("Failing tests", p2)
            self.assertNotIn("sol_test", p2)

    def test_false_accept_and_false_reject_computation(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            bank, state = tmp / "bank", tmp / "state"
            tdir = _make_toy_exam_task(bank, "t_fafr")
            # XM is a WEAK exam (always passes solve(10)==101, misses solve(99)==999 -> false_accept!)
            (tdir / "exams" / "XM" / "test_weak.py").write_text(
                "from sol import solve\ndef test_weak():\n    assert solve(10) == 101\n",
                encoding="utf-8",
            )
            # EX is an OVER-STRICT/BROKEN exam (fails even when hidden passes -> false_reject!)
            (tdir / "exams" / "EX" / "test_strict.py").write_text(
                "from sol import solve\ndef test_impossible():\n    assert solve(10) == -999999\n",
                encoding="utf-8",
            )
            stub = tmp / "fafr_stub.py"
            stub.write_text(
                "import json, os, pathlib\n"
                "cell = os.environ['REDO_CELL']; arm = cell.split('/')[2]\n"
                "att = int(os.environ['REDO_ATTEMPT'])\n"
                "if arm == 'XM':\n"
                # Passes weak XM (solve(10)==101), fails hidden (solve(99)!=999)
                "    pathlib.Path('sol.py').write_text('def solve(x):\\n    return 101 if x == 10 else 0\\n')\n"
                "elif arm == 'EX':\n"
                # Attempt 1 passes hidden (but EX rejects it -> false_reject!), attempt 2 fails hidden
                "    if att == 1:\n"
                "        pathlib.Path('sol.py').write_text('def solve(x):\\n    return {10: 101, 20: 202, 99: 999}.get(x, 0)\\n')\n"
                "    else:\n"
                "        pathlib.Path('sol.py').write_text('def solve(x):\\n    return 0\\n')\n"
                "else:\n"
                "    pathlib.Path('sol.py').write_text('def solve(x):\\n    return {10: 101, 20: 202, 99: 999}.get(x, 0)\\n')\n"
                "print(json.dumps({'type': 'message_end', 'message': {'role': 'assistant', 'usage': {'input': 30, 'output': 10}}}))\n",
                encoding="utf-8",
            )
            plan = {
                "schema": self.redo.SCHEMA, "id": "test_fafr", "seed": 2, "bank": str(bank),
                "tasks": ["t_fafr"], "reps": 1,
                "arms": {
                    "GT": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                           "min_attempt_s": 0.5, "acceptance_source": "gate_visible", "hint": "failing_tests_noexpect"},
                    "XM": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                           "min_attempt_s": 0.5, "acceptance_source": "exam:XM", "hint": "failing_tests_noexpect"},
                    "EX": {"policy": "restart", "max_attempts": 2, "attempt_timeout_s": 5, "budget_s": 10,
                           "min_attempt_s": 0.5, "acceptance_source": "exam:EX", "hint": "failing_tests_noexpect"},
                },
                "pair": ["XM", "GT"], "attempt_timeout_s": 5, "backoff_scale": 0.0,
                "agent": {"argv": [sys.executable, str(stub)], "env": {"STUB_STATE": str(state)},
                          "export_cell_env": True, "usage": "pi_json"},
                "providers": [{"name": "stub", "provider": "p", "model": "m", "jobs": 1}],
                "acceptance": {"kind": "workspace_tests", "timeout_s": 30},
                "grader": {"timeout_s": 30, "visible_equals_grader": False},
            }
            pf = tmp / "plan.json"
            self.redo.write_json(pf, plan)
            root = tmp / "root"
            ns = argparse.Namespace(plan=str(pf), root=str(root), bank=None, only_tasks=None,
                                    only_reps=None, max_pairs=None, only_providers=None,
                                    allow_uncommitted_plan=True)
            self.assertEqual(self.redo.cmd_run(ns), 0)

            c_xm = self.redo.read_json(root / "cells" / "t_fafr" / "r1" / "XM" / "cell.json")
            self.assertTrue(c_xm["accepted"])
            self.assertFalse(c_xm["pass"])
            self.assertTrue(c_xm["false_accept"])
            self.assertFalse(c_xm["false_reject"])
            self.assertEqual(c_xm["false_accept_attempts"], 1)
            self.assertEqual(c_xm["attempts"][0]["acceptance_source"], "exam:XM")
            self.assertTrue(c_xm["attempts"][0]["test_results"]["test_weak.test_weak"])

            c_ex = self.redo.read_json(root / "cells" / "t_fafr" / "r1" / "EX" / "cell.json")
            self.assertFalse(c_ex["accepted"])
            self.assertFalse(c_ex["pass"])
            self.assertFalse(c_ex["false_accept"])
            self.assertTrue(c_ex["false_reject"])
            self.assertEqual(c_ex["false_reject_attempts"], 1)
            self.assertTrue(c_ex["attempts"][0]["grade_pass"])
            self.assertFalse(c_ex["attempts"][1]["grade_pass"])

            c_gt = self.redo.read_json(root / "cells" / "t_fafr" / "r1" / "GT" / "cell.json")
            self.assertTrue(c_gt["accepted"])
            self.assertTrue(c_gt["pass"])
            self.assertFalse(c_gt["false_accept"])
            self.assertFalse(c_gt["false_reject"])

    def test_importer_copies_verifies_manifest_and_refuses_missing_tasks(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            bank = tmp / "bank"
            _make_toy_exam_task(bank, "t1")
            _make_toy_exam_task(bank, "t2")
            (bank / "MANIFEST.json").write_text(
                json.dumps({"task_order": ["t1", "t2"], "files_sha256": {}}), encoding="utf-8"
            )

            # 1) Missing t2 -> REFUSE with exit 2 and leave bank untouched
            bad_exam = tmp / "bad_exam"
            for k in ("XM", "XMV", "PB", "EX"):
                (bad_exam / "t1" / k).mkdir(parents=True)
                (bad_exam / "t1" / k / f"test_{k.lower()}.py").write_text("def test_ok(): pass\n", encoding="utf-8")
            rc = self.importer.main([str(bad_exam), str(bank)])
            self.assertEqual(rc, 2)
            self.assertEqual(list((bank / "t1" / "exams" / "XM").iterdir()), [])

            # 2) Valid exam dir with MANIFEST sha256 -> succeeds
            good_exam = tmp / "good_exam"
            files_sha = {}
            for t in ("t1", "t2"):
                for k in ("XM", "XMV", "PB", "EX"):
                    (good_exam / t / k).mkdir(parents=True)
                    fp = good_exam / t / k / f"test_{k.lower()}.py"
                    fp.write_text(f"def test_{t}_{k.lower()}(): pass\n", encoding="utf-8")
                    rel = fp.relative_to(good_exam).as_posix()
                    files_sha[rel] = hashlib.sha256(fp.read_bytes()).hexdigest()
            (good_exam / "MANIFEST.json").write_text(json.dumps({"files_sha256": files_sha}), encoding="utf-8")
            rc_ok = self.importer.main([str(good_exam), str(bank)])
            self.assertEqual(rc_ok, 0)
            self.assertTrue((bank / "t2" / "exams" / "EX" / "test_ex.py").is_file())
            bm = json.loads((bank / "MANIFEST.json").read_text(encoding="utf-8"))
            self.assertIn("t2/exams/EX/test_ex.py", bm["files_sha256"])

            # 3) Tampered file against MANIFEST sha256 -> REFUSE with exit 2
            (good_exam / "t1" / "XM" / "test_xm.py").write_text("# tampered\n", encoding="utf-8")
            rc_tamper = self.importer.main([str(good_exam), str(bank)])
            self.assertEqual(rc_tamper, 2)

    def test_exam_metrics_gain_share_indistinguishable_and_tok_s(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / "run"
            tasks = ["t1", "t2", "t3", "t4"]
            plan = {
                "id": "mock_exam", "tasks": tasks, "reps": 1,
                "arms": {
                    "A": {"policy": "single"},
                    "N3": {"policy": "continue", "hint": "review", "deliver": "last"},
                    "GT": {"policy": "restart", "acceptance_source": "gate_visible"},
                    "XM": {"policy": "restart", "acceptance_source": "exam:XM"},
                    "EX": {"policy": "restart", "acceptance_source": "exam:EX"},
                },
            }
            sha = "abc123"
            root.mkdir(parents=True)
            (root / "RUN.json").write_text(json.dumps({"plan_sha256": sha, "plan": plan}), encoding="utf-8")

            # Case 1: GT=4/4, N3=2/4 -> GT-N3=0.5; XM=3/4 (gain_share=0.5, FA=0 -> qualifies!); EX=4/4 but FA=0
            # Wait: make t4 for XM fail hidden & accepted? No, if XM=3/4 with 0 FA, qualifies; EX=3/4 with 1 FA (> 2*0) -> fails qual
            outcomes = {
                "A":  [True, False, False, False],
                "N3": [True, True, False, False],
                "GT": [True, True, True, True],
                "XM": [True, True, True, False],
                "EX": [True, True, True, False],
            }
            for arm, passes in outcomes.items():
                for i, t in enumerate(tasks):
                    cdir = root / "cells" / t / "r1" / arm
                    (cdir / "attempt_1" / "logs" / "sessions").mkdir(parents=True)
                    p = passes[i]
                    acc = p or (arm == "EX" and i == 3)  # EX has 1 false accept on t4
                    cell = {
                        "cell": f"{t}/r1/{arm}", "task": t, "rep": 1, "arm": arm,
                        "plan_sha256": sha, "infra_void": None, "n_attempts": 1,
                        "delivered_attempt": 1, "accepted": acc, "pass": p,
                        "wall_s": 10.0, "agent_wall_s": 9.0,
                        "false_accept": (acc and not p) if arm in ("GT", "XM", "EX") else None,
                        "false_reject": False if arm in ("GT", "XM", "EX") else None,
                        "attempts": [{
                            "k": 1, "accept": acc, "grade_pass": p, "timed_out": (arm == "A" and i == 3),
                            "wall_s": 9.0, "usage": {"calls": 1, "input": 100, "output": 50},
                        }],
                    }
                    (cdir / "cell.json").write_text(json.dumps(cell), encoding="utf-8")
                    # Session jsonl with 50 output tokens in 2.0s => 25.0 tok/s
                    t0_ms = int(self.metrics._iso_to_s("2026-11-27T00:00:00.000Z") * 1000)
                    sfile = cdir / "attempt_1" / "logs" / "sessions" / "s.jsonl"
                    sfile.write_text(
                        json.dumps({"type": "message", "timestamp": "2026-11-27T00:00:00.000Z",
                                    "message": {"role": "user", "timestamp": t0_ms}}) + "\n" +
                        json.dumps({"type": "message", "timestamp": "2026-11-27T00:00:02.000Z",
                                    "message": {"role": "assistant", "timestamp": t0_ms,
                                                "usage": {"input": 100, "output": 50}}}) + "\n",
                        encoding="utf-8",
                    )
            res = self.metrics.analyse(root)
            self.assertTrue(res["discriminable"])
            self.assertAlmostEqual(res["gain_share"]["GT"], 1.0)
            self.assertAlmostEqual(res["gain_share"]["XM"], 0.5)
            self.assertTrue(res["qualification"]["XM"]["qualifies"])
            self.assertFalse(res["qualification"]["EX"]["qualifies"])  # FA 0.25 > 2*0
            self.assertEqual(res["per_arm"]["A"]["timeouts"], 1)
            self.assertAlmostEqual(res["overall_per_stream_tok_s"]["aggregate"], 25.0)
            self.assertIn("XM", res["paired_vs_N3"])
            self.assertIn("XM", res["paired_vs_A"])

            # Case 2: GT <= N3 -> must print "題組無法區分"
            for i, t in enumerate(tasks):
                cp = root / "cells" / t / "r1" / "GT" / "cell.json"
                c = json.loads(cp.read_text(encoding="utf-8"))
                c["pass"] = (i == 0)  # GT = 1/4 < N3 = 2/4
                cp.write_text(json.dumps(c), encoding="utf-8")
            res2 = self.metrics.analyse(root)
            self.assertFalse(res2["discriminable"])
            self.assertEqual(res2["verdict"], "題組無法區分")
            self.assertIn("題組無法區分", self.metrics.render_report(res2))

    def test_plan_exam37_colab_e4b_loads_and_matches_ctl12_provider(self) -> None:
        plan = self.redo.load_plan(PLAN_EXAM37)
        ctl12 = self.redo.load_plan(PLAN_CTL12)
        self.assertEqual(len(plan["tasks"]), 37)
        self.assertEqual(plan["reps"], 2)
        self.assertEqual(list(plan["arms"].keys()), ["A", "N3", "GT", "XM", "XMV", "PB", "EX"])
        self.assertEqual(plan["providers"], ctl12["providers"])
        self.assertEqual(plan["agent"], ctl12["agent"])
        self.assertIn("題組無法區分", plan["prereg"]["readout"])
        self.assertIn("false-block", plan["prereg"]["readout"])
        self.assertEqual(plan["arms"]["GT"]["hint"], "failing_tests_noexpect")
        self.assertEqual(plan["arms"]["N3"]["policy"], "continue")

    def test_local_smoke_one_task_all_seven_arms(self) -> None:
        """Local smoke: 1 task × all 7 arms [A, N3, GT, XM, XMV, PB, EX] with fake agent + exam_metrics."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            bank, state, exam_src = tmp / "bank", tmp / "state", tmp / "exam_src"
            _make_toy_exam_task(bank, "ex_smoke")
            (bank / "MANIFEST.json").write_text(
                json.dumps({"task_order": ["ex_smoke"], "files_sha256": {}}), encoding="utf-8"
            )
            # Build frozen fake exams for all 4 kinds and import via import_exams.py
            exam_contents = {
                "XM": "from sol import solve\ndef test_xm():\n    assert solve(10) == 101 and solve(99) == 999\n",
                "XMV": "import unittest\nfrom sol import solve\nclass T(unittest.TestCase):\n    def test_xmv(self):\n        self.assertEqual(solve(10), 101)\n        self.assertEqual(solve(99), 999)\n",
                "PB": "from sol import solve\ndef test_pb():\n    for k, v in [(10, 101), (99, 999)]:\n        assert solve(k) == v\n",
                "EX": "from sol import solve\ndef test_ex_weak():\n    assert solve(10) == 101\n",
            }
            files_sha = {}
            for kind, code in exam_contents.items():
                fp = exam_src / "ex_smoke" / kind / f"test_{kind.lower()}.py"
                fp.parent.mkdir(parents=True)
                fp.write_text(code, encoding="utf-8")
                files_sha[fp.relative_to(exam_src).as_posix()] = hashlib.sha256(fp.read_bytes()).hexdigest()
            (exam_src / "MANIFEST.json").write_text(json.dumps({"files_sha256": files_sha}), encoding="utf-8")
            self.assertEqual(self.importer.main([str(exam_src), str(bank)]), 0)

            stub = tmp / "smoke_agent.py"
            stub.write_text(
                "import json, os, pathlib, sys\n"
                "cell = os.environ['REDO_CELL']; arm = cell.split('/')[2]\n"
                "att = int(os.environ['REDO_ATTEMPT'])\n"
                "GOOD = 'def solve(x):\\n    return {10: 101, 20: 202, 99: 999}.get(x, 0)\\n'\n"
                "PARTIAL = 'def solve(x):\\n    return 101 if x == 10 else 0\\n'\n"
                "BAD = 'def solve(x):\\n    return 0\\n'\n"
                "if arm == 'A':\n"
                "    pathlib.Path('sol.py').write_text(BAD)\n"
                "elif arm == 'N3':\n"
                "    pathlib.Path('step.log').open('a').write(f'{att},')\n"
                "    pathlib.Path('sol.py').write_text(BAD)\n"
                "elif arm == 'EX':\n"
                "    pathlib.Path('sol.py').write_text(PARTIAL)\n"
                "else:\n"
                "    pathlib.Path('sol.py').write_text(GOOD if att >= 2 else PARTIAL)\n"
                "print(json.dumps({'type': 'message_end', 'message': {'role': 'assistant', 'usage': {'input': 60, 'output': 25}}}))\n",
                encoding="utf-8",
            )
            plan = {
                "schema": self.redo.SCHEMA, "id": "local_smoke_7arms", "seed": 20261127,
                "bank": str(bank), "tasks": ["ex_smoke"], "reps": 1,
                "arms": {
                    "A": {"policy": "single", "attempt_timeout_s": 10},
                    "N3": {"policy": "continue", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                           "min_attempt_s": 0.5, "hint": "review", "deliver": "last"},
                    "GT": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                           "min_attempt_s": 0.5, "acceptance_source": "gate_visible", "hint": "failing_tests_noexpect"},
                    "XM": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                           "min_attempt_s": 0.5, "acceptance_source": "exam:XM", "hint": "failing_tests_noexpect"},
                    "XMV": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                            "min_attempt_s": 0.5, "acceptance_source": "exam:XMV", "hint": "failing_tests_noexpect"},
                    "PB": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                           "min_attempt_s": 0.5, "acceptance_source": "exam:PB", "hint": "failing_tests_noexpect"},
                    "EX": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                           "min_attempt_s": 0.5, "acceptance_source": "exam:EX", "hint": "failing_tests_noexpect"},
                },
                "pair": ["N3", "GT"], "attempt_timeout_s": 5, "backoff_scale": 0.0,
                "agent": {"argv": [sys.executable, str(stub), "{prompt}"],
                          "env": {"STUB_STATE": str(state)},
                          "export_cell_env": True, "usage": "pi_json"},
                "providers": [{"name": "stub", "provider": "p", "model": "m", "jobs": 1}],
                "acceptance": {"kind": "workspace_tests", "timeout_s": 30},
                "grader": {"timeout_s": 30, "visible_equals_grader": False},
            }
            pf = tmp / "smoke_plan.json"
            self.redo.write_json(pf, plan)
            root = tmp / "smoke_root"
            # Preflight must pass with --allow-uncommitted-plan
            pf_rc = subprocess.run(
                [sys.executable, str(REDO_PY), "preflight", "--plan", str(pf), "--allow-uncommitted-plan"],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(pf_rc.returncode, 0, pf_rc.stdout + pf_rc.stderr)
            self.assertIn("PREFLIGHT_OK", pf_rc.stdout)

            # Run all 7 arms
            run_rc = subprocess.run(
                [sys.executable, str(REDO_PY), "run", "--plan", str(pf), "--root", str(root), "--allow-uncommitted-plan"],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(run_rc.returncode, 0, run_rc.stdout + run_rc.stderr)

            # Analyze with exam_metrics.py
            met_rc = subprocess.run(
                [sys.executable, str(METRICS_PY), str(root), "--json"],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(met_rc.returncode, 0, met_rc.stdout + met_rc.stderr)
            res = json.loads(met_rc.stdout)
            self.assertTrue(res["discriminable"])
            self.assertEqual(res["per_arm"]["A"]["hidden_pass"], 0)
            self.assertEqual(res["per_arm"]["N3"]["hidden_pass"], 0)
            for arm in ("GT", "XM", "XMV", "PB"):
                self.assertEqual(res["per_arm"][arm]["hidden_pass"], 1, arm)
                self.assertAlmostEqual(res["gain_share"][arm], 1.0, msg=arm)
            self.assertEqual(res["per_arm"]["EX"]["hidden_pass"], 0)
            self.assertEqual(res["per_arm"]["EX"]["false_accept_cells"], 1)
            self.assertFalse(res["qualification"]["EX"]["qualifies"])
            self.assertTrue(res["qualification"]["XM"]["qualifies"])

    def test_acceptance_pass_ratio_threshold_errors_and_hint(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            bank = tmp / "bank"
            tdir = _make_toy_exam_task(bank, "t_ratio")
            # Build a 20-test exam in exams/XMT where test_i checks solve(i) == i * 10
            lines = ["from sol import solve\n"]
            for i in range(1, 21):
                lines.append(f"def test_case_{i:02d}():\n    inp = {i}\n    expected = {i * 10}\n    assert solve(inp) == expected\n")
            (tdir / "exams" / "XMT").mkdir(parents=True, exist_ok=True)
            (tdir / "exams" / "XMT" / "test_xmt.py").write_text("\n".join(lines), encoding="utf-8")

            # Also build a degenerate exam with 0 test functions (module-level assert like ex_series XMV)
            (tdir / "exams" / "ZERO").mkdir(parents=True, exist_ok=True)
            (tdir / "exams" / "ZERO" / "test_zero.py").write_text("from sol import solve\nassert solve(1) == 10\n", encoding="utf-8")

            ws = tmp / "ws"
            ws.mkdir()

            # 1) 17/20 pass = 0.85 -> accepted under ratio 0.85, rejected under strict (None)
            (ws / "sol.py").write_text("def solve(x):\n    return x * 10 if x <= 17 else -1\n", encoding="utf-8")
            acc_strict = self.redo.acceptance(tdir / "workspace", ws, {}, tdir=tdir, source="exam:XMT")
            self.assertFalse(acc_strict["accept"])
            self.assertNotIn("pass_ratio", acc_strict)
            self.assertNotIn("acceptance_pass_ratio", acc_strict)

            acc_85 = self.redo.acceptance(tdir / "workspace", ws, {}, tdir=tdir, source="exam:XMT", pass_ratio=0.85)
            self.assertEqual(acc_85["status"], "ok")
            self.assertEqual(acc_85["passed"], 17)
            self.assertEqual(acc_85["run"], 20)
            self.assertAlmostEqual(acc_85["pass_ratio"], 0.85)
            self.assertEqual(acc_85["acceptance_pass_ratio"], 0.85)
            self.assertTrue(acc_85["accept"])

            # 2) 16/20 pass = 0.80 < 0.85 -> rejected, hint keeps failing test + input, strips expected
            (ws / "sol.py").write_text("def solve(x):\n    return x * 10 if x <= 16 else -1\n", encoding="utf-8")
            acc_80 = self.redo.acceptance(tdir / "workspace", ws, {}, tdir=tdir, source="exam:XMT", pass_ratio=0.85)
            self.assertFalse(acc_80["accept"])
            self.assertAlmostEqual(acc_80["pass_ratio"], 0.8)
            hint = self.redo.make_hint_failing_tests_noexpect(acc_80)
            self.assertIn("test_case_17", hint)
            self.assertIn("inp = 17", hint)
            self.assertNotIn("170", hint)
            self.assertLessEqual(len(hint.encode("utf-8")), 400)

            # 3) load_error (syntax error in sol.py) -> fail with pass_ratio=0.0
            (ws / "sol.py").write_text("def solve(x):\n    return (\n", encoding="utf-8")
            acc_err = self.redo.acceptance(tdir / "workspace", ws, {}, tdir=tdir, source="exam:XMT", pass_ratio=0.85)
            self.assertEqual(acc_err["status"], "load_error")
            self.assertFalse(acc_err["accept"])
            self.assertEqual(acc_err["pass_ratio"], 0.0)

            # 4) 0 collected test functions -> fail closed with pass_ratio=0.0
            (ws / "sol.py").write_text("def solve(x):\n    return x * 10\n", encoding="utf-8")
            acc_zero = self.redo.acceptance(tdir / "workspace", ws, {}, tdir=tdir, source="exam:ZERO", pass_ratio=0.85)
            self.assertEqual(acc_zero["run"], 0)
            self.assertFalse(acc_zero["accept"])
            self.assertEqual(acc_zero["pass_ratio"], 0.0)

            # 5) load_plan validation rejects bad acceptance_pass_ratio values
            base_plan = {
                "schema": self.redo.SCHEMA, "id": "bad_ratio", "tasks": ["t_ratio"], "reps": 1,
                "arms": {
                    "A": {"policy": "single", "attempt_timeout_s": 5},
                    "XMT": {"policy": "restart", "acceptance_source": "exam:XMT", "acceptance_pass_ratio": 0.0},
                },
                "pair": ["A", "XMT"], "attempt_timeout_s": 5,
                "agent": {"argv": ["true"]}, "providers": [{"name": "p", "jobs": 1}],
            }
            pf = tmp / "bad.json"
            for bad_val in (0.0, -0.1, 1.01, True, "0.85"):
                base_plan["arms"]["XMT"]["acceptance_pass_ratio"] = bad_val
                self.redo.write_json(pf, base_plan)
                with self.assertRaises(self.redo.PlanError):
                    self.redo.load_plan(pf)

    def test_exam_metrics_false_block_stratification_and_combined_roots(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            root1 = tmp / "part1"
            root2 = tmp / "part2"
            tasks = ["t_ok_1", "t_ok_2", "t_fail_1", "t_fail_2"]
            ref_ok = {
                "xm_reference_ok": ["t_ok_1", "t_ok_2"],
                "xm_reference_fail": ["t_fail_1", "t_fail_2"],
            }
            ref_ok_path = tmp / "ref_ok.json"
            ref_ok_path.write_text(json.dumps(ref_ok), encoding="utf-8")

            plan1 = {
                "id": "mock_part1", "tasks": tasks, "reps": 1,
                "arms": {
                    "A": {"policy": "single"},
                    "N3": {"policy": "continue", "hint": "review", "deliver": "last"},
                    "GT": {"policy": "restart", "acceptance_source": "gate_visible"},
                    "XM": {"policy": "restart", "acceptance_source": "exam:XM"},
                },
            }
            plan2 = {
                "id": "mock_part2", "tasks": tasks, "reps": 1,
                "arms": {
                    "XMV": {"policy": "restart", "acceptance_source": "exam:XMV"},
                    "PB": {"policy": "restart", "acceptance_source": "exam:PB"},
                    "XMT": {"policy": "restart", "acceptance_source": "exam:XMT", "acceptance_pass_ratio": 0.85},
                },
            }
            root1.mkdir(parents=True)
            root2.mkdir(parents=True)
            (root1 / "RUN.json").write_text(json.dumps({"plan_sha256": "sha1", "plan": plan1}), encoding="utf-8")
            (root2 / "RUN.json").write_text(json.dumps({"plan_sha256": "sha2", "plan": plan2}), encoding="utf-8")

            def write_cell(root: pathlib.Path, sha: str, task: str, arm: str, *,
                           attempts: list[dict], delivered_idx: int, gated: bool) -> None:
                cdir = root / "cells" / task / "r1" / arm
                cdir.mkdir(parents=True, exist_ok=True)
                d = attempts[delivered_idx]
                fa = (bool(d["accept"]) and d["grade_pass"] is False) if gated else None
                fr = any((not bool(a["accept"])) and a["grade_pass"] is True for a in attempts) if gated else None
                cell = {
                    "cell": f"{task}/r1/{arm}", "task": task, "rep": 1, "arm": arm,
                    "plan_sha256": sha, "infra_void": None, "n_attempts": len(attempts),
                    "delivered_attempt": delivered_idx + 1, "accepted": bool(d["accept"]),
                    "pass": bool(d["grade_pass"]), "wall_s": 10.0, "agent_wall_s": 9.0,
                    "false_accept": fa, "false_reject": fr, "attempts": attempts,
                }
                (cdir / "cell.json").write_text(json.dumps(cell), encoding="utf-8")

            def att(k: int, acc: bool, gp: bool) -> dict:
                return {"k": k, "accept": acc, "grade_pass": gp, "timed_out": False,
                        "wall_s": 4.0, "usage": {"calls": 1, "input": 50, "output": 20}}

            # Part 1:
            # A:  [F, F, F, F] (0/4)
            # N3: [T, F, F, F] (1/4)
            # GT: [T, T, T, T] (4/4) -> GT-N3 = 0.75
            # XM: ok tasks [T, T], fail tasks [F (false-blocked on att1!), F] -> 2/4; ok=1.0, fail=0.0; FB=1/4 cells, 1/5 atts
            for i, t in enumerate(tasks):
                write_cell(root1, "sha1", t, "A", attempts=[att(1, False, False)], delivered_idx=0, gated=False)
                write_cell(root1, "sha1", t, "N3", attempts=[att(1, False, i == 0)], delivered_idx=0, gated=False)
                write_cell(root1, "sha1", t, "GT", attempts=[att(1, True, True)], delivered_idx=0, gated=True)
                if t == "t_fail_1":
                    # Attempt 1 passes hidden but XM gate rejects (false_block!), attempt 2 fails hidden
                    write_cell(root1, "sha1", t, "XM", attempts=[att(1, False, True), att(2, False, False)], delivered_idx=1, gated=True)
                else:
                    p = t.startswith("t_ok")
                    write_cell(root1, "sha1", t, "XM", attempts=[att(1, p, p)], delivered_idx=0, gated=True)

            # Part 2:
            # XMV: [T, T, F (false-blocked twice!), F] -> 2/4; FB cells=1/4, FB atts=2/6
            # PB:  [T, T, T, F] -> 3/4 (gain_share = (0.75 - 0.25)/0.75 = 0.6667, FA=0 -> qualifies!)
            # XMT: [T, T, T, F (FA)] -> 3/4, FA=0.25 > 2*0 -> does not qualify
            for t in tasks:
                if t == "t_fail_1":
                    write_cell(root2, "sha2", t, "XMV",
                               attempts=[att(1, False, True), att(2, False, True), att(3, False, False)],
                               delivered_idx=2, gated=True)
                else:
                    p = t.startswith("t_ok")
                    write_cell(root2, "sha2", t, "XMV", attempts=[att(1, p, p)], delivered_idx=0, gated=True)
                p_pb = t != "t_fail_2"
                write_cell(root2, "sha2", t, "PB", attempts=[att(1, p_pb, p_pb)], delivered_idx=0, gated=True)
                if t == "t_fail_2":
                    write_cell(root2, "sha2", t, "XMT", attempts=[att(1, True, False)], delivered_idx=0, gated=True)
                else:
                    write_cell(root2, "sha2", t, "XMT", attempts=[att(1, True, True)], delivered_idx=0, gated=True)

            # Combine via CLI
            proc = subprocess.run(
                [sys.executable, str(METRICS_PY), str(root1), str(root2), "--reference-ok-json", str(ref_ok_path), "--json"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            res = json.loads(proc.stdout)

            self.assertEqual(list(res["per_arm"].keys()), ["A", "N3", "GT", "XM", "XMV", "PB", "XMT"])
            self.assertEqual(len(res["roots"]), 2)
            self.assertTrue(res["discriminable"])
            # False-block (per-cell and per-attempt)
            self.assertEqual(res["per_arm"]["XM"]["false_block_cells"], 1)
            self.assertAlmostEqual(res["per_arm"]["XM"]["false_block_cell_rate"], 0.25)
            self.assertEqual(res["per_arm"]["XM"]["false_block_attempts"], 1)
            self.assertAlmostEqual(res["per_arm"]["XM"]["false_block_attempt_rate"], 0.2)
            self.assertEqual(res["per_arm"]["XMV"]["false_block_cells"], 1)
            self.assertAlmostEqual(res["per_arm"]["XMV"]["false_block_cell_rate"], 0.25)
            self.assertEqual(res["per_arm"]["XMV"]["false_block_attempts"], 2)
            self.assertAlmostEqual(res["per_arm"]["XMV"]["false_block_attempt_rate"], round(2 / 6, 4))
            # Part-2 arms compared against Part-1's N3 and GT
            for arm in ("XMV", "PB", "XMT"):
                self.assertIn(arm, res["paired_vs_N3"])
                self.assertIn(arm, res["paired_vs_A"])
                self.assertIn(arm, res["qualification"])
            self.assertTrue(res["qualification"]["PB"]["qualifies"])
            self.assertFalse(res["qualification"]["XMT"]["qualifies"])
            self.assertAlmostEqual(res["per_arm"]["XMT"]["acceptance_pass_ratio"], 0.85)

            # Stratified table (2 ok vs 2 fail)
            strat = res["stratified_by_xm_reference_ok"]
            self.assertIsNotNone(strat)
            self.assertEqual(strat["xm_ref_ok"]["n_tasks"], 2)
            self.assertEqual(strat["xm_ref_fail"]["n_tasks"], 2)
            self.assertAlmostEqual(strat["xm_ref_ok"]["per_arm"]["XM"]["hidden_success_rate"], 1.0)
            self.assertAlmostEqual(strat["xm_ref_fail"]["per_arm"]["XM"]["hidden_success_rate"], 0.0)
            self.assertAlmostEqual(strat["xm_ref_fail"]["per_arm"]["PB"]["hidden_success_rate"], 0.5)
            self.assertAlmostEqual(strat["xm_ref_fail"]["per_arm"]["XMV"]["false_block_cell_rate"], 0.5)

            md = self.metrics.render_report(res)
            self.assertIn("Combined roots (2)", md)
            self.assertIn("Stratified by XM Exam Correctness", md)
            self.assertIn("False-Block (cell)", md)

            # Duplicate arm name across roots must raise ValueError
            with self.assertRaises(ValueError):
                self.metrics.analyse([root1, root1])

    def test_plan_exam37_colab_e4b_part2_and_reference_ok_json(self) -> None:
        p1 = self.redo.load_plan(PLAN_EXAM37_PART1)
        p2 = self.redo.load_plan(PLAN_EXAM37_PART2)
        for field in ("schema", "seed", "bank", "bank_candidates", "attempt_timeout_s",
                      "agent", "providers", "acceptance", "grader", "tasks", "reps"):
            self.assertEqual(p2[field], p1[field], f"part2 {field} differs from part1")
        self.assertEqual(list(p2["arms"].keys()), ["XMV", "PB", "XMT"])
        self.assertEqual(p2["arms"]["XMV"]["acceptance_source"], "exam:XMV")
        self.assertNotIn("acceptance_pass_ratio", p2["arms"]["XMV"])
        self.assertEqual(p2["arms"]["PB"]["acceptance_source"], "exam:PB")
        self.assertNotIn("acceptance_pass_ratio", p2["arms"]["PB"])
        self.assertEqual(p2["arms"]["XMT"]["acceptance_source"], "exam:XMT")
        self.assertEqual(p2["arms"]["XMT"]["acceptance_pass_ratio"], 0.85)
        for arm in ("XMV", "PB", "XMT"):
            self.assertEqual(p2["arms"][arm]["hint"], "failing_tests_noexpect")
            self.assertEqual(p2["arms"][arm]["budget_s"], 1800)
            self.assertEqual(p2["arms"][arm]["attempt_timeout_s"], 600)
            self.assertEqual(p2["arms"][arm]["max_attempts"], 3)

        prereg_txt = json.dumps(p2["prereg"], ensure_ascii=False)
        for must_have in ("EX", "ex_luhn", "ex_say", "ex_series", "40", "0.85", "28/37", "26/37",
                          "false-accept", "false-block", "28", "9", "vacant-cloud", "Haiku", "87%", "85%", "73%"):
            self.assertIn(must_have, prereg_txt)

        ref = json.loads(REF_OK_JSON.read_text(encoding="utf-8"))
        self.assertEqual(len(ref["xm_reference_ok"]), 28)
        self.assertEqual(len(ref["xm_reference_fail"]), 9)
        self.assertEqual(len(ref["xmv_reference_ok"]), 26)
        self.assertEqual(len(ref["xmv_reference_fail"]), 11)
        self.assertEqual(len(ref["pb_reference_ok"]), 26)
        self.assertEqual(len(ref["pb_reference_fail"]), 11)
        self.assertEqual(set(ref["xm_reference_ok"]) | set(ref["xm_reference_fail"]), set(p1["tasks"]))
        self.assertEqual(set(ref["xm_reference_ok"]) & set(ref["xm_reference_fail"]), set())

    def test_local_smoke_part2_combined_with_part1(self) -> None:
        """Fake-agent local smoke of part2 (XMV, PB, XMT@0.85) combined with part1 (A, N3, GT, XM) on 1 task."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            bank, state = tmp / "bank", tmp / "state"
            tdir = _make_toy_exam_task(bank, "ex_luhn")
            # XM/XMT has 10 tests: 9 pass on GOOD_SOL, 1 is a flawed exam test (simulating ~10% flawed exam assertions)
            xm_lines = ["from sol import solve\n"]
            for i in range(1, 10):
                xm_lines.append(f"def test_ok_{i}():\n    assert solve(10) == 101\n")
            xm_lines.append("def test_flawed_10():\n    assert solve(10) == -999\n")
            xm_code = "\n".join(xm_lines)
            (tdir / "exams" / "XM" / "test_xm.py").write_text(xm_code, encoding="utf-8")
            (tdir / "exams" / "XMT").mkdir(parents=True, exist_ok=True)
            (tdir / "exams" / "XMT" / "test_xm.py").write_text(xm_code, encoding="utf-8")
            (tdir / "exams" / "XMV" / "test_xmv.py").write_text(
                "from sol import solve\ndef test_xmv():\n    assert solve(10) == 101 and solve(99) == 999\n",
                encoding="utf-8",
            )
            (tdir / "exams" / "PB" / "test_pb.py").write_text(
                "from sol import solve\ndef test_pb():\n    assert solve(10) == 101 and solve(99) == 999\n",
                encoding="utf-8",
            )

            stub = tmp / "part2_smoke_agent.py"
            stub.write_text(
                "import json, os, pathlib\n"
                "cell = os.environ['REDO_CELL']; arm = cell.split('/')[2]\n"
                "att = int(os.environ['REDO_ATTEMPT'])\n"
                "GOOD = 'def solve(x):\\n    return {10: 101, 20: 202, 99: 999}.get(x, 0)\\n'\n"
                "BAD = 'def solve(x):\\n    return 0\\n'\n"
                "if arm in ('A', 'N3'):\n"
                "    pathlib.Path('sol.py').write_text(BAD)\n"
                "elif arm in ('XM', 'XMT'):\n"
                # Attempt 1 writes GOOD (9/10 on XM -> strict XM rejects & false-blocks; XMT@0.85 accepts 0.9 >= 0.85!)
                "    pathlib.Path('sol.py').write_text(GOOD if att == 1 else BAD)\n"
                "else:\n"
                "    pathlib.Path('sol.py').write_text(GOOD if att >= 2 else BAD)\n"
                "print(json.dumps({'type': 'message_end', 'message': {'role': 'assistant', 'usage': {'input': 50, 'output': 20}}}))\n",
                encoding="utf-8",
            )
            common = {
                "schema": self.redo.SCHEMA, "seed": 20261127, "bank": str(bank), "tasks": ["ex_luhn"], "reps": 1,
                "attempt_timeout_s": 5, "backoff_scale": 0.0,
                "agent": {"argv": [sys.executable, str(stub), "{prompt}"], "env": {"STUB_STATE": str(state)},
                          "export_cell_env": True, "usage": "pi_json"},
                "providers": [{"name": "stub", "provider": "p", "model": "m", "jobs": 1}],
                "acceptance": {"kind": "workspace_tests", "timeout_s": 30},
                "grader": {"timeout_s": 30, "visible_equals_grader": False},
            }
            p1 = {
                **common, "id": "smoke_part1", "pair": ["N3", "GT"],
                "arms": {
                    "A": {"policy": "single", "attempt_timeout_s": 10},
                    "N3": {"policy": "continue", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                           "min_attempt_s": 0.5, "hint": "review", "deliver": "last"},
                    "GT": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                           "min_attempt_s": 0.5, "acceptance_source": "gate_visible", "hint": "failing_tests_noexpect"},
                    "XM": {"policy": "restart", "max_attempts": 2, "attempt_timeout_s": 5, "budget_s": 10,
                           "min_attempt_s": 0.5, "acceptance_source": "exam:XM", "hint": "failing_tests_noexpect"},
                },
            }
            p2 = {
                **common, "id": "smoke_part2", "pair": ["XMV", "XMT"],
                "arms": {
                    "XMV": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                            "min_attempt_s": 0.5, "acceptance_source": "exam:XMV", "hint": "failing_tests_noexpect"},
                    "PB": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                           "min_attempt_s": 0.5, "acceptance_source": "exam:PB", "hint": "failing_tests_noexpect"},
                    "XMT": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 5, "budget_s": 15,
                            "min_attempt_s": 0.5, "acceptance_source": "exam:XMT", "acceptance_pass_ratio": 0.85,
                            "hint": "failing_tests_noexpect"},
                },
            }
            pf1, pf2 = tmp / "p1.json", tmp / "p2.json"
            self.redo.write_json(pf1, p1)
            self.redo.write_json(pf2, p2)
            r1, r2 = tmp / "r1", tmp / "r2"
            for pf, rr in ((pf1, r1), (pf2, r2)):
                rc = subprocess.run(
                    [sys.executable, str(REDO_PY), "run", "--plan", str(pf), "--root", str(rr), "--allow-uncommitted-plan"],
                    capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)

            c_xm = self.redo.read_json(r1 / "cells" / "ex_luhn" / "r1" / "XM" / "cell.json")
            c_xmt = self.redo.read_json(r2 / "cells" / "ex_luhn" / "r1" / "XMT" / "cell.json")
            # Strict XM rejected att 1 (9/10) -> false_reject=True, ran 2 attempts
            self.assertFalse(c_xm["accepted"])
            self.assertTrue(c_xm["false_reject"])
            self.assertEqual(c_xm["n_attempts"], 2)
            # XMT@0.85 accepted att 1 (9/10 = 0.9 >= 0.85) -> 1 attempt, passed hidden, 0 false_block!
            self.assertTrue(c_xmt["accepted"])
            self.assertTrue(c_xmt["pass"])
            self.assertFalse(c_xmt["false_reject"])
            self.assertEqual(c_xmt["n_attempts"], 1)
            self.assertAlmostEqual(c_xmt["attempts"][0]["acc_pass_ratio"], 0.9)

            met = subprocess.run(
                [sys.executable, str(METRICS_PY), str(r1), str(r2), "--json"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(met.returncode, 0, met.stdout + met.stderr)
            res = json.loads(met.stdout)
            self.assertEqual(res["per_arm"]["XM"]["false_block_cells"], 1)
            self.assertEqual(res["per_arm"]["XMT"]["false_block_cells"], 0)
            self.assertTrue(res["qualification"]["XMT"]["qualifies"])
            self.assertTrue(res["qualification"]["XMV"]["qualifies"])
            self.assertTrue(res["qualification"]["PB"]["qualifies"])
            self.assertIsNotNone(res["stratified_by_xm_reference_ok"])
            self.assertEqual(res["stratified_by_xm_reference_ok"]["xm_ref_ok"]["n_tasks"], 1)


if __name__ == "__main__":
    unittest.main()
