#!/usr/bin/env python3
"""e002_carm_failures — e002 C 臂未通過 cell 的失敗型態分類量具（round 201，P20261030_0601-3）。

目的：審查指示第四節第 5 條【P2 · 針對 e002 C 臂失敗題型的失敗機制深入分析】。
對 score.json 中 pass==false 的每個 C 臂 cell（遍歷 polyglot_py-*-pi-C-r1），
點名並落盤可重算的事實：
  - timed_out：cell.json 的逾時狀態；
  - stop_checks：觸發收件閘檢查（stop hook / review）的次數；
  - rejections：交件退回次數＝綜合 rounds_*.json 的 n、events.jsonl 的 stop continue / rounds_used、
    以及 chain.ndjson 的 review 紀錄（因 zerostop 在無 finding 放行時會 unlink rounds_*.json，
    僅看 rounds_*.json 會把已落盤 0 次退回誤判為 null）；
  - last_hint：最後退回 hint＝trace/projects/*/delivery.json 的 unverified[0]
    （形如 "Still open after N round(s): ..."）；沒有 unverified 才退而取 findings[0]。
誠實規則（不變量 5）：
  - 無 vacant_home.tgz 或 tgz 內完全無 intake/trace 紀錄
    → rejections=null、stop_checks=null、last_hint=null（UNKNOWN，不編造為 0）；
  - 有 events.jsonl / chain.ndjson / delivery.json 證明退回 0 次 → rejections=0（int）；
  - 分類只依測得事實：timed_out→"timeout"，否則 "not_converged"；
  - 失敗 cell 數是**測得值**，不寫死 12（數據變了報告跟著變）。
本量具**唯讀**：只讀 /srv/vlab/runs/e002_hypothesis_arms/ 下 cell.json、score.json、
vacant_home.tgz；不寫任何檔、不碰 /srv/eval。
用法：python3 ops/vlab/tools/e002_carm_failures.py [--base /srv/vlab/runs] [--selftest]
輸出：JSON 至 stdout。退出碼：0 成功；2 run 目錄不存在。
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
import tempfile
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
    """唯讀掃 vacant_home.tgz：綜合 rounds_*.json、events.jsonl、chain.ndjson 與 delivery.json。"""
    ev: dict = {"rejections": None, "stop_checks": None, "last_hint": None}
    tgz = cell / "vacant_home.tgz"
    if not tgz.is_file():
        return ev
    has_record = False
    max_n = 0
    stop_events = 0
    evt_continues = 0
    chain_reviews = 0
    chain_continues = 0
    try:
        with tarfile.open(tgz, "r:gz") as tf:
            for m in tf.getmembers():
                if not m.isfile():
                    continue
                n = m.name
                if "/intake/hooks/rounds_" in n and n.endswith(".json"):
                    fobj = tf.extractfile(m)
                    if fobj is None:
                        continue
                    r = _json_bytes(fobj.read())
                    if isinstance(r, dict) and isinstance(r.get("n"), int):
                        has_record = True
                        max_n = max(max_n, r["n"])
                elif n.endswith("/intake/hooks/events.jsonl"):
                    fobj = tf.extractfile(m)
                    if fobj is None:
                        continue
                    has_record = True
                    for raw_ln in fobj.read().decode("utf-8", "replace").splitlines():
                        if not raw_ln.strip():
                            continue
                        try:
                            e = json.loads(raw_ln)
                        except ValueError:
                            continue
                        if not isinstance(e, dict):
                            continue
                        if e.get("kind") == "stop":
                            stop_events += 1
                            if e.get("action") == "continue":
                                evt_continues += 1
                            z = e.get("zero")
                            if isinstance(z, dict):
                                for k in ("round", "rounds_used"):
                                    v = z.get(k)
                                    if isinstance(v, int):
                                        max_n = max(max_n, v)
                elif "/trace/projects/" in n and n.endswith("chain.ndjson"):
                    fobj = tf.extractfile(m)
                    if fobj is None:
                        continue
                    has_record = True
                    for raw_ln in fobj.read().decode("utf-8", "replace").splitlines():
                        if not raw_ln.strip():
                            continue
                        try:
                            e = json.loads(raw_ln)
                        except ValueError:
                            continue
                        if not isinstance(e, dict):
                            continue
                        if e.get("type") == "review":
                            chain_reviews += 1
                            p = e.get("payload")
                            if isinstance(p, dict):
                                if p.get("action") == "continue":
                                    chain_continues += 1
                                for k in ("round", "rounds_used"):
                                    v = p.get(k)
                                    if isinstance(v, int):
                                        max_n = max(max_n, v)
                elif "/trace/projects/" in n and n.endswith("delivery.json"):
                    fobj = tf.extractfile(m)
                    if fobj is None:
                        continue
                    d = _json_bytes(fobj.read())
                    if not isinstance(d, dict):
                        continue
                    has_record = True
                    unv = d.get("unverified") or []
                    if unv:
                        ev["last_hint"] = str(unv[0])[:300]
                    elif d.get("findings"):
                        f0 = d["findings"][0]
                        ev["last_hint"] = (f0.get("test_hint") or f0.get("error") or None)
        if has_record:
            ev["stop_checks"] = max(stop_events, chain_reviews)
            ev["rejections"] = max(max_n, evt_continues, chain_continues)
    except (tarfile.TarError, OSError):
        pass  # tgz 讀不了 → 保持 null（UNKNOWN），不編造
    return ev


def _selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        cell_zero = base / "c_zero"
        cell_zero.mkdir()
        vh = base / "vh" / ".vacant"
        (vh / "intake" / "hooks").mkdir(parents=True)
        (vh / "intake" / "hooks" / "events.jsonl").write_text(
            json.dumps({"kind": "stop", "action": "allow", "zero": {"ran": True, "rounds_used": 0}}) + "\n",
            encoding="utf-8",
        )
        with tarfile.open(cell_zero / "vacant_home.tgz", "w:gz") as tf:
            tf.add(vh, arcname=".vacant")
        ev_zero = _vacant_evidence(cell_zero)
        assert ev_zero["rejections"] == 0 and ev_zero["stop_checks"] == 1, ev_zero

        cell_missing = base / "c_missing"
        cell_missing.mkdir()
        ev_missing = _vacant_evidence(cell_missing)
        assert ev_missing["rejections"] is None and ev_missing["stop_checks"] is None, ev_missing
    print("OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="/srv/vlab/runs")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()
    run = Path(args.base) / "e002_hypothesis_arms"
    if not run.is_dir():
        print(f"找不到 run 目錄 {run}", file=sys.stderr)
        return 2
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
            "stop_checks": ev["stop_checks"],
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
        "note": (
            "rejections=null 表示無 vacant_home.tgz 或無 intake/trace 紀錄（UNKNOWN，不是 0）；"
            "若 events.jsonl / chain.ndjson 已記錄 0 次退回（如 zerostop 放行時 unlink 暫存 rounds_*.json），"
            "rejections 為 0。"
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
