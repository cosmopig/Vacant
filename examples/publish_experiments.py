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
import subprocess
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
e10 = RM / "E10.json"
if e10.exists():
    data["realmodel_toggle"] = json.loads(e10.read_text())
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
