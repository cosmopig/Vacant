"""把實驗檔案庫抽成網頁用的單一 JSON（供 record.html 使用）。

網站是純靜態的：它讀這份 JSON 畫頁面，不自己推論任何東西。

**這一支刻意把「被推翻的結論」也發布出去。** 一個宣稱可究責的系統，如果
只發布站得住的結論、把被推翻的默默拿掉，那它的主張就沒有內容。所以
claims 帶 verdict 欄位，網頁照實顯示「推翻／誇大／成立」。
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

IDX = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/專題/實驗記錄/_index"
REC = IDX.parent
OUT = Path("/Users/cosmopig/Documents/GitHub/vacant-docs-web/data/archive.json")

# 裁決的單一真相來源在 examples/verdicts.py——網頁與機器可讀索引共用同一份，
# 否則索引會比網頁樂觀，而讀索引的 agent 沒有網頁可以對照。
from verdicts import VERDICTS  # noqa: E402


def main() -> None:
    cat = json.loads((IDX / "catalog.json").read_text())
    claims = json.loads((IDX / "claims.json").read_text())["claims"]
    methods = json.loads((IDX / "methods.json").read_text())["methods"]

    # 模型呼叫摘要
    gw = None
    gwp = REC / "真模型_2026-07-26/gateway/model_calls_summary.json"
    if gwp.exists():
        gw = json.loads(gwp.read_text())

    # 測試套件
    tests = None
    tp = IDX / "testruns/pytest.xml"
    if tp.exists():
        import xml.etree.ElementTree as ET
        r = ET.parse(tp).getroot()
        ts = r if r.tag == "testsuite" else r.find("testsuite")
        tests = {"total": int(ts.get("tests")), "failures": int(ts.get("failures")),
                 "errors": int(ts.get("errors")), "skipped": int(ts.get("skipped")),
                 "time_s": round(float(ts.get("time")), 1)}

    # 每輪的實驗與格
    rounds = []
    for rd in cat["輪次"]:
        exps = []
        for e in rd["實驗"]:
            exps.append({
                "id": e["id"], "question": e.get("問題"), "axis": e.get("軸"),
                "note": e.get("註"), "n_logs": e.get("原始紀錄數"),
                "cells": e.get("格"),
            })
        rounds.append({"id": rd["id"], "dir": rd["dir"],
                       "questions": rd.get("問題"), "report": rd.get("報告"),
                       "experiments": exps})

    data = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True).stdout.strip(),
        "totals": cat["統計"],
        "rounds": rounds,
        "claims": [{**c, **VERDICTS.get(c["id"], {})} for c in claims],
        "methods": methods,
        "gateway": gw,
        "tests": tests,
        "index_files": ["catalog.json", "schema.json", "methods.json",
                        "claims.json", "files.jsonl"],
        "honesty": cat.get("誠實邊界", []),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    n_ref = sum(1 for c in data["claims"] if c.get("verdict") == "refuted")
    n_over = sum(1 for c in data["claims"] if c.get("verdict") == "overstated")
    n_held = sum(1 for c in data["claims"] if c.get("verdict") == "held")
    n_null = sum(1 for c in data["claims"] if c.get("verdict") == "no_effect")
    print(f"  裁決：held {n_held}、no_effect {n_null}")
    print(f"寫出 {OUT} {OUT.stat().st_size} bytes")
    print(f"  輪次 {len(rounds)}、宣稱 {len(data['claims'])}"
          f"（被推翻 {n_ref}、誇大 {n_over}）")
    print(f"  檔案 {data['totals']['檔案數']}、行數 {data['totals']['總行數']:,}")
    print(f"  模型呼叫 {gw['筆數'] if gw else '—'} 筆、測試 {tests['total'] if tests else '—'} 支")


if __name__ == "__main__":
    main()
