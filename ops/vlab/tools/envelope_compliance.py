#!/usr/bin/env python3
"""envelope_compliance — C 格 ~/.vacant 體積 vs 256 MiB 穩態封頂的合規量具（round 169，Axis 2）。

背景：
- ASSIGNMENT 10/28 最優先·條件 1：「~/.vacant 的體積有界……每格 C 組的
  vacant_home_bytes（cell.json）……量它從零開始一天長多少」。
  本量具把「格子層的 vacant_home_bytes 有沒有超 256 MiB 穩態封頂」變成
  每格可重算的證據（round 168 留下的 next；disk_report 量的是分佈，本量具量的是**合規**）。
- 封頂常數：vacant_network.retention.STABLE_ENVELOPE_BYTES（256 MiB）。
  本腳本是**獨立量具**：用 .venv python 跑時直接 import 對照；用裸 python3 跑時
  退回字面量 256 MiB 並在輸出標 `envelope_source=literal_fallback`（誠實，不崩）。
- 同一規矩（對照 noncode_cell_audit.py / disk_report.py / e002_wiring_gauge.py）：
  只讀 runs 下的 cell.json，不碰 cell.py / labd.py / report.py（共用量具零改動）。

誠實規則（對照不變量 5：看不到的東西是 UNKNOWN/無證據，不是 PASS 也不是「沒有」）：
  - 格未完成（無 cell.json）→ NA（不計入任何分組的合規判斷）；arm 由目錄名解析
    （<suite>-<task>-<agent>-<arm>-<rep> 倒數第二 token；解析不出才落 by_arm["?"]）。
  - A／H／M／S 臂＝設計上沒裝 Vacant，超出封頂口徑 → NA（不是 FAIL）。
  - C 格 cell.json 無 vacant_home_bytes（或類型異常）→ NO_EVIDENCE，不判 FAIL
    （分不清「cell.py 沒量到」與「真的沒長」；那是 cell.py 的缺口，另案）。
  - C 格 vacant_home_bytes 是整數：≤ 封頂 → PASS；> 封頂 → FAIL。
  - 分組／整體 verdict：有 FAIL→FAIL；否則有 PASS→PASS；否則有 NO_EVIDENCE→NO_EVIDENCE；
    否則 NA。NA／NO_EVIDENCE 是誠實狀態，**不**影響退出碼。
  - 退出碼：0＝無 FAIL；1＝有 FAIL；2＝selftest 失敗或輸入不可讀。

口徑誠實（輸出裡也會帶）：
  - 256 MiB 是**穩態**封頂（trace 64 MiB＋wire body 96＋wire index 8＋日誌／隔離＋
    固定安裝面 ~10 MiB），不是「單一任務的預算」；單一 C 格 PASS 是必要條件，
    **不是**條件 1 的全部——「一天長多少」的真實成長曲線由 vacant_growth_log.py
    在真機上量（~/dev/ops/data/vacant_growth.jsonl），GC 回收與回收後 UNKNOWN 另證。

用法:
    python3 ops/vlab/tools/envelope_compliance.py <exp> [--base /srv/vlab/runs]
        [--envelope BYTES] [--out PATH]
    python3 ops/vlab/tools/envelope_compliance.py --selftest

輸出 JSON：{exp, base, envelope_bytes, envelope_source, cells:[...], by_arm:{...},
verdict, note}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

LITERAL_ENVELOPE_BYTES = 256 * 1024 * 1024  # 與 retention.STABLE_ENVELOPE_BYTES 同值（fallback）
NOT_IN_SCOPE = ("A", "H", "M", "S")  # 設計上沒裝 Vacant 的臂


def _load_envelope() -> tuple[int, str]:
    try:
        from vacant_network import retention  # type: ignore
        v = int(retention.STABLE_ENVELOPE_BYTES)
        if v > 0:
            return v, "vacant_network.retention.STABLE_ENVELOPE_BYTES"
    except Exception:
        pass
    return LITERAL_ENVELOPE_BYTES, "literal_fallback(256MiB)——本機 .venv 載入 vacant_network 失敗，用字面量"


def _load_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _arm_from_name(name: str) -> str | None:
    """從格子目錄名解析 arm：<suite>-<task>-<agent>-<arm>-<rep>，arm＝倒數第二個 token。
    .infra- 前綴與 .infra-<ts> 尾綴先剝掉；少於 2 個 token → None。
    與 opencode_cell_audit._arm_from_name 同邏輯（本腳本是獨立量具，不跨工具 import）。"""
    if name.startswith(".infra-"):
        name = name[7:]
    parts = name.split(".infra-", 1)[0].split("-")
    return parts[-2] if len(parts) >= 2 else None


def _verdict(states: list[str]) -> str:
    if "FAIL" in states:
        return "FAIL"
    if "PASS" in states:
        return "PASS"
    if "NO_EVIDENCE" in states:
        return "NO_EVIDENCE"
    return "NA"


def _cell_state(cell: Path, envelope: int) -> dict:
    name = cell.name
    if ".infra-" in cell.name:
        return {"cell": name, "skipped": "infra-retry 副檔，不計入"}
    cj = _load_json(cell / "cell.json")
    if cj is None:
        return {"cell": name, "arm": _arm_from_name(name),  # 解析不出維持 None
                "state": "incomplete",
                "compliance": "NA", "vacant_home_bytes": None,
                "note": "格未完成（無 cell.json）"}
    arm = str(cj.get("arm") or "")
    rec = {"cell": name, "arm": arm or None, "state": "complete",
           "agent_rc": cj.get("agent_rc"), "timed_out": cj.get("timed_out"),
           "vacant_home_bytes": None, "compliance": None, "note": None}
    if arm in NOT_IN_SCOPE:
        rec["compliance"] = "NA"
        rec["note"] = "此臂設計上沒裝 Vacant，超出封頂口徑"
    elif arm.startswith("C"):
        v = cj.get("vacant_home_bytes")
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            rec["compliance"] = "NO_EVIDENCE"
            rec["note"] = "cell.json 無整數 vacant_home_bytes（或類型異常）——量不到，不判 FAIL"
        else:
            rec["vacant_home_bytes"] = v
            rec["compliance"] = "PASS" if v <= envelope else "FAIL"
            rec["ratio_of_envelope"] = round(v / envelope, 6)
            if isinstance(cj.get("vacant_objects_bytes"), int):
                rec["vacant_objects_bytes"] = cj["vacant_objects_bytes"]
            if rec["compliance"] == "FAIL":
                rec["note"] = "超過穩態封頂——真實發現，需要查該格的工作區規模與 GC 記錄"
    else:
        rec["compliance"] = "NA"
        rec["note"] = f"未知臂 {arm!r}，超出本量具口徑"
    return rec


def _by_arm(cells: list[dict]) -> dict:
    out: dict = {}
    for arm in sorted({str(c.get("arm") or "?") for c in cells if not c.get("skipped")}):
        cs = [c for c in cells if c.get("arm") == arm or (arm == "?" and not c.get("arm"))]
        cs = [c for c in cs if not c.get("skipped")]
        states = [c.get("compliance") for c in cs if c.get("compliance")]
        vals = [c["vacant_home_bytes"] for c in cs
                if isinstance(c.get("vacant_home_bytes"), int)]
        entry = {
            "n_cells": len(cs),
            "n_complete": sum(1 for c in cs if c.get("state") == "complete"),
            "counts": {s: states.count(s) for s in ("PASS", "FAIL", "NO_EVIDENCE", "NA")},
            "verdict": _verdict(states) if states else "NA",
        }
        if vals:
            vs = sorted(vals)
            entry["home_bytes_min_med_max"] = [vs[0], vs[len(vs) // 2], vs[-1]]
        out[arm] = entry
    return out


def evaluate(base: Path, exp: str, envelope: int, envelope_source: str) -> dict:
    root = base / exp
    if not root.is_dir():
        raise SystemExit(f"輸入不可讀：{root} 不存在（rc=2；先確認實驗名與 --base）")
    cells = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        cells.append(_cell_state(d, envelope))
    kept = [c for c in cells if not c.get("skipped")]
    states = [c.get("compliance") for c in kept if c.get("compliance")]
    return {
        "exp": exp,
        "base": str(base),
        "envelope_bytes": envelope,
        "envelope_source": envelope_source,
        "n_cells": len(kept),
        "cells": cells,
        "by_arm": _by_arm(cells),
        "verdict": _verdict(states) if states else "NA",
        "note": ("256 MiB 是穩態封頂（trace 64＋wire body 96＋wire index 8＋日誌/隔離＋"
                 "固定安裝面 ~10 MiB），不是單一任務預算；單格 PASS 是 ASSIGNMENT 條件 1 的"
                 "必要條件，不是全部——『一天長多少』看 vacant_growth_log.py 的真機序列，"
                 "GC 回收與回收後 UNKNOWN 另證。NA/NO_EVIDENCE 是誠實狀態，不代表合規。"),
    }


def _render(out: dict) -> str:
    return json.dumps(out, ensure_ascii=False, indent=2)


def selftest() -> int:
    checks: list[tuple[str, bool]] = []

    def check(name: str, cond: bool) -> None:
        checks.append((name, cond))

    env_default, _ = _load_envelope()
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        root = base / "exp_st"
        def mk(name: str, cj: dict | None) -> None:
            d = root / name
            d.mkdir(parents=True)
            if cj is not None:
                (d / "cell.json").write_text(json.dumps(cj), encoding="utf-8")
        root.mkdir(parents=True)
        mk("c_pass", {"arm": "C", "vacant_home_bytes": 10 * 1024 * 1024})
        mk("c_fail", {"arm": "C", "vacant_home_bytes": env_default + 1})
        mk("c_noev", {"arm": "C"})
        mk("c_badtype", {"arm": "C", "vacant_home_bytes": "x"})
        mk("a_na", {"arm": "A"})
        mk("h_na", {"arm": "H", "append_system": {"sha256": "a" * 64}})
        mk("s_na", {"arm": "S"})
        mk("incomplete", None)
        mk("polyglot_py-pg_task-opencode-M-r1", None)
        (root / ".infra-c_x").mkdir()
        (root / ".infra-c_x" / "cell.json").write_text(json.dumps(
            {"arm": "C", "vacant_home_bytes": env_default + 999}), encoding="utf-8")
        (root / "c_pass.infra-20261028T192916").mkdir()
        (root / "c_pass.infra-20261028T192916" / "cell.json").write_text(json.dumps(
            {"arm": "C", "vacant_home_bytes": env_default + 999}), encoding="utf-8")

        out = evaluate(base, "exp_st", env_default, "selftest")
        by = {c["cell"]: c for c in out["cells"]}
        check("infra 副檔被跳過（留痕、不計入）",
              bool(by[".infra-c_x"]["skipped"])
              and bool(by["c_pass.infra-20261028T192916"]["skipped"])
              and out["n_cells"] == 9
              and by["c_pass"]["compliance"] == "PASS")
        check("PASS 判定", by["c_pass"]["compliance"] == "PASS")
        check("FAIL 判定（超封頂）", by["c_fail"]["compliance"] == "FAIL")
        check("NO_EVIDENCE（無數字）", by["c_noev"]["compliance"] == "NO_EVIDENCE")
        check("NO_EVIDENCE（類型異常）", by["c_badtype"]["compliance"] == "NO_EVIDENCE")
        check("A 臂 NA", by["a_na"]["compliance"] == "NA")
        check("H 臂 NA", by["h_na"]["compliance"] == "NA")
        check("S 臂 NA", by["s_na"]["compliance"] == "NA")
        check("未完成 NA", by["incomplete"]["compliance"] == "NA")
        m_cell = "polyglot_py-pg_task-opencode-M-r1"
        check("未完成格從目錄名解析 arm=M 且不落 by_arm['?']",
              by[m_cell]["arm"] == "M"
              and by[m_cell]["compliance"] == "NA"
              and out["by_arm"]["M"]["n_cells"] == 1
              and out["by_arm"]["?"]["n_cells"] == 1)  # '?' 只剩舊 'incomplete' 格
        check("整體 verdict=FAIL（有 c_fail）", out["verdict"] == "FAIL")
        check("C 分組 verdict=FAIL", out["by_arm"]["C"]["verdict"] == "FAIL")
        check("A 分組 verdict=NA", out["by_arm"]["A"]["verdict"] == "NA")

        # 無 FAIL 的組合 → PASS（刪掉 c_fail 的 cell.json → 該格變成 incomplete/NA）
        (root / "c_fail" / "cell.json").unlink()
        out2 = evaluate(base, "exp_st", env_default, "selftest")
        check("移除 FAIL 格後 verdict=PASS", out2["verdict"] == "PASS")

        # 封頂覆寫：10MiB 格在 5MiB 封頂下應 FAIL
        out3 = evaluate(base, "exp_st", 5 * 1024 * 1024, "selftest-override")
        by3 = {c["cell"]: c for c in out3["cells"]}
        check("封頂覆寫生效", by3["c_pass"]["compliance"] == "FAIL")
        check("envelope_bytes 反映覆寫", out3["envelope_bytes"] == 5 * 1024 * 1024)

    bad = [name for name, ok in checks if not ok]
    if bad:
        print(f"SELFTEST FAIL：{len(bad)}/{len(checks)} 項沒過：{bad}", file=sys.stderr)
        return 2
    print(f"SELFTEST OK：{len(checks)}/{len(checks)} 項全過")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="C 格 vacant_home_bytes vs 256MiB 穩態封頂的合規量具（Axis 2）")
    ap.add_argument("exp", nargs="?", help="實驗名（runs/ 下的目錄名）")
    ap.add_argument("--base", type=Path,
                    default=Path(os.environ.get("VLAB_RUNS", "/srv/vlab/runs")),
                    help="runs 根目錄（預設 /srv/vlab/runs）")
    ap.add_argument("--envelope", type=int, default=None,
                    help="覆寫封頂字節數（預設 256 MiB／retention 常數）")
    ap.add_argument("--out", type=Path, default=None, help="另存 JSON 到檔案")
    ap.add_argument("--selftest", action="store_true", help="跑內建自測後離開")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if not a.exp:
        ap.error("需要 <exp>（或用 --selftest）")

    envelope = a.envelope
    if envelope is None:
        envelope, source = _load_envelope()
    else:
        source = f"command-line --envelope {envelope}"
    try:
        out = evaluate(a.base, a.exp, envelope, source)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2

    text = _render(out)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if out["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
