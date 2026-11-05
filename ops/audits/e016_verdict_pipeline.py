#!/usr/bin/env python3
"""e016_failed_step_ablation 判決管線（round 903 預先登記；packet §3–§4 的機械化）。

純 stdlib；讀 /srv/vlab/runs/e016_failed_step_ablation 的格子（cell.json + score.json，
跳 .infra-*）；配對 McNemar（與 report.py 同式）＋ Holm（family=3）＋成本紅線＋
目標格 pg_list_ops → 五態判定（UNKNOWN / COST_BREACH / MECHANISM_CONFIRMED /
NO_MECHANISM / UNRESOLVED；優先序見 packet §4）。

用法：
<<<<<<< HEAD
  python3 e016_verdict_pipeline.py --selftest      # 合成資料自測（6 態＋邊界）
=======
  python3 e016_verdict_pipeline.py --selftest      # 合成資料自測（10 組：五態＋成本 UNKNOWN＋完賽缺分＋數值）
>>>>>>> auto/argon
  python3 e016_verdict_pipeline.py                 # 讀正式 run 目錄
exit：0＝已判定（含五態）、10＝run 未完成（格子未齊）、20＝UNKNOWN（infra>20%）
"""
from __future__ import annotations

import argparse, json, math, pathlib, sys

ARMS = ("A", "C", "C-nf")
TARGET = "pg_list_ops"
N_CELLS = 102
ALPHA = 0.05


def mcnemar_p(b: int, c: int) -> float:
    """雙邊精確 McNemar（與 report.py 同式）：b＝x-only、c＝y-only、n=b+c。"""
    if b + c == 0:
        return 1.0
    n = b + c
    s = sum(math.comb(n, i) for i in range(0, min(b, c) + 1))
    return min(1.0, 2.0 * s / (2.0 ** n))


def holm(pvals: list[float], alpha: float = ALPHA) -> list[bool]:
    """Holm–Bonferroni step-down：依 p 升序逐一對 α/(m-rank) 門檻，首次未過即停；
    回傳與輸入對齊的「顯著」布林。"""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    out = [False] * m
    for rank, idx in enumerate(order):
        if pvals[idx] <= alpha / (m - rank):
            out[idx] = True
        else:
            break
    return out


def pairwise(rows: list[dict], x: str, y: str) -> dict:
    b = sum(1 for t in _pairs(rows, x, y) if t[0] is True and t[1] is False)
    c = sum(1 for t in _pairs(rows, x, y) if t[0] is False and t[1] is True)
    n_pairs = sum(1 for t in _pairs(rows, x, y))
    return {"x": x, "y": y, "pairs": n_pairs, "x_only": b, "y_only": c,
            "p_raw": mcnemar_p(b, c)}


def _pairs(rows: list[dict], x: str, y: str) -> list[tuple[bool, bool]]:
    m = {r["task"]: r for r in rows if r["arm"] == x}
    out = []
    for r in rows:
        if r["arm"] == y and r["task"] in m:
            out.append((bool(m[r["task"]]["pass"]), bool(r["pass"])))
    return out


def cost(rows: list[dict], arm: str) -> dict:
    rs = [r for r in rows if r["arm"] == arm]
<<<<<<< HEAD
    passed = sum(1 for r in rs if r["pass"])
    calls = sum(int(r.get("calls") or 0) for r in rs)
    tok = sum(int(r.get("tok") or 0) for r in rs)
    return {"arm": arm, "n": len(rs), "pass": passed, "calls": calls, "tok": tok,
            "calls_per_success": (calls / passed) if passed else None,
            "tokens_per_success": (tok / passed) if passed else None}
=======
    # 成本 UNKNOWN 的格（calls/tok=None）不靜默當 0：單獨計數、只對已知格聚合。
    known = [r for r in rs if r.get("calls") is not None and r.get("tok") is not None]
    passed_known = sum(1 for r in known if r["pass"])
    calls = sum(int(r["calls"]) for r in known)
    tok = sum(int(r["tok"]) for r in known)
    return {"arm": arm, "n": len(rs), "pass": sum(1 for r in rs if r["pass"]),
            "cost_unknown_n": len(rs) - len(known),
            "calls": calls, "tok": tok,
            "calls_per_success": (calls / passed_known) if passed_known else None,
            "tokens_per_success": (tok / passed_known) if passed_known else None}
>>>>>>> auto/argon


