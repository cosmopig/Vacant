#!/usr/bin/env python3
"""e002_carm_failures — e002 C 臂未通過 cell 的失敗型態分類量具（round 201，P20261030_0601-3）。

目的：審查指示第四節第 5 條【P2 · 針對 e002 C 臂失敗題型的失敗機制深入分析】。
對 score.json 中 pass==false 的每個 C 臂 cell（遍歷 polyglot_py-*-pi-C-r1），
點名並落盤可重算的事實：
  - timed_out：cell.json 的逾時狀態；
  - rejections：交件退回次數＝vacant_home.tgz 裡 intake/hooks/rounds_*.json 的 n（取最大）；
  - last_hint：最後退回 hint＝trace/projects/*/delivery.json 的 unverified[0]
    （形如 "Still open after N round(s): ..."）；沒有 unverified 才退而取 findings[0]。
誠實規則（不變量 5）：
  - 無 vacant_home.tgz／無 rounds／無 delivery.json → rejections=null、last_hint=null
    （UNKNOWN，不是「0 次」也不是「沒有 hint」）；
  - 分類只依測得事實：timed_out→"timeout"，否則 "not_converged"；
  - 失敗 cell 數是**測得值**，不寫死 12（數據變了報告跟著變）。
本量具**唯讀**：只讀 /srv/vlab/runs/e002_hypothesis_arms/ 下 cell.json、score.json、
vacant_home.tgz；不寫任何檔、不碰 /srv/eval。
用法：python3 ops/vlab/tools/e002_carm_failures.py [--base /srv/vlab/runs]
輸出：JSON 至 stdout。退出碼：0 成功；2 run 目錄不存在。
"""
from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path


def _load_json(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _json_bytes(b: bytes):
    try:
        return json.loads(b.decode("utf-8", "replace"))
    except ValueError:
        return None


def _vacant_evidence(cell: Path) -> dict:
    """唯讀掃 vacant_home.tgz：rounds 的 n（退回次數）與 delivery 的最後 unverified hint。"""
    ev = {"rejections": None, "last_hint": None}
    tgz = cell / "vacant_home.tgz"
    if not tgz.is_file():
        return ev
    try:
        with tarfile.open(tgz, "r:gz") as tf:
            for m in tf.getmembers():
                if not m.isfile():
                    continue
                n = m.name
                if "/intake/hooks/rounds_" in n and n.endswith(".json"):
                    r = _json_bytes(tf.extractfile(m).read())
                    if isinstance(r, dict) and isinstance(r.get("n"), int):
                        ev["rejections"] = max(ev["rejections"] or 0, r["n"])
                elif "/trace/projects/" in n and n.endswith("delivery.json"):
                    d = _json_bytes(tf.extractfile(m).read())
                    if not isinstance(d, dict):
                        continue
                    unv = d.get("unverified") or []
                    if unv:
                        ev["last_hint"] = str(unv[0])[:300]
                    elif d.get("findings"):
                        f0 = d["findings"][0]
                        ev["last_hint"] = (f0.get("test_hint") or f0.get("error") or None)
    except (tarfile.TarError, OSError):
        pass  # tgz 讀不了 → 保持 null（UNKNOWN），不編造
    return ev


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="/srv/vlab/runs")
    args = ap.parse_args()
    run = Path(args.base) / "e002_hypothesis_arms"
    if not run.is_dir():
        raise SystemExit(f"找不到 run 目錄 {run}")
    cells, n_scanned = [], 0
    for c in sorted(run.iterdir()):
        if not c.is_dir() or ".infra-" in c.name:
            continue
        if not (c.name.startswith("polyglot_py-") and c.name.endswith("-pi-C-r1")):
            continue
        n_scanned += 1
        sc = _load_json(c / "score.json")
        if not isinstance(sc, dict) or sc.get("pass") is not False:
            continue
        cj = _load_json(c / "cell.json") or {}
        ev = _vacant_evidence(c)
        rec = {
            "cell": c.name,
            "task": cj.get("task"),
            "timed_out": bool(cj.get("timed_out")),
            "agent_rc": cj.get("agent_rc"),
            "wall_s": cj.get("wall_s"),
            "tests_passed_total": f"{sc.get('tests_passed')}/{sc.get('tests_total')}",
            "rejections": ev["rejections"],
            "last_hint": ev["last_hint"],
            "classification": "timeout" if cj.get("timed_out") else "not_converged",
        }
        cells.append(rec)
    report = {
        "tool": "e002_carm_failures",
        "run": str(run),
        "arm": "C",
        "n_c_cells_scanned": n_scanned,
        "failed_cells": len(cells),
        "timed_out_cells": [r["cell"] for r in cells if r["classification"] == "timeout"],
        "not_converged_cells": [r["cell"] for r in cells if r["classification"] == "not_converged"],
        "cells": cells,
        "note": "rejections=null 表示 vacant_home.tgz 無 rounds_*.json（UNKNOWN，不是 0）；last_hint=null 同理。",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
