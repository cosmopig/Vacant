#!/usr/bin/env python3
"""B54 回饋各輪的出口對帳（預註冊 PREREG_20261128_EXPT_CONFIRM 附錄 B 補充，看結果前）。

這支在架構裡承重什麼：鏈與出口紀錄（egress.jsonl）都在 agent 可寫的 VACANT_HOME 底下；唯一的外部錨點是沙箱外、
沒掛進沙箱的來源伺服器存取紀錄（run root 的 access.jsonl）。對每一臂、每一輪：
  紀錄集合＝該臂 final/vh 的 egress.jsonl 中，該輪執行時間窗內、本格主機、GET 且回 200 的網址；
  伺服器集合＝access.jsonl 在同一時間窗內、本格主機下回 200 的網址。
  紀錄 ⊊ 伺服器（少頁）⇒「量具缺口」（B27(1)）；紀錄有伺服器沒有的（多頁）⇒「紀錄不可信」。兩類可能同時出現。
  時間窗歧義：同一主機、時間窗重疊的其他執行（同一 run root 內）有幾筆，只描述（B54(4)）。
只讀紀錄，不讀任何分數或報告內容。輸出不含網址以外的主機（模型端點的 CONNECT 不列）。
限制（B54(5)）：只能偵測「抓了哪些頁」被改；鏈上其他事件被改寫後用同一把金鑰重簽，偵測不到。
用法：expTc_b54.py ROOT [ROOT ...] --out OUT.json
"""
from __future__ import annotations
import argparse, collections, json, pathlib, re, sys

SLACK = 1.0


def _load_jsonl(p: pathlib.Path) -> list:
    out = []
    for l in p.read_text(errors="replace").splitlines():
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def check_root(root: pathlib.Path) -> dict:
    acc = _load_jsonl(root / "access.jsonl") if (root / "access.jsonl").is_file() else []
    runs = []          # 每一輪：(set, rep, arm, round, host, t0, t1, run_dir, arm_dir)
    for rj in sorted((root / "cells").glob("*/r*/*/round_*/run/run.json")):
        run = rj.parent; rnd = run.parent; arm = rnd.parent; rep = arm.parent; sid = rep.parent
        j = json.loads(rj.read_text())
        runs.append({"set": sid.name, "rep": rep.name, "arm": arm.name, "round": rnd.name,
                     "host": f"{sid.name}-{rep.name}.d2-sources.example", "t0": j.get("t_start"), "t1": j.get("t_end"), "arm_dir": arm})
    rows = []
    for r in runs:
        if r["t0"] is None or r["t1"] is None:
            continue
        lo, hi = r["t0"] - SLACK, r["t1"] + SLACK
        srv = {f"http://{a['host']}{str(a['path']).split('?', 1)[0]}" for a in acc if a.get("host") == r["host"] and a.get("status") == 200 and lo <= a.get("ts", 0) <= hi}
        srv_arm_field = collections.Counter(str(a.get("arm")) for a in acc if a.get("host") == r["host"] and a.get("status") == 200 and lo <= a.get("ts", 0) <= hi)
        vh = r["arm_dir"] / "final" / "vh"
        if not vh.is_dir():
            # 抽核第 7 點：臂沒有 final ⇒ 依 B4 當基礎設施（整對作廢），不是對帳通過
            rows.append({k: r[k] for k in ("set", "rep", "arm", "round")} | {"status": "arm_not_final_infra_B4"}); continue
        rec = set(); missing_ts = 0
        for ej in vh.glob("trace/projects/*/egress.jsonl"):
            for e in _load_jsonl(ej):
                u = re.sub(r"^(http://[^/:]+):80/", r"\1/", str(e.get("url", "")))      # 抽核第 7 點：帶 :80 的網址正規化
                u = u.split("?", 1)[0].split("#", 1)[0]                                    # 伺服器紀錄的 path 不含 query（ff-s17/r5 的 ?format=json）
                if e.get("method") == "GET" and e.get("status") == 200 and u.startswith(f"http://{r['host']}/"):
                    if e.get("ts_ms") is None:                                        # 缺 ts_ms：不當成 0，另計
                        missing_ts += 1; continue
                    if lo * 1000 <= e["ts_ms"] <= hi * 1000:
                        rec.add(u)
        overl = sum(1 for o in runs if o is not r and o["host"] == r["host"] and o["t0"] is not None and o["t1"] is not None
                    and o["t0"] - SLACK <= hi and lo <= o["t1"] + SLACK)
        rows.append({k: r[k] for k in ("set", "rep", "arm", "round")} | {
            "status": "ok", "recorded_200": len(rec), "server_200": len(srv), "equal": rec == srv,
            "gauge_gap": sorted(u.split("/", 3)[-1] for u in srv - rec),          # 少頁：伺服器有、紀錄沒有
            "record_untrusted": sorted(u.split("/", 3)[-1] for u in rec - srv),   # 多頁：紀錄有、伺服器沒有
            "server_arm_field": dict(srv_arm_field), "window_ambiguous_overlaps": overl, "egress_missing_ts_ms": missing_ts})
    ok = [x for x in rows if x.get("status") == "ok"]
    by_arm = collections.defaultdict(lambda: {"rounds": 0, "gauge_gap_rounds": 0, "record_untrusted_rounds": 0, "ambiguous_rounds": 0})
    for x in ok:
        b = by_arm[x["arm"]]; b["rounds"] += 1
        b["gauge_gap_rounds"] += bool(x["gauge_gap"]); b["record_untrusted_rounds"] += bool(x["record_untrusted"])
        b["ambiguous_rounds"] += x["window_ambiguous_overlaps"] > 0
    untrusted_pairs = sorted({f"{x['set']}/{x['rep']}" for x in ok if x["record_untrusted"] and not x["window_ambiguous_overlaps"]})
    return {"root": root.name, "rounds_checked": len(ok), "rounds_not_final": sum(1 for x in rows if x.get("status") != "ok"),
            "pairs_arm_not_final_infra": sorted({f"{x['set']}/{x['rep']}" for x in rows if x.get("status") == "arm_not_final_infra_B4"}),
            "by_arm": dict(by_arm), "pairs_with_record_untrusted_unambiguous": untrusted_pairs,
            "pairs_with_record_untrusted_any": sorted({f"{x['set']}/{x['rep']}" for x in ok if x["record_untrusted"]}),
            "pairs_with_gauge_gap": sorted({f"{x['set']}/{x['rep']}" for x in ok if x["gauge_gap"]}), "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("roots", nargs="+"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = {"rule": "B54", "roots": [check_root(pathlib.Path(r)) for r in a.roots]}
    pathlib.Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for r in res["roots"]:
        print(r["root"], "rounds", r["rounds_checked"], "not_final", r["rounds_not_final"], "untrusted_pairs", len(r["pairs_with_record_untrusted_any"]),
              "gap_pairs", len(r["pairs_with_gauge_gap"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
