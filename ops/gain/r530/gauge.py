#!/usr/bin/env python3
"""R530 的量具（PR-3／E-3）——**雙向**：參考解要全過，每個已知壞樁都要被擋。

判準與紀律逐字沿用 `vacant_network/suitegauge.py`：

  · **單邊保證**：擋得住已知壞解 **≠** 涵蓋真需求。這支全綠的意思是
    「這組驗收至少有鑑別力」，不是「驗收套件固定點已解」。
  · **量不到不是通過**：某一題沒有參考解、或沒有壞樁 ⇒ 那一題**不計入覆蓋**，
    而且 `coverage_n != n_tasks` ⇒ 發射閘門 E-3 紅。不准讓「沒有樁」
    看起來像「樁都擋住了」。

比 `suitegauge` 多做一件事：**逐條記下每個壞樁是被哪幾條隱藏驗收擋下來的**。
理由是覆蓋不足在總分上看不出來——三個壞樁全被同一條驗收擋掉，
與被三條不同的驗收擋掉，`blocked_n` 都是 3。

用法：
    python3 ops/gain/r530/gauge.py --task-set all --backend auto
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from ops.gain.r530 import acceptance, tasks as taskmod, wshash  # noqa: E402
from ops.gain.r530.sandbox import make_sandbox  # noqa: E402

GOOD_NAME = "good.py"
BAD_PREFIX = "bad_"


def _stage(template_dir: pathlib.Path, candidate: pathlib.Path,
           dest: pathlib.Path) -> None:
    """樣板 ＋ 候選解 ⇒ 一個可驗收的工作區（候選解落成 `solution.py`）。"""
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template_dir, dest)
    shutil.copy2(candidate, dest / "solution.py")


def gauge_task(task: dict, sandbox, workroot: pathlib.Path,
               *, timeout_s: float | None = None) -> dict:
    gdir: pathlib.Path = task["gauge_dir"]
    rec: dict = {"task_id": task["task_id"], "gauge_dir": str(gdir),
                 "good": None, "bad": [], "problems": []}
    if not gdir.is_dir():
        rec["problems"].append("沒有 gauge 目錄——這一題不計入覆蓋")
        return rec
    good = gdir / GOOD_NAME
    bads = sorted(p for p in gdir.glob(f"{BAD_PREFIX}*.py"))
    if not good.is_file():
        rec["problems"].append(f"沒有 {GOOD_NAME}——這一題不計入覆蓋")
    if not bads:
        rec["problems"].append("沒有任何壞樁——這一題不計入覆蓋")

    verify_root = workroot / "_verify"
    kwargs = {} if timeout_s is None else {"timeout_s": timeout_s}

    if good.is_file():
        ws = workroot / f"{task['task_id']}__good"
        _stage(task["template_dir"], good, ws)
        before = wshash.tree_hash(ws)
        vis = acceptance.run_suite(sandbox, ws, task["visible_dir"],
                                   suite="visible", task_id=task["task_id"],
                                   verify_root=verify_root, **kwargs)
        hid = acceptance.run_suite(sandbox, ws, task["hidden_dir"],
                                   suite="hidden", task_id=task["task_id"],
                                   verify_root=verify_root, **kwargs)
        after = wshash.tree_hash(ws)
        rec["good"] = {
            "visible": {"passed": vis["passed"], "total": vis["total"],
                        "all_pass": vis["all_pass"]},
            "hidden": {"passed": hid["passed"], "total": hid["total"],
                       "all_pass": hid["all_pass"]},
            "workspace_unchanged": before == after,
            "failing": [f"{c['file']}::{c['case']} {c['kind']}: {c['message']}"
                        for c in acceptance.failing_cases(vis)
                        + acceptance.failing_cases(hid)][:20],
        }
        if not (vis["all_pass"] and hid["all_pass"]):
            rec["problems"].append(
                "參考解沒有全過——那不是參考解寫得不好，是驗收與契約對不起來")
        if before != after:
            rec["problems"].append("跑驗收改動了工作區（V/GT 紅線）")

    for bad in bads:
        ws = workroot / f"{task['task_id']}__{bad.stem}"
        _stage(task["template_dir"], bad, ws)
        vis = acceptance.run_suite(sandbox, ws, task["visible_dir"],
                                   suite="visible", task_id=task["task_id"],
                                   verify_root=verify_root, **kwargs)
        hid = acceptance.run_suite(sandbox, ws, task["hidden_dir"],
                                   suite="hidden", task_id=task["task_id"],
                                   verify_root=verify_root, **kwargs)
        caught_by = [f"{c['file']}::{c['case']}"
                     for c in acceptance.failing_cases(hid)]
        rec["bad"].append({
            "stub": bad.name,
            "visible_all_pass": vis["all_pass"],
            "hidden_all_pass": hid["all_pass"],
            "blocked": not hid["all_pass"],
            "hidden_passed": hid["passed"], "hidden_total": hid["total"],
            "caught_by": caught_by,
            "caught_by_n": len(caught_by),
        })
        if hid["all_pass"]:
            rec["problems"].append(
                f"壞樁 {bad.name} 沒有被任何一條隱藏驗收擋下來")
    return rec


def run_gauge(task_set: str = "all", *, backend: str = "auto",
              timeout_s: float | None = None) -> dict:
    ts = taskmod.load_tasks(task_set)
    with tempfile.TemporaryDirectory(prefix="r530gauge.") as td:
        workroot = pathlib.Path(td)
        sandbox, meta = make_sandbox(backend, workdir=str(workroot / "_probe"))
        rows = [gauge_task(t, sandbox, workroot, timeout_s=timeout_s)
                for t in ts]
    good_ok = sum(1 for r in rows
                  if (r["good"] or {}).get("visible", {}).get("all_pass")
                  and (r["good"] or {}).get("hidden", {}).get("all_pass"))
    covered = sum(1 for r in rows if not r["problems"])
    stubs = [b for r in rows for b in r["bad"]]
    out = {
        "task_set": task_set,
        "n_tasks": len(rows),
        # `coverage_n` ＝ 雙向都驗過而且全綠的題數。E-3 要求它 == n_tasks。
        "coverage_n": covered,
        "coverage_visible_n": good_ok,
        "stubs_n": len(stubs),
        "stubs_blocked_n": sum(1 for b in stubs if b["blocked"]),
        "backend_meta": meta,
        "tasks": rows,
        "verdict": "OK" if (covered == len(rows) and rows
                            and all(b["blocked"] for b in stubs)) else "RED",
        "honest_bound": (
            "單邊保證：擋得住已知壞解 ≠ 涵蓋真需求。本表全綠的意思是"
            "「這組驗收至少有鑑別力」，不是「驗收套件固定點已解」"
            "（vacant_network/suitegauge.py 的同一句）。"),
    }
    return out


def render(out: dict) -> str:
    L = [f"═══ R530 量具（雙向）task_set={out['task_set']} ═══",
         f"題 {out['n_tasks']}　覆蓋 {out['coverage_n']}　"
         f"參考解全過 {out['coverage_visible_n']}　"
         f"壞樁 {out['stubs_blocked_n']}/{out['stubs_n']} 被擋",
         f"沙箱 {out['backend_meta'].get('backend')} "
         f"(network_isolated={out['backend_meta'].get('network_isolated')} "
         f"write_confined={out['backend_meta'].get('write_confined')})",
         ""]
    for t in out["tasks"]:
        g = t["good"] or {}
        L.append(f"· {t['task_id']}")
        if g:
            L.append(f"    good: visible {g['visible']['passed']}/"
                     f"{g['visible']['total']}  hidden {g['hidden']['passed']}/"
                     f"{g['hidden']['total']}  ws_unchanged={g['workspace_unchanged']}")
            for f in g.get("failing", []):
                L.append(f"      ! {f}")
        for b in t["bad"]:
            mark = "擋住" if b["blocked"] else "**沒擋住**"
            L.append(f"    {b['stub']:26} {mark}  hidden "
                     f"{b['hidden_passed']}/{b['hidden_total']}  "
                     f"被 {b['caught_by_n']} 條抓到")
        for p in t["problems"]:
            L.append(f"    ✗ {p}")
    L += ["", f"總判：{out['verdict']}", out["honest_bound"]]
    return "\n".join(L)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="R530 雙向量具（零模型呼叫）")
    ap.add_argument("--task-set", default="all")
    ap.add_argument("--backend", default="auto")
    ap.add_argument("--timeout-s", type=float, default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    out = run_gauge(args.task_set, backend=args.backend, timeout_s=args.timeout_s)
    print(render(out))
    if args.json:
        p = pathlib.Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
        print(f"\nJSON → {args.json}")
    return 0 if out["verdict"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
