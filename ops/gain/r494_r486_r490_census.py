#!/usr/bin/env python3
"""R494：R486–R490 判決函式的可證偽性普查（**結構半邊**）。

判準先行：DECISION_20260905_R494_R486_R490_FALSIFIABILITY_CENSUS_PREREG.md（commit 8d64c82）。

⚠ 本尺只答 R491 詞彙的 IDENTITY 半邊（邏輯上可不可能為假），**不是** EMPIRICAL 半邊
（那份閘道快照翻不翻得動）。判 EVALUABLE 只准讀成「結構上可證偽」。

分類（判準 §二，不准事後加格）：
    REACHABLE / UNREACHABLE          單一判決字串
    FORCED_GREEN / EVALUABLE / UNSCANNED   一條指名判決的預測

用法：
  python3 ops/gain/r494_r486_r490_census.py --selftest
  python3 ops/gain/r494_r486_r490_census.py --json ops/gain/data/r494_census.json
"""
from __future__ import annotations
import argparse, ast, itertools, json, os, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LIVE = "g_r461_lcb3_three_arm"
_live_reads = 0

_real_open = open


def _guarded_open(file, *a, **k):          # G-LIVE：唯一的開檔入口
    global _live_reads
    if LIVE in str(file):
        _live_reads += 1
        raise RuntimeError(f"G-LIVE: 拒絕碰主 run 的路徑：{file}")
    return _real_open(file, *a, **k)


import builtins                                                    # noqa: E402
builtins.open = _guarded_open

from ops.gain import r486_longreq_attrib as R486                   # noqa: E402
from ops.gain import r487_concurrency_tax as R487                  # noqa: E402
from ops.gain import r487_ts_semantics as R487TS                   # noqa: E402
from ops.gain import r488_pointwise_concurrency as R488            # noqa: E402
from ops.gain import r489_permutation_placebo as R489              # noqa: E402
from ops.gain import r490_leveled_placebo as R490                  # noqa: E402

N_TOOLS_EXPECTED = 6          # 判準 §四.G-SCAN（見 §報告的 gate_ambiguity 註記）
MIN_VERDICTS_SCANNED = 20


def _mut() -> str:
    """突變體旗標，**呼叫時**才讀（絕不在 import 時讀）。"""
    return os.environ.get("R494_MUTANT", "")


# ─────────────────────────────────────────────── G-VOCAB：用 ast 逐字取詞彙表
def _src(rel: str) -> str:
    return _guarded_open(ROOT / rel, encoding="utf-8").read()


def vocab_from_returns(rel: str, fn_name: str) -> set:
    """該函式所有 `return "..."` 的字串字面（含三元／dict 查表的字串常數）。"""
    tree = ast.parse(_src(rel))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return):
                    for s in ast.walk(sub):
                        if isinstance(s, ast.Constant) and isinstance(s.value, str) \
                                and s.value.isupper() and len(s.value) > 3:
                            out.add(s.value)
    return out


def vocab_from_constant(rel: str, name: str) -> set:
    tree = ast.parse(_src(rel))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    try:
                        return set(ast.literal_eval(node.value))
                    except Exception:
                        return set()
    return set()


# ─────────────────────────────────────────────── 輸入產生器（每欄位獨立設定）
G_N = (0, 49, 50, 200)
G_COV = (0.0, 0.49, 0.5, 0.9, 1.0)
G_RATIO = (None, 0.5, 0.8, 0.95, 1.0, 1.05, 1.3, 2.0)
G_CI = (None, 0.3, 0.85, 0.9, 0.95, 1.0, 1.02, 1.1, 1.16, 3.0)


def _real_grid(rng, extra=()):
    d = {"n_hi": rng.choice(G_N), "n_lo": rng.choice(G_N),
         "coverage": rng.choice(G_COV), "ratio": rng.choice(G_RATIO),
         "ci_lo": rng.choice(G_CI), "ci_hi": rng.choice(G_CI)}
    for k in extra:
        d[k] = rng.choice(G_CI)
    return d


