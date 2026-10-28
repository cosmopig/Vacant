#!/usr/bin/env python3
"""~/.vacant 成長趨勢記錄器（Axis 2，round 151）。

ASSIGNMENT 10/28 驗收 1 要求「量它從零開始一天長多少」：本工具把
`~/.vacant` 的體積（總計＋各子目錄＋objects blob 數）記成一筆 JSONL，
供隔日比對「一天真實成長」。

- **唯讀**：不碰 `~/.vacant` 任何檔案（只 stat／du）。
- 輸出預設 `~/dev/ops/data/vacant_growth.jsonl`（可用 `--out` 改）。
- 同一分鐘內重複跑會覆蓋最後一筆（避免誤觸濫記）。

用法:
    python3 vacant_growth_log.py [--home PATH] [--out FILE] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import time


def _du(p: pathlib.Path) -> int:
    """apparent bytes（與 ASSIGNMENT 的 872M 口徑一致，非 block 用量）。"""
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            fp = pathlib.Path(root) / f
            try:
                if not fp.is_symlink():
                    total += fp.stat().st_size
            except OSError:
                pass
    return total


def snapshot(home: pathlib.Path) -> dict:
    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "home": str(home),
           "total_bytes": 0}
    if not home.is_dir():
        out["note"] = "home missing"
        return out
    out["total_bytes"] = _du(home)
    per_dir: dict[str, int] = {}
    for d in sorted(p for p in home.iterdir() if p.is_dir()):
        per_dir[d.name] = _du(d)
    out["per_dir_bytes"] = per_dir
    obj = home / "trace" / "objects"
    if obj.is_dir():
        out["objects_files"] = sum(1 for _ in obj.glob("**/*")
                                   if _.is_file())
    rep = home / "gc_report.json"
    if rep.is_file():
        try:
            r = json.loads(rep.read_text(encoding="utf-8"))
            out["gc_last"] = {"status": r.get("status"),
                              "target_reached": (r.get("trace") or {}).get("target", {}).get("target_reached")}
        except (OSError, ValueError):
            pass
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--home", type=pathlib.Path,
                    default=pathlib.Path(os.environ.get("VACANT_HOME",
                                                        pathlib.Path.home() / ".vacant")))
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path.home() / "dev/ops/data/vacant_growth.jsonl")
    ap.add_argument("--json", action="store_true", help="只印這一筆，不寫檔")
    a = ap.parse_args(argv)

    rec = snapshot(a.home)
    if a.json:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        return 0

    a.out.parent.mkdir(parents=True, exist_ok=True)
    lines = a.out.read_text(encoding="utf-8").splitlines() if a.out.is_file() else []
    if lines:
        try:
            last = json.loads(lines[-1])
            if (time.strftime("%Y-%m-%dT%H:%M") ==
                    last.get("ts", "")[:16] and last.get("home") == rec["home"]):
                lines[-1] = json.dumps(rec, ensure_ascii=False)
            else:
                lines.append(json.dumps(rec, ensure_ascii=False))
        except ValueError:
            lines.append(json.dumps(rec, ensure_ascii=False))
    else:
        lines.append(json.dumps(rec, ensure_ascii=False))
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"recorded {a.out}: {rec['total_bytes']:,} B "
          f"({rec['total_bytes'] / 2**20:.1f} MiB) at {rec['ts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
