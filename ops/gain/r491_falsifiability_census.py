#!/usr/bin/env python3
"""R491：對 R484／R485 的每條預註冊判準問「它有可能是假的嗎？」——零 API、純本機。

判準先行：`DECISION_20260905_R491_R484_R485_FALSIFIABILITY_CENSUS_PREREG.md`
（commit 7116db6，本檔之前）。分類、對照、擋門、預測全在那裡，本檔只是編碼它。

分類（DECISION §二，不准事後加格）：
    EVALUABLE               證偽方向在真資料的某個切法下實際出現過（具名 witness）
    FORCED_GREEN_IDENTITY   合成輸入下證偽方向也到不了 ⇒ 恆等式候選，且真資料 witness=0
    FORCED_GREEN_EMPIRICAL  合成到得了、真資料 >= MIN_WINDOWS 個切法下 witness=0
    UNRESOLVED              兩者皆無
    UNSCANNED               切法數 < MIN_WINDOWS

⚠ IDENTITY 與 EMPIRICAL 收官不准混用：前者邏輯上不可能為假，後者只是**這份資料**翻不動。

用法：
  python3 ops/gain/r491_falsifiability_census.py --selftest
  python3 ops/gain/r491_falsifiability_census.py --calls runs/g_r461_lcb3_three_arm/calls.jsonl \
      --json ops/gain/data/r491_census.json
"""
from __future__ import annotations
import argparse, ast, hashlib, json, os, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ops.gain import r484_time_attribution as R484          # noqa: E402
from ops.gain import r485_runaway_strata as R485            # noqa: E402

MIN_WINDOWS = 8            # DECISION §三（本檔唯一新增的可調參數）
SYNTH_TRIALS = 400         # 合成可達性的抽樣次數


def _mut() -> str:
    """突變體旗標，**呼叫時**才讀（絕不在 import 時讀）。"""
    return os.environ.get("R491_MUTANT", "")


# ──────────────────────────────────────────────────────────────────
# B2：被引用的原始碼運算式，用 ast 逐字取出（不准自己改寫一份）
# ──────────────────────────────────────────────────────────────────
SOURCE_CLAIMS = {
    # 正對照：R484 把 busy<=wall 釘成恆等式斷言（附錄 A.6）
    "r484_identity_assert": ("ops/gain/r484_time_attribution.py", "analyse",
                             "assert busy <= wall + 1e-6"),
    # R484 P-0 的三分判決線
    "r484_p0_server_bound": ("ops/gain/r484_time_attribution.py", "analyse",
                             'if ratio >= P0_SERVER_BOUND:'),
    # R485 P-1/P-2 共用的 CR 判決線
    "r485_cr_hi": ("ops/gain/r485_runaway_strata.py", "cr_verdict", "if mx >= CR_HI:"),
    # 負對照：R485 P-3 的自由統計量
    "r485_task_hi": ("ops/gain/r485_runaway_strata.py", "top_task_share",
                     "elif obs >= TASK_HI_MULT * null:"),
    # R485 P-5（guard）
    "r485_retry": ("ops/gain/r485_runaway_strata.py", "retry_verdict", "else (mx is not None and mx > 1)"),
}


def _source_segment(relpath: str, funcname: str) -> str | None:
    src = (ROOT / relpath).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == funcname:
            return ast.get_source_segment(src, node)
    return None


def check_source_claims() -> dict:
    """B2：釘死的字面還在不在原始碼裡。不在 ⇒ SOURCE_DRIFT（不是「證明成立」）。"""
    out = {}
    for key, (rel, fn, literal) in SOURCE_CLAIMS.items():
        if _mut() == "M1_SOURCE_CHECK_TOOTHLESS":
            out[key] = True                     # 不看原始碼就宣稱在＝沒牙齒
            continue
        seg = _source_segment(rel, fn)
        out[key] = bool(seg) and (literal in seg)
    return out


# ──────────────────────────────────────────────────────────────────
# 資料
# ──────────────────────────────────────────────────────────────────
def load_calls(path) -> list:
    recs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass            # run 活著 ⇒ 最後一行可能寫到一半
    return recs