def gen_r487_p1(rng):
    return (rng.choice(G_RATIO), rng.choice(G_CI), rng.choice(G_CI),
            rng.choice((0, 2, 3, 9)), rng.choice((0, 29, 30, 99)), rng.choice((0, 29, 30, 99)))


def gen_r487_p2(rng):
    v = (None, 0.0, 0.05, 0.1, 0.4, 0.9)
    return (rng.choice(v), rng.choice(v))


def gen_r487_p3(rng):
    return (rng.choice((0.0, 1.0, 5.0, 20.0)), rng.choice((-1.0, 0.0, 1.0, 10.0)),
            rng.choice((0.001, 0.04, 0.06, 0.9)), rng.choice((0, 4, 5, 50)))


def gen_r487ts(rng):
    v = (0.0, 0.01, 0.02, 0.03, 0.2, 0.5)
    return ({"ts": rng.choice(v), "ts_plus_lat": rng.choice(v), "ts_minus_lat": rng.choice(v)},)


def gen_r488(rng):
    real = _real_grid(rng)
    n_p = rng.choice((0, 1, 3))
    placebos = [{"coverage": rng.choice(G_COV), "ratio": rng.choice(G_RATIO)}
                for _ in range(n_p)]
    return (real, placebos)


def gen_r489(rng):
    real = _real_grid(rng)
    pl = {"coverage": rng.choice(G_COV), "n_hi": rng.choice(G_N), "n_lo": rng.choice(G_N),
          "abs_log_max": rng.choice((None, 0.0, 0.05, 0.3, 2.0)),
          "abs_log_median": rng.choice((None, 0.0, 0.05, 0.3))}
    return (real, pl, rng.choice((True, False)))


def _rung(rng, block):
    return {"block_s": block, "role": rng.choice(("gate", "positive_control", None)),
            "p": rng.choice((None, 0.001, 0.04, 0.2)),
            "coverage_min": rng.choice(G_COV),
            "n_hi_min": rng.choice(G_N), "n_lo_min": rng.choice(G_N),
            "measurable": rng.choice((True, False)),
            "reproduction_frac": rng.choice((None, 0.0, 0.3, 0.6, 0.99)),
            "abs_log_max": rng.choice((None, 0.0, 0.05, 0.3, 2.0)),
            "agreement": rng.choice((0.0, 0.4, 0.6, 1.0))}


def gen_r490(rng):
    real = _real_grid(rng)
    real["abs_log"] = rng.choice((0.0, 0.05, 0.3, 1.0))
    blocks = rng.choice(((60.0, 1800.0), (1800.0,), (60.0,), (60.0, 900.0, 1800.0)))
    ladder = [_rung(rng, b) for b in blocks]
    anchors = {"anchor_a_ok": rng.choice((True, False)),
               "anchor_b_ok": rng.choice((True, False))}
    return (real, ladder, anchors)


# ─────────────────────────────────────────────── r486：沒有純判決函式，用合成 rows 驅動
def _row(ts, lat_ms, model="gemma-4-12b-it-qat", ip="10.0.0.1", ctok=300, sc=200):
    return {"ts": ts, "latency_ms": lat_ms, "model": model, "client_ip": ip,
            "completion_tokens": ctok, "status_code": sc, "path": "/v1/chat/completions"}


def gen_r486(rng):
    n = rng.choice((1, 6, 12))
    rows, t = [], 0.0
    for i in range(n):
        overlap = rng.choice((True, False))
        t = t + (rng.choice((10.0, 400.0)) if not overlap else 1.0)
        lat = rng.choice((1000.0, 700_000.0, 900_000.0))
        rows.append(_row(t, lat,
                         model=rng.choice(("gemma-4-12b-it-qat", "qwen/qwen3.6-35b-a3b")),
                         ip=rng.choice(("10.0.0.1", "10.0.0.9")),
                         ctok=rng.choice((10, 300))))
    events = [{"ts": rng.choice((0.0, 500.0)), "event": rng.choice(("loaded", "unloaded"))}
              for _ in range(rng.choice((0, 8)))]
    return (rows, events, rng.choice(("start", "end")))


