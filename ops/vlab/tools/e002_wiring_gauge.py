#!/usr/bin/env python3
"""e002_wiring_gauge — e002 實驗臂線路驗收量具（round 165，依資深審查 20261029 指示 #2 的驗收判準）。

背景：
- 審查指示 #2 的驗收判準：(b) H/M/S 的 cell.json 皆有非空的 append_system sha256；
  (c) C 臂 pg_affine_cipher／pg_beer_song 確實透過 *_test.py 執行 unittest 驗收門。
  (a) rescore_mismatches==0 是 report.py 的活（跑完後 --rescore），本量具不代做。
- 歷史教訓：第一次冒煙 e002_smoke（8 格）的 H/M/S 格 append_system 全為 None——
  佇列檔缺 env，附加系統提示根本没送進 agent。本量具把「線路有沒有通」變成
  每格可重算的證據，跑批中／跑完都能量。
- 本腳本是**獨立量具**：只讀 /srv/vlab/runs 下的 cell.json、score.json、
  以及 vacant_home.tgz 的存在性；不碰 cell.py / labd.py / report.py
  （與 noncode_cell_audit.py、disk_report.py 同一規矩）。

誠實規則（對照不變量 5：看不到的東西是 UNKNOWN/無證據，不是 PASS 也不是「沒有」）：
  - 格未完成（無 cell.json）→ 該格所有判準 = NO_EVIDENCE，不計入 PASS/FAIL。
  - cell.json 存在但 H/M/S 格無 append_system → FAIL（線路斷，e002_smoke 第一次就是這樣）。
  - cell.json 存在但 append_system.sha256 非 64 位 hex → FAIL。
  - C 格有 score.json 但 tests_total==0 → FAIL（零測試不是過門，I-4 同形）。
  - C 格無 score.json → NO_EVIDENCE（未完成），不判 FAIL。
  - unittest_marker：只在 score.json.detail 裡搜到 unittest 形狀（test_xxx 名稱或
    *_test.py 路徑）才為 true；搜不到是「沒有 unittest 形狀的證據」，不是「跑了別的東西」。

用法：
  python3 ops/vlab/tools/e002_wiring_gauge.py <exp> [--base /srv/vlab/runs] [--out PATH]
  python3 ops/vlab/tools/e002_wiring_gauge.py --selftest

輸出 JSON：{exp, base, n_cells, cells:[...], criteria:{...}, summary:{...}}
退出碼：0 無 FAIL；1 有 FAIL（線路斷／零測試）；2 selftest 失敗或輸入不可讀。
  infra（agent_rc／timeout）是**測得的結果**（e001 就有 7 格 A 臂 timeout，仍是證據），
  只報在 criteria.infra，**不**影響退出碼——量具驗的是線路，不是模型的快慢。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")
UNITTEST_MARK = re.compile(r"(\btest_[a-z0-9_]+\s*\(|[A-Za-z0-9_]+_test\.py)")


def _load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def cell_record(cell: Path) -> dict:
    """讀一格，回誠實記錄。cell 不存在/無 cell.json → state=incomplete。"""
    cj = _load_json(cell / "cell.json")
    if cj is None:
        # 格未完成＝各判準不適用（NA）；「無證據」保留給格完成但證據檔缺的形狀。
        return {"cell": cell.name, "state": "incomplete",
                "baseline_purity": "NA", "arm_wiring": "NA",
                "c_gate": "NA", "unittest_marker": None,
                "c_installed": None, "infra": None}
    rec = {"cell": cell.name, "state": "complete", "arm": cj.get("arm"),
           "agent_rc": cj.get("agent_rc"), "timed_out": cj.get("timed_out")}
    rec["infra"] = "OK" if (cj.get("agent_rc") == 0 and not cj.get("timed_out")) else "BAD"

    arm = str(cj.get("arm") or "")
    append = cj.get("append_system")

    # A 臂＝沒裝、無附加文本：append_system 必須是 None（不變量 1 的格子層證據）
    if arm == "A":
        rec["baseline_purity"] = "PASS" if append is None else "FAIL"
        rec["arm_wiring"] = "NA"
    elif arm in ("H", "M", "S"):
        ok = (isinstance(append, dict) and isinstance(append.get("sha256"), str)
              and HEX64.match(append["sha256"]) is not None)
        rec["arm_wiring"] = "PASS" if ok else "FAIL"
        rec["baseline_purity"] = "NA"
        if ok:
            rec["append_sha256"] = append["sha256"]
            rec["append_path"] = append.get("path")
    else:
        rec["baseline_purity"] = "NA"
        rec["arm_wiring"] = "NA"

    # C 臂＝裝 Vacant 走驗收門
    if arm.startswith("C"):
        rec["c_installed"] = (cell / "vacant_home.tgz").is_file()
        sc = _load_json(cell / "score.json")
        if sc is None:
            rec["c_gate"] = "NO_EVIDENCE"
            rec["unittest_marker"] = None
        else:
            tt = sc.get("tests_total")
            rec["c_gate"] = "PASS" if (isinstance(tt, int) and tt >= 1) else "FAIL"
            rec["tests_total"] = tt
            detail = sc.get("detail")
            rec["unittest_marker"] = bool(detail and UNITTEST_MARK.search(str(detail)))
    else:
        rec["c_gate"] = "NA"
        rec["unittest_marker"] = None
        rec["c_installed"] = None
    return rec


def collect(exp: str, base: Path) -> list[dict]:
    run = base / exp
    if not run.is_dir():
        raise SystemExit(f"找不到執行目錄 {run}")
    cells = sorted(p for p in run.iterdir() if p.is_dir())
    return [cell_record(c) for c in cells]


def criteria(records: list[dict]) -> dict:
    def bucket(key: str) -> dict:
        b = {"PASS": 0, "FAIL": 0, "NO_EVIDENCE": 0, "NA": 0}
        for r in records:
            v = r.get(key)
            if v in b:
                b[v] += 1
        return b
    out = {"baseline_purity_A": bucket("baseline_purity"),
           "arm_wiring_HMS": bucket("arm_wiring"),
           "c_gate_C": bucket("c_gate"),
           "infra": {"OK": sum(1 for r in records if r.get("infra") == "OK"),
                     "BAD": sum(1 for r in records if r.get("infra") == "BAD"),
                     "NO_EVIDENCE": sum(1 for r in records if r.get("infra") is None)}}
    out["c_unittest_marker_true"] = sum(1 for r in records if r.get("unittest_marker") is True)
    out["c_unittest_marker_false"] = sum(1 for r in records if r.get("unittest_marker") is False)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exp", nargs="?", help="實驗名（/srv/vlab/runs 下的目錄名）")
    ap.add_argument("--base", default="/srv/vlab/runs")
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if not a.exp:
        ap.error("exp 或 --selftest 必給其一")

    records = collect(a.exp, Path(a.base))
    if not records:
        print(json.dumps({"error": "no cells"}, ensure_ascii=False), file=sys.stderr)
        return 1
    crit = criteria(records)
    doc = {"exp": a.exp, "base": str(a.base), "n_cells": len(records),
           "cells": records, "criteria": crit}
    text = json.dumps(doc, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    # 只算線路／驗收門 FAIL；infra BAD（timeout 等）是測得結果，不影響退出碼。
    fails = (crit["baseline_purity_A"]["FAIL"] + crit["arm_wiring_HMS"]["FAIL"]
             + crit["c_gate_C"]["FAIL"])
    return 1 if fails else 0


def selftest() -> int:
    import tempfile
    from pathlib import Path as P

    base = P(tempfile.mkdtemp(prefix="e002gauge_"))
    exp = base / "synthetic"
    exp.mkdir()

    def mk(name: str, arm: str, append=None, score=None, home: bool = False) -> None:
        d = exp / f"polyglot_py-task1-pi-{arm}-r1-{name}"
        d.mkdir(parents=True)
        cell = {"arm": arm, "agent_rc": 0, "timed_out": False, "append_system": append}
        (d / "cell.json").write_text(json.dumps(cell), encoding="utf-8")
        if score is not None:
            (d / "score.json").write_text(json.dumps(score), encoding="utf-8")
        if home:
            (d / "vacant_home.tgz").write_bytes(b"1f8b")

    SHA = {"path": "/srv/vlab/arms/e002_H.md", "sha256": "ab" * 32}
    mk("hgood", "H", append=SHA)
    mk("hbad", "H", append=None)                      # 線路斷（第一次 e002_smoke 的形狀）
    mk("hshort", "H", append={"path": "x", "sha256": "ab"})  # 短 hash
    mk("aclean", "A", append=None)
    mk("adirty", "A", append=SHA)                     # A 臂混入附加文本
    mk("cgood", "C", score={"pass": False, "tests_total": 31,
                            "detail": "test_strike (bowling_test.BowlingTest)"},
       home=True)
    mk("czero", "C", score={"pass": True, "tests_total": 0})  # 零測試不是過門
    mk("cnone", "C", score=None, home=True)             # 未完成形狀
    d = exp / "polyglot_py-task1-pi-H-r1-incomplete"
    d.mkdir()                                          # 無 cell.json

    records = collect("synthetic", base)
    by = {r["cell"]: r for r in records}
    checks = [
        ("hgood wiring PASS", by["polyglot_py-task1-pi-H-r1-hgood"]["arm_wiring"] == "PASS"),
        ("hbad wiring FAIL", by["polyglot_py-task1-pi-H-r1-hbad"]["arm_wiring"] == "FAIL"),
        ("hshort wiring FAIL", by["polyglot_py-task1-pi-H-r1-hshort"]["arm_wiring"] == "FAIL"),
        ("aclean baseline PASS", by["polyglot_py-task1-pi-A-r1-aclean"]["baseline_purity"] == "PASS"),
        ("adirty baseline FAIL", by["polyglot_py-task1-pi-A-r1-adirty"]["baseline_purity"] == "FAIL"),
        ("cgood gate PASS", by["polyglot_py-task1-pi-C-r1-cgood"]["c_gate"] == "PASS"),
        ("cgood unittest marker", by["polyglot_py-task1-pi-C-r1-cgood"]["unittest_marker"] is True),
        ("cgood installed", by["polyglot_py-task1-pi-C-r1-cgood"]["c_installed"] is True),
        ("czero gate FAIL", by["polyglot_py-task1-pi-C-r1-czero"]["c_gate"] == "FAIL"),
        ("cnone gate NO_EVIDENCE", by["polyglot_py-task1-pi-C-r1-cnone"]["c_gate"] == "NO_EVIDENCE"),
        ("incomplete all NA",
         by["polyglot_py-task1-pi-H-r1-incomplete"]["arm_wiring"] == "NA"
         and by["polyglot_py-task1-pi-H-r1-incomplete"]["c_gate"] == "NA"
         and by["polyglot_py-task1-pi-H-r1-incomplete"]["state"] == "incomplete"),
    ]
    ok = True
    for name, cond in checks:
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and cond
    crit = criteria(records)
    for name, cond in [
        ("crit wiring PASS==1 FAIL==2 NA==6",
         crit["arm_wiring_HMS"]["FAIL"] == 2 and crit["arm_wiring_HMS"]["PASS"] == 1
         and crit["arm_wiring_HMS"]["NA"] == 6),
        ("crit gate PASS==1 FAIL==1 NO_EVIDENCE==1 NA==6",
         crit["c_gate_C"]["FAIL"] == 1 and crit["c_gate_C"]["PASS"] == 1
         and crit["c_gate_C"]["NO_EVIDENCE"] == 1 and crit["c_gate_C"]["NA"] == 6),
        ("crit baseline PASS==1 FAIL==1 NA==7",
         crit["baseline_purity_A"]["FAIL"] == 1 and crit["baseline_purity_A"]["PASS"] == 1
         and crit["baseline_purity_A"]["NA"] == 7),
        ("crit infra OK==8 NO_EVIDENCE==1",
         crit["infra"]["OK"] == 8 and crit["infra"]["NO_EVIDENCE"] == 1),
    ]:
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and cond
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
