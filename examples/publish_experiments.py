"""把實驗記錄抽成網頁視覺化用的單一 JSON（供 lab.html 使用）。

用法：
    python examples/publish_experiments.py

網站是純靜態的：它讀這份 JSON 畫圖，不自己推論任何東西。實驗跑完就重跑
這支腳本、commit 產出的 data/experiments.json，網頁就更新。

只輸出**聚合後的數字與一條代表性軌跡**——逐輪原始紀錄留在實驗目錄，
不上網站（量太大，而且原始檔才是對帳的依據）。
"""
import json
import pathlib
import random
import subprocess
import sys
import time

EC = pathlib.Path("/Users/cosmopig/Library/Mobile Documents/com~apple~CloudDocs/專題/實驗記錄/入場成本_2026-07-26")
RM = pathlib.Path("/Users/cosmopig/Library/Mobile Documents/com~apple~CloudDocs/專題/實驗記錄/真模型_2026-07-26")
OUT = pathlib.Path("/Users/cosmopig/Documents/GitHub/vacant-docs-web/data/experiments.json")

def cells(name):
    p = EC / f"{name}.json"
    if not p.exists(): return None
    d = json.loads(p.read_text())
    return {
        "question": d["question"], "axis": d["axis"],
        "cells": [{
            "label": c["label"],
            "bad": c["accepted_bad"]["mean"], "bad_sd": c["accepted_bad"].get("sd", 0),
            "bad_min": c["accepted_bad"].get("min"), "bad_max": c["accepted_bad"].get("max"),
            "shutout": c["shutout_rate"],
            "hv": (c.get("high_value_hits") or {}).get("mean"),
            "roi": c["roi"]["mean"] if c["roi"]["n"] else None,
            "harm": c["honest_damage"]["mean"],
            "ids": c["identities_used"]["mean"],
            "seeds": c["n_seeds"],
        } for c in d["cells"]],
    }

data = {
    "generated_iso": time.strftime("%Y-%m-%d %H:%M"),
    "commit": subprocess.run(["git","rev-parse","--short","HEAD"],capture_output=True,text=True).stdout.strip(),
    "entrycost": {n: cells(n) for n in ["E1","E2","E3","E4","E5","E6","E7","E8","E9",
                              "E12","E13","E14","E15","E16"]},
    "realmodel": None,
}
# 逐輪紀錄總量
logs = list(EC.rglob("*.jsonl"))
data["entrycost_meta"] = {
    "log_files": len(logs),
    "log_lines": sum(sum(1 for _ in f.open()) for f in logs),
}
# 一支代表性的攻擊者生命史（E1 patient）
tr = EC / "E1" / "logs" / "patient__E1patient-s0.jsonl"
if tr.exists():
    rows = [json.loads(l) for l in tr.open()]
    data["trace"] = [
        {"round": r["round"], "bad": r["bad"], "caught": r["caught"],
         "score": r["score"], "obs": r["obs"], "got": r["accepted_bad"]}
        for r in rows if r["attacker"]
    ]
# 真模型（可能未完成）
#
# E10 的 paired 區塊由 realmodel_suite 在收尾時寫出，但只帶 b/c 兩格
# discordant 資訊，湊不出完整 2×2；而且長跑期間 E10.json 還是上一輪的
# 舊檔。所以這裡一律直接從 rows.jsonl 重算——資料源頭是逐列原始紀錄，
# 誰先寫完都不影響發布出去的數字。
e10_path = RM / "E10.json"