def call_r486(rows, events, hypo):
    """回傳該次呼叫吐出的所有判決字串（六個 VERDICT_KEYS）。"""
    out = R486.analyze_under(rows, events, hypo)
    return {str(out.get(k)) for k in R486.VERDICT_KEYS if out.get(k) is not None}



# ─────────────────────────────────────────── 刻意構造反例（memory：恆等式宣稱要撐得住）
# R491 的第一版把 4 條誤標 IDENTITY，被測檔自己的夾具卻造得出反例。本尺第一版**重犯同一個
# bug**（見 DECISION §K）：隨機產生器抽不到，不等於到不了。任何 UNREACHABLE 在報出來之前，
# 一律要先被這一關的手工輸入嘗試推翻。舊量無條件保留成 unreachable_sampling_only。
def _r490_rung(b, role, p, frac):
    return {"block_s": b, "role": role, "p": p, "reproduction_frac": frac,
            "coverage_min": 0.9, "n_hi_min": 200, "n_lo_min": 200,
            "measurable": True, "abs_log_max": 0.05, "agreement": 0.4}


_R490_REAL = {"n_hi": 200, "n_lo": 200, "coverage": 0.9, "ratio": 1.3,
              "ci_lo": 1.05, "ci_hi": 1.5, "abs_log": 0.3}
_R490_ANCH = {"anchor_a_ok": True, "anchor_b_ok": True}
_R490_GATE = [_r490_rung(1800.0, "gate", 0.001, 0.3)]

CONSTRUCTIVE = {
    ("r490_leveled_placebo", "decide"): [
        (_R490_REAL, [_r490_rung(1800.0, "gate", 0.001, 0.3),
                      _r490_rung(60.0, "gate", 0.2, 0.3)], _R490_ANCH),
        (_R490_REAL, _R490_GATE, _R490_ANCH),
        (dict(_R490_REAL, ci_lo=1.02, ci_hi=1.10), _R490_GATE, _R490_ANCH),
        (dict(_R490_REAL, ci_lo=0.3, ci_hi=0.8, ratio=0.5), _R490_GATE, _R490_ANCH),
    ],
}


def constructive_hits(key, fn) -> dict:
    """手工輸入實際到達的判決 -> witness。到不了就不記（不准假裝到得了）。"""
    seen = {}
    for args in CONSTRUCTIVE.get(key, []):
        if _mut() == "M4_DROP_CONSTRUCTIVE":
            break
        try:
            v = fn(*args)
        except Exception:
            continue
        for s in (v if isinstance(v, set) else {v}):
            seen.setdefault(s, "constructed:" + repr(args)[:300])
    return seen


# ─────────────────────────────────────────────── 母體
TOOLS = [
    ("r486_longreq_attrib", "ops/gain/r486_longreq_attrib.py", None,
     [("analyze_under", gen_r486, call_r486)]),
    ("r487_concurrency_tax", "ops/gain/r487_concurrency_tax.py", None,
     [("verdict_p1", gen_r487_p1, R487.verdict_p1),
      ("verdict_p2", gen_r487_p2, R487.verdict_p2),
      ("verdict_p3", gen_r487_p3, R487.verdict_p3)]),
    ("r487_ts_semantics", "ops/gain/r487_ts_semantics.py", None,
     [("decide", gen_r487ts, R487TS.decide)]),
    ("r488_pointwise_concurrency", "ops/gain/r488_pointwise_concurrency.py", None,
     [("decide", gen_r488, R488.decide)]),
    ("r489_permutation_placebo", "ops/gain/r489_permutation_placebo.py", "VERDICTS",
     [("decide", gen_r489, R489.decide)]),
    ("r490_leveled_placebo", "ops/gain/r490_leveled_placebo.py", "VERDICTS",
     [("decide", gen_r490, R490.decide)]),
]