def decide(rows: list[dict], total_cells: int, missing: int) -> dict:
    if missing > 0.20 * N_CELLS:
        return {"state": "UNKNOWN", "why": f"infra/缺分 {missing}/{N_CELLS} > 20%（e015 先例：未測，非負結果）"}
    pairs = [pairwise(rows, a, b) for a, b in (("A", "C"), ("A", "C-nf"), ("C", "C-nf"))]
    sig = holm([p["p_raw"] for p in pairs])
    for p, s in zip(pairs, sig):
        p["holm_significant"] = s
    costs = {a: cost(rows, a) for a in ARMS}
<<<<<<< HEAD
=======
    cost_unknown = sum(costs[a]["cost_unknown_n"] for a in ARMS)
    if cost_unknown > 0:
        # 任何一格成本 UNKNOWN ⇒ 成本判定 UNKNOWN（不是 0、不是通過；未測≠負結果）。
        # 優於 COST_BREACH：有 UNKNOWN 在場時紅線既不能說「過」也不能說「破」。
        return {"state": "UNKNOWN",
                "why": (f"成本 UNKNOWN：{cost_unknown}/{len(rows)} 格成本欄位缺失"
                        "（cell.json.metrics 缺 model_calls/input_tokens/output_tokens 或 cell.json 缺失；"
                        "成本紅線不可評——未測≠0、≠通過）"),
                "pairs": pairs, "costs": costs}
>>>>>>> auto/argon
    ac, acnf, ccnf = pairs
    a_ok = costs["A"]["calls_per_success"]
    cost_breach = []
    for arm in ("C", "C-nf"):
        if a_ok and costs[arm]["calls_per_success"] and costs[arm]["calls_per_success"] > 2 * a_ok:
            cost_breach.append(f"{arm}/A calls {costs[arm]['calls_per_success']:.2f} > 2×{a_ok:.2f}")
        at = costs["A"]["tokens_per_success"]
        if at and costs[arm]["tokens_per_success"] and costs[arm]["tokens_per_success"] > 2 * at:
            cost_breach.append(f"{arm}/A tokens {costs[arm]['tokens_per_success']:.0f} > 2×{at:.0f}")
    if cost_breach:
        return {"state": "COST_BREACH", "why": "成本紅線（e014 §5 先例，優先於機制判定）：" + "; ".join(cost_breach),
                "pairs": pairs, "costs": costs}
    tgt = {r["arm"]: r["pass"] for r in rows if r["task"] == TARGET}
    mech = (ac["holm_significant"] and ac["y_only"] > ac["x_only"]
            and ccnf["holm_significant"] and ccnf["x_only"] > ccnf["y_only"]
            and not acnf["holm_significant"]
            and tgt.get("C") is True and tgt.get("C-nf") is False)
    if mech:
        return {"state": "MECHANISM_CONFIRMED",
                "why": "A<C 顯著、C>C-nf 顯著（消融去掉贏）、A≈C-nf、目標格 pg_list_ops C 贏/C-nf 掛（packet §4）",
                "pairs": pairs, "costs": costs, "target": tgt}
    if not ccnf["holm_significant"]:
        return {"state": "NO_MECHANISM",
                "why": "C vs C-nf 未顯著（開關無可測效應；packet §4：不改產品、非「無用」結論、1 rep H-12）",
                "pairs": pairs, "costs": costs, "target": tgt}
    return {"state": "UNRESOLVED",
            "why": "其餘組合（含方向反轉；無『有害』預登記結論，AMEND1 先例）",
            "pairs": pairs, "costs": costs, "target": tgt}


def load(runs_root: pathlib.Path, exp: str) -> tuple[list[dict], int, int]:
    root = runs_root / exp
    if not root.is_dir():
        sys.exit(f"NO RUN DIR: {root}")
    rows, missing = [], 0
    for arm in ARMS:
        for d in sorted(root.iterdir()):
            if not (d.is_dir() and d.name.endswith(f"-{arm}-r1")):
                continue
            task = d.name.split("-", 2)[1]
            score = d / "score.json"
            if not score.exists():
                missing += 1
                continue
            s = json.loads(score.read_text())
            if s.get("pass") is None:
                missing += 1
                continue
<<<<<<< HEAD
            rows.append({"task": task, "arm": arm, "pass": bool(s["pass"]),
                         "calls": s.get("model_calls"), "tok": s.get("tokens")})
=======
            calls, tok = _cell_cost(d)
            rows.append({"task": task, "arm": arm, "pass": bool(s["pass"]),
                         "calls": calls, "tok": tok})
