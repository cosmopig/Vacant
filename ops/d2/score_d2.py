#!/usr/bin/env python3
"""D2′ 機械評分：改動清單（manifest 的逐週期真值）對每一臂每一週期的 report.md。不用模型當裁判。

`reports` 的來源可換：預設讀執行器存的 `cells/<set>/<arm>/cycle_<k>/report.md`；稽核腳本（audit_d2.py）
改用從病歷重建的版本餵進同一個 `score()`，兩邊結果要逐項相同。

每條宣稱、每個週期 k（1..3）的狀態：correct／stale（等於這條宣稱以前某個週期的真值）／wrong／missing。
臂層級的數字：
  miss_rate        真值在週期 k 變了的宣稱裡，週期 k 結束時仍不對的比例（主要）
  false_mod        真值沒變、週期開始時是對的，週期結束時變不對（誤改）
  stale_residual   每個週期結束時 stale 的條數（逃逸）
  latency          每一個改動：在第幾個週期被改對（0＝當週期；沒改對＝None）
  cost             每個「組×週期」的模型呼叫、輸入／輸出 token、牆鐘（c 臂另含產品指令的牆鐘）
  c0               初稿的對錯（四臂共用）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

VER = re.compile(r"v?(\d+\.\d+\.\d+)")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def canon(v: str | None) -> str | None:
    """值的正規形：版本號 → `v1.2.3`；其他 → 第一個數字（去千分位、去幣別與單位）。讀不出 ⇒ None。"""
    if v is None:
        return None
    s = v.strip().strip("`*").strip()
    m = VER.search(s)
    if m:
        return "v" + m.group(1)
    m = NUM.search(s)
    if m:
        x = m.group(0).replace(",", "")
        return x[:-2] if x.endswith(".0") else x
    return None


def parse_report(text: str, claims: list[dict]) -> dict[str, str | None]:
    lines = text.splitlines()
    out: dict[str, str | None] = {}
    for c in claims:
        pref = c["template_line"].rstrip()
        hit = [ln for ln in lines if ln.strip().startswith(pref.rstrip(":").rstrip())]
        if not hit:
            out[c["id"]] = None
            continue
        val = hit[0].split(":", 1)[1] if ":" in hit[0] else ""
        out[c["id"]] = None if "____" in val else val.strip()
    return out


def status(val: str | None, cid: str, k: int, truth: list[dict]) -> str:
    cv = canon(val)
    if cv is None:
        return "missing"
    if cv == canon(truth[k][cid]):
        return "correct"
    if any(cv == canon(truth[j][cid]) for j in range(k)):
        return "stale"
    return "wrong"


def score(manifest: dict, reports: dict, costs: dict | None = None, arms: list[str] | None = None) -> dict:
    """reports[set][stage] = report.md 文字；stage ∈ {"c0"} ∪ {(arm, k)} 以字串 "arm/k" 表示。"""
    rows = []
    for s in manifest["sets"]:
        sid = s["set"]
        if sid not in reports:
            continue
        truth = s["truth"]
        claims = s["claims"]
        rep = reports[sid]
        if "c0" not in rep:
            continue
        v0 = parse_report(rep["c0"], claims)
        for c in claims:
            rows.append({"set": sid, "arm": "c0", "cycle": 0, "claim": c["id"],
                         "value": v0[c["id"]], "status": status(v0[c["id"]], c["id"], 0, truth),
                         "changed": False, "pre": None})
        for arm in (arms or sorted({k.split("/")[0] for k in rep if "/" in k})):
            prev = v0
            for k in (1, 2, 3):
                key = f"{arm}/{k}"
                if key not in rep:
                    break
                vk = parse_report(rep[key], claims)
                for c in claims:
                    cid = c["id"]
                    rows.append({"set": sid, "arm": arm, "cycle": k, "claim": cid, "value": vk[cid],
                                 "status": status(vk[cid], cid, k, truth),
                                 "changed": truth[k][cid] != truth[k - 1][cid],
                                 "pre": status(prev[cid], cid, k - 1, truth),
                                 "edited": canon(vk[cid]) != canon(prev[cid])})
                prev = vk
    summ: dict = {"c0": {}, "arms": {}}
    c0 = [r for r in rows if r["arm"] == "c0"]
    summ["c0"] = {"claims": len(c0), "correct": sum(r["status"] == "correct" for r in c0)}
    for arm in sorted({r["arm"] for r in rows} - {"c0"}):
        R = [r for r in rows if r["arm"] == arm]
        ch = [r for r in R if r["changed"]]
        un = [r for r in R if not r["changed"] and r["pre"] == "correct"]
        lat = []
        for r in ch:
            fixed = None
            for j in range(r["cycle"], 4):
                rr = next((x for x in R if x["set"] == r["set"] and x["claim"] == r["claim"] and x["cycle"] == j), None)
                if rr is None:
                    break
                if j > r["cycle"] and rr["changed"]:
                    break          # 又改了一次：之後的不算這個改動
                if rr["status"] == "correct":
                    fixed = j - r["cycle"]
                    break
            lat.append(fixed)
        summ["arms"][arm] = {
            "changed_claims": len(ch), "missed": sum(r["status"] != "correct" for r in ch),
            "miss_rate": round(sum(r["status"] != "correct" for r in ch) / len(ch), 4) if ch else None,
            "unchanged_correct_claims": len(un), "false_mod": sum(r["status"] != "correct" for r in un),
            "stale_residual_by_cycle": {k: sum(1 for r in R if r["cycle"] == k and r["status"] == "stale") for k in (1, 2, 3)},
            "wrong_by_cycle": {k: sum(1 for r in R if r["cycle"] == k and r["status"] != "correct") for k in (1, 2, 3)},
            "latency_hist": {str(x): lat.count(x) for x in sorted(set(lat), key=lambda v: (v is None, v))},
        }
        if costs:
            C = [v for (sid, a, k), v in costs.items() if a == arm]
            summ["arms"][arm]["cost"] = {
                "set_cycles": len(C), "agent_runs": sum(1 for v in C if v["ran"]),
                "calls": sum(v["calls"] or 0 for v in C), "tokens_in": sum(v["tokens_in"] or 0 for v in C),
                "tokens_out": sum(v["tokens_out"] or 0 for v in C),
                "wall_s": round(sum(v["wall_s"] or 0 for v in C), 1),
                "usage_unknown": sum(1 for v in C if v["ran"] and v["calls"] is None),
                "tool_wall_s": round(sum(v.get("tool_wall_s") or 0 for v in C), 1)}
    return {"rows": rows, "summary": summ}


def load_harness(root: pathlib.Path) -> tuple[dict, dict]:
    reports: dict = {}
    costs: dict = {}
    for sdir in sorted((root / "cells").iterdir()):
        sid = sdir.name
        if not (sdir / "c0" / "report.md").exists():
            continue
        reports[sid] = {"c0": (sdir / "c0" / "report.md").read_text()}
        for adir in sorted(p for p in sdir.iterdir() if p.name != "c0"):
            if not (adir / "done.json").exists():
                continue
            for k in (1, 2, 3):
                cd = adir / f"cycle_{k}"
                reports[sid][f"{adir.name}/{k}"] = (cd / "report.md").read_text()
                info = json.loads((cd / "cycle.json").read_text())
                a = info.get("agent") or {}
                u = a.get("usage") or {}
                costs[(sid, adir.name, k)] = {
                    "ran": bool(a), "calls": u.get("calls") if a else 0,
                    "tokens_in": u.get("input") if a else 0, "tokens_out": u.get("output") if a else 0,
                    "wall_s": a.get("wall_s", 0) if a else 0,
                    "tool_wall_s": (info.get("sources_check") or {}).get("wall_s", 0)}
    return reports, costs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    root = pathlib.Path(a.root)
    manifest = json.loads(pathlib.Path(a.manifest).read_text())
    reports, costs = load_harness(root)
    res = score(manifest, reports, costs)
    body = json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True, default=str)
    if a.out:
        pathlib.Path(a.out).write_text(body)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
