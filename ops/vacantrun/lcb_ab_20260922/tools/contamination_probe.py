#!/usr/bin/env python3
"""污染檢查：**只給題目標題**，看模型能不能把題目複述出來。

能複述 ⇒ 它在訓練時看過 ⇒ 這一題不能拿來量「解題能力」。

⚠ 這是**單邊**的證據，跟本 repo 其他量具同一條紀律：
  · 「複述得出來」⇒ **確定看過**（強證據）
  · 「複述不出來」⇒ **只是沒有從標題回憶起來**，不等於訓練資料裡沒有（弱證據）
  所以它不能證明無污染，只能把**明顯被記住的題**挑出來剔除。

⚠ 正控制（`Two Sum` 這種一定看過的）要先答得出來，否則這把尺量不動，
  全部 UNKNOWN 只代表模型不合作。2026-09-22 第一次跑就踩到：`max_tokens` 太小，
  思考模型把額度用在推理上 ⇒ content 全空 ⇒ **看起來像全部 UNKNOWN**。
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:19000/v1"
MODEL = sys.argv[2] if len(sys.argv) > 2 else "gemma-4-12b-it-qat"

PROMPT = ("LeetCode problem titled '{t}'. State what the problem asks, in one "
          "sentence. If you do not know this specific problem, reply exactly: UNKNOWN")

#: 正控制：模型**一定**看過的老題。它答不出來 ⇒ 這一輪的 UNKNOWN 不算數。
POSITIVE_CONTROLS = ("Two Sum", "Merge Two Sorted Lists", "Valid Parentheses")


def ask(title: str, max_tokens: int = 900) -> str:
    body = json.dumps({"model": MODEL, "temperature": 0,
                       "max_tokens": max_tokens,
                       "messages": [{"role": "user",
                                     "content": PROMPT.format(t=title)}]}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    return (d["choices"][0]["message"].get("content") or "").strip()


def classify(ans: str) -> str:
    if not ans:
        return "EMPTY"                  # 量不到，不是 UNKNOWN
    return "UNKNOWN" if ans.upper().startswith("UNKNOWN") else "RECALLED"


def main() -> int:
    man = json.load(open(HERE / "manifest.json"))
    out = {"base": BASE, "model": MODEL, "positive_controls": [], "tasks": []}
    for t in POSITIVE_CONTROLS:
        a = ask(t)
        out["positive_controls"].append({"title": t, "verdict": classify(a),
                                         "answer": a[:200]})
        print(f"  [正控制] {t:<26} {classify(a)}")
    ok_ctl = sum(1 for c in out["positive_controls"] if c["verdict"] == "RECALLED")
    out["positive_controls_recalled"] = f"{ok_ctl}/{len(POSITIVE_CONTROLS)}"
    print(f"  正控制回憶出 {ok_ctl}/{len(POSITIVE_CONTROLS)}"
          f"{'  ⇒ 尺量得動' if ok_ctl else '  🔴 尺量不動，下面的 UNKNOWN 不算數'}")
    for p in man["picked"]:
        a = ask(p["title"])
        v = classify(a)
        out["tasks"].append({"task_id": p["task_id"], "title": p["title"],
                             "contest_date": p["contest_date"],
                             "difficulty": p["difficulty"],
                             "verdict": v, "answer": a[:200]})
        print(f"  {p['task_id']:<14}{p['contest_date']}  {p['difficulty']:<7}{v}")
    n = len(out["tasks"])
    rec = sum(1 for t in out["tasks"] if t["verdict"] == "RECALLED")
    emp = sum(1 for t in out["tasks"] if t["verdict"] == "EMPTY")
    out["summary"] = {"n": n, "recalled": rec, "unknown": n - rec - emp, "empty": emp}
    print(f"\n本批 {n} 題：複述得出來 {rec}、UNKNOWN {n-rec-emp}、量不到 {emp}")
    (HERE / "contamination.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