TRIALS = 40000


def reachable(fn, gen, rng, trials=TRIALS):
    """回傳 {判決字串: witness 輸入}。多回傳值的（r486）併集。"""
    seen = {}
    for _ in range(trials):
        args = gen(rng)
        try:
            v = fn(*args)
        except Exception:
            continue
        vs = v if isinstance(v, set) else {v}
        for s in vs:
            if s not in seen:
                seen[s] = repr(args)[:400]
        if _mut() == "M1_STOP_AFTER_FIRST" and seen:
            break
    return seen


def classify_prediction(predicted: str, reach: set) -> str:
    if _mut() == "M2_ALWAYS_EVALUABLE":
        return "EVALUABLE"
    if _mut() == "M3_ALWAYS_FORCED":
        return "FORCED_GREEN"
    if predicted is None:
        return "UNSCANNED"
    if not reach:
        return "UNSCANNED"
    return "EVALUABLE" if (reach - {predicted}) else "FORCED_GREEN"


# R486–R490 六份 PREREG 裡指名判決字串的預測（判準 §一）
PREDICTIONS = [
    # (id, 工具, 函式, 預測的判決, intent)
    ("R486-P1",  "r486_longreq_attrib", "analyze_under", "QUEUE_RULED_OUT", "evidence"),
    ("R486-P1b", "r486_longreq_attrib", "analyze_under", "FORCED_GREEN_FLAG", "guard"),
    ("R486-P2",  "r486_longreq_attrib", "analyze_under", "RELOAD_CONTRIBUTES", "evidence"),
    ("R486-P4",  "r486_longreq_attrib", "analyze_under", "SERIAL_NO_QUEUE", "evidence"),
    ("R487-P1",  "r487_concurrency_tax", "verdict_p1", "CONCURRENCY_TAXES", "evidence"),
    ("R487-P2",  "r487_concurrency_tax", "verdict_p2", "DURATION_BIAS_PRESENT", "guard"),
    ("R487-P3",  "r487_concurrency_tax", "verdict_p3", "RELOAD_AS_CHANCE", "evidence"),
    ("R487B-P1", "r487_ts_semantics", "decide", "TS_IS_START", "evidence"),
    ("R488-P1",  "r488_pointwise_concurrency", "decide", "CONCURRENCY_TAXES", "evidence"),
    ("R488-P2",  "r488_pointwise_concurrency", "decide", "PERIOD_CONFOUNDED", "evidence"),
    ("R489-P2",  "r489_permutation_placebo", "decide", "CONCURRENCY_TAXES", "evidence"),
    ("R490-P7",  "r490_leveled_placebo", "decide", "SCALE_DEPENDENT_TAX", "evidence"),
]


