#!/usr/bin/env python3
"""R486：長請求的伺服器端時間去了哪裡——生成／排隊／模型重載。

判準凍結在 DECISION_20260905_R486_LONGREQ_TIME_ATTRIBUTION_PREREG.md（commit 8a447c7）。
本工具只讀落盤快照（8766 的 /api/requests + /api/events），判決路徑上不打網路。

突變體一律在被測函式**內部**讀 env（r700：寫在模組層永遠不生效）。
"""
import argparse, json, os, random, statistics, sys

LONG_MS = 600_000.0          # 客戶端 --request-timeout-s 600 的放手點
OVERLAP_THRESHOLD = 0.50     # P-1：單筆算「被排隊」的重疊時間佔比
QUEUE_LIVE_SHARE = 0.50
QUEUE_RULED_OUT_SHARE = 0.10
RELOAD_CONTRIB_SHARE = 0.30
GEN_HI, GEN_LO = 0.70, 0.30
MIN_TARGETS = 5
REF_MIN_CTOK = 200
GEN_TOLERANCE = 1.5


def _M():
    """突變體旗標——在函式內部呼叫，import 當下不讀。"""
    return os.environ.get("R486_MUTANT", "")


# ---------------------------------------------------------------- 步驟 0
def resolve_ts_semantics(rows):
    """`id` 是落盤時序號 ⇒ 結束時刻應對 id 單調不減。反序對數 0 的那個假設勝。"""
    rs = sorted(rows, key=lambda r: r["id"])
    inv = {}
    for hypo in ("start", "end"):
        ends = [(r["ts"] + r["latency_ms"] / 1000.0) if hypo == "start" else r["ts"] for r in rs]
        n = 0
        run_max = float("-inf")
        for e in ends:
            if e < run_max - 1e-9:
                n += 1
            run_max = max(run_max, e)
        inv[hypo] = n
    zeros = [h for h in ("start", "end") if inv[h] == 0]
    if _M() == "M1_TS_ALWAYS_START":
        return {"inversions": inv, "hypo": "start", "verdict": "TS_RESOLVED_START"}
    if len(zeros) != 1:
        return {"inversions": inv, "hypo": None, "verdict": "TS_AMBIGUOUS"}
    return {"inversions": inv, "hypo": zeros[0],
            "verdict": "TS_RESOLVED_" + zeros[0].upper()}


def to_interval(r, hypo):
    d = r["latency_ms"] / 1000.0
    return (r["ts"], r["ts"] + d) if hypo == "start" else (r["ts"] - d, r["ts"])


# ---------------------------------------------------------------- 幾何
def union_len_within(others, s, e):
    """others 的區間聯集與 [s,e) 的交集總長。"""
    segs = []
    for (a, b) in others:
        lo, hi = max(a, s), min(b, e)
        if hi > lo:
            segs.append((lo, hi))
    if not segs:
        return 0.0
    segs.sort()
    tot, ca, cb = 0.0, segs[0][0], segs[0][1]
    for a, b in segs[1:]:
        if a > cb:
            tot += cb - ca
            ca, cb = a, b
        else:
            cb = max(cb, b)
    return tot + (cb - ca)


def max_concurrency(ivals):
    ev = []
    for a, b in ivals:
        ev.append((a, 1)); ev.append((b, -1))
    ev.sort(key=lambda x: (x[0], x[1]))  # 半開區間 [a,b)：同時刻先關後開
    cur = mx = 0
    for _, d in ev:
        cur += d
        mx = max(mx, cur)
    return mx


