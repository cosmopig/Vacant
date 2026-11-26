"""tests/test_e1.py — E1′ 實驗基建的單元與整合測試（真實 bwrap 沙箱＋真實負控制＋端對端自測）。"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops.e1 import DEFAULT_EVALPLUS_DIR, PLAN_SCHEMA, atomic_write_json
from ops.e1.analyze_e1 import analyze_root, format_report, mcnemar_exact
from ops.e1.build_code_chains import build_code_chains
from ops.e1.build_doc_chains import build_doc_chains
from ops.e1.evaluate import (
    check_doc_structural,
    compute_doc_scope_s,
    evaluate_code_source,
    evaluate_doc_report,
)
from ops.e1.negative_controls import run_negative_controls
from ops.e1.run_e1 import E1Runner, assert_git_clean, usage_from_pi_log
from ops.e1.sandbox import prepare_sanitized_pi_cfg
from ops.e1.selftest import SAMPLE_DOC_MATERIALS, make_synthetic_evalplus, run_selftest
from ops.e1.units import (
    atomic_commit_file,
    commit_code_scoped,
    commit_doc_scoped,
    extract_code_scope_from_task,
    extract_code_units,
    extract_doc_units,
)


class TestUnitsCode(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = (
            "import math\n\n"
            "CONST = 10\n\n"
            "def f1(x):\n"
            "    return x + 1\n\n"
            "def f2(x):\n"
            "    return int(math.sqrt(x)) + CONST\n"
        )

    def test_extract_code_units(self) -> None:
        units = extract_code_units(self.baseline)
        self.assertEqual(list(units.keys()), ["f1", "f2"])
        self.assertIn("return x + 1", units["f1"]["source"])

    def test_add_in_scope_and_reject_out_of_scope(self) -> None:
        cand = (
            "import math\n"
            "import heapq\n\n"
            "CONST = 999\n\n"
            "def f1(x):\n"
            "    return -1  # broken out-of-scope\n\n"
            "def f2(x):\n"
            "    return int(math.sqrt(x)) + CONST\n\n"
            "def f3(x):\n"
            "    return heapq.nsmallest(1, x)[0]\n\n"
            "def sneak():\n"
            "    return 0\n"
        )
        res = commit_code_scoped(self.baseline, cand, allowed_units=["f3"])
        self.assertFalse(res["syntax_error"])
        self.assertEqual(res["committed_units"], ["f3"])
        self.assertEqual(set(res["rejected_units"]), {"f1", "sneak"})
        self.assertTrue(res["rejected_non_unit_changes"])
        # 基線 CONST 與 f1 均受保護，且 f3 與不碰撞的新增 import heapq 被接受
        self.assertIn("CONST = 10", res["committed_src"])
        self.assertNotIn("CONST = 999", res["committed_src"])
        self.assertIn("return x + 1", res["committed_src"])
        self.assertIn("def f3(x):", res["committed_src"])
        self.assertIn("import heapq", res["committed_src"])
        self.assertNotIn("def sneak", res["committed_src"])

    def test_rename_in_scope_preserves_other_functions(self) -> None:
        cand = (
            "import math\n\n"
            "CONST = 10\n\n"
            "def f1_v2(x):\n"
            "    return x + 1\n\n"
            "def f2(x):\n"
            "    return 0  # broken\n"
        )
        res = commit_code_scoped(self.baseline, cand, allowed_units=["f1", "f1_v2"])
        self.assertEqual(set(res["committed_units"]), {"f1", "f1_v2"})
        self.assertEqual(res["rejected_units"], ["f2"])
        units_after = extract_code_units(res["committed_src"])
        self.assertEqual(set(units_after.keys()), {"f1_v2", "f2"})
        self.assertIn("math.sqrt", units_after["f2"]["source"])

    def test_confirm_round_empty_scope_blocks_all(self) -> None:
        cand = "import os\n\ndef f1(x):\n    return 999\n"
        res = commit_code_scoped(self.baseline, cand, allowed_units=[])
        self.assertEqual(res["committed_units"], [])
        self.assertEqual(set(res["rejected_units"]), {"f1", "f2"})
        self.assertNotIn("import os", res["committed_src"])
        self.assertEqual(set(extract_code_units(res["committed_src"]).keys()), {"f1", "f2"})

    def test_syntax_error_fails_closed(self) -> None:
        res = commit_code_scoped(self.baseline, "def broken(:\n", allowed_units=["f1"])
        self.assertTrue(res["syntax_error"])
        self.assertEqual(res["committed_src"], self.baseline)

    def test_extract_code_scope_from_task(self) -> None:
        t_add = "Add the function:\n```python\ndef foo_bar(a: int) -> int:\n    pass\n```"
        self.assertEqual(extract_code_scope_from_task(t_add), ["foo_bar"])
        t_ren = "Rename the existing function `old_fn` in `solution.py` to `new_fn`."
        self.assertEqual(extract_code_scope_from_task(t_ren), ["old_fn", "new_fn"])
        t_conf = "Review `solution.py` and confirm that all functions are correct."
        self.assertEqual(extract_code_scope_from_task(t_conf), [])

    def test_atomic_commit_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "sub" / "solution.py"
            sha = atomic_commit_file(p, "x = 1\n")
            self.assertEqual(p.read_text(encoding="utf-8"), "x = 1\n")
            self.assertEqual(len(sha), 64)


class TestUnitsDoc(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = (
            "# Report\n\n"
            "- Alpha H220 — 2023 apps (goals): 10 (0)\n"
            "- Alpha H220 — 2024 apps (goals): 12 (1)\n"
            "- Beta — 2025 apps (goals): 5 (2)\n"
        )

    def test_extract_and_scoped_commit_doc(self) -> None:
        units = extract_doc_units(self.baseline)
        self.assertEqual(len(units), 3)
        self.assertEqual(units["- Alpha H220 — 2023 apps (goals)"], "10 (0)")

        cand = (
            "# Hacked Header\n\n"
            "- Alpha H220 — 2023 apps (goals): 99 (9)\n"
            "- Alpha H220 — 2024 apps (goals): 15 (3)\n"
            # Beta 被刪除
        )
        res = commit_doc_scoped(
            self.baseline,
            cand,
            allowed_prefixes=["- Alpha H220 — 2024 apps (goals)"],
        )
        self.assertEqual(res["committed_units"], ["- Alpha H220 — 2024 apps (goals)"])
        self.assertEqual(
            set(res["rejected_units"]),
            {"- Alpha H220 — 2023 apps (goals)", "- Beta — 2025 apps (goals)"},
        )
        self.assertTrue(res["rejected_non_unit_changes"])
        self.assertIn("# Report", res["committed_text"])
        self.assertIn("- Alpha H220 — 2023 apps (goals): 10 (0)", res["committed_text"])
        self.assertIn("- Alpha H220 — 2024 apps (goals): 15 (3)", res["committed_text"])
        self.assertIn("- Beta — 2025 apps (goals): 5 (2)", res["committed_text"])

    def test_compute_doc_scope_s_uses_value_status(self) -> None:
        prev_html = (
            "<html><body><table>"
            "<tr><th>Season</th><th>Club</th><th>Apps</th><th>Goals</th></tr>"
            "<tr><td>2023</td><td>Alpha</td><td>10</td><td>(0)</td></tr>"
            "<tr><td>2024</td><td>Alpha</td><td>12</td><td>(1)</td></tr>"
            "</table></body></html>"
        )
        cur_html = (
            "<html><body><table>"
            "<tr><th>Season</th><th>Club</th><th>Apps</th><th>Goals</th></tr>"
            "<tr><td>2023</td><td>Alpha</td><td>10</td><td>(0)</td></tr>"
            "<tr><td>2024</td><td>Alpha</td><td>15</td><td>(3)</td></tr>"
            "</table></body></html>"
        )
        sc = compute_doc_scope_s(self.baseline, {"p1.html": prev_html}, {"p1.html": cur_html})
        # 2023 未變、2024 變動、Beta 找不到來源 (no_source) ⇒ 2024 與 Beta 在範圍內
        self.assertEqual(sc["per_unit"]["- Alpha H220 — 2023 apps (goals)"]["status"], "unchanged")
        self.assertEqual(sc["per_unit"]["- Alpha H220 — 2024 apps (goals)"]["status"], "changed")
        self.assertEqual(sc["per_unit"]["- Beta — 2025 apps (goals)"]["status"], "no_source")
        self.assertEqual(
            set(sc["allowed_units"]),
            {"- Alpha H220 — 2024 apps (goals)", "- Beta — 2025 apps (goals)"},
        )


class TestEvaluatorSandbox(unittest.TestCase):
    def test_code_eval_pass_fail_atol_set_and_timeout(self) -> None:
        src = (
            "def ok_fn(x):\n"
            "    return x + 1\n\n"
            "def float_fn(x):\n"
            "    return x + 0.000001\n\n"
            "def set_fn(a, b):\n"
            "    return [b, a]\n\n"
            "def hang_fn(x):\n"
            "    while True:\n"
            "        pass\n"
        )
        specs = {
            "ok_fn": {"cases": [{"args": [2], "expected": 3}], "atol": 0.0, "cmp_mode": "exact"},
            "float_fn": {"cases": [{"args": [1.0], "expected": 1.0}], "atol": 1e-4, "cmp_mode": "exact"},
            "set_fn": {"cases": [{"args": [1, 2], "expected": [1, 2]}], "atol": 0.0, "cmp_mode": "set_equivalent"},
            "hang_fn": {"cases": [{"args": [1], "expected": 1}], "atol": 0.0, "cmp_mode": "exact"},
        }
        ev = evaluate_code_source(src, specs, per_fn_timeout_s=1.0, total_timeout_s=15.0)
        self.assertFalse(ev["all_pass"])
        self.assertTrue(ev["functions"]["ok_fn"]["passed"])
        self.assertTrue(ev["functions"]["float_fn"]["passed"])
        self.assertTrue(ev["functions"]["set_fn"]["passed"])
        self.assertFalse(ev["functions"]["hang_fn"]["passed"])
        self.assertIn("timeout", (ev["functions"]["hang_fn"]["error"] or "").lower())

    def test_empty_cases_fail_closed_i4(self) -> None:
        ev = evaluate_code_source("def f(x):\n    return x\n", {"f": {"cases": []}})
        self.assertFalse(ev["all_pass"])
        self.assertFalse(ev["functions"]["f"]["passed"])

    def test_doc_structural_and_truth_eval(self) -> None:
        claims = [
            {"id": "c1", "template_line": "- Item A: "},
            {"id": "c2", "template_line": "- Item B: "},
        ]
        good = "- Item A: 10 (0)\n- Item B: 5 (1)\n"
        bad_blank = "- Item A: 10 (0)\n- Item B: ____\n"
        self.assertTrue(check_doc_structural(good, ["- Item A", "- Item B"])["all_pass"])
        self.assertFalse(check_doc_structural(bad_blank, ["- Item A", "- Item B"])["all_pass"])
        ev_ok = evaluate_doc_report(good, claims, {"c1": "10 (0)", "c2": "5 (1)"})
        self.assertTrue(ev_ok["all_pass"])
        ev_bad = evaluate_doc_report(good, claims, {"c1": "10 (1)", "c2": "5 (1)"})
        self.assertFalse(ev_bad["all_pass"])
        self.assertFalse(ev_bad["claims"]["c1"]["passed"])


class TestBuilders(unittest.TestCase):
    def test_build_code_chains_tiny_fixture_and_sha_guard(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            ep_dir = make_synthetic_evalplus(tp / "ep", n_he=10, n_mbpp=10)
            # 驗證 sha256 釘死：未關驗證時對假檔必失敗
            with self.assertRaises(ValueError):
                build_code_chains(seed=1, n=1, out_dir=tp / "out_fail", evalplus_dir=ep_dir, verify_sha256=True)

            idx = build_code_chains(
                seed=7,
                n=1,
                out_dir=tp / "out_ok",
                evalplus_dir=ep_dir,
                min_init=8,
                max_init=10,
                verify_sha256=False,
            )
            self.assertEqual(idx["n_chains"], 1)
            self.assertFalse(idx["behavior_change_round_possible"])
            cdir = pathlib.Path(idx["chains"][0]["path"])
            ch = json.loads((cdir / "chain.json").read_text(encoding="utf-8"))
            hid = json.loads((cdir / "hidden_tests.json").read_text(encoding="utf-8"))
            self.assertEqual([r["kind"] for r in ch["rounds"]], ["add", "add", "add", "rename", "confirm"])
            self.assertIn("extension", ch["extension_note"].lower())
            self.assertFalse(ch["behavior_change_round_possible"])
            self.assertTrue(ch["initial_eval_verified"])
            self.assertIn(ch["rounds"][3]["rename_to"], hid["hidden_tests_by_function"])

    @unittest.skipUnless(DEFAULT_EVALPLUS_DIR.is_dir(), "EvalPlus reference dir not present")
    def test_build_code_chain_real_evalplus(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            idx = build_code_chains(
                seed=123,
                n=1,
                out_dir=pathlib.Path(td) / "real_code",
                evalplus_dir=DEFAULT_EVALPLUS_DIR,
                min_init=8,
                max_init=9,
                max_plus_cases=30,
                verify_sha256=True,
            )
            self.assertEqual(idx["n_chains"], 1)
            self.assertTrue(idx["evalplus_sha256"]["HumanEvalPlus-v0.1.10.jsonl.gz"].startswith("272720b9"))
            self.assertTrue(idx["evalplus_sha256"]["MbppPlus-v0.2.0.jsonl.gz"].startswith("af43697e"))

    @unittest.skipUnless(SAMPLE_DOC_MATERIALS.is_dir(), "realrev sample dir not present")
    def test_build_doc_chains_real_sample(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            idx = build_doc_chains(
                materials_dir=SAMPLE_DOC_MATERIALS,
                sets=["set_01", "set_02"],
                out_dir=pathlib.Path(td) / "doc_out",
            )
            self.assertEqual(idx["n_chains"], 2)
            cdir = pathlib.Path(idx["chains"][0]["path"])
            ch = json.loads((cdir / "chain.json").read_text(encoding="utf-8"))
            hid = json.loads((cdir / "hidden_truth.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ch["rounds"]), 4)
            self.assertNotIn("truth", ch)
            self.assertEqual(len(hid["truth"]), 5)


class TestNegativeControlsAndSanitizer(unittest.TestCase):
    def test_real_negative_controls_pass(self) -> None:
        rep = run_negative_controls()
        self.assertTrue(rep["passed"], f"負控制未通過：{rep}")
        self.assertEqual(rep["leaks"], [])
        self.assertTrue(rep["eval_net_isolated"])
        self.assertTrue(rep["sanity"]["work_rw"])
        self.assertTrue(rep["sanity"]["home_isolated"])
        self.assertTrue(rep["sanity"]["cfg_no_secret_key"])
        self.assertTrue(rep["sanity"]["cfg_readonly"])

    def test_negative_controls_catch_intentional_leak(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            secret = pathlib.Path(td) / "leaked_hidden.json"
            secret.write_text('{"secret": 1}', encoding="utf-8")
            rep = run_negative_controls(
                hidden_tests_path=secret,
                extra_worker_binds=[(secret, str(secret))],
            )
            self.assertFalse(rep["passed"])
            self.assertTrue(any(lk["name"] == "hidden_tests" for lk in rep["leaks"]))

    def test_negative_controls_cli_exits_zero(self) -> None:
        r = subprocess.run(
            [sys.executable, str(REPO_ROOT / "ops" / "e1" / "negative_controls.py")],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(r.returncode, 0, f"stdout={r.stdout}\nstderr={r.stderr}")
        self.assertIn("PASS", r.stdout)

    def test_pi_cfg_sanitizer_strips_keys_and_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src = pathlib.Path(td) / "src"
            dst = pathlib.Path(td) / "dst"
            (src / "extensions").mkdir(parents=True)
            (src / "extensions" / "vacant.ts").write_text("// ext\n", encoding="utf-8")
            atomic_write_json(
                src / "models.json",
                {
                    "providers": {
                        "openrouter": {"baseUrl": "https://openrouter.ai/api/v1", "apiKey": "sk-or-secret"},
                        "lms1003q9": {"baseUrl": "http://100.119.113.56:1234/v1", "apiKey": "lmstudio"},
                    }
                },
            )
            hosts = prepare_sanitized_pi_cfg(src, dst, allowed_providers=["lms1003q9"])
            self.assertEqual(hosts, ["100.119.113.56"])
            self.assertFalse((dst / "extensions").exists())
            out_txt = (dst / "models.json").read_text(encoding="utf-8")
            self.assertNotIn("sk-or-secret", out_txt)
            self.assertIn("lms1003q9", out_txt)


class TestRunnerGuardsAndDiagnostics(unittest.TestCase):
    def test_uncommitted_plan_refused(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "untracked_plan.json"
            p.write_text("{}", encoding="utf-8")
            with self.assertRaises(SystemExit):
                assert_git_clean(p)

    def test_usage_from_pi_log(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            lp = pathlib.Path(td) / "agent.log"
            lp.write_text(
                json.dumps({"type": "message_end", "message": {"role": "assistant", "usage": {"input": 100, "output": 30}}}) + "\n"
                + json.dumps({"type": "message_end", "message": {"role": "assistant", "stopReason": "error", "errorMessage": "boom"}}) + "\n",
                encoding="utf-8",
            )
            u = usage_from_pi_log(lp)
            self.assertEqual(u["calls"], 1)
            self.assertEqual(u["errors"], 1)
            self.assertEqual(u["input"], 100)
            self.assertEqual(u["output"], 30)

    def test_calibrate_mode_runs_b0_only_and_resume_mismatch_refused(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            ep_dir = make_synthetic_evalplus(tp / "ep", n_he=10, n_mbpp=10)
            cdir = tp / "chains"
            build_code_chains(seed=9, n=1, out_dir=cdir, evalplus_dir=ep_dir, min_init=8, max_init=8, verify_sha256=False)
            plan_p = tp / "plan.json"
            atomic_write_json(
                plan_p,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "cal_test",
                    "chains_dir": str(cdir),
                    "arms": ["B0", "S"],
                    "model": {"providers": ["fake"], "model": "fake", "fake_agent": "ops/e1/fake_agent.py"},
                    "jobs": 1,
                    "attempt_timeout_s": 20,
                },
            )
            root = tp / "root"
            E1Runner(plan_p, root, calibrate=True, allow_uncommitted=True).run()
            summ = analyze_root(root)
            self.assertEqual(list(summ["arms"].keys()), ["B0"])
            # 同一 root 換成非 calibrate 模式必須拒絕續跑
            with self.assertRaises(SystemExit):
                E1Runner(plan_p, root, calibrate=False, allow_uncommitted=True).run()

    def test_mcnemar_exact(self) -> None:
        self.assertEqual(mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(mcnemar_exact(6, 0), 0.03125, places=5)

    def test_scope_false_reject_and_in_scope_wrong_diagnostics(self) -> None:
        """驗證 S 臂事後診斷：範圍內接受但錯（accepted_in_scope_but_wrong）與誤拒但候選正確（rejected_but_correct）。"""
        with tempfile.TemporaryDirectory() as td:
            tp = pathlib.Path(td)
            # 構造單回合極簡文件鏈：c1 未變（但在網頁故意讓 value_status 漏判不變）、c2 變動
            mat = tp / "mat"
            s0 = mat / "sets" / "s1" / "cycle_0" / "site"
            s1 = mat / "sets" / "s1" / "cycle_1" / "site"
            s0.mkdir(parents=True)
            s1.mkdir(parents=True)
            # c1=10 在 cycle_0 和 cycle_1 都出現於同一列（所以 value_status 判 unchanged），但真值從 10 改為 20
            # c2=5 在 cycle_1 改成 6（value_status 判 changed，但在假 agent 裡故意寫錯成 999）
            (s0 / "index.html").write_text('<a href="p1.html">p1</a>', encoding="utf-8")
            (s1 / "index.html").write_text('<a href="p1.html">p1</a>', encoding="utf-8")
            (s0 / "p1.html").write_text("<table><tr><th>K</th><th>V</th></tr><tr><td>A</td><td>10</td></tr><tr><td>B</td><td>5</td></tr></table>", encoding="utf-8")
            (s1 / "p1.html").write_text("<table><tr><th>K</th><th>V</th></tr><tr><td>A</td><td>10</td></tr><tr><td>B</td><td>6</td></tr></table>", encoding="utf-8")
            (mat / "sets" / "s1" / "template.md").write_text("# T\n- A: ____\n- B: ____\n", encoding="utf-8")
            atomic_write_json(
                mat / "manifest.json",
                {
                    "schema": "vacant.d2.manifest/1",
                    "sets": [{
                        "set": "s1",
                        "index": "index.html",
                        "pages": ["p1.html"],
                        "claims": [
                            {"id": "c1", "template_line": "- A: "},
                            {"id": "c2", "template_line": "- B: "},
                        ],
                        "truth": [
                            {"c1": "10", "c2": "5"},
                            {"c1": "20", "c2": "6"},
                        ],
                        "cycles": [{"cycle": 1, "changed_claims": ["c1", "c2"]}],
                    }],
                },
            )
            cdir = tp / "doc_chains"
            build_doc_chains(materials_dir=mat, out_dir=cdir)
            # 假 agent：把 A 改對成 20（但不在 S 範圍內 → harmful false reject），把 B 改錯成 999（在 S 範圍內 → accepted_in_scope_but_wrong）
            fa = tp / "diag_fake.py"
            fa.write_text(
                'import json, pathlib\n'
                'pathlib.Path("report.md").write_text("# T\\n- A: 20\\n- B: 999\\n", encoding="utf-8")\n'
                'print(json.dumps({"type":"message_end","message":{"role":"assistant","usage":{"input":10,"output":5}}}))\n',
                encoding="utf-8",
            )
            plan_p = tp / "plan.json"
            atomic_write_json(
                plan_p,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "diag_test",
                    "chains_dir": str(cdir),
                    "arms": ["S"],
                    "model": {"providers": ["fake"], "model": "fake", "fake_agent": str(fa)},
                    "jobs": 1,
                    "attempt_timeout_s": 20,
                },
            )
            root = tp / "root"
            E1Runner(plan_p, root, allow_uncommitted=True).run()
            summ = analyze_root(root)
            sd = summ["arms"]["S"]["scope_diagnostics"]
            self.assertEqual(sd["rejected_but_correct_harmful"], 1)
            self.assertEqual(sd["rejected_candidate_correct_all"], 1)
            self.assertEqual(sd["accepted_in_scope_but_wrong"], 1)


class TestEndToEndSelftest(unittest.TestCase):
    def test_selftest_b0_regresses_and_s_protects(self) -> None:
        res = run_selftest()
        self.assertTrue(res["passed"])
        self.assertTrue(res["resume_lines_unchanged"])
        self.assertEqual(res["code"]["arms"]["B0"]["primary_final_all_pass_rate"], 0.0)
        self.assertEqual(res["code"]["arms"]["S"]["primary_final_all_pass_rate"], 1.0)
        self.assertEqual(res["code"]["arms"]["S+B2"]["primary_final_all_pass_rate"], 1.0)
        self.assertEqual(res["code"]["arms"]["O"]["primary_final_all_pass_rate"], 1.0)
        txt = format_report(res["code"])
        self.assertIn("Paired Final-Round Comparison vs B0", txt)
        if res["doc"] is not None:
            self.assertEqual(res["doc"]["arms"]["B0"]["primary_final_all_pass_rate"], 0.0)
            self.assertEqual(res["doc"]["arms"]["S"]["primary_final_all_pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