def _e10_from_rows() -> dict | None:
    arms: dict[str, dict] = {}
    per_task: dict[str, dict[str, bool]] = {}
    for arm in ("on", "off"):
        p = RM / "E10" / arm / "rows.jsonl"
        if not p.exists():
            continue
        rows = [json.loads(l) for l in p.open() if l.strip()]
        if not rows:
            continue
        ok = sum(1 for r in rows if r.get("passed"))
        arms[arm] = {"passed": ok, "valid": len(rows),
                     "pass_rate": round(ok / len(rows), 4)}
        for r in rows:
            if "task_id" not in r:      # 這一格是 error 列，沒跑成
                continue
            per_task.setdefault(str(r["task_id"]), {})[arm] = {
                "passed": bool(r.get("passed")), "i": r.get("i")}
    if not arms:
        return None
    out: dict = {"arms": arms}
    # 只有兩臂都跑到的題目才能配對。
    #
    # 用 task_id 而不是列的順序來配：task_id 是 sha256(prompt+tests) 的內容
    # 雜湊（ecosystem._task_id），同一題在兩臂必然相同。用索引配的話，萬一
    # 兩臂的題目集不一樣（例如中途改過 --tasks 又續跑），會靜默把不相干的
    # 兩題配在一起，做出一個看起來正常的假結果。
    both = [(v["on"], v["off"]) for v in per_task.values()
            if "on" in v and "off" in v]
    pairs = [(o["passed"], f["passed"]) for o, f in both]
    # 保險：內容雜湊相同的兩筆，索引也該相同。不同就如實記下來，不吞掉。
    misaligned = sum(1 for o, f in both if o["i"] != f["i"])
    if pairs:
        a = sum(1 for on, off in pairs if on and off)          # 兩臂都過
        b = sum(1 for on, off in pairs if on and not off)      # 只有 ON 過
        c = sum(1 for on, off in pairs if off and not on)      # 只有 OFF 過
        dd = sum(1 for on, off in pairs if not on and not off)  # 兩臂都沒過
        n = len(pairs)
        blk = {"n_pairs": n, "a_both_pass": a, "b_on_only": b,
               "c_off_only": c, "d_both_fail": dd, "discordant": b + c,
               "delta": round((b - c) / n, 4)}
        try:
            sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
            from vacant.research import mcnemar_exact
            blk["mcnemar_p"] = round(mcnemar_exact(b, c), 6)
        except Exception:
            pass
        # delta 的 bootstrap 區間：對「配對」重抽樣。種子寫死，
        # 重複發布得到同一個區間（紀錄要可重現）。
        rng = random.Random(20260726)
        diffs = [(1 if on and not off else -1 if off and not on else 0)
                 for on, off in pairs]
        boot = []
        for _ in range(5000):
            s = sum(diffs[rng.randrange(n)] for _ in range(n))
            boot.append(s / n)
        boot.sort()
        blk["ci95"] = [round(boot[int(0.025 * len(boot))], 4),
                       round(boot[int(0.975 * len(boot)) - 1], 4)]
        blk["boot"] = 5000
        if misaligned:
            blk["index_misaligned"] = misaligned
        out["paired"] = blk
    out["tasks"] = max(v["valid"] for v in arms.values())
    # 完成訊號用 E10.json 是否比逐列紀錄新——它只在 realmodel_suite 收尾時
    # 才寫。用「總列數是否到 120」判斷不可靠：只要有幾筆 infra_void 收在
    # 118，頁面就會永遠顯示「進行中」。
    newest = max((p.stat().st_mtime for arm in ("on", "off")
                  if (p := RM / "E10" / arm / "rows.jsonl").exists()),
                 default=0.0)
    done = e10_path.exists() and e10_path.stat().st_mtime >= newest
    out["in_progress"] = not done
    return out

_live = _e10_from_rows()
if _live:
    data["realmodel_toggle"] = _live
elif e10_path.exists():
    data["realmodel_toggle"] = json.loads(e10_path.read_text())
e11 = RM / "E11.json"
if e11.exists():
    data["realmodel"] = json.loads(e11.read_text())
else:
    arms = {}
    for a in ("M0","M1","M2"):
        f = RM / "E11" / a / "records.jsonl"
        io = RM / "E11" / a / "model_io.jsonl"
        if f.exists():
            recs = [json.loads(l) for l in f.open() if l.strip()]
            ok = sum(1 for r in recs if r.get("outcome")=="pass")
            arms[a] = {"passed": ok, "valid": len(recs),
                       "pass_rate": round(ok/len(recs),4) if recs else None}
        elif io.exists():
            arms[a] = {"in_progress": sum(1 for _ in io.open())}
    if arms: data["realmodel"] = {"arms": arms, "in_progress": True}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("寫出", OUT, OUT.stat().st_size, "bytes")
print("實驗:", [k for k,v in data["entrycost"].items() if v])
print("逐輪紀錄:", data["entrycost_meta"])
print("軌跡點數:", len(data.get("trace", [])))
print("真模型:", data["realmodel"])