# ---------------------------------------------------------------- 主分析
def analyze_under(rows, events, hypo):
    """在指定的 ts 語意假設底下算完整一份。hypo in {"start","end"}。"""
    out = {}
    chat = [r for r in rows if "chat/completions" in (r.get("path") or "")]
    out["rows_scanned"] = len(rows)
    out["chat_rows"] = len(chat)
    out["events_scanned"] = len(events)

    if out["rows_scanned"] == 0 or out["chat_rows"] == 0 or out["events_scanned"] == 0:
        out["verdict"] = "BROKEN"
        for k in ("p1_verdict", "p1b_verdict", "p2_verdict", "p3_verdict", "p4_verdict"):
            out[k] = "BROKEN"
        return out

    ivals_all = [to_interval(r, hypo) for r in chat]
    out["max_concurrency"] = max_concurrency(ivals_all)
    out["p4_verdict"] = "SERIAL_NO_QUEUE" if out["max_concurrency"] == 1 else "CONCURRENT_OBSERVED"

    long_ms = 0.0 if _M() == "M6_TARGET_THRESHOLD_LOW" else LONG_MS
    targets = [r for r in chat if (r.get("latency_ms") or 0) >= long_ms
               and "gemma" in (r.get("model") or "")]
    out["n_targets"] = len(targets)

    # 基準率（P-1b）：不是主 run 的 chat 請求有幾筆
    out["n_foreign_by_model"] = sum(1 for r in chat if "gemma" not in (r.get("model") or ""))
    ips = {}
    for r in chat:
        ips[r.get("client_ip")] = ips.get(r.get("client_ip"), 0) + 1
    out["chat_client_ips"] = ips
    main_ip = max(ips, key=lambda k: ips[k]) if ips else None
    out["main_client_ip"] = main_ip
    out["n_foreign_by_ip"] = sum(1 for r in chat if r.get("client_ip") != main_ip)
    n_foreign = out["n_foreign_by_model"] + out["n_foreign_by_ip"]
    if _M() == "M4_DROP_FOREIGN_BASERATE":
        n_foreign = 1
    out["n_foreign_chat"] = n_foreign

    if out["n_targets"] < MIN_TARGETS and _M() != "M8_UNSCANNED_TO_VERDICT":
        for k in ("p1_verdict", "p1b_verdict", "p2_verdict", "p3_verdict"):
            out[k] = "UNSCANNED"
        out["verdict"] = "UNSCANNED"
        return out

    # ---- P-1 重疊
    thr = 0.0 if _M() == "M3_OVERLAP_THRESHOLD_ZERO" else OVERLAP_THRESHOLD
    per = []
    for r in targets:
        s, e = to_interval(r, hypo)
        if _M() == "M2_OVERLAP_INCLUDES_SELF":
            others = [to_interval(o, hypo) for o in chat]
        else:
            others = [to_interval(o, hypo) for o in chat if o["id"] != r["id"]]
        frac = (union_len_within(others, s, e) / (e - s)) if e > s else 0.0
        per.append({"id": r["id"], "latency_ms": r["latency_ms"], "overlap_frac": round(frac, 6),
                    "status": r.get("status_code"), "ctok": r.get("completion_tokens"),
                    "error": (r.get("error") or "")[:80]})
    out["targets_detail"] = per
    qs = sum(1 for p in per if p["overlap_frac"] >= thr) / len(per)
    out["queue_share"] = round(qs, 6)
    out["p1_verdict"] = ("QUEUE_LIVE" if qs >= QUEUE_LIVE_SHARE else
                         "QUEUE_RULED_OUT" if qs <= QUEUE_RULED_OUT_SHARE else "UNRESOLVED")
    out["p1b_verdict"] = "FORCED_GREEN" if (n_foreign == 0 and out["p1_verdict"] == "QUEUE_RULED_OUT") \
        else "BASERATE_OK"

    # ---- P-2 模型重載
    ev_kinds = ("loaded",) if _M() == "M5_RELOAD_IGNORE_UNLOADED" else ("loaded", "unloaded")
    evs = [e for e in events if (e.get("machine") == "1004" and e.get("event") in ev_kinds)]
    out["reload_events_in_scope"] = len(evs)
    spans = 0
    for r in targets:
        s, e = to_interval(r, hypo)
        if any(s <= x["ts"] < e for x in evs):
            spans += 1
    out["reload_share"] = round(spans / len(targets), 6)
    tgt_min = min(to_interval(r, hypo)[0] for r in targets)
    ev_min = min((e["ts"] for e in events), default=float("inf"))
    if ev_min > tgt_min and _M() != "M9_EVENTS_WINDOW_GUARD_OFF":
        out["p2_verdict"] = "UNSCANNED_EVENT_WINDOW"
    else:
        out["p2_verdict"] = ("RELOAD_CONTRIBUTES" if out["reload_share"] >= RELOAD_CONTRIB_SHARE
                             else "RELOAD_RULED_OUT" if out["reload_share"] == 0.0 else "UNRESOLVED")
    out["events_min_ts"] = ev_min if ev_min != float("inf") else None
    out["targets_min_start"] = tgt_min

    # ---- P-3 吞吐
    if _M() == "M7_REF_BAND_USE_MEAN_OF_ALL":
        ref_pool = chat
    else:
        ref_pool = [r for r in chat if (r.get("latency_ms") or 0) < LONG_MS
                    and (r.get("completion_tokens") or 0) >= REF_MIN_CTOK
                    and r.get("status_code") == 200 and "gemma" in (r.get("model") or "")]
    ref = sorted(r["latency_ms"] / r["completion_tokens"] for r in ref_pool
                 if (r.get("completion_tokens") or 0) > 0)
    out["ref_n"] = len(ref)
    if ref:
        out["ref_ms_per_tok_p50"] = round(statistics.median(ref), 3)
        out["ref_ms_per_tok_p90"] = round(ref[min(len(ref) - 1, int(0.90 * len(ref)))], 3)
    sub = [p for p in per if (p["ctok"] or 0) > 0]
    out["p3_subgroup_n"] = len(sub)
    if len(sub) < 3 or not ref:
        out["p3_verdict"] = "UNSCANNED"
    else:
        lim = out["ref_ms_per_tok_p90"] * GEN_TOLERANCE
        ok = sum(1 for p in sub if p["latency_ms"] / p["ctok"] <= lim)
        out["p3_share"] = round(ok / len(sub), 6)
        out["p3_verdict"] = ("GENERATING" if out["p3_share"] >= GEN_HI else
                             "NOT_GENERATING" if out["p3_share"] <= GEN_LO else "UNRESOLVED")
    out["verdict"] = "OK"
    return out


