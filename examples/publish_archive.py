"""把實驗檔案庫抽成網頁用的單一 JSON（供 record.html 使用）。

網站是純靜態的：它讀這份 JSON 畫頁面，不自己推論任何東西。

**這一支刻意把「被推翻的結論」也發布出去。** 一個宣稱可究責的系統，如果
只發布站得住的結論、把被推翻的默默拿掉，那它的主張就沒有內容。所以
claims 帶 verdict 欄位，網頁照實顯示「推翻／誇大／成立／同號未解析」。

**兩個宣稱來源**（2026-09-07 起）：舊的十二加八條在 `_index/claims.json`（由
`build_archive_index.py` 產生）；2026-09-07 新增的八條自帶 `宣稱`／`來源`，
直接寫在 `verdicts.py` 裡。這一支把兩邊併起來餵網頁。

這件事有代價，寫在這裡不藏：在有人把那八條搬進 `build_archive_index.py::CLAIMS`
之前，機器可讀索引 `_index/claims.json` **少了那八條**。索引不會因此變樂觀
（它沒有多說什麼），但它**不完整**——所以 `archive.json` 帶一個 `index_gap` 欄位
把缺口列出來，讀索引的 agent 至少能知道自己少看了什麼。
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

# 自帶宣稱本文的裁決條目——判斷方式就是「有沒有 `宣稱` 欄位」。
SELF_DESCRIBING = {cid: v for cid, v in VERDICTS.items() if v.get("宣稱")}


def _claim_from_verdict(cid: str, v: dict) -> dict:
    """把自帶宣稱的裁決條目攤成一條網頁用的宣稱。

    `依據.檔案` 是 record.html 印在 SOURCE 後面的東西，所以「來源」必須進去；
    沒有來源的宣稱不該出現在這面牆上。
    """
    src = v.get("來源", "")
    assert src, f"{cid} 沒有來源——沒有來源的宣稱不准上牆"
    out = {"id": cid, "輪次": v.get("輪次"), "宣稱": v["宣稱"],
           "型別": v.get("型別"), "依據": {"檔案": src}}
    out.update({k: val for k, val in v.items()
                if k not in ("宣稱", "輪次", "型別", "來源")})
    return out


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
        "claims": ([{**c, **VERDICTS.get(c["id"], {})} for c in claims]
                   + [_claim_from_verdict(cid, v)
                      for cid, v in SELF_DESCRIBING.items()]),
        "methods": methods,
        "gateway": gw,
        "tests": tests,
        "index_files": ["catalog.json", "schema.json", "methods.json",
                        "claims.json", "files.jsonl"],
        # 索引缺口照實列出：這幾條宣稱只在網頁與 verdicts.py 裡，還沒進機器索引。
        "index_gap": {
            "說明": "以下宣稱自帶於 examples/verdicts.py，尚未搬進 "
                    "examples/build_archive_index.py::CLAIMS，所以 "
                    "_index/claims.json 不含它們。索引不完整，不是索引樂觀。",
            "ids": sorted(SELF_DESCRIBING),
        },
        "honesty": cat.get("誠實邊界", []),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    n_ref = sum(1 for c in data["claims"] if c.get("verdict") == "refuted")
    n_over = sum(1 for c in data["claims"] if c.get("verdict") == "overstated")
    n_held = sum(1 for c in data["claims"] if c.get("verdict") == "held")
    n_null = sum(1 for c in data["claims"] if c.get("verdict") == "no_effect")
    n_unres = sum(1 for c in data["claims"] if c.get("verdict") == "unresolved")
    print(f"  裁決：held {n_held}、no_effect {n_null}、unresolved {n_unres}")
    print(f"  索引缺口：{len(SELF_DESCRIBING)} 條只在 verdicts.py（見 index_gap）")
    print(f"寫出 {OUT} {OUT.stat().st_size} bytes")
    print(f"  輪次 {len(rounds)}、宣稱 {len(data['claims'])}"
          f"（被推翻 {n_ref}、誇大 {n_over}）")
    print(f"  檔案 {data['totals']['檔案數']}、行數 {data['totals']['總行數']:,}")
    print(f"  模型呼叫 {gw['筆數'] if gw else '—'} 筆、測試 {tests['total'] if tests else '—'} 支")


if __name__ == "__main__":
    main()