def windows(calls: list) -> list:
    """真資料的多種切法：等寬時間視窗 + 等量分段。切法越多，FORCED_EMPIRICAL 越難成立。"""
    cs = [c for c in calls if c.get("ts_ms") is not None]
    cs.sort(key=lambda c: c["ts_ms"])
    out = []
    if len(cs) < 4:
        return out
    t0, t1 = cs[0]["ts_ms"], cs[-1]["ts_ms"]
    for w in (4, 6, 8, 12, 16):
        if t1 <= t0:
            break
        step = (t1 - t0) / w
        for i in range(w):
            lo, hi = t0 + i * step, t0 + (i + 1) * step
            seg = [c for c in cs if lo <= c["ts_ms"] <= hi]
            if len(seg) >= 4:
                out.append((f"time{w}_{i}", seg))
    for k in (4, 6, 8, 12, 16):
        n = max(1, len(cs) // k)
        for i in range(k):
            seg = cs[i * n:(i + 1) * n]
            if len(seg) >= 4:
                out.append((f"count{k}_{i}", seg))
    if _mut() == "M2_SINGLE_WINDOW":
        out = out[:1]
    return out


# ──────────────────────────────────────────────────────────────────
# 合成可達性：證偽方向在**構造得出來的**輸入下到不到得了
# ──────────────────────────────────────────────────────────────────
def _synth_calls(rng, n, gap_scale, lat_scale, personas=6, arms=3, tasks=40):
    """合成 calls：gap_scale 控制 client 端空檔，lat_scale 控制伺服器延遲。"""
    out, t = [], 1_000_000
    for i in range(n):
        lat = max(1.0, rng.expovariate(1.0 / lat_scale))
        gap = max(0.0, rng.expovariate(1.0 / gap_scale)) if gap_scale > 0 else 0.0
        t += gap
        out.append({
            "ts_ms": t, "latency_ms": lat, "ok": True, "attempt": 1,
            "usage": {"completion_tokens": 100},
            "role": "gen", "timeout_s": 600,
            "agent_id": f"p{rng.randrange(personas)}",
            "meta": {"task_id": f"t{rng.randrange(tasks)}",
                     "arm": ["OFF", "CONFORM", "OFF5"][rng.randrange(arms)]},
        })
        t += lat                       # ts_ms = 起始時刻語意
    return out


def _adversarial(rng) -> list:
    """**針對每個證偽方向刻意構造**的輸入。

    ⚠ 這是本檔第一版的缺陷修正（見 DECISION 附錄）：原本只用隨機合成輸入判「到不到得了」，
    但隨機生成器碰不到的區域會被誤判成恆等式——`R485_P3` 的 `TASK_FLAT` 就是這樣被誤標成
    `FORCED_GREEN_IDENTITY`，而被測檔**自己的** selftest 夾具 `f8f` 明明造得出來。
    ⇒ **恆等式的宣稱必須撐得住「刻意去構造反例」**，不是「隨機抽樣沒抽到」。
    """
    out = []
    n = 360          # 6 personas -> 60/格 (>30)；3 arms -> 120/格 (>100)
    # 1) 完全均勻的延遲＋題目輪流 -> 集中度統計量的 FLAT 方向
    cs = []
    t = 1_000_000
    for i in range(n):
        cs.append({"ts_ms": t, "latency_ms": 1000.0, "ok": True, "attempt": 1,
                   "role": "gen", "timeout_s": 600,
                   "agent_id": f"p{i % 6}", "usage": {"completion_tokens": 100},
                   "meta": {"task_id": f"t{i % 30}", "arm": ["OFF", "CONFORM", "OFF5"][i % 3]}})
        t += 1000.0
    out.append(("uniform_flat", cs))
    # 2) 單一題目／單一人格吃掉幾乎全部時間 -> CONCENTRATED 方向
    cs2 = [dict(c, meta=dict(c["meta"])) for c in cs]
    for c in cs2[:20]:
        c["latency_ms"] = 500000.0
        c["meta"]["task_id"] = "hot"
        c["agent_id"] = "p0"
        c["meta"]["arm"] = "OFF"
    out.append(("hot_concentrated", cs2))
    # 3) 巨大 client 端空檔 -> CLIENT_GAP_BOUND 方向
    cs3, t = [], 1_000_000
    for i in range(n):
        cs3.append({"ts_ms": t, "latency_ms": 10.0, "ok": True, "attempt": 1,
                    "role": "gen", "timeout_s": 600,
                    "agent_id": f"p{i % 6}", "usage": {"completion_tokens": 100},
                    "meta": {"task_id": f"t{i % 30}", "arm": ["OFF", "CONFORM", "OFF5"][i % 3]}})
        t += 100000.0
    out.append(("huge_gaps", cs3))
    # 4) 吞吐隨時間惡化 -> ENDPOINT_DEGRADING 方向（逐桶 ms/tok 拉大）
    cs4, t = [], 1_000_000
    for i in range(300):
        hour = i // 50
        lat = 1000.0 * (1 + 3 * hour)
        cs4.append({"ts_ms": t, "latency_ms": lat, "ok": True, "attempt": 1,
                    "role": "gen", "timeout_s": 600,
                    "agent_id": f"p{i % 6}", "usage": {"completion_tokens": 100},
                    "meta": {"task_id": f"t{i % 30}", "arm": ["OFF", "CONFORM", "OFF5"][i % 3]}})
        t += lat + 3_600_000 / 50
    out.append(("degrading", cs4))
    # 5) 全部 attempt==1 -> RETRIES_NOT_LOGGED 方向
    cs5 = [dict(c, attempt=1) for c in cs]
    out.append(("no_retries", cs5))
    return out


def synth_reachable(fn, rng) -> set:
    """把判決函式餵隨機合成 + **刻意構造**的輸入，回傳「到得了的判決集合」。"""
    seen = set()
    for _ in range(SYNTH_TRIALS):
        gap = rng.choice([0.0, 1.0, 50.0, 500.0, 5000.0, 50000.0])
        lat = rng.choice([10.0, 100.0, 1000.0, 10000.0])
        cs = _synth_calls(rng, rng.randrange(30, 120), gap, lat)
        try:
            v = fn(cs)
        except Exception:
            v = "BROKEN"
        if v:
            seen.add(v)
    if _mut() != "M7_NO_ADVERSARIAL":
        for _name, cs in _adversarial(rng):
            try:
                v = fn(cs)
            except Exception:
                v = "BROKEN"
            if v:
                seen.add(v)
    return seen


# ──────────────────────────────────────────────────────────────────
# 被普查的八條預測：每條 = (取判決的函式, 證偽方向的判決集合, intent)
# ──────────────────────────────────────────────────────────────────
def _gen(cs):
    """R485 的母體＝`role=='gen'`（preflight 的 timeout_s 不同）。用被測檔自己的過濾器。"""
    return R485.gen_calls(cs)


def _p0(cs):
    return R484.analyse(cs).get("verdict")


def _p1_endpoint(cs):
    return (R484.analyse(cs).get("p1") or {}).get("verdict")


def _cr(keyfn, min_n):
    def f(cs):
        return R485.cr_verdict(R485.strata(_gen(cs), keyfn), min_n)[0]
    return f


def _task(cs):
    return R485.top_task_share(_gen(cs))["verdict"]


def _retry(cs):
    return R485.retry_verdict(_gen(cs))[0]


def _identity_busy_gt_wall(cs):
    """正對照：R484 釘成恆等式的那件事。回傳 VIOLATED / HOLDS。"""
    a = R484.analyse(cs)
    b, w = a.get("busy_ms"), a.get("wall_ms")
    if b is None or w is None:
        return None
    return "VIOLATED" if b > w + 1e-6 else "HOLDS"


PREDICTIONS = [
    # key, 標籤, 取判決的函式, 證偽方向, intent, 角色
    ("CTRL_POS", "正對照 R484 busy>wall（已知恆假）", _identity_busy_gt_wall,
     {"VIOLATED"}, "guard", "control"),
    ("CTRL_NEG", "負對照 R485 top_task_share（自由統計量）", _task,
     {"TASK_FLAT", "UNRESOLVED"}, "guard", "control"),
    ("R484_P0", "R484 P-0 busy/wall ⇒ SERVER_BOUND", _p0,
     {"CLIENT_GAP_BOUND", "MIXED"}, "evidence", "real"),
    ("R484_P1", "R484 P-1 端點退化", _p1_endpoint,
     {"ENDPOINT_DEGRADING"}, "evidence", "real"),
    ("R485_P1", "R485 P-1 人格集中度", _cr(lambda c: c.get("agent_id"), 30),
     {"CONCENTRATED"}, "evidence", "real"),
    ("R485_P2", "R485 P-2 臂集中度", _cr(lambda c: (c.get("meta") or {}).get("arm"), 100),
     {"CONCENTRATED"}, "evidence", "real"),
    ("R485_P3", "R485 P-3 題目集中度", _task,
     {"TASK_FLAT"}, "evidence", "real"),
    ("R485_P5", "R485 P-5 retry 落盤（guard）", _retry,
     {"RETRIES_NOT_LOGGED"}, "guard", "real"),
]


def classify(real_verdicts: set, synth_verdicts: set, falsifying: set,
             n_windows: int) -> str:
    """DECISION §二 的分類。順序固定，不准事後加格。"""
    if _mut() == "M4_ALWAYS_FORCED":
        return "FORCED_GREEN_IDENTITY"       # 什麼都判 FORCED ⇒ 負對照必須抓到
    if _mut() == "M5_ALWAYS_EVALUABLE":
        return "EVALUABLE"                   # 什麼都判可證偽 ⇒ 正對照必須抓到
    if n_windows < MIN_WINDOWS and _mut() != "M3_SKIP_MIN_WINDOWS":
        return "UNSCANNED"
    hit_real = real_verdicts & falsifying
    hit_synth = synth_verdicts & falsifying
    if hit_real:
        return "EVALUABLE"
    if not hit_synth:
        return "FORCED_GREEN_IDENTITY"
    return "FORCED_GREEN_EMPIRICAL"


REQUIRED_FIELDS = {
    "ts_ms":        lambda c: c.get("ts_ms") is not None,
    "latency_ms":   lambda c: c.get("latency_ms") is not None,
    "attempt":      lambda c: c.get("attempt") is not None,
    "meta.task_id": lambda c: (c.get("meta") or {}).get("task_id") is not None,
    "agent_id":     lambda c: c.get("agent_id") is not None,
    "meta.arm":     lambda c: (c.get("meta") or {}).get("arm") is not None,
    "role":         lambda c: c.get("role") is not None,
}


def schema_gauge(calls: list) -> dict:
    """前置尺：真資料到底有沒有普查讀的那些欄位。

    r699：selftest 的夾具由本檔自己的 `_synth_calls` 造 ⇒ 它**結構上**驗不到真資料的
    schema。欄位若整欄缺席，分層會塌成一格、CR 被迫恆等於 1 ⇒ 判決被強制，
    但外觀跟「真的很平」一模一樣（「安靜量不到」第二型）。
    """
    n = len(calls)
    out = {"n": n, "present": {}, "distinct": {}}
    for name, ok in REQUIRED_FIELDS.items():
        if _mut() == "M6_SCHEMA_GAUGE_TOOTHLESS":
            out["present"][name] = 1.0
            continue
        out["present"][name] = (sum(1 for c in calls if ok(c)) / n) if n else 0.0
    for name, keyfn in (("meta.task_id", lambda c: (c.get("meta") or {}).get("task_id")),
                        ("agent_id", lambda c: c.get("agent_id")),
                        ("meta.arm", lambda c: (c.get("meta") or {}).get("arm"))):
        out["distinct"][name] = len({keyfn(c) for c in calls if keyfn(c) is not None})
    out["missing"] = sorted(k for k, v in out["present"].items() if v < 0.99)
    out["collapsed"] = sorted(k for k, v in out["distinct"].items() if v < 2)
    return out


def census(calls: list, seed: int = 491) -> dict:
    rng = random.Random(seed)
    wins = windows(calls)
    src_ok = check_source_claims()
    sch = schema_gauge(calls)
    out = {"n_calls": len(calls), "n_windows": len(wins),
           "min_windows": MIN_WINDOWS, "source_claims": src_ok,
           "schema": sch, "cells": {}, "blockers": []}

    if not all(src_ok.values()):
        out["blockers"].append("SOURCE_DRIFT")
    # 欄位整欄缺席／分層塌成一格 ⇒ 那些格的判決是被 schema 強制的，不是量出來的
    if sch["missing"]:
        out["blockers"].append("SCHEMA_MISSING:" + ",".join(sch["missing"]))
    if sch["collapsed"]:
        out["blockers"].append("SCHEMA_COLLAPSED:" + ",".join(sch["collapsed"]))

    for key, label, fn, falsifying, intent, role in PREDICTIONS:
        real = set()
        witnesses = []
        for wname, seg in wins:
            try:
                v = fn(seg)
            except Exception:
                v = None
            if v:
                real.add(v)
                if v in falsifying:
                    witnesses.append(wname)
        try:
            full = fn(calls)
        except Exception:
            full = None
        if full:
            real.add(full)
            if full in falsifying:
                witnesses.append("FULL")
        synth = synth_reachable(fn, rng)
        cell = classify(real, synth, falsifying, len(wins))
        # B1：恆等式成立卻有 witness ⇒ CONTRADICTION
        if cell == "FORCED_GREEN_IDENTITY" and witnesses:
            out["blockers"].append(f"CONTRADICTION:{key}")
        out["cells"][key] = {
            "label": label, "intent": intent, "role": role,
            "full_verdict": full, "cell": cell,
            "real_verdicts": sorted(real), "synth_verdicts": sorted(synth),
            "falsifying": sorted(falsifying),
            "n_witnesses": len(witnesses), "witnesses": witnesses[:5],
        }

    # B4：雙向校準
    pos = out["cells"]["CTRL_POS"]["cell"]
    neg = out["cells"]["CTRL_NEG"]["cell"]
    out["calibration"] = {"positive": pos, "negative": neg}
    if pos != "FORCED_GREEN_IDENTITY" or neg != "EVALUABLE":
        out["blockers"].append("CENSUS_BROKEN")

    # B5：擋門觸發時不吐任何 FORCED_*
    if out["blockers"]:
        out["verdict"] = "CENSUS_BROKEN"
        for k, v in out["cells"].items():
            if v["cell"].startswith("FORCED"):
                v["cell"] = "WITHHELD"
    else:
        out["verdict"] = "CENSUS_OK"

    reals = [v for k, v in out["cells"].items() if v["role"] == "real"]
    out["n_real_predictions"] = len(reals)
    out["n_forced"] = sum(1 for v in reals if v["cell"].startswith("FORCED"))
    out["n_evaluable"] = sum(1 for v in reals if v["cell"] == "EVALUABLE")
    return out


# ──────────────────────────────────────────────────────────────────
# selftest：夾具**不共用**被測檔的 helper，每個輸入獨立設定
# ──────────────────────────────────────────────────────────────────
FAILS: list[str] = []


def _ck(name, cond, detail=""):
    if not cond:
        FAILS.append(f"{name} {detail}")


def selftest() -> int:
    FAILS.clear()
    rng = random.Random(7)

    # A：分類函式的每一格都到得了（不留不可達的格）
    _ck("A1_evaluable", classify({"X"}, {"X"}, {"X"}, 99) == "EVALUABLE")
    _ck("A2_identity", classify({"Y"}, {"Y"}, {"X"}, 99) == "FORCED_GREEN_IDENTITY")
    _ck("A3_empirical", classify({"Y"}, {"X", "Y"}, {"X"}, 99) == "FORCED_GREEN_EMPIRICAL")
    _ck("A4_unscanned", classify({"X"}, {"X"}, {"X"}, 1) == "UNSCANNED")

    # B：正對照——恆等式在合成輸入下也違反不了
    _ck("B1_pos_identity", _identity_busy_gt_wall(_synth_calls(rng, 60, 100.0, 500.0)) == "HOLDS")
    seen = synth_reachable(_identity_busy_gt_wall, rng)
    _ck("B2_pos_never_violated", "VIOLATED" not in seen, str(seen))

    # C：負對照——自由統計量在合成輸入下兩個方向都到得了
    seen_t = synth_reachable(_task, rng)
    _ck("C1_neg_two_sided", len(seen_t & {"TASK_FLAT", "TASK_CONCENTRATED", "UNRESOLVED"}) >= 2,
        str(seen_t))

    # D：切法數——窗口切法必須遠多於 MIN_WINDOWS，否則普查沒解析度
    cs = _synth_calls(rng, 200, 100.0, 500.0)
    _ck("D1_windows", len(windows(cs)) >= MIN_WINDOWS, str(len(windows(cs))))

    # E：B2 的字面在真原始碼裡逐字找得到
    src = check_source_claims()
    for k, v in src.items():
        _ck(f"E_{k}", v, "literal not found in source")

    # F：擋門——校準壞掉時不吐任何 FORCED_*
    fake = {"cells": {"Z": {"cell": "FORCED_GREEN_IDENTITY", "role": "real"}},
            "blockers": ["CENSUS_BROKEN"]}
    for v in fake["cells"].values():
        if fake["blockers"] and v["cell"].startswith("FORCED"):
            v["cell"] = "WITHHELD"
    _ck("F1_withheld", fake["cells"]["Z"]["cell"] == "WITHHELD")

    # G：schema 前置尺兩個方向都要動（夾具獨立設定每個輸入）
    good = [{"ts_ms": 1, "latency_ms": 2, "attempt": 1, "role": "gen", "agent_id": "p1",
             "meta": {"task_id": "t1", "arm": "OFF"}},
            {"ts_ms": 3, "latency_ms": 2, "attempt": 1, "role": "gen", "agent_id": "p2",
             "meta": {"task_id": "t2", "arm": "CONFORM"}}]
    _ck("G1_good_schema", schema_gauge(good)["missing"] == [], str(schema_gauge(good)))
    bad = [dict(c) for c in good]
    for c in bad:
        c.pop("agent_id")                                       # persona 整欄拔掉
    _ck("G2_missing_detected", "agent_id" in schema_gauge(bad)["missing"])
    coll = [dict(c) for c in good]
    for c in coll:
        c["meta"] = dict(c["meta"], arm="OFF")                  # 臂塌成一格
    _ck("G3_collapse_detected", "meta.arm" in schema_gauge(coll)["collapsed"])

    # H：刻意構造要真的到得了各證偽方向（這是 IDENTITY 宣稱的承重牆）
    _ck("H1_task_flat_reachable", "TASK_FLAT" in synth_reachable(_task, random.Random(1)))
    _ck("H2_client_bound_reachable", "CLIENT_GAP_BOUND" in synth_reachable(_p0, random.Random(2)))
    _ck("H3_degrading_reachable",
        "ENDPOINT_DEGRADING" in synth_reachable(_p1_endpoint, random.Random(3)))
    _ck("H4_persona_conc_reachable",
        "CONCENTRATED" in synth_reachable(_cr(lambda c: c.get("agent_id"), 30), random.Random(4)))
    # H5 反方向：關掉刻意構造，TASK_FLAT 就回到「看起來像恆等式」＝證明它承重
    os.environ["R491_MUTANT"] = "M7_NO_ADVERSARIAL"
    try:
        _ck("H5_adversarial_load_bearing",
            "TASK_FLAT" not in synth_reachable(_task, random.Random(1)))
    finally:
        os.environ.pop("R491_MUTANT", None)

    print("\n".join(f"FAIL {f}" for f in FAILS) or "selftest all passed")
    return 1 if FAILS else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    calls = load_calls(a.calls)
    blob = pathlib.Path(a.calls).read_bytes()
    res = census(calls)
    res["calls_path"] = a.calls
    res["calls_sha256_8"] = hashlib.sha256(blob).hexdigest()[:8]
    res["calls_lines"] = len(blob.splitlines())
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps({k: res[k] for k in
                      ("verdict", "n_calls", "n_windows", "calibration",
                       "n_real_predictions", "n_forced", "n_evaluable", "blockers")},
                     indent=2, ensure_ascii=False))
    for k, v in res["cells"].items():
        print(f"  {k:10s} {v['role']:7s} {v['intent']:8s} {v['cell']:24s} "
              f"full={v['full_verdict']} witnesses={v['n_witnesses']}")


if __name__ == "__main__":
    main()
