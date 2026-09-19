#!/usr/bin/env python3
"""寫入探針：一條路徑寫不寫得進去，而且**寫不進去的時候要講清楚是哪一種**。

⚠ 這支存在的理由是 2026-09-20 踩到的一個量具說謊：用
  `echo x > "$d/f" || echo READONLY $d` 去量，`/home/user1` 印了 `READONLY`
  ——但真因是 `No such file or directory`（enclosure 裡那條路徑**根本不存在**），
  不是唯讀。「寫不進去」有至少五種 errno，混成一格布林值就會判錯。

所以這支印的是 errno 名字：
  · `WROTE`      —— 真的寫進去了（而且會把檔案刪掉）
  · `EROFS`      —— 唯讀掛載（`--ro-bind` 要的就是這一個）
  · `ENOENT`     —— 路徑不存在（**不是**唯讀）
  · `EACCES`／`EPERM`／其它 —— 原樣印出來

用法：`write_probe.py <路徑...>`；`--json <檔>` 落盤。
"""
import argparse
import errno
import json
import os
import pathlib
import sys


def probe(d: str) -> dict:
    target = pathlib.Path(d) / f"_vacant_write_probe_{os.getpid()}"
    try:
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("x")
    except OSError as e:
        return {"path": d, "writable": False,
                "errno": errno.errorcode.get(e.errno, str(e.errno)),
                "detail": str(e)[:200]}
    try:
        target.unlink()
    except OSError:                                  # pragma: no cover
        pass
    return {"path": d, "writable": True, "errno": None, "detail": "wrote+unlinked"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    rows = [probe(p) for p in a.paths]
    for r in rows:
        tag = "WROTE" if r["writable"] else (r["errno"] or "ERR")
        print(f"WRITE {tag:<9s} {r['path']}  {r['detail']}", flush=True)
    if a.json:
        pathlib.Path(a.json).write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WRITE_PROBE_DONE rows={len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