# 修訂 A：不依賴解出 ts 語意——兩個假設各算一次，只有判決一致才採用。
VERDICT_KEYS = ("p1_verdict", "p1b_verdict", "p2_verdict", "p3_verdict", "p4_verdict", "verdict")


def analyze(rows, events):
    by = {h: analyze_under(rows, events, h) for h in ("start", "end")}
    chat = [r for r in rows if "chat/completions" in (r.get("path") or "")]
    ts = resolve_ts_semantics(chat) if chat else {"verdict": "TS_AMBIGUOUS", "inversions": {}}
    out = {"by_hypo": by,
           "ts_inversions": ts.get("inversions"),      # 舊判別量：無條件保留、降級為附註
           "ts_verdict_note_only": ts.get("verdict")}
    for k in ("rows_scanned", "chat_rows", "events_scanned", "n_targets", "n_foreign_chat",
              "n_foreign_by_ip", "n_foreign_by_model", "max_concurrency", "queue_share",
              "reload_share", "ref_n", "ref_ms_per_tok_p50", "ref_ms_per_tok_p90",
              "p3_subgroup_n", "p3_share", "reload_events_in_scope"):
        a, b = by["start"].get(k), by["end"].get(k)
        out[k] = a if a == b else {"start": a, "end": b}
    for k in VERDICT_KEYS:
        a, b = by["start"].get(k), by["end"].get(k)
        out[k] = a if a == b else "TS_SENSITIVE"
    out["targets_detail"] = by["start"].get("targets_detail", [])
    out["targets_detail_end"] = by["end"].get("targets_detail", [])
    return out


