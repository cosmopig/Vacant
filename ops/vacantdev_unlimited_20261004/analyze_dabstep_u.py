#!/usr/bin/env python3
"""DABstep × v3.7、不設回合上限（vacant-dev）的凍結分析（由 analyze_dabstep.py 改：只有 A／C37、沒有次要檢定）。原說明：批次收完、void 清單確認之後跑一次：

    PYTHONPATH=<repo 含 vacant_network> python3 analyze_dabstep.py <cells 目錄> <plan.json> --prefix d37 > report.json

預註冊 `decisions/prereg/PREREG_20261002_COLAB_DABSTEP_V37.md` 第五節：
- 主要分析 77 題（去掉 5、70）；「完整的次數」＝三組 77 題都有分數（或依 void 規則拿掉）的次數。
- 主要檢定：每題在完整各次的平均答對率，C37 − A，Wilcoxon 符號等級精確雙尾（`research.wilcoxon_signed_rank_exact`，差為 0 的題去掉）；
  只有 1 次完整 ⇒ McNemar 精確（二項）。
- 次要（Holm，家族 2）：C37R − A、C37R − C37。
- 描述：每組每次答對／沒交／答錯、Vacant 的動作（交件前檢查、退回類別、提醒、ended 說明）、傷害（第一次交件對、退回後改錯）。
`--void-only`：只印 void 清單，不讀任何分數（補跑前用）。
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib

EXCLUDED = {"5", "70"}
ARMS = ["A", "C37"]   # 不設回合上限 ⇒ 沒有 C37R（提醒只在寫明上限時作用）


def load(cells: pathlib.Path, prefix: str, read_scores: bool) -> list[dict]:
    rows = []
    for d in sorted(cells.glob(f"{prefix}-*")):
        if not (d / "DONE").exists():
            continue
        meta = json.loads((d / "meta.json").read_text())
        arm = meta["arm"]
        task = pathlib.Path(meta["task_dir"]).name
        sample = int(d.name.rsplit("-s", 1)[1])
        # 模型有沒有回過任何一則 assistant 訊息（沒有＝infra）
        answered = False
        try:
            for ln in (d / "pi_stdout.txt").read_text(errors="replace").splitlines():
                if '"role":"assistant"' in ln and '"stopReason":"error"' not in ln:
                    answered = True
                    break
        except OSError:
            pass
        r = {"cell": d.name, "arm": arm, "task": task, "sample": sample, "rc": meta.get("rc"),
             "timeout": meta.get("timeout"), "install_rc": meta.get("install_rc"), "wall_s": meta.get("wall_s"),
             "answered": answered}
        sc = None
        try:
            sc = json.loads((d / "score.json").read_text().strip().splitlines()[-1])
        except (OSError, ValueError, IndexError):
            pass
        r["score_ok"] = sc is not None and sc.get("pass") is not None
        r["void"] = (not r["score_ok"]) or (not answered)
        if read_scores and sc is not None:
            r["pass"] = sc.get("pass")
            r["answer_exists"] = sc.get("answer_exists")
        # Vacant 的動作（C 組）
        acts = {"reviews": 0, "sendbacks": [], "nudges": 0, "ended": 0, "first_review_action": None}
        for ch in d.glob("vacant_home/trace/projects/*/chain.ndjson"):
            for ln in ch.read_text().splitlines():
                try:
                    e = json.loads(ln)
                except ValueError:
                    continue
                p = e.get("payload") or {}
                if e.get("type") == "review":
                    acts["reviews"] += 1
                    if acts["first_review_action"] is None:
                        acts["first_review_action"] = p.get("action")
                    if p.get("action") != "allow":
                        acts["sendbacks"] += [f"{f.get('kind')}/{f.get('sub') or '-'}" for f in (p.get("findings") or [])]
                elif e.get("type") == "nudge":
                    acts["nudges"] += 1
                elif e.get("type") == "ended":
                    acts["ended"] += 1
        r["vacant"] = acts
        try:
            r["check"] = json.loads((d / "vacant_check.json").read_text().strip().splitlines()[-1])
        except (OSError, ValueError, IndexError):
            r["check"] = None
        rows.append(r)
    return rows


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cells", type=pathlib.Path)
    ap.add_argument("plan", type=pathlib.Path)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--void-only", action="store_true")
    a = ap.parse_args()
    plan = json.loads(a.plan.read_text())
    tasks = [t["id"] for t in plan["tasks"]]
    rows = load(a.cells, a.prefix, read_scores=not a.void_only)
    by = {(r["task"], r["sample"], r["arm"]): r for r in rows}
    voids = [r["cell"] for r in rows if r["void"]]
    if a.void_only:
        print(json.dumps({"cells_done": len(rows), "void": voids,
                          "by_arm_done": dict(collections.Counter(r["arm"] for r in rows))}, indent=1))
        return 0
    from vacant_network.research import wilcoxon_signed_rank_exact

    main_tasks = [t for t in tasks if t not in EXCLUDED]
    samples = sorted({r["sample"] for r in rows})
    complete, dropped = [], {}
    for s in samples:
        ok, drop = True, []
        for t in main_tasks:
            cs = [by.get((t, s, arm)) for arm in ARMS]
            if any(c is None for c in cs):
                ok = False
                break
            if any(c["void"] for c in cs):
                drop.append(t)      # 依第四節：補跑也壞 ⇒ 這題這一次的三組都拿掉
        if ok:
            complete.append(s)
            dropped[s] = drop
    res = {"samples_seen": samples, "complete_samples": complete, "dropped_by_sample": dropped, "void_cells": voids}

    def rate(t, arm):
        v = [1.0 if by[(t, s, arm)].get("pass") else 0.0 for s in complete if t not in dropped[s]]
        return sum(v) / len(v) if v else None

    per_task = {t: {arm: rate(t, arm) for arm in ARMS} for t in main_tasks}

    def test(x, y):
        pairs = [(per_task[t][x], per_task[t][y]) for t in main_tasks
                 if per_task[t][x] is not None and per_task[t][y] is not None]
        if len(complete) == 1:
            b = sum(1 for p, q in pairs if p > q)
            c = sum(1 for p, q in pairs if q > p)
            return {"test": "mcnemar_exact", "x_only": b, "y_only": c, "p": mcnemar_exact(b, c), "n_tasks": len(pairs)}
        diffs = [round(p - q, 12) for p, q in pairs]
        out = wilcoxon_signed_rank_exact(diffs)
        return {"test": "wilcoxon_signed_rank_exact", "n_tasks": len(pairs),
                "mean_diff": sum(diffs) / len(diffs) if diffs else None,
                "x_better": sum(d > 0 for d in diffs), "y_better": sum(d < 0 for d in diffs), "result": out}

    if complete:
        res["primary_C37_minus_A"] = test("C37", "A")
    # 描述
    desc = {}
    for s in samples:
        for arm in ARMS:
            rs = [by[(t, s, arm)] for t in main_tasks if (t, s, arm) in by]
            desc[f"s{s}-{arm}"] = {"cells": len(rs), "pass": sum(bool(r.get("pass")) for r in rs),
                                   "no_answer_file": sum(r.get("answer_exists") is False for r in rs),
                                   "wrong": sum(r.get("answer_exists") is True and not r.get("pass") for r in rs),
                                   "void": sum(r["void"] for r in rs), "timeout": sum(bool(r["timeout"]) for r in rs)}
    res["describe"] = desc
    va = {}
    for arm in ("C37",):
        rs = [r for r in rows if r["arm"] == arm and r["task"] not in EXCLUDED]
        va[arm] = {"cells": len(rs), "install_fail": sum(r["install_rc"] not in (0, None) for r in rs),
                   "c_arm_ok": sum(bool((r["check"] or {}).get("c_arm_ok")) for r in rs),
                   "reached_review": sum(r["vacant"]["reviews"] > 0 for r in rs),
                   "cells_sent_back": sum(bool(r["vacant"]["sendbacks"]) for r in rs),
                   "sendback_kinds": dict(collections.Counter(k for r in rs for k in r["vacant"]["sendbacks"])),
                   "cells_nudged": sum(r["vacant"]["nudges"] > 0 for r in rs),
                   "nudges": sum(r["vacant"]["nudges"] for r in rs),
                   "ended_notes": sum(r["vacant"]["ended"] for r in rs),
                   "pass_after_sendback": sum(bool(r["vacant"]["sendbacks"]) and bool(r.get("pass")) for r in rs)}
    res["vacant_actions"] = va
    res["per_task"] = per_task
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
