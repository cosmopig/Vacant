#!/usr/bin/env python3
"""e002_pair_breakdown — e002_hypothesis_arms A/C 臂題目級機制差異唯讀量具（P20261030_1851-1）。

對應審查 20261030_1759 第四節指示 4 與 ASSIGNMENT 主軸 3。對 run 目錄
（預設 /srv/vlab/runs/e002_hypothesis_arms）各格 cell.json＋score.json：
  - A/C 配對分類：both / C_only / A_only / neither；任一侧缺格或 pass 未測 → incomplete；
分工：p02_carm_audit.py 驗「逐題紀錄是否存在」（線路/證據完整度），本量具驗
「題目級機制介入差異」（A/C 配對＋C 臂閘門介入分佈）；review 證據源相同
（vacant_home.tgz 內 chain.ndjson），refuse 詞彙與其對齊。
  - C 臂 review 歷史（自 vacant_home.tgz 內 chain.ndjson 的 review 條目，
    payload.action ∈ {"continue","refuse"} 記為 refuse；無 review 條目＝NO_EVIDENCE/UNKNOWN）：
      gate_salvaged    有 refuse 且最終 pass；
      first_pass       無 refuse 且 pass；
      refused_not_saved 有 refuse 但未過；never_refused 無 refuse 未過；
      unknown          無 tgz 或 tgz 內無 chain.ndjson（UNKNOWN，不編造為 0）；
  - 各臂 A/C/H/M/S 的 timed_out 題目清單；H/M 逾時分佈（wall_s/timeout_s）。
本量具**唯讀**：只讀 run 目錄下 cell.json、score.json、vacant_home.tgz；不寫檔、不碰 /srv/eval。
用法：python3 ops/vlab/tools/e002_pair_breakdown.py [exp] [--base DIR] [--json] [--out PATH] [--selftest]
退出碼：0 成功；2 run 目錄不存在。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path

ARMS = ("A", "C", "H", "M", "S")


def _load_json(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
    except (OSError, ValueError):
        return None
    return v if isinstance(v, dict) else None


def _cell_parts(name: str) -> tuple[str, str] | None:
    """<suite>-<task>-pi-<ARM>-r1 → (arm, task)；與 holm_e002 同解法。"""
    parts = name.split("-")
    if len(parts) < 5:
        return None
    arm, rep = parts[-2], parts[-1]
    if not (len(arm) == 1 and arm.isalpha()) or not rep.startswith("r"):
        return None
    return arm, "-".join(parts[1:-3])


def _c_refuses(cell: Path) -> int | None:
    """唯讀 vacant_home.tgz：chain.ndjson 中 review(action∈continue/refuse) 次數；None=UNKNOWN。

    詞彙對齊 p02_carm_audit.criteria（review_allow/review_continue/review_refuse 三分）：
    擋回＝continue 或 refuse。"""
    tgz = cell / "vacant_home.tgz"
    if not tgz.is_file():
        return None
    refuses, found = 0, False
    try:
        with tarfile.open(tgz, "r:gz") as tf:
            for m in tf.getmembers():
                if not (m.isfile() and m.name.endswith("chain.ndjson")):
                    continue
                fobj = tf.extractfile(m)
                if fobj is None:
                    continue
                found = True
                for ln in io.TextIOWrapper(fobj, encoding="utf-8", errors="replace"):
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        e = json.loads(ln)
                    except ValueError:
                        continue
                    if isinstance(e, dict) and e.get("type") == "review":
                        p = e.get("payload")
                        if isinstance(p, dict) and p.get("action") in ("continue", "refuse"):
                            refuses += 1
    except (tarfile.TarError, OSError):
        return None  # 讀不了 → UNKNOWN，不編造
    return refuses if found else None


def analyze_e002(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    arms: dict[str, dict[str, dict]] = {a: {} for a in ARMS}
    for d in sorted(run_dir.iterdir()) if run_dir.is_dir() else []:
        if not d.is_dir() or ".infra-" in d.name:
            continue
        cp = _cell_parts(d.name)
        if cp is None:
            continue
        arm, task = cp
        cj = _load_json(d / "cell.json") or {}
        sc = _load_json(d / "score.json") or {}
        p = sc.get("pass")
        rec = {
            "pass": p if isinstance(p, bool) else None,
            "timed_out": cj.get("timed_out") if isinstance(cj.get("timed_out"), bool) else None,
            "wall_s": cj.get("wall_s"),
            "timeout_s": cj.get("timeout_s"),
        }
        if arm == "C":
            refuses = _c_refuses(d)
            rec["refuses"] = refuses
            rec["c_review"] = None
            if refuses is not None and rec["pass"] is not None:
                if rec["pass"]:
                    rec["c_review"] = "gate_salvaged" if refuses else "first_pass"
                else:
                    rec["c_review"] = "refused_not_saved" if refuses else "never_refused"
        arms[arm][task] = rec
    a, c = arms["A"], arms["C"]
    pair = {"both": [], "C_only": [], "A_only": [], "neither": [], "incomplete": []}
    for t in sorted(set(a) | set(c)):
        ra, rc = a.get(t), c.get(t)
        if ra is None or rc is None or ra["pass"] is None or rc["pass"] is None:
            pair["incomplete"].append(t)
        elif ra["pass"] and rc["pass"]:
            pair["both"].append(t)
        elif rc["pass"] and not ra["pass"]:
            pair["C_only"].append(t)
        elif ra["pass"] and not rc["pass"]:
            pair["A_only"].append(t)
        else:
            pair["neither"].append(t)
    c_rev = {k: [] for k in ("gate_salvaged", "first_pass", "refused_not_saved", "never_refused", "unknown")}
    for t, rec in sorted(c.items()):
        c_rev[rec["c_review"] or "unknown"].append(t)
    timed = {arm: sorted(t for t, r in arms[arm].items() if r["timed_out"] is True) for arm in ARMS}
    hm = [{"arm": arm, "task": t, "wall_s": r["wall_s"], "timeout_s": r["timeout_s"]}
          for arm in ("H", "M") for t, r in sorted(arms[arm].items()) if r["timed_out"] is True]
    return {
        "tool": "e002_pair_breakdown",
        "run": str(run_dir),
        "n_cells": sum(len(v) for v in arms.values()),
        "n_tasks_AC": len(set(a) | set(c)),
        "n_cells_per_arm": {k: len(v) for k, v in arms.items()},
        "pairs_AC": pair,
        "c_review": c_rev,
        "timed_out": {**timed, "hm_distribution": hm},
        "note": ("refuses=chain.ndjson 中 review(action∈continue/refuse) 次數（詞彙對齊 p02_carm_audit）；"
                 "c_review unknown＝無 vacant_home.tgz 或無 chain.ndjson（UNKNOWN，非 0）；"
                 "incomplete＝A/C 任一侧缺格或 pass 未測；"
                 "hm_distribution＝H/M timed_out 格的 wall_s/timeout_s"),
    }


def _mk_cell(base: Path, name: str, *, p: bool, timed_out: bool = False,
             wall_s: float = 10.0, timeout_s: int = 60) -> Path:
    d = base / name
    d.mkdir(parents=True)
    (d / "cell.json").write_text(json.dumps({"task": name.split("-")[1], "timed_out": timed_out,
                                             "wall_s": wall_s, "timeout_s": timeout_s}), encoding="utf-8")
    (d / "score.json").write_text(json.dumps({"pass": p}), encoding="utf-8")
    return d


def _mk_chain_tgz(cell: Path, reviews: list[dict]) -> None:
    tmp = Path(tempfile.mkdtemp())
    pj = tmp / ".vacant" / "trace" / "projects" / "x"
    pj.mkdir(parents=True)
    (pj / "chain.ndjson").write_text("".join(json.dumps(e) + "\n" for e in reviews), encoding="utf-8")
    with tarfile.open(cell / "vacant_home.tgz", "w:gz") as tf:
        tf.add(tmp, arcname=".")


def selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "e002_hypothesis_arms"
        base.mkdir()
        _mk_cell(base, "mock-t1-pi-A-r1", p=True)
        _mk_chain_tgz(_mk_cell(base, "mock-t1-pi-C-r1", p=True),
                      [{"type": "review", "payload": {"action": "continue"}},
                       {"type": "review", "payload": {"action": "allow"}}])
        _mk_cell(base, "mock-t2-pi-A-r1", p=False)
        _mk_chain_tgz(_mk_cell(base, "mock-t2-pi-C-r1", p=True),
                      [{"type": "review", "payload": {"action": "allow"}}])
        _mk_cell(base, "mock-t3-pi-A-r1", p=True)
        _mk_chain_tgz(_mk_cell(base, "mock-t3-pi-C-r1", p=False),
                      [{"type": "review", "payload": {"action": "continue"}}])
        _mk_cell(base, "mock-t4-pi-A-r1", p=False)
        _mk_cell(base, "mock-t4-pi-C-r1", p=False)
        _mk_cell(base, "mock-t5-pi-H-r1", p=False, timed_out=True, wall_s=1800.0, timeout_s=1800)
        _mk_cell(base, "mock-t5-pi-M-r1", p=False, timed_out=True, wall_s=1795.0, timeout_s=1800)
        # t6：僅 C 格（A 缺 → incomplete）且 review action=="refuse" 亦計 refuse（詞彙對齊 p02_carm_audit）
        _mk_chain_tgz(_mk_cell(base, "mock-t6-pi-C-r1", p=True),
                      [{"type": "review", "payload": {"action": "refuse"}},
                       {"type": "review", "payload": {"action": "allow"}}])
        r = analyze_e002(base)
        assert r["pairs_AC"]["both"] == ["t1"] and r["pairs_AC"]["C_only"] == ["t2"], r["pairs_AC"]
        assert r["pairs_AC"]["A_only"] == ["t3"] and r["pairs_AC"]["neither"] == ["t4"], r["pairs_AC"]
        assert r["pairs_AC"]["incomplete"] == ["t6"], r["pairs_AC"]
        assert r["c_review"]["gate_salvaged"] == ["t1", "t6"] and r["c_review"]["first_pass"] == ["t2"], r["c_review"]
        assert r["c_review"]["refused_not_saved"] == ["t3"], r["c_review"]
        assert r["c_review"]["unknown"] == ["t4"] and r["c_review"]["never_refused"] == [], r["c_review"]
        assert r["timed_out"]["H"] == ["t5"] and r["timed_out"]["M"] == ["t5"], r["timed_out"]
        assert r["timed_out"]["A"] == [] and r["timed_out"]["C"] == [] and r["timed_out"]["S"] == []
        hm = r["timed_out"]["hm_distribution"]
        assert [h["wall_s"] for h in hm] == [1800.0, 1795.0] and all(h["timeout_s"] == 1800 for h in hm), hm
        assert r["n_cells"] == 11 and r["n_cells_per_arm"] == {"A": 4, "C": 5, "H": 1, "M": 1, "S": 0}, r
    print("OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="e002 A/C 配對與 C 臂閘門介入分佈（唯讀量具）")
    ap.add_argument("exp", nargs="?", default="e002_hypothesis_arms")
    ap.add_argument("--base", default="/srv/vlab/runs")
    ap.add_argument("--json", action="store_true", help="stdout 輸出完整 JSON")
    ap.add_argument("--out", default=None, help="JSON 寫入指定路徑")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    run_dir = Path(args.base) / args.exp
    if not run_dir.is_dir():
        print(f"找不到 run 目錄 {run_dir}", file=sys.stderr)
        return 2
    report = analyze_e002(run_dir)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(payload + "\n", encoding="utf-8")
        print(f"已寫入 {p}（n_cells={report['n_cells']}）", file=sys.stderr)
        return 0
    if args.json:
        print(payload)
        return 0
    for k in ("both", "C_only", "A_only", "neither", "incomplete"):
        v = report["pairs_AC"][k]
        print(f"pair {k}: {len(v)} {' '.join(v)}".rstrip())
    for k in ("gate_salvaged", "first_pass", "refused_not_saved", "never_refused", "unknown"):
        v = report["c_review"][k]
        print(f"c_review {k}: {len(v)} {' '.join(v)}".rstrip())
    for arm in ARMS:
        v = report["timed_out"][arm]
        print(f"timed_out {arm}: {len(v)} {' '.join(v)}".rstrip())
    print(f"hm_distribution: {len(report['timed_out']['hm_distribution'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
