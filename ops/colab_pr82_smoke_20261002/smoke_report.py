#!/usr/bin/env python3
"""PR #82 機制冒煙的病歷讀取（不做統計）。用法：smoke_report.py <cells 目錄> <plan.json> [--scores]

每一格：組別、rc、逾時、有沒有交 solution.py、每次交件前檢查的 action 與 findings（kind/sub）、
那次檢查**之前**有沒有跑過 run_tests.sh（指令本文在 vacant_home/trace/objects/）。
--scores 才讀 score.json（批次全部收完之後才給）。輸出不含題目、測資或程式碼本文。"""
import collections, json, pathlib, sys

cells, plan = pathlib.Path(sys.argv[1]), json.loads(pathlib.Path(sys.argv[2]).read_text())
want_scores = "--scores" in sys.argv
group = {f"{t['bank']}/{t['id']}": t["group"] for t in plan["tasks"]}
rows = []
for d in sorted(cells.glob("p82-*")):
    meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
    bank_id = meta.get("task_dir", "").replace("/srv/eval/staged/", "")
    after = (d / "workspace_after.sha256").read_text() if (d / "workspace_after.sha256").exists() else ""
    r = {"cell": d.name, "group": group.get(bank_id), "done": (d / "DONE").exists(), "rc": meta.get("rc"),
         "timeout": meta.get("timeout"), "wall_s": meta.get("wall_s"), "install_rc": meta.get("install_rc"),
         "delivered_solution_py": "  ./solution.py" in after, "reviews": [], "ran_run_tests_sh_ever": False}
    ran = False
    for ch in d.glob("vacant_home/trace/projects/*/chain.ndjson"):
        for ln in ch.read_text().splitlines():
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            p = e.get("payload") or {}
            if e.get("type") == "step" and p.get("tool") == "bash":
                ib = p.get("input_blob") or ""
                ob = d / "vacant_home" / "trace" / "objects" / ib[:2] / ib
                if ib and ob.is_file() and b"run_tests.sh" in ob.read_bytes():
                    ran = True
            if e.get("type") == "review":
                r["reviews"].append({"action": p.get("action"), "ran_run_tests_sh_before": ran,
                                     "findings": [f"{f.get('kind')}/{f.get('sub') or '-'}" for f in (p.get("findings") or [])]})
            if e.get("type") in ("ended",):
                r.setdefault("ended", 0); r["ended"] = r.get("ended", 0) + 1
    r["ran_run_tests_sh_ever"] = ran
    r["sendback_findings"] = [k for rv in r["reviews"] if rv["action"] != "allow" for k in rv["findings"]]
    r["test_claim_none_after_run_tests"] = sum(1 for rv in r["reviews"] if rv["action"] != "allow"
                                             and rv["ran_run_tests_sh_before"] and "test_claim/none" in rv["findings"])
    r["delivery_md"] = any(d.glob("vacant_home/trace/projects/*/delivery.md")) or any(d.glob("vacant_home/**/delivery.md"))
    if want_scores:
        try:
            s = json.loads((d / "score.json").read_text().strip().splitlines()[-1])
            r["pass"] = s.get("pass")
        except (OSError, ValueError, IndexError):
            r["pass"] = None
    rows.append(r)

summ = {}
for g in ("misreject20", "nodeliver_natural", "nodeliver_forced"):
    rs = [r for r in rows if r["group"] == g]
    summ[g] = {"cells": len(rs), "done": sum(r["done"] for r in rs), "timeout": sum(bool(r["timeout"]) for r in rs),
               "install_fail": sum(r["install_rc"] not in (0, None) for r in rs),
               "reached_review": sum(bool(r["reviews"]) for r in rs),
               "ran_run_tests_sh": sum(r["ran_run_tests_sh_ever"] for r in rs),
               "cells_test_claim_none_after_run_tests": sum(r["test_claim_none_after_run_tests"] > 0 for r in rs),
               "cells_with_any_sendback": sum(bool(r["sendback_findings"]) for r in rs),
               "sendback_kinds": dict(collections.Counter(k for r in rs for k in r["sendback_findings"])),
               "all_finding_kinds_incl_allow": dict(collections.Counter(k for r in rs for rv in r["reviews"] for k in rv["findings"])),
               "delivered_solution_py": sum(r["delivered_solution_py"] for r in rs),
               "cells_missing_output_sendback": sum(any(k.startswith("missing_output") for k in r["sendback_findings"]) for r in rs)}
    if want_scores:
        summ[g]["pass"] = sum(r.get("pass") is True for r in rs)
print(json.dumps({"summary": summ, "cells": rows}, ensure_ascii=False, indent=1))
