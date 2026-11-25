#!/usr/bin/env python3
"""越界讀取掃描（第三輪獨立稽核 11-25 第 5 點之後的要求）：agent 有沒有讀到自己工作目錄以外的 harness 路徑。

看每一次 agent 執行的 agent.log（pi 的 JSON 事件、Claude Code 的串流 JSON）裡的工具呼叫輸入（command／path／file_path／pattern），
找出提到 harness 路徑的：`cells/`、`d2_runs`、`d2_materials`、`d2_results`、`d2_private`、別組的 `live/sNN`、往上跳出工作目錄的 `../`。
只是字串比對：會有誤報（例如 agent 只是印出自己的路徑），所以逐筆列出、人看；沒提到不等於沒讀（例如腳本裡拼接路徑）。

用法：scan_escape.py --root R [--out J]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re

FIELDS = re.compile(r'"(command|path|file_path|pattern|cwd)"\s*:\s*"((?:[^"\\]|\\.)*)"')
HARNESS = re.compile(r"cells/|d2_materials|d2_results|d2_private|/live/(s\d\d)\b|\.\./")
LISTING = re.compile(r"\b(find|ls|tree|du|grep\s+-\w*r)\b")
ABSPATH = re.compile(r"(?<![\w.])/?home/[\w./-]+")


def scan_log(log: pathlib.Path, own_set: str) -> list[str]:
    hits = []
    txt = log.read_text(errors="replace")
    cwd = next((m.group(2) for m in FIELDS.finditer(txt) if m.group(1) == "cwd"), None)
    own = str(pathlib.PurePosixPath(cwd).parent) if cwd else None     # 自己那一組的 live 目錄（ws 的上一層）
    for m in FIELDS.finditer(txt):
        if m.group(1) == "cwd":
            continue
        val = m.group(2).encode().decode("unicode_escape", "ignore")
        val_chk = val.replace(own, "<OWN>").replace(own.lstrip("/"), "<OWN>") if own else val
        # 列舉自己工作目錄的上層（find／ls 上層目錄）＝越界的列舉
        if own and m.group(1) == "command" and LISTING.search(val):
            anc = [t for t in ABSPATH.findall(val_chk)
                   if own.startswith("/" + t.lstrip("/").rstrip("/")) and ("/" + t.lstrip("/").rstrip("/")) != own]
            if anc:
                hits.append(f"list-ancestor {m.group(1)}: {val[:300]}")
                continue
        for h in HARNESS.finditer(val_chk):
            if h.group(1) and h.group(1) == own_set:
                continue                     # 自己那一組的工作目錄
            if h.group(0) == "../" and not re.search(r"\.\./\.\.|\.\./(s\d\d|cells|live)", val_chk):
                continue                     # 一層 ../ 多半還在自己的組目錄裡；只記跳兩層以上或指向別組
            hits.append(f"{m.group(1)}: {val[:300]}")
            break
    return list(dict.fromkeys(hits))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    root = pathlib.Path(a.root).expanduser()
    rows = []
    for log in sorted(root.glob("cells/s*/**/agent.log")):
        rel = log.relative_to(root / "cells").parts
        own = rel[0]
        hits = scan_log(log, own)
        if hits:
            rows.append({"set": own, "where": "/".join(rel[1:-1]), "hits": hits})
    by_set = collections.Counter(r["set"] for r in rows)
    out = {"root": root.name, "logs_with_hits": len(rows), "sets_with_hits": sorted(by_set), "rows": rows}
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    if a.out:
        pathlib.Path(a.out).expanduser().write_text(txt + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False))
    for r in rows[:40]:
        print(r["set"], r["where"], "|", r["hits"][0][:160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
