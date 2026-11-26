#!/usr/bin/env python3
"""D2′ 實驗一：只靠紀錄算出的逐條標記，能不能指向最終的錯（零模型呼叫的重播）。

預註冊：ops/d2/plans/exp1_flags_prereg.json（先提交、推上遠端，才在任何資料上算「標記對錯誤」）。

標記只用這三樣算：簽章鏈（步驟、輸入輸出內容、出口紀錄 source_fetch）、紀錄裡抓過的來源內容、
以及「重抓」——實驗的來源伺服器在那個評估點會回的頁面（教材的 cycle_k/site/ 檔；那就是伺服器送出的東西，不是答案）。
**不讀** manifest 的真值、評分結果、改動清單。錯誤（對照用）才讀評分結果（score_d2.py 的 rows）。

每個評估點（初稿 c0；各臂每個週期結束時）、每條宣稱（範本的一行）：
- F1 找不到出處：這一行沒有值（沒填或被清掉），或值不在這個評估點之前紀錄過的任何抓取內容裡。
- F2 來源在該值的位置變了：帶著這個值的那些抓過的頁面，在這個評估點重抓，值的位置（JSON 路徑／表頭＋列／最像的那一行）不再是這個值。
- F3 沒讀來源就改：這一行的值在這個週期被改了，但這個週期裡沒有抓過它（改之前的值）的任何候選來源；沒有候選來源時看這個週期有沒有任何抓取。
- F4 被刪：這一行在上一版（初稿的上一版＝範本）還在，這一版不見了。這些臂沒有「交辦範圍」，所以「範圍外被改」不適用。
任一成立＝被標記。

用法：exp1_flags.py --root R --materials M --score S --arms a,b,d_diff_real --out J
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE))
from vacant_network.trace import blame as B  # noqa: E402
from vacant_network.trace import locate as L  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402
from vacant_network.trace.recorder import Recorder  # noqa: E402


def open_rec(vh: pathlib.Path) -> Recorder | None:
    proj = vh / "trace" / "projects"
    dirs = [d for d in proj.iterdir() if d.is_dir()] if proj.exists() else []
    if not dirs:
        return None
    rec = Recorder("/nonexistent-d2-replay", root=vh / "trace")
    rec.dir = dirs[0]
    rec.chain_path = rec.dir / "chain.ndjson"
    rec.state_path = rec.dir / "state.json"
    return rec


def fetch_universe(rec: Recorder) -> list[dict]:
    """紀錄裡所有「抓取內容」：產品認得的抓取步驟、輸入提到網址的步驟的輸出、出口紀錄。"""
    trace = B.Trace(rec)
    out = []
    try:
        for r in S._fetch_records(trace, B.Blamer(trace)):
            out.append({"seq": int(r["seq"]), "url": r["url"], "text": r["text"]})
    except Exception:                           # noqa: BLE001
        pass
    for st in trace.steps:
        us = S._urls_in(trace.input_text(st))
        if us:
            t = trace.output_text(st) or ""
            for u in us:
                out.append({"seq": int(st.seq), "url": u, "text": t})
    for e in rec.events():
        if e.get("type") == "source_fetch" and e.get("url") and not e.get("tls"):
            t = S._blob_text(rec, e.get("sha256"))
            if t is not None:
                out.append({"seq": int(e["seq"]), "url": e["url"], "text": t})
    return out


def _norm(t: str) -> str:
    import html as _h
    import re as _re
    return " ".join(_h.unescape(_re.sub(r"<[^>]+>", " ", t)).split())


def site_text(mat: pathlib.Path, sid: str, k: int, url: str) -> str | None:
    try:
        host, path = url.split("/")[2], url.split("/", 3)[3] if url.count("/") >= 3 else ""
    except IndexError:
        return None
    if not host.startswith(sid + "."):
        return None
    p = mat / "sets" / sid / f"cycle_{k}" / "site" / (path.split("?")[0] or "index.html")
    try:
        return p.read_text(errors="replace")
    except OSError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--materials", required=True)
    ap.add_argument("--score", required=True)
    ap.add_argument("--arms", default="a,b,d_diff_real")
    ap.add_argument("--out", required=True)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--original-defs", action="store_true",
                    help="敏感度分析（原預註冊定義 9dff991ec）：F1 拿值比 HTML 原文（不轉純文字）")
    a = ap.parse_args()
    root = pathlib.Path(a.root).expanduser()
    mat = pathlib.Path(a.materials).expanduser()
    man = json.loads((mat / "manifest.json").read_text())
    templates = {s["set"]: [c["template_line"] for c in s["claims"]] for s in man["sets"]}   # 只用範本行（不是真值）
    cids = {s["set"]: [c["id"] for c in s["claims"]] for s in man["sets"]}
    domains = {s["set"]: s.get("domain", "") for s in man["sets"]}
    sc = json.loads(pathlib.Path(a.score).expanduser().read_text())
    val = {}
    for r in sc["rows"]:
        stage = "c0" if r["arm"] == "c0" else r["arm"]
        val[(r["set"], stage, int(r["cycle"]), r["claim"])] = (r.get("value"), r["status"])
    arms = [x for x in a.arms.split(",") if x]
    rows = []
    for sdir in sorted((root / "cells").glob("s*")):
        sid = sdir.name
        if sid not in templates:
            continue
        stages = [("c0", sdir / "c0" / "snapshot" / "vh", [(0, int(json.loads((sdir / "c0" / "done.json").read_text()).get("chain_len") or 10 ** 9))])]
        for arm in arms:
            fin = sdir / arm / "final" / "vh"
            if not fin.exists():
                continue
            ks = []
            for k in range(1, 5):
                cj = sdir / arm / f"cycle_{k}" / "cycle.json"
                if cj.exists():
                    ks.append((k, int(json.loads(cj.read_text()).get("chain_len") or 10 ** 9)))
            stages.append((arm, fin, ks))
        c0_bound = stages[0][2][0][1]
        for stage, vh, ks in stages:
            rec = open_rec(vh)
            if rec is None:
                continue
            U = fetch_universe(rec)

            prev_bound = c0_bound if stage != "c0" else 0
            for k, bound in ks:
                Uk = [u for u in U if u["seq"] <= bound]
                cyc = [u for u in U if prev_bound < u["seq"] <= bound]
                for cid in cids[sid]:
                    if (sid, stage, k, cid) not in val:
                        continue
                    v, status = val[(sid, stage, k, cid)]
                    pv = None
                    if stage == "c0":
                        prev_present = True                                     # 範本裡有這一行
                    else:
                        pk = ("c0", 0) if k == 1 else (stage, k - 1)
                        pv = val.get((sid, pk[0], pk[1], cid), (None, None))[0]
                        prev_present = pv is not None
                    f = {"F1": False, "F2": False, "F3": False, "F4": False}
                    if v is None:
                        f["F4"] = prev_present
                        f["F1"] = True          # 沒有值（沒填或被清掉）＝不可能「有出處」
                    else:
                        # 主要定義（預註冊修正 1，看過探索性資料、確認性資料還不存在時改的）：以來源轉成純文字後比對
                        match = (lambda t: L.contains(t, v)) if a.original_defs else (lambda t: S.plain_contains(t, v))
                        carriers = [u for u in Uk if match(u["text"])]
                        f["F1"] = not carriers
                        latest: dict[str, str] = {}
                        for u in sorted(carriers, key=lambda x: x["seq"]):
                            latest[u["url"]] = u["text"]
                        for url, prev_text in latest.items():
                            cur = site_text(mat, sid, k, url)
                            if cur is not None and S.value_status(prev_text, cur, v, by_field=True) == "changed":
                                f["F2"] = True
                                break
                        if stage != "c0" and pv is not None and pv != v:
                            Uprev = [u for u in U if u["seq"] <= prev_bound]
                            cand = {u["url"] for u in Uprev if L.contains(u["text"], pv)}
                            fetched = {u["url"] for u in cyc}
                            f["F3"] = (not (cand & fetched)) if cand else (not fetched)
                    etype = status
                    if status == "wrong" and v is not None:      # 錯誤型態（只用於對照，不進標記）：讀錯值＝值在這一組某頁上、編造＝哪頁都沒有
                        pages_k = [(mat / "sets" / sid / f"cycle_{k}" / "site").glob("*")]
                        etype = "wrong_read" if any(S.plain_contains(pp.read_text(errors="replace"), v)
                                                    for g in pages_k for pp in g if pp.is_file()) else "fabricated"
                    rows.append({"set": sid, "arm": stage, "eval": k, "claim": cid, "status": status, "etype": etype,
                                 "domain": domains.get(sid, ""),
                                 "error": status != "correct", **f, "flagged": any(f.values())})
                prev_bound = bound
    def verdict(fs, rc, lo, ratio, erate):
        """預註冊修正 1（看過探索性資料、確認性資料還不存在時）：被標上限隨該批錯誤率調整。"""
        if fs is None or rc is None or erate is None:
            return "n/a"
        if rc < 0.5 or fs > max(0.5, erate + 0.25):
            return "FAIL"
        if rc >= 0.7 and (lo or 0) >= 0.6 and (ratio is None or ratio >= 3) and fs <= max(0.3, erate + 0.15):
            return "PASS"
        return "UNRESOLVED"

    # 摘要
    def summarize(rs: list[dict]) -> dict:
        n = len(rs)
        fl = sum(r["flagged"] for r in rs)
        er = sum(r["error"] for r in rs)
        tp = sum(r["flagged"] and r["error"] for r in rs)
        in_rate = tp / fl if fl else None
        out_rate = (er - tp) / (n - fl) if n - fl else None
        by_err = collections.Counter((r.get("etype", r["status"]), r["flagged"]) for r in rs if r["error"])
        by_flag = {fk: {"flagged": sum(r[fk] for r in rs), "errors_caught": sum(r[fk] and r["error"] for r in rs)} for fk in ("F1", "F2", "F3", "F4")}
        sets = sorted({r["set"] for r in rs})
        rng = random.Random(20261126)
        recs = []
        if er:
            by_set = {s: [r for r in rs if r["set"] == s] for s in sets}
            for _ in range(a.boot):
                pick = [rng.choice(sets) for _ in sets]
                e2 = sum(r["error"] for s in pick for r in by_set[s])
                t2 = sum(r["error"] and r["flagged"] for s in pick for r in by_set[s])
                if e2:
                    recs.append(t2 / e2)
            recs.sort()
        return {"units": n, "flagged": fl, "flagged_share": fl / n if n else None, "errors": er,
                "recall": tp / er if er else None,
                "recall_lower95": recs[int(0.05 * len(recs))] if recs else None,
                "recall_ci95": [recs[int(0.025 * len(recs))], recs[int(0.975 * len(recs)) - 1]] if recs else None,
                "error_rate_flagged": in_rate, "error_rate_unflagged": out_rate,
                "rate_ratio": (in_rate / out_rate) if in_rate is not None and out_rate else None,
                "random_baseline_recall": fl / n if n else None,
                "errors_by_status_flagged": {f"{st}|{'flagged' if fl_ else 'missed'}": c for (st, fl_), c in sorted(by_err.items())},
                "by_flag": by_flag, "sets": len(sets),
                "error_rate": er / n if n else None,
                "plain": {"look_share": fl / n if n else None, "miss_share_of_errors": (1 - tp / er) if er else None,
                          "random_same_size_miss_share": (1 - fl / n) if n else None},
                "verdict_amend1": verdict(fl / n if n else None, tp / er if er else None,
                                          recs[int(0.05 * len(recs))] if recs else None,
                                          (in_rate / out_rate) if in_rate is not None and out_rate else None, er / n if n else None)}
    res = {"root": root.name, "arms": arms, "overall": summarize(rows),
           "by_arm": {ar: summarize([r for r in rows if r["arm"] == ar]) for ar in sorted({r["arm"] for r in rows})},
           "by_domain": {dm: summarize([r for r in rows if r["domain"] == dm]) for dm in sorted({r["domain"] for r in rows})}}
    pathlib.Path(a.out).expanduser().write_text(json.dumps({**res, "rows": rows}, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items()}, ensure_ascii=False)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