def census(seed: int = 494) -> dict:
    live_at_entry = _live_reads       # 只算「本次普查期間」的 G-LIVE 觸發次數
    rng = random.Random(seed)
    out = {"tools": {}, "verdicts": [], "predictions": [], "vocab_diffs": {}}
    per_fn = {}
    for tool, rel, const, fns in TOOLS:
        out["tools"][tool] = {}
        for fn_name, gen, fn in fns:
            reach = reachable(fn, gen, rng)
            sampled_only = set(reach)
            reach.update(constructive_hits((tool, fn_name), fn))
            v_ret = vocab_from_returns(rel, fn_name)
            v_const = vocab_from_constant(rel, const) if const else set()
            declared = v_ret | v_const
            # G-VOCAB：兩個來源的差集要具名印出來，不准安靜取聯集就算數
            out["vocab_diffs"][f"{tool}.{fn_name}"] = {
                "in_const_not_in_returns": sorted(v_const - v_ret),
                "in_returns_not_in_const": sorted(v_ret - v_const) if const else [],
            }
            per_fn[(tool, fn_name)] = set(reach)
            out["tools"][tool][fn_name] = {
                "n_declared": len(declared), "n_reachable": len(reach),
                "reachable": sorted(reach),
                "unreachable": sorted(declared - set(reach)),
                # 舊量：只靠隨機產生器時的結果，無條件保留（判準 §六.5）
                "unreachable_sampling_only": sorted(declared - sampled_only),
                "found_only_by_construction": sorted(set(reach) - sampled_only),
            }
            for v in sorted(declared | set(reach)):
                out["verdicts"].append({
                    "tool": tool, "fn": fn_name, "verdict": v,
                    "cell": "REACHABLE" if v in reach else "UNREACHABLE",
                    "witness": reach.get(v),
                    "declared": v in declared,
                })
    for pid, tool, fn_name, pred, intent in PREDICTIONS:
        reach = per_fn.get((tool, fn_name), set())
        cell = classify_prediction(pred, reach)
        out["predictions"].append({
            "id": pid, "tool": tool, "fn": fn_name, "predicted": pred,
            "intent": intent, "cell": cell,
            "predicted_is_reachable": pred in reach,
            "n_other_reachable": len(reach - {pred}),
        })

    # 雙向校準（判準 §三）
    def _const_fn(x):
        return "ALWAYS_SAME"

    def _free_fn(x):
        return "A_VERDICT" if x > 0 else "B_VERDICT"

    g = lambda r: (r.choice((-1, 1)),)
    c_pos = classify_prediction("ALWAYS_SAME", set(reachable(_const_fn, g, random.Random(1), 200)))
    c_neg = classify_prediction("A_VERDICT", set(reachable(_free_fn, g, random.Random(1), 200)))
    out["calibration"] = {"C_POS": c_pos, "C_NEG": c_neg}

    n_tools = len(out["tools"])
    n_v = len(out["verdicts"])
    out["n_tools_scanned"] = n_tools
    out["n_functions_scanned"] = sum(len(v) for v in out["tools"].values())
    out["n_verdicts_scanned"] = n_v
    out["n_unreachable"] = sum(1 for v in out["verdicts"] if v["cell"] == "UNREACHABLE")
    out["n_unreachable_sampling_only"] = sum(
        len(d["unreachable_sampling_only"]) for fns in out["tools"].values() for d in fns.values())
    out["n_found_only_by_construction"] = sum(
        len(d["found_only_by_construction"]) for fns in out["tools"].values() for d in fns.values())
    out["n_forced_green"] = sum(1 for p in out["predictions"] if p["cell"] == "FORCED_GREEN")
    out["live_reads"] = _live_reads - live_at_entry
    out["trials_per_fn"] = TRIALS
    # 判準 §四 G-SCAN 的「6」寫得有歧義（表格 6 列 = 6 支工具，但其中一列有 3 個函式）
    out["gate_ambiguity_note"] = ("判準 §四 G-SCAN 寫 n_functions_scanned==6；§一 表格是 6 列工具、"
                                  "共 8 個函式。兩個數字都報，擋門照『工具數』套用。")
    if c_pos != "FORCED_GREEN" or c_neg != "EVALUABLE":
        out["verdict"] = "BROKEN"                      # 推翻條件 1
    elif n_tools != N_TOOLS_EXPECTED or n_v < MIN_VERDICTS_SCANNED:
        out["verdict"] = "UNSCANNED"                   # 推翻條件 2 / G-SCAN
    else:
        out["verdict"] = "CENSUS_OK"
    return out


# ─────────────────────────────────────────────── 自檢
_fails = []


def _ck(name, cond, detail=""):
    if not cond:
        _fails.append(f"{name} {detail}")


