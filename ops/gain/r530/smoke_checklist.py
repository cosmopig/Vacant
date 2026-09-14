#!/usr/bin/env python3
"""冒煙的逐格檢核表 C1–C8（預註冊 §三-6，Fable 裁決第 6 點）。

「跑得完」不是合格。合格的定義是下面這八格**逐格**都對得上，
落盤成 `runs/_smoke/<run>/checklist.json`。
**不合格就不准發射，而且修完要重跑整份冒煙**（不是只補那一格）。

⚠ 這支**不判實驗結論**，一個字都不判。它判的是「量具有沒有接上」。
  三條臂誰贏誰輸在這裡完全不看——冒煙的資料永不進證據。

用法：
    python3 ops/gain/r530/smoke_checklist.py --run runs/_smoke/g_r530_smoke
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ops.gain.r530 import gates  # noqa: E402
from ops.gain.r530 import openwork_arms as oa, tasks as taskmod  # noqa: E402
from ops.gain.r530 import wshash  # noqa: E402

CHECKS = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9",
          "E9", "E10", "E11")


def _read_json(p: pathlib.Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return None


def _rows(run: pathlib.Path) -> list[dict]:
    p = run / "rows.jsonl"
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()] \
        if p.exists() else []


def _calls(run: pathlib.Path) -> list[dict]:
    p = run / "calls.jsonl"
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()] \
        if p.exists() else []


def check(runs) -> dict:
    """一份冒煙的檢核表。`runs` 可以是**一個或多個** run 目錄。

    ⚠ 為什麼要吃多個：預註冊 §三-6 說的是「冒煙那 **6 格**」，而 6 格為了
      同時用兩顆後端會被切成兩塊（一塊一題三臂）。C9（「兩條有閘門的臂真的
      動起來了」）是**整份冒煙**的性質不是單塊的：`A-CONF` 的第二份可能只在
      難的那一題出現，而 `A-GATE` 的回饋輪可能只在另一題出現。
      逐塊判會讓「兩件事都發生過、只是不在同一塊」被判成紅。
    ⚠ 反過來，`C7`（沙箱身分）在多塊之下變**更嚴**：兩塊的沙箱必須是同一種，
      否則那 6 格不是在同一個實驗條件下量的。
    """
    if isinstance(runs, (str, pathlib.Path)):
        runs = [runs]
    runs = [pathlib.Path(r) for r in runs]
    summaries = {}
    rows: list[dict] = []
    calls: list[dict] = []
    for r in runs:
        sp = r / "summary.json"
        summaries[str(r)] = (json.loads(sp.read_text(encoding="utf-8"))
                             if sp.exists() else {})
        rows += _rows(r)
        calls += _calls(r)
    run = runs[0]
    summary = summaries[str(run)]
    out: dict = {"run": str(run), "runs": [str(r) for r in runs],
                 "rows_n": len(rows), "checks": {}}

    def put(cid, ok, detail):
        out["checks"][cid] = {"ok": bool(ok), "detail": detail}

    # ── C1 模型呼叫數 ─────────────────────────────────────────────────
    cap = (summary.get("budget") or {}).get("max_model_calls")
    model_calls: dict[tuple, int] = {}
    for c in calls:
        if c.get("kind") == "tool" or not c.get("ok"):
            continue
        m = c.get("meta") or {}
        if m.get("arm") in oa.ARMS:
            key = (m["arm"], m.get("task_id"))
            model_calls[key] = model_calls.get(key, 0) + 1
    c1_bad = []
    for r in rows:
        key = (r["arm"], r["task_id"])
        if cap is not None and r["calls"] > cap:
            c1_bad.append(f"{key}: calls={r['calls']} > cap {cap}")
        if model_calls.get(key) != r["calls"]:
            c1_bad.append(
                f"{key}: rows.calls={r['calls']} != calls.jsonl "
                f"{model_calls.get(key)}")
    put("C1", not c1_bad and bool(rows),
        {"cap": cap, "per_cell": {f"{k[0]}/{k[1]}": v
                                  for k, v in sorted(model_calls.items())},
         "problems": c1_bad})

    # ── C2 宣告完成的輪次 ─────────────────────────────────────────────
    c2 = {f"{r['arm']}/{r['task_id']}": r.get("declared_done_turn") for r in rows}
    # 撞預算而從來沒宣告完成的格子不算不合格——它是一個**真的**結局
    # （`budget_*`），檢核表要分得出「偵測不到宣告」與「它沒宣告」。
    c2_bad = [k for k, v in c2.items()
              if v is None and not (
                  next(r for r in rows if f"{r['arm']}/{r['task_id']}" == k)
                  ["stop_reason"] or "").startswith("budget")]
    put("C2", not c2_bad, {"declared_done_turn": c2, "problems": c2_bad})

    # ── C3 可見驗收（**A-SOLO 那格也要有**）────────────────────────────
    c3_bad = [f"{r['arm']}/{r['task_id']}" for r in rows
              if r.get("visible_total") in (None, 0)]
    put("C3", not c3_bad,
        {"visible": {f"{r['arm']}/{r['task_id']}":
                     f"{r.get('visible_passed')}/{r.get('visible_total')}"
                     for r in rows},
         "problems": c3_bad})

    # ── C4 隱藏驗收條數與題庫相符 ─────────────────────────────────────
    want = {}
    for tid in sorted({r["task_id"] for r in rows}):
        try:
            t = taskmod.load_task(tid)
        except SystemExit:
            continue
        want[tid] = _count_hidden_cases(t)
    c4_bad = []
    for r in rows:
        if want.get(r["task_id"]) not in (None, r["hidden_total"]):
            c4_bad.append(f"{r['arm']}/{r['task_id']}: hidden_total="
                          f"{r['hidden_total']} != {want[r['task_id']]}")
        if r.get("hidden_frac") is None:
            c4_bad.append(f"{r['arm']}/{r['task_id']}: frac 算不出來")
        if "deliv" not in r:
            c4_bad.append(f"{r['arm']}/{r['task_id']}: deliv 缺")
    put("C4", not c4_bad, {"expected_hidden_cases": want, "problems": c4_bad})

    # ── C5 樹雜湊前後 ─────────────────────────────────────────────────
    starts = {r.get("workspace_start_sha256") or r.get("ws_start_sha256")
              for r in rows}
    tmpl = {tid: wshash.tree_hash(taskmod.load_task(tid)["template_dir"])
            for tid in sorted({r["task_id"] for r in rows})}
    per_task_ok = all(
        (r.get("workspace_start_sha256") or r.get("ws_start_sha256"))
        == tmpl[r["task_id"]] for r in rows)
    moved = [r for r in rows
             if (r.get("workspace_end_sha256") or r.get("ws_end_sha256"))
             != (r.get("workspace_start_sha256") or r.get("ws_start_sha256"))]
    put("C5", per_task_ok and bool(moved),
        {"distinct_starts": sorted(starts), "template_hashes": tmpl,
         "cells_that_changed_the_workspace": len(moved),
         "problems": ([] if per_task_ok else ["起點與樣板不符"])
                     + ([] if moved else ["沒有任何一格動過工作區"])})

    # ── C6 收據條數與驗鏈 ─────────────────────────────────────────────
    c6 = {}
    c6_ok = True
    for r in runs:
        rc = subprocess.run(
            [sys.executable, "ops/gain/replay/verify_run_receipts.py",
             "--glob", str(r.relative_to(ROOT)) if _under(r) else str(r)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=300)
        c6[r.name] = {"verify_rc": rc.returncode,
                      "tail": rc.stdout.strip().splitlines()[-8:]}
        c6_ok = c6_ok and rc.returncode == 0
    put("C6", c6_ok, c6)

    # ── C7 沙箱身分 ───────────────────────────────────────────────────
    meta = summary.get("backend_meta") or {}
    backends = {r.get("backend") for r in rows}
    # 多塊之下這一條變**更嚴**：每一塊的沙箱身分與三個隔離欄位都要一樣，
    # 否則那 6 格不是在同一個實驗條件下量的。
    sig = {str(r): tuple(
        ((summaries[str(r)].get("backend_meta") or {}).get(k))
        for k in ("sandbox", "network_isolated", "write_confined",
                  "repo_hidden_from_sandbox", "sandbox_uid"))
        for r in runs}
    put("C7", len(backends) == 1 and bool(meta.get("sandbox"))
        and len(set(sig.values())) == 1,
        {"sandbox": meta.get("sandbox"), "per_row": sorted(b for b in backends if b),
         "network_isolated": meta.get("network_isolated"),
         "write_confined": meta.get("write_confined"),
         "repo_hidden_from_sandbox": meta.get("repo_hidden_from_sandbox"),
         "per_run_signature": {k: list(v) for k, v in sig.items()}})

    # ── C8 V/GT ───────────────────────────────────────────────────────
    from ops.gain.harness_vgt_audit import audit_run_r530
    tasks = {tid: taskmod.load_task(tid) for tid in sorted({r["task_id"] for r in rows})}
    c8 = {}
    c8_ok = True
    for r in runs:
        vgt = audit_run_r530(r, tasks)
        c8[r.name] = {"verdict": vgt["verdict"],
                      "violations_n": len(vgt["violations"]),
                      "deny_hidden_read_n": vgt["deny_hidden_read_n"],
                      "excused_by_rule": vgt["excused_by_rule"],
                      "workspace_needle_hits_n": vgt["workspace_needle_hits_n"],
                      "records_audited": vgt["records_audited"],
                      "per_role": vgt["per_role"]}
        c8_ok = c8_ok and vgt["verdict"] == "CLEAN" and vgt["deny_hidden_read_n"] == 0
    put("C8", c8_ok, c8)

    # ── C9：兩條有閘門的臂**真的動起來了**（預註冊 §三-6，第五輪裁決 4）──
    # 其他八條問的是「有沒有壞掉」，C9 問的是**「有沒有發生」**。
    # 它擋的是第五輪推翻的那個死法：預算不夠時 `A-CONF` 連第二份都抽不到、
    # `A-GATE` 一輪回饋都跑不到 ⇒ 兩條臂在資料上與 `A-SOLO` 無法區分，
    # 而那不會有任何錯誤訊息，只會安靜地產出一個 `INCONCLUSIVE`。
    conf_second = [f"{r['arm']}/{r['task_id']}" for r in rows
                   if r["arm"] == "A-CONF" and r.get("attempts_n", 0) >= 2]
    gate_round1 = [f"{r['arm']}/{r['task_id']}" for r in rows
                   if r["arm"] == "A-GATE"
                   and sum(len(a.get("gate_rounds") or [])
                           for a in (r.get("attempts") or [])) >= 1]
    put("C9", bool(conf_second) and bool(gate_round1),
        {"conf_cells_with_a_second_draw": conf_second,
         "gate_cells_that_reached_a_feedback_round": gate_round1,
         "honest_bound": (
             "C9 用的是冒煙那幾格，而冒煙只有 2 題 ⇒ 它證得了「機制跑得起來」，"
             "**證不了**「機制在 20 題上都會啟動」。這一句要跟著 C9 一起帶。")})

    # ── E-9／E-10（Fable 2026-09-14）──────────────────────────────────
    # 冒煙如果是 `--brain stub` 跑的，E-9 沒有被強制（見 run_r530）——
    # 那一份冒煙證明的是 harness 的路徑，不是沙箱的隔離強度。
    # 兩件事要分得開，所以這裡照著各 run 目錄裡那份 `gate_e9.json` 的
    # `enforced` 走，而不是自己重新決定。
    e9_all = {}
    e9_ok = True
    for r in runs:
        m = (summaries[str(r)].get("backend_meta") or {})
        rec = gates.e9_sandbox_gate(m)
        stored = _read_json(r / "gate_e9.json") or {}
        rec["enforced"] = stored.get(
            "enforced", summaries[str(r)].get("brain") != "stub")
        e9_all[r.name] = rec
        e9_ok = e9_ok and (rec["ok"] or not rec["enforced"])
    put("E9", e9_ok, e9_all)
    # E-11：逐塊判推論模式（**一塊紅就整份冒煙紅**——不能併的資料不能併）。
    e11_all = {}
    e11_ok = True
    for r in runs:
        stored = _read_json(r / "gate_e11_closeout.json")
        if stored is None:
            stored = gates.e11_closeout_gate(_calls(r), block=r.name)
        e11_all[r.name] = {k: stored.get(k) for k in
                           ("calls_audited", "reasoning_tokens_total",
                            "completion_tokens_total", "reasoning_share",
                            "calls_without_the_field", "verdict", "reason")}
        pre = _read_json(r / "gate_e11.json") or {}
        e11_all[r.name]["preflight_ok"] = pre.get("ok")
        e11_all[r.name]["preflight_skipped"] = pre.get("skipped_reason")
        # `--brain stub` 沒有真的端點 ⇒ 收官那一半不判（沒有東西可判）。
        if (summaries[str(r)].get("brain") == "stub"):
            continue
        e11_ok = e11_ok and bool(stored.get("ok")) and pre.get("ok") is not False
    put("E11", e11_ok, e11_all)

    e10 = gates.e10_noop_gate(rows)
    put("E10", e10["ok"], {k: e10[k] for k in
                           ("per_arm", "arms_over_threshold",
                            "offending_cells", "reason")})

    # ── 每通平均秒數 T（逐臂；**含工具往返**）──────────────────────────
    # 預註冊 §七-2b 的時程公式要填它。**不是**端點延遲：它把沙箱、驗收、
    # 樹雜湊、封存全部算進去，因為排程要的是「一格要多久」不是「一通多快」。
    stats: dict = {}
    for r in runs:
        for arm, st in (summaries[str(r)].get("arms_stats") or {}).items():
            d = stats.setdefault(arm, {"calls": 0, "wall_s": 0.0})
            d["calls"] += st.get("calls") or 0
            d["wall_s"] += st.get("wall_s") or 0.0
    per_arm_t = {}
    for arm, st in stats.items():
        calls = st.get("calls") or 0
        per_arm_t[arm] = (round((st.get("wall_s") or 0.0) / calls, 1)
                          if calls else None)
    tot_wall = sum((st.get("wall_s") or 0.0) for st in stats.values())
    tot_calls = sum((st.get("calls") or 0) for st in stats.values())
    out["seconds_per_call"] = {
        "per_arm": per_arm_t,
        "overall": round(tot_wall / tot_calls, 1) if tot_calls else None,
        "note": ("T ＝ 該臂的總牆鐘 ÷ 該臂的總模型呼叫數，**含工具往返與驗收**。"
                 "冒煙是單串跑的；併發之下 T 會變大（R460 量到三併發會讓長生成"
                 "變慢但沒有量過倍率），所以拿它去推時程要帶那個未知數。"),
    }

    out["verdict"] = ("PASS" if all(out["checks"][c]["ok"] for c in CHECKS)
                      else "FAIL")
    out["note"] = (
        "這張表判的是**量具有沒有接上**，不是實驗結論。冒煙的資料永不進證據："
        "不進 runs/INDEX、不進任何 analyzer、不進配對、不進 token 帳、不進質化。"
        "不合格就不准發射，而且修完要**重跑整份冒煙**（不是只補那一格）。")
    return out


def _under(p: pathlib.Path) -> bool:
    try:
        p.relative_to(ROOT)
        return True
    except ValueError:
        return False


def _count_hidden_cases(task: dict) -> int:
    """隱藏驗收有幾條 ＝ 所有 `test_*.py` 裡 `check_*` 函式的總數。"""
    import ast
    n = 0
    for p in sorted(pathlib.Path(task["hidden_dir"]).glob("test_*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        found = [x for x in tree.body
                 if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and x.name.startswith("check_")]
        n += len(found) or 1
    return n


def render(out: dict) -> str:
    tpc = (out.get("seconds_per_call") or {})
    L = [f"═══ R530 冒煙檢核表 {' + '.join(out.get('runs') or [out['run']])} ═══",
         f"rows {out['rows_n']}　每通平均秒數 T(逐臂)="
         f"{json.dumps(tpc.get('per_arm'), ensure_ascii=False)}"
         f"　整體={tpc.get('overall')}"]
    for cid in CHECKS:
        c = out["checks"][cid]
        L.append(f"  {cid} {'OK  ' if c['ok'] else '**紅**'} "
                 f"{json.dumps(c['detail'], ensure_ascii=False)[:220]}")
    L += ["", f"總判：{out['verdict']}", out["note"]]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="R530 冒煙檢核表（零模型呼叫）")
    ap.add_argument("--run", required=True, nargs="+",
                    help="一個或多個 run 目錄。冒煙為了同時用兩顆後端會被切成"
                         "兩塊，而 C9 是**整份冒煙**的性質（見 check 的 docstring）")
    ap.add_argument("--json", default=None,
                    help="預設寫到 <第一個 run>/checklist.json")
    args = ap.parse_args()
    runs = [(p if p.is_absolute() else ROOT / p)
            for p in (pathlib.Path(x) for x in args.run)]
    out = check(runs)
    print(render(out))
    dest = pathlib.Path(args.json) if args.json else (runs[0] / "checklist.json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"\nchecklist → {dest}")
    return 0 if out["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