>>>>>>> auto/argon
    total = sum(1 for d in root.iterdir() if d.is_dir() and not d.name.startswith(".") and d.name.endswith("-r1"))
    return rows, total, missing


<<<<<<< HEAD
def run(runs_root: pathlib.Path, exp: str) -> dict:
    rows, total, missing = load(runs_root, exp)
    
=======
def _cell_cost(cell_dir: pathlib.Path) -> tuple[int | None, int | None]:
    """成本在 cell.json.metrics（model_calls / input_tokens / output_tokens）；
    score.json 只有 pass / tests_*，沒有成本欄位（舊版從 score.json 讀⇒恆 None⇒
    成本紅線形同沒在檢查；round 954 監督者 11/04 點名修復）。
    任一必要欄位缺失／非整數／cell.json 缺失 ⇒ (None, None)＝該格成本 UNKNOWN。"""
    p = cell_dir / "cell.json"
    if not p.exists():
        return None, None
    try:
        m = json.loads(p.read_text()).get("metrics")
    except (OSError, json.JSONDecodeError):
        return None, None
    if not isinstance(m, dict):
        return None, None
    calls, itok, otok = m.get("model_calls"), m.get("input_tokens"), m.get("output_tokens")
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in (calls, itok, otok)):
        return None, None
    return calls, itok + otok


def missing_total(total: int, missing_scored: int) -> int:
    """缺合格分的格（滿 N_CELLS）＝「有目錄但無有效分」＋「連目錄都沒有」。
    senior 11/04 #1.2：run 完賽（進 done/）後不以目錄數 <102 阻斷，而是把缺合格
    -r1 的格全數記入 missing 交 decide()（missing > 20% ⇒ UNKNOWN；未測≠通過）。"""
    return missing_scored + max(0, N_CELLS - total)


def run(runs_root: pathlib.Path, exp: str) -> dict:
    rows, total, missing = load(runs_root, exp)

>>>>>>> auto/argon
    # Job completion check logic
    done_file = "/srv/vlab/done/16_e016_failed_step_ablation.json"
    is_done = pathlib.Path(done_file).exists() or (total >= N_CELLS)

    if total < N_CELLS and not is_done:
<<<<<<< HEAD
        print(f"INCOMPLETE: {total}/{N_CELLS} 格未完成（等 job 結束再判決）")
        sys.exit(10)
=======
        print(f"INCOMPLETE: 只到 {total}/{N_CELLS} 格在位（等 job 結束再判決）")
        sys.exit(10)
    missing = missing_total(total, missing)   # 無目錄的格也計缺分（senior 11/04 #1.2）
>>>>>>> auto/argon
    v = decide(rows, total, missing)
    out = pathlib.Path(__file__).parent / f"{exp}_verdict.json"
    out.write_text(json.dumps(v, ensure_ascii=False, indent=2))
    print(f"{v['state']}  ({v['why']})  -> {out}")
    for p in v.get("pairs", []):
<<<<<<< HEAD
        print(f"  {p['x']} vs {p['y']}: pairs={p['pairs']} {p['x']}_only={p['x_only']} {p['y']}_only={p['y']}_only={p['y_only']} p_raw={p['p_raw']:.4f} holm={'SIG' if p['holm_significant'] else 'ns'}")
=======
        print(f"  {p['x']} vs {p['y']}: pairs={p['pairs']} {p['x']}_only={p['x_only']} {p['y']}_only={p['y_only']} p_raw={p['p_raw']:.4f} holm={'SIG' if p['holm_significant'] else 'ns'}")
>>>>>>> auto/argon
    for a in ARMS:
        c = v.get("costs", {}).get(a, {})
        print(f"  cost {a}: n={c.get('n')} pass={c.get('pass')} calls/success={c.get('calls_per_success')} tok/success={c.get('tokens_per_success')}")
    if "target" in v:
        print(f"  target {TARGET}: {v['target']}")
    sys.exit(20 if v["state"] == "UNKNOWN" else 0)
    return v