def selftest() -> int:
    _fails.clear()
    # A：分類器本身
    _ck("A1", classify_prediction("X", {"X", "Y"}) == "EVALUABLE")
    _ck("A2", classify_prediction("X", {"X"}) == "FORCED_GREEN")
    _ck("A3", classify_prediction("X", set()) == "UNSCANNED")
    _ck("A4", classify_prediction(None, {"X"}) == "UNSCANNED")
    # B：G-VOCAB 用 ast 逐字取，不是抄的
    v = vocab_from_returns("ops/gain/r487_concurrency_tax.py", "verdict_p1")
    _ck("B1_returns", {"UNSCANNED", "CONCURRENCY_TAXES", "NO_TAX", "UNRESOLVED"} <= v, sorted(v))
    vc = vocab_from_constant("ops/gain/r489_permutation_placebo.py", "VERDICTS")
    _ck("B2_const", "PERIOD_CONFOUNDED" in vc, sorted(vc))
    _ck("B3_no_bleed", "SCALE_DEPENDENT_TAX" not in v)
    # C：G-LIVE 真的擋
    try:
        _guarded_open(f"runs/{LIVE}/rows.jsonl")
        _ck("C1_glive", False, "沒擋住")
    except RuntimeError:
        _ck("C1_glive", True)
    # D：雙向校準
    r = census(seed=7)
    _ck("D1_cpos", r["calibration"]["C_POS"] == "FORCED_GREEN", r["calibration"])
    _ck("D2_cneg", r["calibration"]["C_NEG"] == "EVALUABLE", r["calibration"])
    # E：已知可達的判決真的被搜到（承重牆；若這條紅了代表產生器太窄）
    rng = random.Random(11)
    _ck("E1_p1", {"UNSCANNED", "CONCURRENCY_TAXES", "NO_TAX", "UNRESOLVED"}
        <= set(reachable(R487.verdict_p1, gen_r487_p1, rng)))
    _ck("E2_ts", len(reachable(R487TS.decide, gen_r487ts, rng)) >= 2)
    # E3 承重牆：r490 那四條只有構造關找得到；拿掉構造關必須回到 UNREACHABLE
    k490 = ("r490_leveled_placebo", "decide")
    hits = set(constructive_hits(k490, R490.decide))
    _ck("E3_construct", {"SCALE_DEPENDENT_TAX", "CONCURRENCY_TAXES",
                         "TAXES_BELOW_MARGIN", "SPEEDUP_ANOMALY"} <= hits, sorted(hits))
    d490 = r["tools"]["r490_leveled_placebo"]["decide"]
    _ck("E4_old_kept", len(d490["unreachable_sampling_only"]) >= 1
        and d490["unreachable"] == [], d490["unreachable_sampling_only"])
    # F：live_reads 必須 0（普查跑完之後）
    _ck("F1_live", r["live_reads"] == 0, r["live_reads"])
    print("selftest:", "all passed" if not _fails else f"FAILED {_fails}")
    return 0 if not _fails else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--seed", type=int, default=494)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = census(a.seed)
    if a.json:
        _real_open(ROOT / a.json, "w", encoding="utf-8").write(json.dumps(r, indent=2, ensure_ascii=False))
    print(f"verdict={r['verdict']}  tools={r['n_tools_scanned']}  fns={r['n_functions_scanned']}  "
          f"verdicts={r['n_verdicts_scanned']}  unreachable={r['n_unreachable']}  "
          f"forced_green={r['n_forced_green']}  live_reads={r['live_reads']}")
    print(f"[舊量，非判定] 只靠隨機產生器時 unreachable={r['n_unreachable_sampling_only']}"
          f"；靠手工構造才找到的判決={r['n_found_only_by_construction']}")
    print("calibration:", r["calibration"])
    for t, fns in r["tools"].items():
        for fn, d in fns.items():
            print(f"  {t}.{fn}: reachable={d['n_reachable']} unreachable={d['unreachable']}")
    for p in r["predictions"]:
        print(f"  {p['id']:9s} {p['cell']:12s} intent={p['intent']:8s} "
              f"pred={p['predicted']} reachable={p['predicted_is_reachable']} others={p['n_other_reachable']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
