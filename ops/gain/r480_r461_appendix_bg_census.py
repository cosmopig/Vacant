#!/usr/bin/env python3
"""R480（round751）：普查 R461 附錄 A.4／B.3／G —— 最後三段沒被 R453 式普查掃過的。

判準：DECISION_20260905_R480_R461_APPENDIX_A4_B3_G_CENSUS.md（工具與量測之前 commit）。
⚠ 主 run `g_r461_lcb3_three_arm` 還在跑 ⇒ G-LIVE 硬擋門：讀到它就 RuntimeError，
   輸出必帶 live_reads=0；B3-3 的重掃具名排除它並另記 runs_excluded_live。
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import pathlib
import subprocess
import sys
from collections import Counter
from math import comb

ROOT = pathlib.Path(__file__).resolve().parents[2]
PREREG = ROOT / "DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md"
SELF_PREREG = ROOT / "DECISION_20260905_R480_R461_APPENDIX_A4_B3_G_CENSUS.md"
RAW_DIR = pathlib.Path.home() / "vacant" / ".raw_lcb"
FORBIDDEN_RUN = "g_r461_lcb3_three_arm"                 # G-LIVE
BANK = {"v2": ROOT / "ops/gain/data/lcb_bank_v2.jsonl",
        "v3": ROOT / "ops/gain/data/lcb_bank_v3.jsonl"}
BUILDER = "ops/gain/build_lcb_bank.py"
CERT_GATE = ROOT / "ops/gain/cert_drift_gate.py"

MUTANT = os.environ.get("R480_MUTANT", "")              # 模組層讀，import 與 __main__ 都生效
LIVE_READS = 0
TOL_PP = 0.5                                            # 判準 §二 釘死，量測後不准動

# ── 被普查的 11 條（pin＝R461 原文逐字片段，抓得到才算普查到那一條）
CLAUSES: dict[str, dict] = {
    "A4-1": {"pin": "恰好 189 題", "intent": "evidence"},
    "A4-2": {"pin": "overlap=0、union=309", "intent": "evidence"},
    "A4-3": {"pin": "日期 2023-05-07 → 2024-08-10", "intent": "evidence"},
    "A4-4": {"pin": "medium 135／hard 54", "intent": "evidence"},
    "B3-1": {"pin": "綠燈基準率是 79.45%", "intent": "evidence"},
    "B3-2": {"pin": "基準率 **14.09%**", "intent": "evidence"},
    "B3-3": {"pin": "掃過 29 個 run", "intent": "guard"},
    "G2-3": {"pin": "必須先跑", "intent": "guard"},
    "G3": {"pin": "docs=138  cert_headings=6", "intent": "guard"},
    "G4": {"pin": "不是「那個數字錯了」", "intent": "guard"},
    "G6": {"pin": "這是結構強制綠燈", "intent": "guard"},
}
PRED_CLASS = {"A4-1": "FORCED_GREEN", "A4-2": "FORCED_GREEN", "A4-3": "EVALUABLE",
              "A4-4": "EVALUABLE", "B3-1": "EVALUABLE", "B3-2": "EVALUABLE",
              "B3-3": "EVALUABLE", "G2-3": "EVALUABLE", "G3": "EVALUABLE",
              "G4": "EVALUABLE", "G6": "FORCED_GREEN"}
PRED_EXEC = {k: (k not in ("B3-1", "B3-2")) for k in CLAUSES}
PRED_STALE = {k: (k in ("B3-3", "G3")) for k in CLAUSES}
PRED_REPRO = {"B3-1": True, "B3-2": False}              # 判準 §三：預測 B3-2 至少一個復現不了


def _read(p: pathlib.Path) -> str:
    global LIVE_READS
    if FORBIDDEN_RUN in str(p):
        LIVE_READS += 1
        if MUTANT != "M1_no_live_guard":
            raise RuntimeError(f"G-LIVE: 禁止讀主 run {p}")
    return p.read_text(encoding="utf-8")


def _rows(p: pathlib.Path) -> list[dict]:
    return [json.loads(l) for l in _read(p).splitlines() if l.strip()]


# ── witness 掃描器（FORCED_GREEN 的唯一來源：witness==0 且母體>0）
def witness_scan(pop: list, pred) -> dict:
    if MUTANT == "M4_scanner_always_zero":
        return {"n": len(pop), "witnesses": 0}
    return {"n": len(pop), "witnesses": sum(1 for x in pop if pred(x))}


def classify(ws: dict) -> str:
    if ws["n"] == 0:
        return "UNSCANNED"                              # 第三型「安靜量不到」
    return "FORCED_GREEN" if ws["witnesses"] == 0 else "EVALUABLE"


def witness_calibration(v3: list[dict]) -> dict:
    """雙向：正對照＝已知恆假（無 witness）／負對照＝自由量（一定有 witness）。"""
    pos = witness_scan(v3, lambda r: not r["task_id"].startswith("lcb_"))
    neg = witness_scan(v3, lambda r: r["difficulty"] == "hard")
    return {"positive_no_witness": pos["witnesses"], "negative_has_witness": neg["witnesses"],
            "ok": pos["witnesses"] == 0 and neg["witnesses"] > 0}


# ── A.4
def a4() -> dict:
    v2, v3 = _rows(BANK["v2"]), _rows(BANK["v3"])
    t2 = {r["task_id"] for r in v2}
    t3 = {r["task_id"] for r in v3}
    raw: dict[str, list[dict]] = {}
    for f in ("test", "test2", "test3"):
        p = RAW_DIR / f"{f}.jsonl"
        raw[f] = _rows(p) if p.exists() else []
    n_raw = sum(len(v) for v in raw.values())
    # A4-1：189 是不是由輸入行數強制？witness＝被 builder 丟掉的原始紀錄
    drops = max(0, n_raw - len(v3)) if n_raw else 0
    ws1 = {"n": n_raw, "witnesses": drops} if MUTANT != "M4_scanner_always_zero" \
        else {"n": n_raw, "witnesses": 0}
    # A4-2：零交集的 witness＝任兩個來源視窗共用 question_id
    ids = {f: {str(r.get("question_id")) for r in rs} for f, rs in raw.items()}
    v2ids = {t.split("_")[-1] for t in t2}
    ids["_v2bank"] = v2ids
    keys = sorted(ids)
    pairs = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:] if ids[a] and ids[b]]
    ws2 = witness_scan(pairs, lambda ab: bool(ids[ab[0]] & ids[ab[1]]))
    dates = [r["contest_date"] for r in v3]
    rawdates = [r.get("contest_date") for rs in raw.values() for r in rs if r.get("contest_date")]
    diff = Counter(r["difficulty"] for r in v3)
    diff2 = Counter(r["difficulty"] for r in v2)
    return {
        "v3_n": len(v3), "v2_n": len(v2), "raw_n": n_raw, "builder_drops": drops,
        "src_counter": dict(Counter(r["source_file"] for r in v3)),
        "overlap": len(t2 & t3), "union": len(t2 | t3),
        "date_min": min(dates)[:10], "date_max": max(dates)[:10],
        "raw_date_min": (min(rawdates)[:10] if rawdates else None),
        "raw_date_max": (max(rawdates)[:10] if rawdates else None),
        "v3_medium": diff["medium"], "v3_hard": diff["hard"],
        "v2_medium": diff2["medium"], "v2_hard": diff2["hard"],
        "merged_medium": diff["medium"] + diff2["medium"],
        "merged_hard": diff["hard"] + diff2["hard"],
        "ws_a41": ws1, "ws_a42": ws2, "pairs_scanned": len(pairs),
        "builder_is_1to1": drops == 0,
    }


# ── B.3
def _binpmf(k: int, n: int, p: float) -> float:
    return comb(n, k) * p ** k * (1 - p) ** (n - k)


def _mcnemar_p(b: int, nd: int) -> float:
    if nd == 0:
        return 1.0
    lo = sum(_binpmf(k, nd, 0.5) for k in range(0, b + 1))
    hi = sum(_binpmf(k, nd, 0.5) for k in range(b, nd + 1))
    return min(1.0, 2 * min(lo, hi))


def b31(n: int = 189, disc: float = 0.1917, pi: float = 0.6087) -> float:
    tot = 0.0
    for nd in range(0, n + 1):
        pnd = _binpmf(nd, n, disc)
        if pnd < 1e-15:
            continue
        tot += pnd * sum(_binpmf(b, nd, pi) for b in range(0, nd + 1)
                         if _mcnemar_p(b, nd) < 0.05)
    return (1 - tot) * 100


def b32(n: int = 189) -> dict:
    def grid(lo, hi, den):
        ks = [k for k in range(0, n + 1) if lo <= 100 * k / n <= hi]
        return 100 * len(ks) / den
    return {"num_continuous": 14.0, "dec_continuous": 30.0,
            "num_grid190": grid(38, 52, n + 1), "dec_grid190": grid(30, 60, n + 1),
            "num_grid189": grid(38, 52, n), "dec_grid189": grid(30, 60, n),
            "contradiction_band_pp": (38 - 30) + (60 - 52)}


DEN_KEYS = ("tasks", "n", "processed")                  # ⚠ 'tasks' 是真的那個；M6 拿掉它


def b33(keys: tuple = DEN_KEYS) -> dict:
    if MUTANT == "M6_denominator_drops_tasks":
        keys = DEN_KEYS[1:]
    runs = sorted(p for p in (ROOT / "runs").iterdir() if p.is_dir())
    if MUTANT in ("M2_empty_targets", "M3_empty_targets_no_guard"):
        runs = []
    scanned, excluded_live, over, unresolved = 0, 0, [], []
    for r in runs:
        if FORBIDDEN_RUN in r.name and MUTANT != "M1_no_live_guard":
            excluded_live += 1
            continue
        s = r / "summary.json"
        if not s.exists():
            continue
        try:
            d = json.loads(_read(s))
        except ValueError:
            continue
        scanned += 1
        arms = d.get("arms")
        if not isinstance(arms, dict):
            continue
        for a, v in arms.items():
            if not isinstance(v, dict) or not isinstance(v.get("infra_void"), int):
                continue
            den = next((v[k] for k in keys if isinstance(v.get(k), int) and v[k] > 0), None)
            if den is None:
                unresolved.append(f"{r.name}:{a}")      # 不准安靜跳過（型二）
                continue
            if v["infra_void"] / den > 0.20:
                over.append((r.name, a, v["infra_void"], den))
    top = max(over, key=lambda x: x[2] / x[3], default=None)
    return {"runs_scanned": scanned, "runs_excluded_live": excluded_live,
            "arms_over": len(over), "runs_over": len({o[0] for o in over}),
            "unresolved_arms": unresolved,
            "top": (list(top) if top else None),
            "top_rate_pp": (round(100 * top[2] / top[3], 1) if top else None)}


# ── G
def cert_gate() -> dict:
    if MUTANT == "M2_empty_targets":
        return {"rc": None, "counts": {}, "docs": 0, "cert_headings": 0, "ran": False}
    tmp = ROOT / "ops/gain/data/r480_cert_gate_probe.json"
    pr = subprocess.run([sys.executable, str(CERT_GATE), "--json", str(tmp)],
                        capture_output=True, text=True, cwd=str(ROOT), timeout=180)
    d = json.loads(tmp.read_text(encoding="utf-8")) if tmp.exists() else {}
    return {"rc": pr.returncode, "counts": d.get("counts", {}),
            "docs": d.get("docs_scanned"), "cert_headings": d.get("cert_headings"),
            "has_mismatch_field": "cert_sha_mismatches" in d,
            "mismatches": d.get("cert_sha_mismatches"), "ran": bool(d),
            "gate_verdict": d.get("verdict")}


def g4_identity() -> dict:
    """G.4 的宣稱＝STALE 只由 blob sha 決定、不看數字。逐字取 STALE 的判定式證明。"""
    tree = ast.parse(_read(CERT_GATE))
    src = _read(CERT_GATE)
    exprs = [ast.get_source_segment(src, n) for n in ast.walk(tree)
             if isinstance(n, ast.Compare) and "CERT_STALE" not in (ast.get_source_segment(src, n) or "")]
    stale_sites = [ast.get_source_segment(src, n) for n in ast.walk(tree)
                   if isinstance(n, ast.Constant) and n.value == "CERT_STALE"]
    # 判定式：整支工具有沒有把「輸出數字」讀進來比較（有＝G.4 的宣稱不成立）
    reads_outputs = any(w in src for w in ("delta_pp", "verdict ==", "rerun"))
    return {"stale_sites": len(stale_sites), "compares": len(exprs),
            "reads_tool_outputs": reads_outputs}


def g6_identity(cg: dict) -> dict:
    """G.6 自承 cert_sha_mismatches=0 是結構強制：自記值是照反推值抄的 ⇒ witness 恆 0。"""
    txt = _read(PREREG)
    blobs = [l for l in txt.splitlines() if "CERT-BLOB" in l]
    return {"cert_blob_lines": len(blobs), "self_declared_forced": "這是結構強制綠燈" in txt,
            "mismatch_field_present": cg.get("has_mismatch_field")}


# ── 普查本體
def census() -> dict:
    global LIVE_READS
    LIVE_READS = 0
    prereg = _read(PREREG)
    broken: list[str] = []

    pins = {}
    for cid, c in CLAUSES.items():
        pin = c["pin"] + ("＜不在原文＞" if MUTANT == "M5_pin_break" and cid == "G4" else "")
        pins[cid] = pin in prereg
    if not all(pins.values()):
        broken.append("BROKEN_PIN_MISSING")

    A = a4()
    v3rows = _rows(BANK["v3"])
    cal = witness_calibration(v3rows)
    if not cal["ok"]:
        broken.append("BROKEN_WITNESS_CALIBRATION")

    r31 = b31()
    r32 = b32()
    B33 = b33()
    # 分母敏感度：B.3-3 的正文沒有釘死分母 ⇒ 同一份資料兩個分母兩組數字（照實兩份都報）
    ALT = b33(("n", "processed")) if MUTANT != "M6_denominator_drops_tasks" else dict(B33)
    B33["arms_over_alt_den"] = ALT["arms_over"]
    B33["runs_over_alt_den"] = ALT["runs_over"]
    B33["alt_den_unresolved_arms"] = len(ALT["unresolved_arms"])
    B33["denominator_pinned_in_prose"] = False
    if B33["unresolved_arms"]:
        broken.append("BROKEN_ARM_ACCOUNTING")
    if B33["runs_scanned"] == 0:
        if MUTANT == "M3_empty_targets_no_guard":
            pass                                        # M3＝拿掉 UNSCANNED 擋門
        else:
            broken.append("UNSCANNED")

    CG = cert_gate()
    G4 = g4_identity()
    G6 = g6_identity(CG)

    tol = TOL_PP
    bump = 10.0 if MUTANT == "M7_claim_corrupted" else 0.0   # 讓容差比較真的被行使
    repro = {
        "B3-1": {"claim": 79.45 + bump, "recomputed": round(r31, 2),
                 "delta_pp": round(abs(r31 - 79.45 - bump), 4)},
        "B3-2": {"claim": [14.09 + bump, 30.07 + bump],
                 "recomputed": [r32["num_continuous"], r32["dec_continuous"]],
                 "delta_pp": round(max(abs(14.09 + bump - r32["num_continuous"]),
                                       abs(30.07 + bump - r32["dec_continuous"])), 4),
                 "exact_rule_match": any(abs(14.09 - x) < 1e-9 for x in
                                         (r32["num_continuous"], r32["num_grid190"],
                                          r32["num_grid189"]))},
    }
    for k in repro:
        repro[k]["reproducible"] = repro[k]["delta_pp"] <= tol
        repro[k]["tolerance_pp"] = tol

    out: dict = {}
    def emit(cid, clazz, exec_ok, stale, **ev):
        out[cid] = {"clazz": clazz, "executable_as_pinned": exec_ok, "premise_stale": stale,
                    "intent": CLAUSES[cid]["intent"], "pin_found": pins[cid], **ev}

    emit("A4-1", classify(A["ws_a41"]), True, False,
         witnesses=A["ws_a41"]["witnesses"], population=A["ws_a41"]["n"],
         note=f"builder 丟掉 {A['builder_drops']}/{A['raw_n']} 筆 ⇒ 189 不是輸入行數強制")
    emit("A4-2", classify(A["ws_a42"]), True, False,
         witnesses=A["ws_a42"]["witnesses"], population=A["pairs_scanned"],
         union_is_derived=(A["union"] == A["v2_n"] + A["v3_n"] - A["overlap"]),
         note="union=309 由 overlap=0 恆等式導出 ⇒ 與第一項是同一個事件")
    emit("A4-3", "EVALUABLE" if A["builder_drops"] > 0 else "UNRESOLVED", True, False,
         bank_range=[A["date_min"], A["date_max"]],
         raw_range=[A["raw_date_min"], A["raw_date_max"]],
         matches_pinned=(A["date_min"] == "2023-05-07" and A["date_max"] == "2024-08-10"))
    emit("A4-4", "EVALUABLE", True, False,
         v3=[A["v3_medium"], A["v3_hard"]], v2=[A["v2_medium"], A["v2_hard"]],
         merged=[A["merged_medium"], A["merged_hard"]],
         merged_matches_r460=(A["merged_medium"] == 207 and A["merged_hard"] == 102))
    emit("B3-1", "EVALUABLE", False, False, no_emitter=True, **repro["B3-1"])
    emit("B3-2", "EVALUABLE", False, False, no_emitter=True, readings=r32, **repro["B3-2"])
    emit("B3-3", "EVALUABLE", True,
         not (B33["runs_scanned"] == 29 and B33["arms_over"] == 15 and B33["runs_over"] == 9),
         **{k: v for k, v in B33.items() if k != "unresolved_arms"})
    emit("G2-3", "EVALUABLE", CG["ran"] and CG["rc"] in (0, 1, 2), False,
         rc=CG["rc"], counts=CG["counts"])
    emit("G3", "EVALUABLE", CG["ran"],
         not (CG["docs"] == 138 and CG["cert_headings"] == 6),
         docs_today=CG["docs"], headings_today=CG["cert_headings"], counts_today=CG["counts"])
    emit("G4", "EVALUABLE", True, False, **G4)
    emit("G6", "FORCED_GREEN" if G6["self_declared_forced"] else "EVALUABLE", True, False,
         witnesses=0, population=G6["cert_blob_lines"], **G6)

    if LIVE_READS > 0:
        broken.append("BROKEN_LIVE_READ")

    hits = {"class": sum(1 for k in out if out[k]["clazz"] == PRED_CLASS[k]),
            "exec": sum(1 for k in out if out[k]["executable_as_pinned"] == PRED_EXEC[k]),
            "stale": sum(1 for k in out if out[k]["premise_stale"] == PRED_STALE[k]),
            "repro": sum(1 for k in PRED_REPRO if repro[k]["reproducible"] == PRED_REPRO[k])}
    verdict = broken[0] if broken else "OK"
    return {"verdict": verdict, "broken": broken, "clauses": out, "live_reads": LIVE_READS,
            "counts": dict(Counter(v["clazz"] for v in out.values())),
            "calibration": cal, "pred_hits": hits, "blind": False,
            "unresolved_arms": B33["unresolved_arms"], "a4_raw": A, "repro": repro}


# ── 自檢
FAILS: list[str] = []


def ck(name: str, cond: bool, extra: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  ' + extra) if extra else ''}")
    if not cond:
        FAILS.append(name)


def _with(mut: str):
    global MUTANT
    old, MUTANT = MUTANT, mut
    try:
        return census()
    except Exception as e:                              # 偵測器不准 crash 收場
        return {"verdict": f"CRASH:{type(e).__name__}", "broken": ["CRASH"], "clauses": {},
                "live_reads": LIVE_READS, "counts": {}, "pred_hits": {}}
    finally:
        MUTANT = old


def selftest() -> int:
    print("[乾淨基線]")
    r = census()
    ck("A 乾淨 verdict==OK", r["verdict"] == "OK", r["verdict"])
    ck("B live_reads==0", r["live_reads"] == 0)
    ck("C 11 條都掃到（pin 抓得到）", len(r["clauses"]) == 11 and
       all(c["pin_found"] for c in r["clauses"].values()))
    ck("D witness 雙向校準", r["calibration"]["ok"], json.dumps(r["calibration"]))
    ck("E 每條四欄齊全", all({"clazz", "executable_as_pinned", "premise_stale", "intent"}
                            <= set(c) for c in r["clauses"].values()))
    ck("F 沒有未解析的臂（分母全找得到）", not r["unresolved_arms"], str(r["unresolved_arms"])[:120])
    ck("G intent 只有 evidence/guard",
       {c["intent"] for c in r["clauses"].values()} <= {"evidence", "guard"})
    print("[植入缺陷]")
    m1 = _with("M1_no_live_guard")
    ck("M1 拿掉 G-LIVE ⇒ BROKEN_LIVE_READ（不是 crash）",
       m1["verdict"] == "BROKEN_LIVE_READ" and m1["live_reads"] > 0,
       f"{m1['verdict']} reads={m1['live_reads']}")
    m2 = _with("M2_empty_targets")
    ck("M2 掃描目標清空、擋門留著 ⇒ UNSCANNED", m2["verdict"] == "UNSCANNED", m2["verdict"])
    m3 = _with("M3_empty_targets_no_guard")
    ck("M3 清空＋拿掉 UNSCANNED 擋門 ⇒ 不再叫（M2 的負對照）",
       m3["verdict"] == "OK" and m3["clauses"]["B3-3"]["runs_scanned"] == 0, m3["verdict"])
    m4 = _with("M4_scanner_always_zero")
    ck("M4 witness 掃描器恆吐 0 ⇒ 校準擋門要叫",
       m4["verdict"] == "BROKEN_WITNESS_CALIBRATION", m4["verdict"])
    m5 = _with("M5_pin_break")
    ck("M5 pin 不在原文 ⇒ BROKEN_PIN_MISSING", m5["verdict"] == "BROKEN_PIN_MISSING", m5["verdict"])
    m6 = _with("M6_denominator_drops_tasks")
    ck("M6 分母清單少了 'tasks' ⇒ 型二安靜量不到 ⇒ BROKEN_ARM_ACCOUNTING",
       m6["verdict"] == "BROKEN_ARM_ACCOUNTING",
       f"{m6['verdict']} over={m6['clauses'].get('B3-3', {}).get('arms_over')}")
    m7 = _with("M7_claim_corrupted")
    ck("M7 宣稱值 +10pp ⇒ 容差比較要翻 False（乾淨時兩條都 True，容差在真資料上沒被行使）",
       m7["repro"]["B3-1"]["reproducible"] is False and
       m7["repro"]["B3-2"]["reproducible"] is False and
       r["repro"]["B3-1"]["reproducible"] is True,
       f"M7 delta={m7['repro']['B3-2']['delta_pp']} / clean delta={r['repro']['B3-2']['delta_pp']}")
    print(f"\nselftest {'SELFTEST_PASS' if not FAILS else 'SELFTEST_FAIL'} {len(FAILS)} fail")
    return 1 if FAILS else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = census()
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"verdict {r['verdict']}  live_reads={r['live_reads']}  clauses={len(r['clauses'])}")
    print(f"  counts={r['counts']}")
    h = r["pred_hits"]
    print(f"  事前預測命中 class={h['class']}/11  exec={h['exec']}/11  stale={h['stale']}/11  "
          f"repro={h['repro']}/2   （blind=False）")
    for cid, c in r["clauses"].items():
        flags = []
        if not c["executable_as_pinned"]:
            flags.append("⚠不可執行")
        if c["premise_stale"]:
            flags.append("⚠正文過期")
        miss = [n for n, p, v in (("class", PRED_CLASS[cid], c["clazz"]),
                                  ("exec", PRED_EXEC[cid], c["executable_as_pinned"]),
                                  ("stale", PRED_STALE[cid], c["premise_stale"])) if p != v]
        print(f"  {cid:<5} {c['clazz']:<12} intent={c['intent']:<8} "
              f"{' '.join(flags)}{('   MISS:' + ','.join(miss)) if miss else ''}")
    return 0 if r["verdict"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