# ---------------------------------------------------------------- 自檢
def _row(i, ts, lat, **kw):
    """夾具用的原始列——**手寫欄位**，不呼叫被測模組的任何 helper。"""
    d = {"id": i, "ts": ts, "latency_ms": lat, "machine": "1004",
         "path": "[gw] /v1/chat/completions", "model": "gemma-4-12b-it-qat",
         "client_ip": "10.0.0.1", "status_code": 200, "completion_tokens": 1000,
         "prompt_tokens": 100, "error": None}
    d.update(kw)
    return d


def selftest():
    F, P = [], 0
    def chk(name, cond):
        nonlocal P
        if cond: P += 1
        else: F.append(name)

    EV = [{"machine": "1004", "event": "loaded", "ts": 0.0, "model": "gemma-4-12b-it-qat"}]

    # 夾具 A：六筆長請求，首尾相接、完全不重疊，時間戳是「開始」語意
    A = [_row(i + 1, 100.0 + i * 700.0, 700_000.0) for i in range(6)]
    ra = analyze(A, EV)
    chk("A_ts_note_ambiguous", ra.get("ts_verdict_note_only") == "TS_AMBIGUOUS")  # 修訂 A 的理由
    chk("A_targets6", ra.get("n_targets") == 6)
    chk("A_maxconc1", ra.get("max_concurrency") == 1)
    chk("A_p4", ra.get("p4_verdict") == "SERIAL_NO_QUEUE")
    chk("A_queue0", ra.get("queue_share") == 0.0)
    chk("A_p1", ra.get("p1_verdict") == "QUEUE_RULED_OUT")
    chk("A_p1b_forced", ra.get("p1b_verdict") == "FORCED_GREEN")   # 沒有外來請求 ⇒ 空綠燈

    # 夾具 B：同 A，但另加一個**別的模型**的長請求，覆蓋每一筆目標 60% 以上
    B = list(A) + [_row(100 + i, 100.0 + i * 700.0, 690_000.0, model="qwen/qwen3.8-27b",
                        client_ip="10.0.0.9") for i in range(6)]
    rb = analyze(B, EV)
    chk("B_p1_live", rb.get("p1_verdict") == "QUEUE_LIVE")
    chk("B_p1b_ok", rb.get("p1b_verdict") == "BASERATE_OK")
    chk("B_foreign12", rb.get("n_foreign_by_model") == 6)
    chk("B_conc2", rb.get("max_concurrency") == 2)

    # 夾具 C：只翻「外來請求存在」這一個量，不動任何區間 → 只有 p1b 該變（r695：不得同源）
    C = list(A) + [_row(200, 1.0, 1.0, model="qwen/qwen3.8-27b", client_ip="10.0.0.9")]
    rc = analyze(C, EV)
    chk("C_p1_same", rc.get("p1_verdict") == ra.get("p1_verdict") == "QUEUE_RULED_OUT")
    chk("C_p1b_flipped", rc.get("p1b_verdict") == "BASERATE_OK")
    chk("C_queue_same", rc.get("queue_share") == ra.get("queue_share"))

    # 夾具 D：重載事件落在第一筆目標的區間內
    EVD = [{"machine": "1004", "event": "unloaded", "ts": 0.0, "model": "g"},
           {"machine": "1004", "event": "unloaded", "ts": 300.0, "model": "g"},
           {"machine": "1004", "event": "unloaded", "ts": 900.0, "model": "g"}]
    rd = analyze(A, EVD)
    chk("D_reload_share_start", abs(rd["by_hypo"]["start"].get("reload_share") - 2 / 6) < 1e-5)
    chk("D_p2_start", rd["by_hypo"]["start"].get("p2_verdict") == "RELOAD_CONTRIBUTES")
    # 事件密到兩個假設都看得到 ⇒ 合併後才准是 RELOAD_CONTRIBUTES
    EVD2 = [{"machine": "1004", "event": "unloaded", "ts": t, "model": "g"}
            for t in [x * 350.0 for x in range(-3, 16)]]
    rd3 = analyze(A, EVD2)
    chk("D3_reload_both", rd3.get("reload_share") == 1.0)
    chk("D3_p2_merged", rd3.get("p2_verdict") == "RELOAD_CONTRIBUTES")
    chk("D3_ev_window_ok", rd3.get("p2_verdict") != "UNSCANNED_EVENT_WINDOW")
    # 只翻事件種類（不動任何區間）：只有 loaded 被算 ⇒ 全部 unloaded 的夾具該掉到 0
    chk("D4_kind_matters", analyze(A, [{"machine": "1004", "event": "unloaded", "ts": t,
                                        "model": "g"} for t in [x * 350.0 for x in range(-3, 16)]]
                                   ).get("reload_share") == 1.0)

    # 夾具 D2：事件窗口不涵蓋目標 ⇒ 必須是 UNSCANNED_EVENT_WINDOW，不是 RULED_OUT
    rd2 = analyze(A, [{"machine": "1004", "event": "loaded", "ts": 9e9, "model": "g"}])
    chk("D2_ev_window_guard", rd2.get("p2_verdict") == "UNSCANNED_EVENT_WINDOW")

    # 夾具 E：P-3。短請求參考帶正常（10 ms/tok），長請求 ctok 極少 ⇒ 不是在生成
    E = [_row(i + 1, 100.0 + i * 700.0, 700_000.0, completion_tokens=5) for i in range(6)]
    E += [_row(500 + i, 200000.0 + i * 20.0, 10_000.0, completion_tokens=1000) for i in range(20)]
    re_ = analyze(E, EV)
    chk("E_ref_n20", re_.get("ref_n") == 20)
    chk("E_targets6", re_.get("n_targets") == 6)
    chk("E_p3_not_gen", re_.get("p3_verdict") == "NOT_GENERATING")
    # 夾具 E2：長請求的 ms/tok 落在參考帶內 ⇒ GENERATING
    E2 = [_row(i + 1, 100.0 + i * 700.0, 700_000.0, completion_tokens=70000) for i in range(6)]
    E2 += [_row(500 + i, 200000.0 + i * 20.0, 10_000.0, completion_tokens=1000) for i in range(20)]
    chk("E2_p3_gen", analyze(E2, EV).get("p3_verdict") == "GENERATING")
    # 夾具 E3：沒有 ctok 的長請求（400 context-exceeded 那型）⇒ 子群為 0 ⇒ UNSCANNED
    E3 = [_row(i + 1, 100.0 + i * 700.0, 700_000.0, completion_tokens=None,
               status_code=400, error="Context size has been exceeded") for i in range(6)]
    E3 += [_row(500 + i, 200000.0 + i * 20.0, 10_000.0, completion_tokens=1000) for i in range(20)]
    r3 = analyze(E3, EV)
    chk("E3_p3_unscanned", r3.get("p3_verdict") == "UNSCANNED")
    chk("E3_sub0", r3.get("p3_subgroup_n") == 0)

    # 夾具 F：型三「安靜量不到」
    chk("F_no_rows", analyze([], EV).get("verdict") == "BROKEN")
    chk("F_no_chat", analyze([_row(1, 0.0, 5.0, path="[gw] /api/events")], EV).get("verdict") == "BROKEN")
    chk("F_no_events", analyze(A, []).get("verdict") == "BROKEN")
    r_small = analyze(A[:3], EV)
    chk("F_unscanned_lt5", r_small.get("verdict") == "UNSCANNED")
    chk("F_unscanned_p1", r_small.get("p1_verdict") == "UNSCANNED")

    # 夾具 G：ts 語意。把 A 改寫成「結束時刻」語意（ts = 原 end），id 序不變
    G = [_row(i + 1, 100.0 + i * 700.0 + 700.0, 700_000.0) for i in range(6)]
    rg = analyze(G, EV)
    chk("G_agree_under_shift", rg.get("p1_verdict") == "QUEUE_RULED_OUT")
    # 夾具 G2：兩個假設都有反序 ⇒ TS_AMBIGUOUS ⇒ 下游全 UNRESOLVED
    G2 = [_row(1, 5000.0, 1000.0), _row(2, 10.0, 1000.0), _row(3, 4000.0, 900_000.0),
          _row(4, 3000.0, 10.0), _row(5, 20.0, 10.0), _row(6, 15.0, 5.0)]
    rg2 = analyze(G2, EV)
    chk("G2_note_ambiguous", rg2.get("ts_verdict_note_only") == "TS_AMBIGUOUS")

    # 夾具 H：兩個 ts 假設**判決不同** ⇒ 必須是 TS_SENSITIVE，不准挑一邊
    #   每個區塊：目標 lat=1000s，另一筆 lat=2000s 起點偏後 600s。
    #   H_start 底下重疊 400/1000=0.40（<0.5）；H_end 底下目標被完全含住 ⇒ 1.00。
    H = []
    for i in range(6):
        b = i * 100_000.0
        H.append(_row(2 * i + 1, b + 0.0, 1_000_000.0))
        H.append(_row(2 * i + 2, b + 600.0, 2_000_000.0, model="qwen/qwen3.8-27b",
                      client_ip="10.0.0.9", latency_ms=2_000_000.0))
    rh = analyze(H, EV)
    chk("H_start_frac_040", abs(rh["by_hypo"]["start"]["targets_detail"][0]["overlap_frac"] - 0.4) < 1e-6)
    chk("H_end_frac_100", abs(rh["by_hypo"]["end"]["targets_detail"][0]["overlap_frac"] - 1.0) < 1e-6)
    chk("H_start_ruled_out", rh["by_hypo"]["start"]["p1_verdict"] == "QUEUE_RULED_OUT")
    chk("H_end_live", rh["by_hypo"]["end"]["p1_verdict"] == "QUEUE_LIVE")
    chk("H_merged_ts_sensitive", rh.get("p1_verdict") == "TS_SENSITIVE")

    # 窮舉斷言（r695／同源擋門是恆假死碼 ⇒ 不做成 runtime gate，做成隨機窮舉）
    rnd = random.Random(486)
    viol = 0
    for _ in range(20000):
        k = rnd.randint(1, 5)
        iv = []
        for _ in range(k):
            a = rnd.uniform(0, 100); iv.append((a, a + rnd.uniform(0.1, 30)))
        mc = max_concurrency(iv)
        worst = max((union_len_within([o for j, o in enumerate(iv) if j != i], s, e) / (e - s))
                    for i, (s, e) in enumerate(iv))
        if mc == 1 and worst > 1e-9:
            viol += 1
    chk("X_identity_conc1_implies_no_overlap", viol == 0)

    # union_len_within 的獨立對照（不靠 max_concurrency）
    chk("X_union_disjoint", abs(union_len_within([(0, 1), (2, 3)], 0, 3) - 2.0) < 1e-9)
    chk("X_union_nested", abs(union_len_within([(0, 10), (2, 3)], 1, 4) - 3.0) < 1e-9)
    chk("X_union_clip", abs(union_len_within([(-5, 100)], 0, 2) - 2.0) < 1e-9)

    print(f"selftest {P}/{P + len(F)} passed" + (f"  FAILED={F}" if F else ""))
    return 0 if not F else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="ops/gain/data/r486_gateway_snapshot.json")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    snap = json.load(open(a.snapshot))
    out = analyze(snap["rows"], snap["events"])
    out["snapshot"] = a.snapshot
    if a.json:
        json.dump(out, open(a.json, "w"), indent=2, sort_keys=True)
    d = dict(out); det = d.pop("targets_detail", [])
    print(json.dumps(d, indent=2, sort_keys=True))
    print("--- targets ---")
    for p in det:
        print(f"  id={p['id']} lat={p['latency_ms']/1000:8.1f}s overlap={p['overlap_frac']:.3f} "
              f"status={p['status']} ctok={p['ctok']} err={p['error']}")


if __name__ == "__main__":
    main()
