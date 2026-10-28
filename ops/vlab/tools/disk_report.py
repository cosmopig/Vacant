#!/usr/bin/env python3
"""disk_report — 主軸 2 量具：從實驗格子的 cell.json / vacant_home.tgz 彙整 ~/.vacant 真實用量與回收觸發證據（round 133）。

背景（為什麼需要這支）：
- ASSIGNMENT 主軸 2：「在 lab 格子量到真實的 ~/.vacant 用量，證明回收有沒有在真實使用裡生效，
  回收後追緝還站不站得住」。e001 研究包 §5 已掛勾：從 cell.json 彙整 C 組的 vacant_home_bytes。
- cell.py（共用量具，不改）在 C 組格子收尾時已寫下：
  - cell.json: vacant_home_bytes / vacant_objects_bytes / workspace_bytes（含 objects 快照）；
  - vacant_home.tgz: 該格 ~/.vacant 的證據快照（**不含 trace/objects**），其中若有
    gc_last.json / gc_report.json 就代表 auto_gc 在真實使用中被觸發過（Stop/session_end 掛鉤
    → 背景 `vacant gc --auto`）。
- 本腳本是**獨立量具**：只讀 /srv/vlab/runs 下的 cell.json、score.json、vacant_home.tgz，
  不碰 cell.py / labd.py / report.py（與 holm_e002.py 同一規矩）。

用法：
  python3 ops/vlab/tools/disk_report.py <exp> [--base /srv/vlab/runs] [--table] [--out PATH]
  python3 ops/vlab/tools/disk_report.py --selftest

輸出 JSON 欄位（每格）：
  cell, arm, pass, vacant_home_bytes, vacant_objects_bytes, workspace_bytes,
  gc_fired(bool), gc_status, gc_bytes_freed, gc_files_removed, gc_last_ts
聚合（by_arm）：
  n, n_with_home, home_bytes:{sum,min,median,max}, objects_bytes:{...},
  gc_fired, gc_statuses:{status:n}, cells:[...]
「沒有 vacant_home_bytes」的格子（A 組＝沒裝 Vacant）計入 n、**不**計入 n_with_home，
也不進任何 byte 統計——「沒裝」不是「0 用量」，是「沒有這支量具可讀的對照」。

退出碼：0 正常；1 找不到任何 cell.json；2 selftest 失敗或輸入不可讀。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tarfile
import tempfile
from pathlib import Path


def _read_tar_member(tgz: Path, arcname: str):
    """讀取 tgz 內的 JSON 成員；不存在/解不開 → None（誠實：沒證據 ≠ 沒發生，但本欄位只報「有證據」的）。"""
    try:
        with tarfile.open(tgz, "r:gz") as t:
            f = t.extractfile(arcname)
            if f is None:
                return None
            return json.loads(f.read().decode("utf-8"))
    except (OSError, tarfile.TarError, ValueError, KeyError, TypeError):
        return None


def cell_record(d: Path) -> dict | None:
    """讀一格（目錄）的磁碟證據。cell.json 不在 → None。"""
    cj = d / "cell.json"
    if not cj.is_file():
        return None
    try:
        info = json.loads(cj.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"cell.json 不可讀：{cj}: {e}")
    rec: dict = {
        "cell": info.get("cell") or d.name,
        "arm": info.get("arm"),
        "pass": None,
        "vacant_home_bytes": info.get("vacant_home_bytes"),
        "vacant_objects_bytes": info.get("vacant_objects_bytes"),
        "workspace_bytes": info.get("workspace_bytes"),
        "gc_fired": False,
        "gc_status": None,
        "gc_bytes_freed": None,
        "gc_files_removed": None,
        "gc_last_ts": None,
    }
    sc = d / "score.json"
    if sc.is_file():
        try:
            rec["pass"] = json.loads(sc.read_text(encoding="utf-8")).get("pass")
        except (OSError, ValueError):
            pass
    tgz = d / "vacant_home.tgz"
    if tgz.is_file():
        last = _read_tar_member(tgz, ".vacant/gc_last.json")
        rep = _read_tar_member(tgz, ".vacant/gc_report.json")
        if last is not None:
            rec["gc_fired"] = True
            rec["gc_last_ts"] = last.get("ts")
            rec["gc_status"] = last.get("status")
            rec["gc_bytes_freed"] = last.get("bytes_freed")
            rec["gc_files_removed"] = last.get("files_removed")
        elif rep is not None:
            rec["gc_status"] = rep.get("status")
    return rec


def _stats(vals: list[int]) -> dict:
    return {
        "n": len(vals), "sum": sum(vals), "min": min(vals),
        "median": statistics.median(vals), "max": max(vals),
    }


def aggregate(records: list[dict]) -> dict:
    by_arm: dict[str, dict] = {}
    for r in records:
        arm = r["arm"] or "?"
        a = by_arm.setdefault(arm, {
            "n": 0, "n_with_home": 0, "home_bytes": None, "objects_bytes": None,
            "workspace_bytes": None, "gc_fired": 0, "gc_statuses": {}, "cells": [],
        })
        a["n"] += 1
        a["cells"].append(r["cell"])
        if r["vacant_home_bytes"] is not None:
            a["n_with_home"] += 1
        if r["gc_fired"]:
            a["gc_fired"] += 1
            st = r["gc_status"] or "unknown"
            a["gc_statuses"][st] = a["gc_statuses"].get(st, 0) + 1
    for arm, a in by_arm.items():
        home = [r["vacant_home_bytes"] for r in records
                if (r["arm"] or "?") == arm and r["vacant_home_bytes"] is not None]
        objs = [r["vacant_objects_bytes"] for r in records
                if (r["arm"] or "?") == arm and r["vacant_objects_bytes"] is not None]
        ws = [r["workspace_bytes"] for r in records
              if (r["arm"] or "?") == arm and r["workspace_bytes"] is not None]
        a["home_bytes"] = _stats(home) if home else None
        a["objects_bytes"] = _stats(objs) if objs else None
        a["workspace_bytes"] = _stats(ws) if ws else None
    return by_arm


def collect(exp: str, base: Path) -> list[dict]:
    root = base / exp
    if not root.is_dir():
        raise SystemExit(f"實驗目錄不存在：{root}")
    recs = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        r = cell_record(d)
        if r is not None:
            recs.append(r)
    return recs


def render_table(exp: str, by_arm: dict) -> str:
    L = [f"== {exp}（主軸 2：~/.vacant 真實用量）==",
         f"{'arm':<6}{'n':>4}{'n_home':>8}{'home min':>12}{'home med':>12}{'home max':>12}{'gc_fired':>10}"]
    for arm in sorted(by_arm):
        a = by_arm[arm]
        h = a["home_bytes"] or {}
        L.append(f"{arm:<6}{a['n']:>4}{a['n_with_home']:>8}"
                 f"{h.get('min', 0):>12}{h.get('median', 0):>12}{h.get('max', 0):>12}"
                 f"{a['gc_fired']:>10}")
    return "\n".join(L) + "\n"


def selftest() -> int:
    """離線自測：假格子（A 無 Vacant／C 有）→ 聚合與 gc 證據斷言。失敗退出 2。"""
    ok = True
    def check(name: str, cond: bool) -> None:
        nonlocal ok
        if not cond:
            ok = False
            print(f"SELFTEST FAIL: {name}", file=sys.stderr)

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        expd = base / "exp_x"
        def mkcell(name: str, arm: str, home: int | None, objs: int | None,
                   score_pass: bool, gc: bool):
            d = expd / name
            d.mkdir(parents=True)
            info = {"cell": name, "arm": arm, "exp": "exp_x"}
            if home is not None:
                info["vacant_home_bytes"] = home
                info["vacant_objects_bytes"] = objs
                info["workspace_bytes"] = 1000
            (d / "cell.json").write_text(json.dumps(info))
            (d / "score.json").write_text(json.dumps({"pass": score_pass}))
            if gc:
                import tarfile as _tf
                with _tf.open(d / "vacant_home.tgz", "w:gz") as t:
                    payload = json.dumps({"ts": 1.0, "status": "ok",
                                         "bytes_freed": 7, "files_removed": 2}).encode()
                    import io as _io
                    ti = _tf.TarInfo(".vacant/gc_last.json")
                    ti.size = len(payload)
                    t.addfile(ti, _io.BytesIO(payload))
        mkcell("c1", "C", 114655, 76848, False, gc=True)
        mkcell("c2", "C", 41185, 18355, True, gc=False)
        mkcell("a1", "A", None, None, True, gc=False)
        recs = collect("exp_x", base)
        by_arm = aggregate(recs)
        check("three cells", len(recs) == 3)
        c = by_arm.get("C", {})
        check("C.n==2", c.get("n") == 2)
        check("C.n_with_home==2", c.get("n_with_home") == 2)
        check("C.home.min", c.get("home_bytes", {}).get("min") == 41185)
        check("C.home.max", c.get("home_bytes", {}).get("max") == 114655)
        check("C.home.median", c.get("home_bytes", {}).get("median") == (114655 + 41185) / 2)
        check("C.gc_fired==1", c.get("gc_fired") == 1)
        check("C.gc_status ok", c.get("gc_statuses", {}).get("ok") == 1)
        a = by_arm.get("A", {})
        check("A.n==1", a.get("n") == 1)
        check("A.n_with_home==0", a.get("n_with_home") == 0)
        check("A.home_bytes is None（沒裝≠0 用量）", a.get("home_bytes") is None)
        check("table renders", "c1" not in render_table("exp_x", by_arm) and "arm" in render_table("exp_x", by_arm))
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exp", nargs="?", help="實驗名（/srv/vlab/runs 下的目錄）")
    ap.add_argument("--base", default="/srv/vlab/runs", help="runs 根目錄（預設 /srv/vlab/runs）")
    ap.add_argument("--table", action="store_true", help="印人讀表格（另有 JSON 到 stdout/--out）")
    ap.add_argument("--out", help="JSON 另存路徑")
    ap.add_argument("--selftest", action="store_true", help="離線自測後退出")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.exp:
        ap.error("需要 <exp>（或 --selftest）")
    recs = collect(a.exp, Path(a.base))
    if not recs:
        print(f"找不到任何 cell.json：{Path(a.base) / a.exp}", file=sys.stderr)
        return 1
    by_arm = aggregate(recs)
    out = {"exp": a.exp, "base": str(a.base), "n_cells": len(recs),
           "by_arm": by_arm, "cells": recs,
           "note": "home_bytes=None 的格子＝沒裝 Vacant（A 組）或格子未完成，不是 0 用量"}
    s = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(s + "\n", encoding="utf-8")
    if a.table:
        sys.stdout.write(render_table(a.exp, by_arm))
    else:
        print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
