#!/usr/bin/env python3
"""leak_scan — 要進 repo 的證據檔裡，有沒有題目內容（題目敘述、契約、隱藏測資、參考答案）。

    python3 leak_scan.py --staged <staged 樹> --paths <要掃的檔或目錄…> [--min-len 24]

規矩（CLAUDE.md／SPEC）：題目內容不進 repo。這裡的做法：把 staged 樹裡每一題的 goal.md／contract.md／hidden 底下每個檔的
**每一行（≥ min-len 個字元）**收成集合，逐行掃要提交的檔，任何一行出現在證據檔裡就列出來、exit 1。
有負控制：先把一行真題目文字寫進暫存檔、確認掃得出來，掃不出來整個停下來（掃描器本身壞了就不能報 0 筆）。
誠實邊界：只抓「整行原文」；改寫過的內容、被截短到 min-len 以下的片段抓不到。
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


def task_lines(staged: Path, min_len: int) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in staged.rglob("*"):
        if not f.is_file() or f.name in ("tasks_index.json", "MANIFEST.json", "scorer.py", "instruction.txt"):
            continue
        rel = f.relative_to(staged).as_posix()
        if not (rel.endswith(("goal.md", "contract.md")) or "/hidden/" in rel or "/workspace/" in rel):
            continue
        try:
            txt = f.read_text(errors="replace")
        except OSError:
            continue
        for ln in txt.splitlines():
            ln = ln.strip()
            if len(ln) >= min_len:
                out.setdefault(ln, rel)
    return out


def files_of(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        out += [x for x in p.rglob("*") if x.is_file()] if p.is_dir() else [p]
    return out


def scan(lines: dict[str, str], files: list[Path]) -> list[tuple[str, str, str]]:
    hits = []
    for f in files:
        try:
            txt = f.read_text(errors="replace")
        except OSError:
            continue
        for ln, src in lines.items():
            if ln in txt:
                hits.append((str(f), src, ln[:60]))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--staged", type=Path, required=True)
    ap.add_argument("--paths", type=Path, nargs="+", required=True)
    ap.add_argument("--min-len", type=int, default=24)
    a = ap.parse_args()
    lines = task_lines(a.staged, a.min_len)
    if not lines:
        print("no task lines collected: refusing to report a clean scan", file=sys.stderr)
        return 3
    sample = next(iter(lines))
    with tempfile.TemporaryDirectory() as d:                        # 負控制：掃描器得抓得到一行真題目文字
        neg = Path(d) / "neg.txt"
        neg.write_text("prefix\n" + sample + "\nsuffix\n")
        if not scan(lines, [neg]):
            print("NEGATIVE CONTROL FAILED: the scanner cannot see a known task line", file=sys.stderr)
            return 4
    fs = files_of(a.paths)
    hits = scan(lines, fs)
    for f, src, ln in hits:
        print(f"LEAK {f}: line from {src}: {ln!r}")
    print(f"scanned {len(fs)} file(s) against {len(lines)} task line(s): {len(hits)} hit(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
