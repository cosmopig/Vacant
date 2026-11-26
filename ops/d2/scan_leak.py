#!/usr/bin/env python3
"""越界讀取（掃工具輸出，不只指令字串）——照獨立稽核者 leak4b.py 的口徑（第三／四輪稽核 11-25）。

對每一次 agent 執行的工具呼叫：指令或路徑提到教材目錄（heldout_vN_seed…／realrev_seed…）底下的檔案，
而且工具真的回了內容（不是「找不到」）⇒ 記一筆。分類：自己這一組／別組或別的種子 × 範本／過去週期／這一週期／未來週期／manifest 或 SOURCES（答案）。
pi 的事件（tool_execution_start／end）與 Claude Code 的串流（tool_use／tool_result）都收。
用法：scan_leak.py --root R --seed-of-batch <教材資料夾名> [--out J]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re

PAT = re.compile(r"(heldout_v\d_seed\d+|realrev_seed\d+)/(?:sets/(s\d+)/(?:cycle_(\d)/site/([\w.\-]+)|(template\.md))|(manifest\.json|SOURCES\.md|manifest\.sha256))")
READY = re.compile(r"\bcat\b|\bhead\b|\btail\b|\bgrep\b|\bless\b|\bsed\b|\bawk\b|open\(|read_text|Read")


def calls(log: pathlib.Path):
    starts: dict = {}
    for ln in log.read_text(errors="replace").splitlines():
        if not ln.startswith("{"):
            continue
        try:
            o = json.loads(ln)
        except ValueError:
            continue
        t = o.get("type")
        if t == "tool_execution_start":
            starts[o.get("toolCallId")] = (o.get("toolName", ""), json.dumps(o.get("args"), ensure_ascii=False))
        elif t == "tool_execution_end":
            tn, s = starts.get(o.get("toolCallId"), ("", ""))
            yield tn, s, json.dumps(o.get("result"), ensure_ascii=False)
        elif t == "assistant":
            for c in (o.get("message") or {}).get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    starts[c.get("id")] = (c.get("name", ""), json.dumps(c.get("input"), ensure_ascii=False))
        elif t == "user":
            for c in (o.get("message") or {}).get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    tn, s = starts.get(c.get("tool_use_id"), ("", ""))
                    yield tn, s, json.dumps(c.get("content"), ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--seed-of-batch", required=True, help="這一批教材的資料夾名，例如 realrev_seed20261172")
    ap.add_argument("--out")
    a = ap.parse_args()
    root = pathlib.Path(a.root).expanduser()
    rows = []
    for log in sorted(root.glob("cells/s*/**/agent.log")):
        parts = log.relative_to(root / "cells").parts
        sid, arm = parts[0], parts[1]
        cur = next((int(p.split("_")[1]) for p in parts if p.startswith("cycle_")), 0)
        for tn, s, out in calls(log):
            ms = PAT.findall(s)
            if not ms or not (tn.lower() in ("read", "bash") or READY.search(s)):
                continue
            if len(out) < 80 or "ENOENT" in out or "No such file" in out or "Permission denied" in out:
                continue
            for mat, s2, c, fn, tpl, ans in ms:
                own = mat == a.seed_of_batch and (s2 == sid or ans)
                if ans:
                    kind = "manifest/SOURCES (answers)"
                elif tpl:
                    kind = "template"
                else:
                    kind = "future cycle" if int(c) > cur else ("current cycle" if int(c) == cur else "past cycle")
                rows.append({"set": sid, "arm": arm, "cycle": cur, "material": mat if mat != a.seed_of_batch else "<this batch>",
                             "target_set": s2 or None, "target_cycle": int(c) if c else None, "file": fn or tpl or ans,
                             "own": bool(own), "kind": kind, "bytes_returned": len(out)})
    by = collections.Counter((("own set" if r["own"] else "OTHER set or material") + " | " + r["kind"]) for r in rows)
    res = {"root": root.name, "rows": len(rows), "by_kind": dict(by),
           "runs": len({(r["set"], r["arm"], r["cycle"]) for r in rows}),
           "sets": sorted({r["set"] for r in rows}), "details": rows}
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        pathlib.Path(a.out).expanduser().write_text(txt + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "details"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
