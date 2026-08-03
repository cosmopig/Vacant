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

# 對抗式複驗的裁決（2026-08-03）。每條由一個獨立 agent 自己重跑、任務是推翻它。
VERDICTS = {
    "pulse.starvation": {
        "verdict": "overstated",
        "一句話": "核心站得住，但原始證據有混淆，且機制解釋是錯的",
        "推翻了什麼": "同格「從未被抓」的 14 個 seed 也一樣停擺，所以「16/16 被抓後零路由」"
                      "無法歸因於被抓。且「恢復不可能」是錯的——slash 0.9 在 177 輪回歸、"
                      "0.8 在 520 輪回歸，是連續曲線。",
        "更正後": "被 slash(0.5) 一次就在任何可達視野內退出路由。乾淨隔離後更強："
                  "defect_budget=1、4000 輪下，未被抓的 27/30 跑到第 3993 輪，"
                  "被抓的 3/3 其後 3961 輪零路由。真正的機制不是「per-stream 時鐘讓等待無效」"
                  "——等待其實有效（UCB 探索項）；致命的是 slash 的 β += (α+β) 同時砍半均值"
                  "並加倍 n，而 n 是回歸時間的指數係數：懲罰把自己的赦免管道一起關小了。",
    },
    "pulse.timing_minor": {
        "verdict": "overstated",
        "一句話": "那個 1.81 倍是雜訊寬度，不是效應量",
        "推翻了什麼": "ANOVA 不顯著（F=1.27、η²=0.039）、permutation p=0.115、"
                      "檢定力僅 25%。而且 E24 十五格全部跑在盲區 0.5——"
                      "正是時間結構效應為零的交叉點（p=0.868）。",
        "更正後": "在盲區 0.5 這一點上量不到時間結構的效應，但那是 absence of evidence。"
                  "把得手拆成「路由次數 × 每次得手率」後，前者跨度 6.06 倍、後者 8.45 倍——"
                  "總數之所以平，是曝光與效率反向抵消。攻擊能力差 8.45 倍。",
    },
    "pulse.blindspot_dominates": {
        "verdict": "overstated",
        "一句話": "8.9 倍／54 倍幾乎全靠 blindspot=1.0 這個退化端點撐著",
        "推翻了什麼": "排掉 blind=1.0 後只剩 pulse 3.28 倍、patient 5.68 倍。"
                      "而 blind=1.0 時 30 個 seed 產生同一條軌跡、sd=0，有效樣本數 n=1。"
                      "更關鍵：被拿來當「盲區威力」證據的 21 vs 79，兩邊盲區都是 1.0——"
                      "那個落差 100% 是時間結構（工作週期 3/13 對 ~100%），沒有盲區成分。",
        "更正後": "盲區與時間結構有強交互作用（雙因子分解 η²=0.264，是時間結構主效應的 4 倍），"
                  "所以「真正的變數是 X」這個句型本身不成立。在盲區 1.0 且曝光固定為 90 次時，"
                  "光是時間結構就跨 29 倍——比歸給盲區的 8.9 倍還大。",
    },
    "pulse.crossover": {
        "verdict": "refuted",
        "一句話": "0.5–0.75 的「反轉」是雜訊；對會挑參數的攻擊者交叉點根本不存在",
        "推翻了什麼": "0.75 的配對差 −0.57、95%CI 跨 0、pulse 在 17/30 個 seed 反而較高、"
                      "中位數完全相同。真正分離點在 ≈0.90。而 blindspot=1.0 是退化端點："
                      "30 個 seed 產生同一條軌跡、sd=0，那個「3.8 倍」是 90×工作週期 的算術恆等式。",
        "更正後": "盲區升高時改變的是**最佳蓄積長度往 0 移動**，不是脈衝這個家族變弱。"
                  "實測 pulse(20,2)/(20,1)/(50,1) 在盲區 1.0 得手 81/84/87，全部高過 patient 的 79。",
    },
    "pulse.audit_cannot_close_blindspot": {
        "verdict": "refuted",
        "一句話": "抽樣率與盲區不正交；加大稽核在任何盲區水準下都有效",
        "推翻了什麼": "同一份資料裡，盲區 0.5 下把稽核率 0.1→1.0 讓總得手掉 82%"
                      "（Wilcoxon p=5.5e-6），連盲區類得手也掉 70%。"
                      "而「盲區 0＋全稽核＝全擋」是恆等式不是量測：audit_rate=1 且 "
                      "audit_accuracy=1 時 caught==bad 是程式寫死的。",
        "更正後": "偵測機率是單一乘積 (1−盲區)×抽樣率×準確率，三者同軸。"
                  "抽樣率與盲區可互相替換（稽核 0.5→1.0 剛好抵銷 50% 盲區，配對差 0.03、p=0.78）。"
                  "盲區改變的是防禦的**天花板**（殘量 β/(1−β)），不是抽樣率有沒有用。",
    },
    "pulse.crude_wins_under_blindspot": {
        "verdict": "refuted",
        "一句話": "E19 根本不是等預算比較",
        "推翻了什麼": "預算 12 只對 whitewash（29/30）與 sybil（30/30）生效；"
                      "patient 1/30、pulse(3,10) 1/30、pulse(5,20) 0/30。"
                      "實際作惡 11.97 對 4.87——whitewash 贏在多作惡 2.5 倍，不是贏在時機。"
                      "舊判準只驗 defected <= BUDGET（上界恆成立），永遠抓不到這件事。",
        "更正後": "真正綁住預算後排名反轉（budget=2：patient/pulse 1.67 vs whitewash 0.97，"
                  "配對 p=0.0015）。whitewash 的優勢來自免費換身份重新取得路由權——"
                  "它用掉 4.7 個身份、到第 542 輪還在接單，而 pulse 第 160 輪就被餓死。"
                  "那是入場成本問題，與脈衝的時機結構無關。",
    },
}


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
    print(f"寫出 {OUT} {OUT.stat().st_size} bytes")
    print(f"  輪次 {len(rounds)}、宣稱 {len(data['claims'])}"
          f"（被推翻 {n_ref}、誇大 {n_over}）")
    print(f"  檔案 {data['totals']['檔案數']}、行數 {data['totals']['總行數']:,}")
    print(f"  模型呼叫 {gw['筆數'] if gw else '—'} 筆、測試 {tests['total'] if tests else '—'} 支")


if __name__ == "__main__":
    main()