def selftest() -> None:
    T = [f"pg_t{i:02d}" for i in range(33)] + [TARGET]

    def rows_from(spec: dict, calls: dict | None = None):
        calls = calls or {a: 10 for a in ARMS}
        out = []
        for i, t in enumerate(T):
            for a in ARMS:
                out.append({"task": t, "arm": a, "pass": bool(spec[a][i]),
                            "calls": calls[a], "tok": calls[a] * 100})
        return out

    # 1) MECHANISM_CONFIRMED：A 10/34、C = A+7（含 target，index 33）、C-nf = A
    base = [False] * 34
    for i in range(10):
        base[i] = True
    c_arm = base[:]; c_arm[10:17] = [True] * 7; c_arm[33] = True   # target 只在 C 贏
    v = decide(rows_from({"A": base, "C": c_arm, "C-nf": base}), 102, 0)
    assert v["state"] == "MECHANISM_CONFIRMED", v
    # 2) NO_MECHANISM：C == C-nf（開關無效應）、A vs C 未顯著
    c2 = base[:]; c2[10] = True; c2[11] = False
    v = decide(rows_from({"A": base, "C": c2, "C-nf": c2}), 102, 0)
    assert v["state"] == "NO_MECHANISM", v
    # 3) COST_BREACH：C 成本 3×A
    v = decide(rows_from({"A": base, "C": c2, "C-nf": c2}, {"A": 10, "C": 30, "C-nf": 10}), 102, 0)
    assert v["state"] == "COST_BREACH", v
    # 4) UNKNOWN：infra 21/102 > 20%
    v = decide(rows_from({"A": base, "C": c2, "C-nf": c2}), 102, 21)
    assert v["state"] == "UNKNOWN", v
    # 5) UNRESOLVED：C vs C-nf 顯著但方向反轉（C-nf 贏）
    cnf = base[:]; cnf[10:17] = [True] * 7
    v = decide(rows_from({"A": base, "C": base, "C-nf": cnf}), 102, 0)
    assert v["state"] == "UNRESOLVED", v
    # 6) A 零通過：成本紅線不誤觸發（cost/success 未定義）
    zero = [False] * 34
    v = decide(rows_from({"A": zero, "C": c2, "C-nf": c2}), 102, 0)
    assert v["state"] in ("NO_MECHANISM", "UNRESOLVED"), v
    # 7) McNemar/Holm 數值對拍（手算）
    assert mcnemar_p(0, 7) == 2 * 1 / 128 and abs(mcnemar_p(0, 7) - 0.015625) < 1e-12
    assert mcnemar_p(3, 3) == 1.0
    assert holm([0.015625, 0.015625, 1.0]) == [True, True, False]
    assert holm([0.03, 0.03, 0.03]) == [False, False, False]
<<<<<<< HEAD
    print("ALL OK（7 組自測：五態＋零通過邊界＋McNemar/Holm 數值）")
=======
    # 8) 成本 UNKNOWN：任一格成本欄位缺失 ⇒ 成本判定 UNKNOWN（不是 0、不是通過）
    r8 = rows_from({"A": base, "C": c2, "C-nf": c2})
    r8[1]["calls"] = None; r8[1]["tok"] = None   # C 首格成本未知
    v = decide(r8, 102, 0)
    assert v["state"] == "UNKNOWN" and "成本" in v["why"], v
    # 9) 成本 UNKNOWN 優於 COST_BREACH：有 UNKNOWN 在場，紅線既不能說「過」也不能說「破」
    r9 = rows_from({"A": base, "C": c2, "C-nf": c2}, {"A": 10, "C": 99, "C-nf": 10})
    r9[1]["calls"] = None; r9[1]["tok"] = None
    v = decide(r9, 102, 0)
    assert v["state"] == "UNKNOWN" and "成本" in v["why"], v
    # 10) 完賽缺分：無目錄的格也計入 missing（senior 11/04 #1.2：缺分 > 20% ⇒ UNKNOWN，
    #     不得對缺格靜默出裁決）
    assert missing_total(102, 0) == 0
    assert missing_total(98, 0) == 4      # 4 格連 -r1 目錄都沒有
    assert missing_total(80, 2) == 24     # 22 格無目錄＋2 格無分
    assert missing_total(90, 15) == 27    # 12 格無目錄＋15 格無分
    assert missing_total(105, 3) == 3     # total>N_CELLS（重試命名）不出負數
    v = decide(rows_from({"A": base, "C": c2, "C-nf": c2}), 102, missing_total(80, 2))
    assert v["state"] == "UNKNOWN" and "缺分" in v["why"], v
    print("ALL OK（10 組自測：五態＋零通過邊界＋成本 UNKNOWN 兩態＋完賽缺分計數＋McNemar/Holm 數值）")
>>>>>>> auto/argon


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--runs-root", default="/srv/vlab/runs")
    ap.add_argument("--exp", default="e016_failed_step_ablation")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        sys.exit(0)
    run(pathlib.Path(a.runs_root), a.exp)
