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
            ctypes = [c.get("type", "F") for c in s.get("cycles") or []] + ["F"] * len(truth)
            for k in range(1, len(truth)):
                key = f"{arm}/{k}"
                if key not in rep:
                    break
                vk = parse_report(rep[key], claims)
                for c in claims:
                    cid = c["id"]
                    rows.append({"set": sid, "arm": arm, "cycle": k, "claim": cid, "value": vk[cid],
                                 "status": status(vk[cid], cid, k, truth),
                                 "changed": truth[k][cid] != truth[k - 1][cid],
                                 "pre": status(prev[cid], cid, k - 1, truth), "ctype": ctypes[k - 1],
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
            for j in range(r["cycle"], max(x["cycle"] for x in R) + 1):
                rr = next((x for x in R if x["set"] == r["set"] and x["claim"] == r["claim"] and x["cycle"] == j), None)
                if rr is None:
                    break
                if j > r["cycle"] and rr["changed"]:
                    break          # 又改了一次：之後的不算這個改動
                if rr["status"] == "correct":
                    fixed = j - r["cycle"]
                    break
            lat.append(fixed)
        chp = [r for r in ch if r["pre"] == "correct"]
        cyc = sorted({r["cycle"] for r in R})
        summ["arms"][arm] = {
            "changed_claims_pre_correct": len(chp), "missed_pre_correct": sum(r["status"] != "correct" for r in chp),
            "miss_rate_pre_correct": round(sum(r["status"] != "correct" for r in chp) / len(chp), 4) if chp else None,
            "changed_claims": len(ch), "missed": sum(r["status"] != "correct" for r in ch),
            "miss_rate": round(sum(r["status"] != "correct" for r in ch) / len(ch), 4) if ch else None,
            "unchanged_correct_claims": len(un), "false_mod": sum(r["status"] != "correct" for r in un),
            "stale_residual_by_cycle": {k: sum(1 for r in R if r["cycle"] == k and r["status"] == "stale") for k in cyc},
            "wrong_by_cycle": {k: sum(1 for r in R if r["cycle"] == k and r["status"] != "correct") for k in cyc},
            "latency_hist": {str(x): lat.count(x) for x in sorted(set(lat), key=lambda v: (v is None, v))},
        }
        if costs:
            C = [v for (sid, a, k), v in costs.items() if a == arm]
            bytype: dict = {}
            for v in C:
                t = bytype.setdefault(v.get("ctype", "F"), {"set_cycles": 0, "agent_runs": 0, "calls": 0, "tokens": 0, "wall_s": 0.0})
                t["set_cycles"] += 1
                t["agent_runs"] += int(bool(v["ran"]))
                t["calls"] += v["calls"] or 0
                t["tokens"] += (v["tokens_in"] or 0) + (v["tokens_out"] or 0)
                t["wall_s"] = round(t["wall_s"] + (v["wall_s"] or 0) + (v.get("tool_wall_s") or 0), 1)
            summ["arms"][arm]["cost_by_cycle_type"] = bytype
            summ["arms"][arm]["cost"] = {
                "set_cycles": len(C), "agent_runs": sum(1 for v in C if v["ran"]),
                "calls": sum(v["calls"] or 0 for v in C), "tokens_in": sum(v["tokens_in"] or 0 for v in C),
                "tokens_out": sum(v["tokens_out"] or 0 for v in C),
                "wall_s": round(sum(v["wall_s"] or 0 for v in C), 1),
                "usage_unknown": sum(1 for v in C if v["ran"] and v["calls"] is None),
                "tool_wall_s": round(sum(v.get("tool_wall_s") or 0 for v in C), 1),
                "source_requests_agent": sum(v.get("src_req_agent") or 0 for v in C),
                "source_requests_vacant": sum(v.get("src_req_vacant") or 0 for v in C)}
    return {"rows": rows, "summary": summ}


def _epoch(ts: str) -> float:
    import datetime as _dt
    return _dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc).timestamp()


def source_requests(access: list[dict], host: str, t0: str, t1: str) -> dict:
    """來源伺服器在這個週期（執行器記的開始～結束，秒級、各留 1 秒）收到這一組的請求數：agent 的、Vacant 重讀的。
    同一組的臂依序跑，所以時間窗不會和別的臂重疊；不同組的主機名不同。"""
    a, b = (t0, t1) if isinstance(t0, float) else (_epoch(t0), _epoch(t1) + 0.999)
    hits = [x for x in access if x["host"] == host and a <= x["ts"] <= b]
    return {"agent": sum(1 for x in hits if x.get("ua") != "vacant-source-check"),
            "vacant": sum(1 for x in hits if x.get("ua") == "vacant-source-check")}


def materials_stats(manifest: dict, mat_dir: pathlib.Path, sets: list[str] | None = None) -> dict:
    """教材的數值碰撞率（第 0 週期）：一條宣稱的值（帶單位，例如 `30 days`）或只看數字（`30`）也出現在同一組**別的**
    產品頁上的比例。值是從小的候選池隨機抽的，沒有刻意避開重複，也沒有刻意製造。"""
    import re as _re
    n = hit_key = hit_num = 0
    for s in manifest["sets"]:
        if sets and s["set"] not in sets:
            continue
        site = mat_dir / "sets" / s["set"] / "cycle_0" / "site"
        texts = {f"p{i}.html": _re.sub(r"<[^>]+>", " ", (site / f"p{i}.html").read_text()) for i in range(1, 6)}
        for c in s["claims"]:
            v = s["truth"][0][c["id"]]
            others = [t for pg, t in texts.items() if pg != c["source_page"]]
            num = canon(v)
            n += 1
            pat = _re.compile(r"(?<![\w$.,])" + _re.escape(v) + r"(?![\w.,]\d|\w)")
            hit_key += any(pat.search(t) for t in others)
            hit_num += any(num is not None and any(canon(m) == num for m in _re.findall(r"v?\d+\.\d+\.\d+|\$?\d[\d,]*", t)) for t in others)
    return {"claims": n, "value_with_unit_on_another_page": hit_key, "bare_number_on_another_page": hit_num,
            "rate_with_unit": round(hit_key / n, 4) if n else None, "rate_bare_number": round(hit_num / n, 4) if n else None}


def load_harness(root: pathlib.Path) -> tuple[dict, dict]:
    reports: dict = {}
    costs: dict = {}
    access = []
    if (root / "access.jsonl").exists():
        access = [json.loads(x) for x in (root / "access.jsonl").read_text().splitlines() if x.strip()]
    for sdir in sorted((root / "cells").iterdir()):
        sid = sdir.name
        if not (sdir / "c0" / "report.md").exists():
            continue
        reports[sid] = {"c0": (sdir / "c0" / "report.md").read_text()}
        for adir in sorted(p for p in sdir.iterdir() if p.name != "c0"):
            if not (adir / "done.json").exists():
                continue
            for k in sorted(int(c.name.split("_")[1]) for c in adir.glob("cycle_*")):
                cd = adir / f"cycle_{k}"
                reports[sid][f"{adir.name}/{k}"] = (cd / "report.md").read_text()
                info = json.loads((cd / "cycle.json").read_text())
                a = info.get("agent") or {}
                u = a.get("usage") or {}
                costs[(sid, adir.name, k)] = {"ctype": info.get("ctype", "F"),
                    "ran": bool(a), "calls": u.get("calls") if a else 0,
                    "tokens_in": u.get("input") if a else 0, "tokens_out": u.get("output") if a else 0,
                    "wall_s": a.get("wall_s", 0) if a else 0,
                    "tool_wall_s": (info.get("sources_check") or {}).get("wall_s", 0)}
                if info.get("ts_start") and info.get("ts_end"):
                    rq = source_requests(access, f"{sid}.d2-sources.example", info.get("t_start", info["ts_start"]),
                                         info.get("t_end", info["ts_end"]))
                    costs[(sid, adir.name, k)].update(src_req_agent=rq["agent"], src_req_vacant=rq["vacant"])
    return reports, costs


def manifest_dir(path: str) -> str:
    return str(pathlib.Path(path).expanduser().resolve().parent)


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
    res["summary"]["materials"] = materials_stats(manifest, pathlib.Path(manifest_dir(a.manifest)), sorted(reports))
    body = json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True, default=str)
    if a.out:
        pathlib.Path(a.out).write_text(body)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
