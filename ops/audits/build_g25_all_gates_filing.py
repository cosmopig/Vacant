#!/usr/bin/env python3
"""G2.5 全三項門禁整合備案（資深審查 2026-11-08 指示 #1）。

所有數值從 run_eval.py --all 的 raw 產物（out/all/phase{1,2,3}.json）載入，非手抄；
三門門檻與 run_eval.py 單一事實來源一致；任一门禁未過或 raw 缺值 → fail-closed（exit 2），
不寫「達標」備案。成本缺值保持 null（UNKNOWN），不填 0。

用法：
    python3 ops/audits/build_g25_all_gates_filing.py          # 重建備案＋印摘要
輸出：
    ops/audits/g25_all_gates_filing.json
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path("/home/user1/dev/Vacant")
RAW = REPO / "ops/reqloop/extract/out/all"
OUT = REPO / "ops/audits/g25_all_gates_filing.json"

# 與 run_eval.py 一致的門檻（RLOOP_PLAN G2.5 第 1/2 項；PHASE3 無門檻、errors==0 即達標）
GATE_CATCH_RATE = 0.70   # run_eval.py:52
MIN_CATCH_BAD = 5        # run_eval.py:539
MAX_FALSE_GOOD = 1       # run_eval.py:540

# 門禁結果所依賴的程式碼（r1228 redo：extract.py 在任務中被點名、原記錄未開啟→現補開＋接地）。
# 角色描述已逐節核對（extract.py 頭部/quote_is_verbatim:132/build_requirement_set:665/
# GlmClient:927/extract_requirements:1185；run_eval.py:40 即從 extract 匯入這些函式）。
CODE_FILES: dict[str, str] = {
    "vacant_network/reqloop/extract.py": (
        "驗證/組裝層：quote 非原文逐字→丟棄該條；verifier 不在白名單／必要參數不合→"
        "unverified（檢查時 UNKNOWN、不當通過）；client/解析例外→空 RequirementSet"
        "（fail-closed、絕不當「沒有需求＝通過」）；GlmClient 只走 `glm` 指令＝擷取模型唯一"
        "入口（rc≠0 丟 ExtractError、不重試）；run_eval.py:40 自本檔匯入"
        " build_requirement_set/extract_requirements/parse_model_output 等"),
    "vacant_network/reqloop/checks.py": (
        "SUPPORTED_VERIFIERS 單一事實來源（extract.py:47 自本檔匯入）＋run_requirement_checks"
        "（PASS/FAIL/FAIL/UNKNOWN 判定）"),
    "ops/reqloop/extract/run_eval.py": (
        "三門門檻：G1 抓錯≥70% 且 0 冤枉；REAL14 抓錯≥5/9 且冤枉≤1/5；PHASE3 errors==0"),
}

TICKET = "vq-el4.14"
ROUND = 1228
REVIEWER = "資深審查 2026-11-08 指示 #1：確認 G2.5 全三項門禁整合達標並備案"


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(name: str, raw_dir: pathlib.Path) -> dict:
    p = raw_dir / name
    if not p.is_file():
        print(f"❌ fail-closed：raw 缺 {p}", file=sys.stderr)
        sys.exit(2)
    return json.loads(p.read_text(encoding="utf-8"))


def git_head() -> tuple[str, str]:
    def run(*a: str) -> str:
        return subprocess.run(a, cwd=REPO, capture_output=True, text=True).stdout.strip()
    return run("git", "rev-parse", "HEAD"), run("git", "branch", "--show-current")


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", default=None, help="raw phase JSON 目錄（預設 out/all；供 fail-closed 測試）")
    ap.add_argument("--out", default=None, help="備案輸出路徑（預設 ops/audits/g25_all_gates_filing.json）")
    a = ap.parse_args(argv)
    raw_dir = pathlib.Path(a.raw).expanduser() if a.raw else RAW
    out = pathlib.Path(a.out).expanduser() if a.out else OUT

    p1 = load("phase1.json", raw_dir)
    p2 = load("phase2.json", raw_dir)
    p3 = load("phase3.json", raw_dir)

    problems: list[str] = []

    # ① G1 重跑：gate=PASS 且 cross-check（抓錯率≥70%、0 冤枉）
    g1_gate = p1.get("gate")
    g1_catch = p1.get("catch_rate")
    g1_fp = p1.get("ext_fp")
    g1_cross = (
        g1_catch is not None and g1_catch >= GATE_CATCH_RATE
        and g1_fp == 0 and p1.get("total_bad", 0) > 0
    )
    if g1_gate != "PASS" or not g1_cross:
        problems.append(f"G1 gate={g1_gate} catch={g1_catch} fp={g1_fp}（門檻 ≥{GATE_CATCH_RATE}、fp 0）")

    # ② REAL14：gate=PASS 且 cross-check（抓錯≥5/9、冤枉≤1/5）
    g2_gate = p2.get("gate")
    g2_caught = p2.get("caught")
    g2_fa = p2.get("false_acc")
    g2_cross = (
        g2_caught is not None and g2_caught >= MIN_CATCH_BAD
        and g2_fa is not None and g2_fa <= MAX_FALSE_GOOD
        and p2.get("total_bad", 0) > 0 and p2.get("total_good", 0) > 0
    )
    if g2_gate != "PASS" or not g2_cross:
        problems.append(f"REAL14 gate={g2_gate} caught={g2_caught} false_acc={g2_fa}"
                        f"（門檻 ≥{MIN_CATCH_BAD}、≤{MAX_FALSE_GOOD}）")

    # ③ PHASE3：rc = errors==0（fixed/unresolved 為觀測數、非門檻）
    p3_errors = p3.get("errors")
    p3_stale = p3.get("stale_cells") or []
    if p3_errors != 0 or p3_stale or p3.get("cells", 0) < 1:
        problems.append(f"PHASE3 errors={p3_errors} stale={p3_stale}（須 errors==0、無 stale）")

    if problems:
        print("❌ 備案 fail-closed（門禁未達標，不寫達備案）：", file=sys.stderr)
        for pr in problems:
            print(f"   - {pr}", file=sys.stderr)
        return 2

    head, branch = git_head()
    filing = {
        "schema": "vacant.filing/g25_all_gates/1",
        "ticket": TICKET,
        "round": ROUND,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "purpose": REVIEWER,
        "git": {"head": head, "branch": branch},
        "gates": {
            "g1_rerun": {
                "gate": "PASS",
                "metrics": {"caught": p1.get("ext_caught"), "total_bad": p1.get("total_bad"),
                            "catch_rate": g1_catch, "false_acc": g1_fp},
                "threshold": {"catch_rate": f">={GATE_CATCH_RATE}", "false_acc": "== 0"},
                "cost": p1.get("cost"),
            },
            "real14": {
                "gate": "PASS",
                "metrics": {"caught": g2_caught, "total_bad": p2.get("total_bad"),
                            "false_acc": g2_fa, "total_good": p2.get("total_good"),
                            "errors": p2.get("errors")},
                "threshold": {"caught": f">={MIN_CATCH_BAD}", "false_acc": f"<={MAX_FALSE_GOOD}"},
                "cost": p2.get("cost"),
            },
            "phase3": {
                "gate": "PASS",
                "metrics": {"cells": p3.get("cells"), "fixed": p3.get("fixed"),
                            "unresolved": p3.get("unresolved"), "rejected": p3.get("rejected"),
                            "right_to_wrong": p3.get("right_to_wrong"), "held": p3.get("held"),
                            "errors": p3_errors, "stale_cells": p3_stale},
                "threshold": "errors==0（fixed/unresolved 為觀測數、非門檻）",
                "extract_model": p3.get("extract_model"),
                "repair_model": p3.get("repair_model"),
                "cost": p3.get("cost"),
                "cost_note": p3.get("cost_note"),
                "comparison_baseline": p3.get("comparison_baseline"),
            },
        },
        "sources": {
            "phase1": {"path": str(RAW / "phase1.json"), "sha256": sha256(RAW / "phase1.json")},
            "phase2": {"path": str(RAW / "phase2.json"), "sha256": sha256(RAW / "phase2.json")},
            "phase3": {"path": str(RAW / "phase3.json"), "sha256": sha256(RAW / "phase3.json")},
        },
        "code": {
            rel: {"sha256": sha256(REPO / rel), "role": role} for rel, role in CODE_FILES.items()
        },
        "boundaries": [
            "開發選樣、單一碼態、單 rep——不宣稱產品成效，不宣稱 localized/generic 孰優",
            "PHASE3 成本為 repair session 的 raw usage（歷史累計），非本備案輪新增呼叫",
            "本備案輪 run_eval.py --all 為全程離線重算（0 新模型呼叫、0 新 token；"
            "phase1/2 重用既有擷取 out/*.json、phase3 接續 progress.json）",
            "G1/REAL14 門禁結果＝run_requirement_checks（checks.py）對 build_requirement_set"
            "（extract.py）組裝的需求集做判定：quote 非逐字→丟棄、unverified→UNKNOWN"
            "不當通過、client/解析例外→空集 fail-closed（本備案已逐節核對 extract.py）",
            "成本缺值＝UNKNOWN（null），不填 0；cost_usd=0 不代表免費",
            "1753 本批排除；hidden/scorer 未讀、未回流",
        ],
        "verify": {
            "gate_command": "python3 ops/reqloop/extract/run_eval.py --all",
            "expected": "exit 0（三門全 PASS）",
            "this_filing_builder": "python3 ops/audits/build_g25_all_gates_filing.py",
        },
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(filing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"① G1 重跑     ：PASS（抓錯 {p1.get('ext_caught')}/{p1.get('total_bad')}、"
          f"率 {g1_catch*100:.1f}%、冤枉 {g1_fp}）成本 呼叫 {p1['cost'].get('calls')}/"
          f"tokens {p1['cost'].get('tokens')}")
    print(f"② REAL14      ：PASS（抓錯 {g2_caught}/{p2.get('total_bad')}、"
          f"冤枉 {g2_fa}/{p2.get('total_good')}）成本 呼叫 {p2['cost'].get('calls')}/"
          f"tokens {p2['cost'].get('tokens')}")
    print(f"③ PHASE3      ：PASS（fixed {p3.get('fixed')}、unresolved {p3.get('unresolved')}、"
          f"rtw {p3.get('right_to_wrong')}、errors {p3_errors}）成本 sessions "
          f"{p3['cost'].get('repair_sessions')}/calls {p3['cost'].get('model_calls')}/"
          f"tokens {p3['cost'].get('tokens')}")
    print("碼態錨點：" + "、".join(f"{rel}={f['sha256'][:8]}" for rel, f in filing["code"].items()))
    print(f"📁 備案已寫：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
