#!/usr/bin/env python3
"""ops.e1.selftest — E1′ 端對端自測（真實 bwrap＋真實負控制＋真實來源伺服器＋假 agent）。

這支在架構裡承重什麼
====================
完整串通 E1′ 所有承重模組（`build_code_chains`、`build_doc_chains`、`negative_controls`、`run_e1`、
`evaluate`、`units`、`analyze_e1`）並實際跑在 Linux bubblewrap 沙箱裡，驗證核心預期對比：
1. 程式碼鏈（合成 EvalPlus 題庫 → 2 條 8 初始函式 × 5 回合鏈）：
   - `B0`、`B0x3` 因假 agent 重寫全檔破壞既有函式而發生回歸（最終全過率 0%）。
   - `B2` 可見測試擋下回歸並回滾至基線（回歸數 0，但無法提交新函式，最終全過率 0%）。
   - `S`、`S+B2`、`O` 僅提交範圍內單元並拒絕範圍外破壞（回歸數 0、最終全過率 100%、rejected_units > 0）。
2. 文件鏈（實讀 `/tmp/claude-1000/agy_real/sample` 的 `set_01`、`set_02`）：
   - `B0` 與只看結構的 `B2` 均因未變動行遭竄改而回歸（最終全過率 0%）。
   - `S`、`S+B2`、`O` 透過產品函式 `value_status(..., by_field=True)` 保護未變動行（回歸數 0、最終全過率 100%）。
3. 斷點續跑安全：同一個 `ROOT` 重跑一次不重做已完成回合、結果不重複。

誠實邊界（改碼請保留）
----------------------
- 本自測使用確定性假 agent（`fake_agent.py`），只證明管線、沙箱、範圍提交、評分與分析器運作正確，
  **不是**任何真實語言模型上的實驗結果。
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import pathlib
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.e1 import PLAN_SCHEMA, atomic_write_json
from ops.e1.analyze_e1 import analyze_root, format_report
from ops.e1.build_code_chains import build_code_chains
from ops.e1.build_doc_chains import build_doc_chains
from ops.e1.run_e1 import E1Runner

SAMPLE_DOC_MATERIALS = pathlib.Path("/tmp/claude-1000/agy_real/sample")


def make_synthetic_evalplus(dst_dir: pathlib.Path, n_he: int = 16, n_mbpp: int = 16) -> pathlib.Path:
    """建立極小的合成 EvalPlus gzip JSONL 題庫，供 selftest 與單元測試使用。"""
    dst_dir.mkdir(parents=True, exist_ok=True)
    he_rows = []
    for i in range(1, n_he + 1):
        ep = f"synth_add_{i}"
        he_rows.append({
            "task_id": f"HumanEval/{i}",
            "entry_point": ep,
            "prompt": f'def {ep}(x: int) -> int:\n    """Add {i} to x (return x + {i})."""\n',
            "canonical_solution": f"    return x + {i}\n",
            "base_input": [[0], [1], [-3]],
            "plus_input": [[10], [25], [-100], [999]],
            "atol": 0,
            "test": f"assert {ep}(0) == {i}",
        })
    mbpp_rows = []
    for i in range(1, n_mbpp + 1):
        ep = f"synth_mul_{i}"
        mbpp_rows.append({
            "task_id": f"Mbpp/{i}",
            "entry_point": ep,
            "prompt": f'"""\nMultiply x by {i} (return x * {i}).\n"""\n',
            "canonical_solution": f"def {ep}(x):\n    return x * {i}\n",
            "base_input": [[0], [2], [-3]],
            "plus_input": [[5], [11], [-7], [42]],
            "atol": 0,
            "assertion": f"assert {ep}(2) == {2 * i}",
        })

    with gzip.open(dst_dir / "HumanEvalPlus-v0.1.10.jsonl.gz", "wt", encoding="utf-8") as fh:
        for r in he_rows:
            fh.write(json.dumps(r) + "\n")
    with gzip.open(dst_dir / "MbppPlus-v0.2.0.jsonl.gz", "wt", encoding="utf-8") as fh:
        for r in mbpp_rows:
            fh.write(json.dumps(r) + "\n")
    return dst_dir


def run_selftest(work_dir: pathlib.Path | None = None, *, doc_materials: pathlib.Path | None = None) -> dict:
    created_tmp = None
    if work_dir is None:
        base_scratch = pathlib.Path("/tmp/claude-1000/agy_e1")
        base_scratch.mkdir(parents=True, exist_ok=True)
        created_tmp = tempfile.TemporaryDirectory(prefix="e1_selftest_", dir=str(base_scratch))
        work_dir = pathlib.Path(created_tmp.name)
    else:
        work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. 程式碼端對端自測
        synth_ep = make_synthetic_evalplus(work_dir / "synth_evalplus")
        code_chains_dir = work_dir / "code_chains"
        build_code_chains(
            seed=42,
            n=2,
            out_dir=code_chains_dir,
            evalplus_dir=synth_ep,
            min_init=8,
            max_init=8,
            verify_sha256=False,
        )
        code_plan = work_dir / "plan_code.json"
        atomic_write_json(
            code_plan,
            {
                "schema": PLAN_SCHEMA,
                "id": "selftest_code",
                "chains_dir": str(code_chains_dir),
                "arms": ["B0", "B0x3", "B2", "S", "S+B2", "O", "Z"],
                "model": {
                    "providers": ["fake"],
                    "model": "fake/selftest",
                    "fake_agent": "ops/e1/fake_agent.py",
                    "fake_mode": "regress_other",
                },
                "jobs": 2,
                "attempt_timeout_s": 30,
                "eval_timeout_s": 20,
                "max_attempts_b2": 2,
                "max_attempts_b0x3": 2,
            },
        )
        code_root = work_dir / "run_code"
        runner_code = E1Runner(code_plan, code_root, allow_uncommitted=True)
        runner_code.run()

        # 續跑安全檢查：同 root 重跑一次，results.jsonl 行數不變
        lines_before = len((code_root / "results.jsonl").read_text(encoding="utf-8").splitlines())
        E1Runner(code_plan, code_root, allow_uncommitted=True).run()
        lines_after = len((code_root / "results.jsonl").read_text(encoding="utf-8").splitlines())
        assert lines_before == lines_after, f"續跑產生重複寫入：{lines_before} -> {lines_after}"

        code_summary = analyze_root(code_root)
        assert code_summary["arms"]["B0"]["primary_final_all_pass_rate"] == 0.0
        assert code_summary["arms"]["B0"]["regression_obligation_count"] > 0
        assert code_summary["arms"]["B0x3"]["primary_final_all_pass_rate"] == 0.0
        assert code_summary["arms"]["B2"]["regression_obligation_count"] == 0
        assert code_summary["arms"]["B2"]["primary_final_all_pass_rate"] == 0.0
        assert code_summary["arms"]["Z"]["regression_obligation_count"] == 0, f"Z 發生回歸：{code_summary['arms']['Z']}"
        assert code_summary["arms"]["Z"]["regression_event_count"] == 0, f"Z 發生回歸事件：{code_summary['arms']['Z']}"
        assert code_summary["arms"]["Z"]["regression_chain_count"] == 0, f"Z 發生鏈回歸：{code_summary['arms']['Z']}"
        assert code_summary["arms"]["Z"]["primary_final_all_pass_rate"] == 0.0
        assert code_summary["arms"]["Z"]["attempts_per_chain_mean"] == 10.0, f"Z 應每回合重試 2 次：{code_summary['arms']['Z']}"
        assert code_summary["arms"]["Z"]["rejected_units_total"] > 0, "Z 應回報被拒單元"
        assert "scope_diagnostics" in code_summary["arms"]["Z"], "Z 應含 scope_diagnostics"
        z_recs = [
            json.loads(ln)
            for ln in (code_root / "results.jsonl").read_text(encoding="utf-8").splitlines()
            if ln.strip() and json.loads(ln).get("arm") == "Z"
        ]
        assert len(z_recs) == 10, f"預期 2 條鏈 × 5 回合 = 10 筆 Z 紀錄，實得 {len(z_recs)}"
        for zr in z_recs:
            assert zr["attempts_count"] == 2
            assert zr["gate_passed"] is False
            for att in zr["attempts"]:
                zc = att.get("z_check")
                assert isinstance(zc, dict), f"缺少 z_check：{att}"
                assert set(zc.keys()) == {
                    "parse", "loads", "scope_ok", "rejected_units", "rejected_non_unit_changes", "load_error"
                }
                assert zc["parse"] is True
                assert zc["loads"] is True
                assert zc["scope_ok"] is False
        for arm in ("S", "S+B2", "O"):
            assert code_summary["arms"][arm]["primary_final_all_pass_rate"] == 1.0, f"{arm} 未全過：{code_summary['arms'][arm]}"
            assert code_summary["arms"][arm]["regression_obligation_count"] == 0, f"{arm} 發生回歸"
            assert code_summary["arms"][arm]["rejected_units_total"] > 0, f"{arm} 應有被拒單元"

        # 2. 文件端對端自測（若教材存在）
        mat = doc_materials if doc_materials is not None else SAMPLE_DOC_MATERIALS
        doc_summary = None
        if mat.is_dir() and (mat / "manifest.json").is_file():
            doc_chains_dir = work_dir / "doc_chains"
            build_doc_chains(materials_dir=mat, out_dir=doc_chains_dir)
            doc_plan = work_dir / "plan_doc.json"
            atomic_write_json(
                doc_plan,
                {
                    "schema": PLAN_SCHEMA,
                    "id": "selftest_doc",
                    "chains_dir": str(doc_chains_dir),
                    "arms": ["B0", "B2", "S", "S+B2", "O"],
                    "model": {
                        "providers": ["fake"],
                        "model": "fake/selftest",
                        "fake_agent": "ops/e1/fake_agent.py",
                        "fake_mode": "regress_other",
                    },
                    "jobs": 2,
                    "attempt_timeout_s": 30,
                    "eval_timeout_s": 20,
                    "max_attempts_b2": 2,
                },
            )
            doc_root = work_dir / "run_doc"
            E1Runner(doc_plan, doc_root, allow_uncommitted=True).run()
            doc_summary = analyze_root(doc_root)
            assert doc_summary["arms"]["B0"]["primary_final_all_pass_rate"] == 0.0
            assert doc_summary["arms"]["B0"]["regression_obligation_count"] > 0
            assert doc_summary["arms"]["B2"]["primary_final_all_pass_rate"] == 0.0
            for arm in ("S", "S+B2", "O"):
                assert doc_summary["arms"][arm]["primary_final_all_pass_rate"] == 1.0, f"doc {arm} 未全過：{doc_summary['arms'][arm]}"
                assert doc_summary["arms"][arm]["regression_obligation_count"] == 0, f"doc {arm} 發生回歸"
                assert doc_summary["arms"][arm]["rejected_units_total"] > 0, f"doc {arm} 應有被拒單元"

        return {
            "passed": True,
            "code": code_summary,
            "doc": doc_summary,
            "resume_lines_unchanged": lines_before == lines_after,
        }
    finally:
        if created_tmp is not None:
            created_tmp.cleanup()


def main() -> int:
    ap = argparse.ArgumentParser(description="E1′ 端對端自測（假 agent＋真實 bwrap＋真實負控制）")
    ap.add_argument("--work-dir", type=pathlib.Path, default=None, help="選用：保留輸出於指定目錄")
    ap.add_argument("--doc-materials", type=pathlib.Path, default=SAMPLE_DOC_MATERIALS, help="realrev 教材目錄")
    args = ap.parse_args()

    res = run_selftest(work_dir=args.work_dir, doc_materials=args.doc_materials)
    print("=== CODE SELFTEST ===")
    print(format_report(res["code"]))
    if res["doc"] is not None:
        print("\n=== DOC SELFTEST ===")
        print(format_report(res["doc"]))
    print("\n[selftest] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
