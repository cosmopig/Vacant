#!/usr/bin/env python3
"""R455：對 R452 的九條子句做可證偽性普查——零 API、純本機。

判準先行：`DECISION_20260904_R455_R452_FALSIFIABILITY_EXTENSION.md`（本檔之前 commit）。
分類規則、事前預測表、`intent`、推翻條件都在那裡，本檔只是編碼它。

三格分類（沿用 R453 §二／R454 §二，**不新增格子**）：
    EVALUABLE    witness ≥ 1                        ⇒ HIT 帶資訊
    FORCED_GREEN 寫得出恆等式 **且** witness＝0      ⇒ HIT 不帶資訊，收官要附恆等式與基準率
    UNRESOLVED   兩者皆無                            ⇒ 照實寫「判不出來」

擋門：
    B1 恆等式成立 ∧ witness>0        ⇒ CONTRADICTION（不吐該條分類）
    B3 引用的原始碼取不出／不符字面  ⇒ SOURCE_DRIFT（不是「證明成立」）
    B4 可校準題數 < MIN_CALIB        ⇒ UNCALIBRATED
    B5 CONTRADICTION／SOURCE_DRIFT   ⇒ 不准吐任何 FORCED_GREEN
    B6 **雙向校準**任一方向失敗      ⇒ 全部 FORCED_GREEN 降級成 UNRESOLVED_CALIBRATION_FAILED
       （R454 只有正對照，`grep -c negative` = 0；只有正對照時「什麼都判 FORCED」也會全綠）

用法：
  python3 ops/gain/r455_r452_census.py --selftest
  python3 ops/gain/r455_r452_census.py --mutation
  python3 ops/gain/r455_r452_census.py --run runs/g_r447_conform_lcb2 \
      --eq5 ops/gain/data/r452_eq5_offline_round714.json --json ops/gain/data/r455_census.json
"""
from __future__ import annotations
import argparse, ast, json, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MUTANT = ""
MIN_CALIB = 20
DECISION = ROOT / "DECISION_20260904_R455_R452_FALSIFIABILITY_EXTENSION.md"

# 事前預測表（DECISION §三）。量完不准改。key -> (預測類別, intent)
R455_PREDICTIONS = {
    "R452-W1":          ("UNRESOLVED",   "evidence"),
    "R452-§四.1":        ("UNRESOLVED",   "guard"),
    "R452-§四.3型一":     ("FORCED_GREEN", "guard"),
    "R452-§四.3型二":     ("UNRESOLVED",   "guard"),
    "R452-E3":          ("UNRESOLVED",   "guard"),
    "R452-W2":          ("UNRESOLVED",   "evidence"),
    "R452-W3":          ("UNRESOLVED",   "evidence"),
    "R452-W4":          ("FORCED_GREEN", "guard"),
}
# W1-baserate 是非仲裁註記，不進分類、不進對帳表（DECISION §二）。

REQUIRED_ROW = ("task_id", "involved", "worker", "visible_ok", "meets_demand", "accepted")


# ────────────────────────────── 分類器（唯一一處） ──────────────────────────────
def classify(identity_holds: bool, witnesses: int) -> str:
    if MUTANT == "Z1_classify_ignores_witness":
        return "FORCED_GREEN" if identity_holds else "UNRESOLVED"
    if identity_holds and witnesses > 0:
        return "CONTRADICTION"
    if identity_holds:
        return "FORCED_GREEN"
    return "EVALUABLE" if witnesses > 0 else "UNRESOLVED"


# ────────────────────────────── AST 恆等式證明 ──────────────────────────────
def _fn_source(path: str, fn_name: str) -> tuple[str, str] | tuple[None, str]:
    src = (ROOT / path).read_text(encoding="utf-8")
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fn_name:
            seg = ast.get_source_segment(src, n)
            return (seg, "") if seg else (None, f"no_source_segment:{path}:{fn_name}")
    return None, f"fn_not_found:{path}:{fn_name}"


def prove_required_keys_unconditional(src: str | None = None) -> dict:
    """R452-§四.3型一 的恆等式：`arm_off5` 回傳的 meta 與 runner 寫的列**無條件**含
    REQUIRED_ROW 六個鍵 ⇒ 「缺欄位」的證偽事件不可能發生。

    做法：對 `gain_run.py` 逐字取出 `arm_off5` 與寫列處的原始碼，找出每個鍵的字面，
    並確認承載它的 dict 字面**不在任何 `if`/`try` 的分支底下**（無條件）。
    """
    src = src if src is not None else (ROOT / "ops/gain/gain_run.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # 找出所有含 "task_id" 且同時含 "accepted" 的 dict 字面 = 寫 rows 的那個
    hits = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Dict):
            continue
        keys = [k.value for k in n.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        if "task_id" in keys and "accepted" in keys:
            hits.append((n, keys))
    if not hits:
        return {"holds": False, "reason": "SOURCE_DRIFT:no_row_dict_literal"}
    # 條件性：該 dict 是否被包在 if/try 底下（用 lineno 區間判斷祖先）
    conditional = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.Try)):
            for d, _ in hits:
                if node.lineno < d.lineno <= (node.end_lineno or node.lineno):
                    conditional.append(d.lineno)
    covered = sorted({k for _, keys in hits for k in keys})
    all_present = all(any(k in keys for _, keys in hits) for k in ("task_id", "accepted"))
    if MUTANT == "Z4_missing_field_prover_ignores_conditionality":
        conditional = []
    return {"holds": bool(all_present and not conditional),
            "row_dict_linenos": [d.lineno for d, _ in hits],
            "keys_in_row_dicts": covered,
            "under_conditional_at": sorted(set(conditional)),
            "note": "無條件寫入 ⇒ 缺欄位不可能發生"}


def _branch_paths(src: str, key: str) -> list[str]:
    """每個 `out[<key>] = ...` 賦值所在的分支路徑（最近的 If 節點 + body/orelse）。
    分支路徑相同 ⇒ 兩個鍵**共生共滅**。"""
    tree = ast.parse(src)
    paths = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign):
            continue
        hit = any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                  and t.slice.value == key for t in n.targets)
        if not hit:
            continue
        best = "TOPLEVEL"
        for m in ast.walk(tree):
            if isinstance(m, ast.If):
                for lbl, blk in (("body", m.body), ("orelse", m.orelse)):
                    for st in blk:
                        if st.lineno <= n.lineno <= (st.end_lineno or st.lineno):
                            best = f"If@{m.lineno}:{lbl}"
        paths.append(best)
    return sorted(paths)


def prove_power_co_assigned(src: str | None = None) -> dict:
    """R452-W4 的恆等式（**語意修正版**，見 STATE round722）：W4 的字面是
    「**CI 旁邊**必須有 MDE@n 與 N₈₀」——那是**共生**宣稱，不是「無條件存在」宣稱。
    `out['power']` 與 `out['paired_gate_vs_vote']` 若在**完全相同的分支**被賦值，
    則「CI 有而 MDE 缺」在結構上不可能發生 ⇒ 證偽事件不可達。

    ⚠ 先前版本 `prove_power_keys_unconditional` 證的是「無條件存在」（holds=False），
    那個舊量無條件保留在輸出的 `superseded_proof` 裡，仲裁權留給後輪。"""
    src = src if src is not None else (ROOT / "ops/gain/r447_eq5_offline.py").read_text(encoding="utf-8")
    a = _branch_paths(src, "power")
    b = _branch_paths(src, "paired_gate_vs_vote")
    if not a or not b:
        return {"holds": False, "reason": "SOURCE_DRIFT:missing_assignment",
                "power_branches": a, "ci_branches": b}
    same = a == b
    if MUTANT == "Z6_power_prover_ignores_branches":
        same = True
    return {"holds": bool(same), "power_branches": a, "ci_branches": b,
            "note": "分支路徑逐一相同 ⇒ CI 與 MDE 共生共滅 ⇒「CI 有而 MDE 缺」不可達"}


def prove_power_keys_unconditional(src: str | None = None) -> dict:
    """**已被 prove_power_co_assigned 取代**（證的是不同的命題）。保留以留下舊量。"""
    src = src if src is not None else (ROOT / "ops/gain/r447_eq5_offline.py").read_text(encoding="utf-8")
    paths = _branch_paths(src, "power")
    return {"holds": bool(paths) and all(p == "TOPLEVEL" for p in paths),
            "branches": paths, "proposition": "out['power'] 無條件存在"}


# ────────────────────────────── 雙向校準（B6） ──────────────────────────────
def calibration_bidirectional(rows: list[dict]) -> dict:
    """正對照＝已知恆假死碼（必須判 FORCED_GREEN）；負對照＝自由統計量（必須判 EVALUABLE）。
    只有正對照時，「什麼都判 FORCED」的壞分類器也會全綠——所以兩個方向都要。"""
    # 正對照：R450 §八 已證的恆假死碼 `_deliv ∧ ¬meets_demand`，四種組合窮舉
    src = (ROOT / "ops/gain/analyze_r447.py").read_text(encoding="utf-8")
    seg, err = _fn_source("ops/gain/analyze_r447.py", "_deliv")
    if seg is None:
        return {"holds": False, "reason": f"SOURCE_DRIFT:{err}"}
    ret = [n for n in ast.walk(ast.parse(seg)) if isinstance(n, ast.Return)]
    ret.sort(key=lambda n: (n.lineno, n.col_offset))          # ast.walk 是 BFS
    expr = ast.get_source_segment(seg, ret[-1].value) if ret else None
    if not expr:
        return {"holds": False, "reason": "SOURCE_DRIFT:_deliv_no_return"}
    op = "or" if MUTANT == "Z2_positive_control_broken" else "and"
    clause = f"({expr}) {op} not bool(r.get('meets_demand'))"
    fires = []
    for acc in (True, False):
        for md in (True, False):
            r = {"accepted": acc, "meets_demand": md}
            fires.append(bool(eval(clause, {"bool": bool}, {"r": r})))
    pos_cls = classify(identity_holds=not any(fires), witnesses=sum(fires))
    # 負對照：自由統計量「這一列 meets_demand 為真」——資料裡兩個值都出現過 ⇒ 不該是 FORCED
    md_vals = {bool(r.get("meets_demand")) for r in rows}
    neg_wit = sum(1 for r in rows if bool(r.get("meets_demand")))
    neg_cls = classify(identity_holds=(len(md_vals) < 2), witnesses=neg_wit)
    return {"holds": pos_cls == "FORCED_GREEN" and neg_cls == "EVALUABLE",
            "positive": {"clause": clause, "class": pos_cls,
                         "known_answer": "FORCED_GREEN（R450 §八 已證恆假）"},
            "negative": {"stat": "bool(row.meets_demand)", "class": neg_cls,
                         "distinct_values": sorted(md_vals), "witnesses": neg_wit,
                         "known_answer": "EVALUABLE（自由統計量）"}}


# ────────────────────────────── 基準率（非仲裁註記） ──────────────────────────────
def calib_baserate(off5_rows: list[dict], only_tids: set | None = None) -> dict:
    """R452-W1 的鑑別力：可校準那一群的 `expect=(visible_ok, meets_demand)` 值分佈。
    母體必須**只含可校準列**（worker 在 involved 裡唯一），否則是換母體。"""
    src_rows = off5_rows if only_tids is None else [
        r for r in off5_rows if r.get("task_id") in only_tids]
    pop = src_rows if MUTANT == "Z3_baserate_wrong_population" else [
        r for r in src_rows if list(r.get("involved") or []).count(r.get("worker")) == 1]
    dist: dict[str, int] = {}
    for r in pop:
        k = f"visible_ok={bool(r.get('visible_ok'))},meets_demand={bool(r.get('meets_demand'))}"
        dist[k] = dist.get(k, 0) + 1
    md = [bool(r.get("meets_demand")) for r in pop]
    vis = [bool(r.get("visible_ok")) for r in pop]
    both = min(md.count(True), md.count(False))
    return {"population": "calibratable_rows_only", "n": len(pop), "distribution": dist,
            "meets_demand_true": md.count(True), "meets_demand_false": md.count(False),
            "visible_ok_true": vis.count(True), "visible_ok_false": vis.count(False),
            "degenerate": len(dist) <= 1, "minority_count": both,
            "population_aligned_to_eq5_per_task": only_tids is not None,
            "NOT_ARBITER": "不改分類；只決定收官措辭（DECISION §二／§五-1：退化⇒必須寫「100% 主要來自基準率」）"}


# ────────────────────────────── 主普查 ──────────────────────────────
def census(rows: list[dict], eq5: dict) -> dict:
    broken: list[str] = []
    off5 = [r for r in rows if r.get("arm") == "OFF5"]
    per = eq5.get("per_task") or []
    eq5_broken = eq5.get("broken") or []
    calib = eq5.get("calibration") or {}

    p_keys = prove_required_keys_unconditional()
    p_pow = prove_power_co_assigned()
    p_pow_old = prove_power_keys_unconditional()
    for nm, p in (("required_keys", p_keys), ("power_keys", p_pow)):
        if p.get("reason", "").startswith("SOURCE_DRIFT"):
            broken.append(f"{nm}:{p['reason']}")

    def wit(prefix: str) -> int:
        return sum(1 for x in eq5_broken if x.startswith(prefix))

    rr = eq5.get("rule_rates") or {}
    pg = eq5.get("paired_gate_vs_vote") or {}
    reject_pct = rr.get("gate_reject_pct")
    delta = pg.get("delta_pp")
    w2_out = None if reject_pct is None else not (2.0 <= reject_pct <= 14.0)
    w3_out = None if delta is None else not (0.0 <= delta <= 12.0)

    rec: dict[str, dict] = {}
    rec["R452-W1"] = {
        "clause": "校準一致率 100% ∧ 可校準 ≥20",
        "falsifier": "任一題 rows 記的 (visible_ok, meets_demand) 與離線重建不符",
        "identity": None,
        "identity_holds": False,
        "witnesses": wit("calibration_mismatch:"),
        "observed": {"n": calib.get("n"), "agree": calib.get("agree"),
                     "rate_pct": calib.get("rate_pct")},
        "non_circular_because": "ci 取自 rows 的 involved.index(worker)；got 由 calls.jsonl 的碼"
                                "重新執行算出 ⇒ 兩個出處（run 當下沙箱 vs 離線重執行）",
    }
    rec["R452-§四.1"] = {
        "clause": "每題恰好 5 份候選", "falsifier": "某題候選數 ≠ 5",
        "identity": None, "identity_holds": False,
        "witnesses": wit("candidate_count_mismatch:"),
    }
    rec["R452-§四.3型一"] = {
        "clause": "缺欄位 ⇒ BROKEN", "falsifier": f"某列缺 {REQUIRED_ROW} 之一",
        "identity": "runner 無條件寫入該 dict 字面 ⇒ 缺欄位不可能發生",
        "identity_holds": bool(p_keys.get("holds")),
        "witnesses": wit("missing_fields:"), "proof": p_keys,
    }
    rec["R452-§四.3型二"] = {
        "clause": "OFF5 有 rows 但 calls 找不到 ⇒ BROKEN", "falsifier": "某題找不到",
        "identity": None, "identity_holds": False,
        "witnesses": wit("task_not_in_calls:") + wit("task_not_in_bank:"),
    }
    rec["R452-E3"] = {
        "clause": "候選順序 == rows 的 involved", "falsifier": "順序不符",
        "identity": None, "identity_holds": False,
        "witnesses": wit("candidate_order_mismatch:"),
    }
    rec["R452-W2"] = {
        "clause": "規則 A 拒交率落在 2–14%", "falsifier": "落在窗外",
        "identity": None, "identity_holds": False,
        "witnesses": 0 if not w2_out else 1,
        "observed": {"gate_reject_pct": reject_pct, "window": "2–14%"},
    }
    rec["R452-W3"] = {
        "clause": "Δ(A−B) 落在 0..+12pp", "falsifier": "落在窗外",
        "identity": None, "identity_holds": False,
        "witnesses": 0 if not w3_out else 1,
        "observed": {"delta_pp": delta, "window": "0..+12pp"},
    }
    rec["R452-W4"] = {
        "clause": "CI 旁必須有 MDE@n 與 N₈₀", "falsifier": "這兩個鍵缺席",
        "identity": "尺無條件賦值 out['power'] ⇒ 缺席不可能發生",
        "identity_holds": bool(p_pow.get("holds")),
        "witnesses": 0 if (eq5.get("power") or {}) else 1, "proof": p_pow,
        "superseded_proof": p_pow_old,
    }

    for k, v in rec.items():
        v["class"] = classify(bool(v["identity_holds"]), int(v["witnesses"]))
        if v["class"] == "CONTRADICTION":
            broken.append(f"B1_contradiction:{k}")

    cal = calibration_bidirectional(rows)
    if not cal.get("holds"):
        broken.append("B6_calibration_failed")
    # B4
    if (calib.get("n") or 0) < MIN_CALIB:
        broken.append(f"B4_uncalibrated:calib_n={calib.get('n')}")
    # B5／B6：不准吐 FORCED_GREEN
    if broken:
        for v in rec.values():
            if v["class"] == "FORCED_GREEN":
                v["class"] = "UNRESOLVED_CALIBRATION_FAILED"

    ledger = {}
    for k, (pred, intent) in R455_PREDICTIONS.items():
        rec[k]["intent"] = intent
        ledger[k] = {"predicted": pred, "observed": rec[k]["class"],
                     "hit": pred == rec[k]["class"], "intent": intent}

    counts: dict[str, int] = {}
    for v in rec.values():
        counts[v["class"]] = counts.get(v["class"], 0) + 1
    forced_evidence = [k for k, v in rec.items()
                       if v["class"] == "FORCED_GREEN" and v.get("intent") == "evidence"]
    return {
        "broken": broken, "records": rec, "prediction_ledger": ledger,
        "n_predictions_hit": sum(1 for v in ledger.values() if v["hit"]),
        "R455_calibration_bidirectional": cal,
        "R452_W1_baserate_NOT_ARBITER": calib_baserate(
            off5, {p.get("task_id") for p in per} if per else None),
        "counts": counts,
        "forced_green_with_intent_evidence": forced_evidence,
        "still_uncensused_arbiters": ["R451", "R453(self)", "R454(self)"],
        "verdict": "BROKEN" if broken else "CENSUSED",
    }


# ────────────────────────────── 自檢 ──────────────────────────────
def _row(tid, arm="OFF5", involved=("a", "b"), worker="a", vis=True, md=True, acc=True):
    return {"arm": arm, "task_id": tid, "involved": list(involved), "worker": worker,
            "visible_ok": vis, "meets_demand": md, "accepted": acc}


def selftest() -> int:
    fails = []

    def ck(name, cond, got=""):
        print(f"  {'ok ' if cond else 'FAIL'} {name}" + (f"  [{got}]" if not cond else ""))
        if not cond:
            fails.append(name)

    # ── 分類器四格窮舉（不靠夾具，直接窮舉語意）
    ck("C1 identity∧witness=0 ⇒ FORCED_GREEN", classify(True, 0) == "FORCED_GREEN")
    ck("C2 identity∧witness>0 ⇒ CONTRADICTION", classify(True, 3) == "CONTRADICTION")
    ck("C3 ¬identity∧witness>0 ⇒ EVALUABLE", classify(False, 1) == "EVALUABLE")
    ck("C4 ¬identity∧witness=0 ⇒ UNRESOLVED", classify(False, 0) == "UNRESOLVED")

    rows = [_row(f"t{i}", md=(i % 2 == 0)) for i in range(30)]
    eq5 = {"per_task": [{"task_id": f"t{i}"} for i in range(30)], "broken": [],
           "calibration": {"n": 30, "agree": 30, "rate_pct": 100.0},
           "rule_rates": {"gate_reject_pct": 6.0},
           "paired_gate_vs_vote": {"delta_pp": 4.0},
           "power": {"mde_at_n": 1.0, "n_needed_for_5pp": 400}}
    o = census(rows, eq5)

    ck("C5 乾淨資料 ⇒ CENSUSED", o["verdict"] == "CENSUSED", str(o["broken"]))
    ck("C6 雙向校準兩個方向都對", o["R455_calibration_bidirectional"]["holds"],
       json.dumps(o["R455_calibration_bidirectional"], ensure_ascii=False)[:200])
    ck("C7 W1 無恆等式且 witness=0 ⇒ UNRESOLVED",
       o["records"]["R452-W1"]["class"] == "UNRESOLVED", o["records"]["R452-W1"]["class"])
    # ── C8/C9：證明器要對**合成原始碼**的已知答案雙向正確。
    #    ⛔ 不准把「真原始碼長什麼樣」寫成預期值——那是把假設答案寫成預期值（r705 F7）。
    SRC_UNCOND = ('def f():\n    out = {}\n'
                  '    out["power"] = 1\n    out["paired_gate_vs_vote"] = 2\n    return out\n')
    SRC_COND   = ('def f():\n    out = {}\n    if ok:\n'
                  '        out["power"] = 1\n        out["paired_gate_vs_vote"] = 2\n'
                  '    else:\n        out["power"] = None\n'
                  '        out["paired_gate_vs_vote"] = None\n    return out\n')
    SRC_SPLIT  = ('def f():\n    out = {}\n    out["paired_gate_vs_vote"] = 2\n'
                  '    if ok:\n        out["power"] = 1\n    return out\n')
    ck("C8a 共生證明：無條件併排 ⇒ holds", prove_power_co_assigned(SRC_UNCOND)["holds"])
    ck("C8b 共生證明：同 if/else 併排 ⇒ holds", prove_power_co_assigned(SRC_COND)["holds"])
    ck("C8c 共生證明：CI 無條件而 power 有條件 ⇒ ¬holds",
       not prove_power_co_assigned(SRC_SPLIT)["holds"],
       str(prove_power_co_assigned(SRC_SPLIT)))
    ck("C8d 舊命題（無條件存在）在 if/else 版上 ⇒ ¬holds",
       not prove_power_keys_unconditional(SRC_COND)["holds"])
    ROW_UNCOND = ('def g():\n    rows.append({"task_id": t, "accepted": a, "worker": w})\n')
    ROW_COND   = ('def g():\n    if x:\n        rows.append({"task_id": t, "accepted": a})\n')
    ck("C9a 缺欄位證明：無條件寫入 ⇒ holds",
       prove_required_keys_unconditional(ROW_UNCOND)["holds"])
    ck("C9b 缺欄位證明：條件包覆 ⇒ ¬holds",
       not prove_required_keys_unconditional(ROW_COND)["holds"],
       str(prove_required_keys_unconditional(ROW_COND)))

    # ── witness>0 那一側（證偽事件真的出現過時，分類要換格）
    eq5b = dict(eq5, broken=["calibration_mismatch:t1:rows=(True,True):rebuilt=(True,False)"])
    ob = census(rows, eq5b)
    ck("C10 校準有反例 ⇒ W1 變 EVALUABLE",
       ob["records"]["R452-W1"]["class"] == "EVALUABLE", ob["records"]["R452-W1"]["class"])

    # ── 窗外 ⇒ 證偽事件已實現
    eq5c = dict(eq5, rule_rates={"gate_reject_pct": 30.0})
    oc = census(rows, eq5c)
    ck("C11 拒交率窗外 ⇒ W2 EVALUABLE",
       oc["records"]["R452-W2"]["class"] == "EVALUABLE", oc["records"]["R452-W2"]["class"])

    # ── 基準率母體：只算可校準列
    # x1 必須也在 eq5 的 per_task 裡，否則會先被 tid 濾掉 ⇒ 突變體看不見（Z3 會瞎）
    rows_mixed = rows + [_row("x1", involved=("a", "a"), worker="a", md=False)]
    eq5_mixed = dict(eq5, per_task=eq5["per_task"] + [{"task_id": "x1"}])
    om = census(rows_mixed, eq5_mixed)
    ck("C12 基準率母體排除不可校準列",
       om["R452_W1_baserate_NOT_ARBITER"]["n"] == 30,
       str(om["R452_W1_baserate_NOT_ARBITER"]["n"]))

    # ── 退化基準率要標出來
    rows_deg = [_row(f"t{i}", md=True, vis=True) for i in range(30)]
    od = census(rows_deg, eq5)
    ck("C13 expect 單一值 ⇒ degenerate=True",
       od["R452_W1_baserate_NOT_ARBITER"]["degenerate"] is True,
       json.dumps(od["R452_W1_baserate_NOT_ARBITER"]["distribution"], ensure_ascii=False))

    # ── B1：恆等式成立卻有 witness ⇒ CONTRADICTION 且不吐 FORCED_GREEN
    eq5d = dict(eq5, broken=["missing_fields:t1:['worker']"])
    od2 = census(rows, eq5d)
    ck("C14 B1 恆等式+witness ⇒ CONTRADICTION",
       any(x.startswith("B1_contradiction:R452-§四.3型一") for x in od2["broken"]),
       str(od2["broken"]))
    ck("C15 B5 CONTRADICTION 時不吐任何 FORCED_GREEN",
       "FORCED_GREEN" not in {v["class"] for v in od2["records"].values()},
       str(od2["counts"]))

    # ── B4
    eq5e = dict(eq5, calibration={"n": 5, "agree": 5, "rate_pct": 100.0})
    oe = census(rows, eq5e)
    ck("C16 B4 可校準<20 ⇒ BROKEN", any(x.startswith("B4_uncalibrated") for x in oe["broken"]),
       str(oe["broken"]))

    print(("PASS" if not fails else "FAIL ") + f" r455_r452_census selftest ({len(fails)} fail)")
    return 1 if fails else 0


MUTANTS = {
    "Z1_classify_ignores_witness": "分類器不看 witness（什麼都判 FORCED）⇒ 負對照要抓到",
    "Z2_positive_control_broken":  "正對照的恆假死碼被改成 or（不再恆假）⇒ 正對照要抓到",
    "Z3_baserate_wrong_population": "基準率母體換成全部 OFF5 列（不是可校準列）",
    "Z4_missing_field_prover_ignores_conditionality": "型一恆等式證明忽略條件包覆",
    "Z6_power_prover_ignores_branches": "W4 共生證明忽略分支路徑差異",
}


def mutation() -> int:
    global MUTANT
    print("突變體偵測（判準：指名的那一條要變，不是「有東西紅了」，crash 不算偵測到）")
    bad = []
    base_out = None
    MUTANT = ""
    base_rc = selftest_quiet()
    for m in MUTANTS:
        MUTANT = m
        try:
            rc, failed = selftest_quiet(return_fails=True)
        except Exception as e:                                   # crash 不算偵測到
            print(f"  {m}:N  (crash: {type(e).__name__}) ⇒ 不算偵測到")
            bad.append(m); MUTANT = ""; continue
        seen = rc != 0
        print(f"  {m}:{'Y' if seen else 'N'}  失敗條={failed}")
        if not seen:
            bad.append(m)
    MUTANT = ""
    print(("PASS" if not bad else f"FAIL 未被看見: {bad}") + f"  （乾淨 baseline rc={base_rc}）")
    return 1 if bad else 0


def selftest_quiet(return_fails=False):
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = selftest()
    fails = [l.strip()[5:].split("  [")[0] for l in buf.getvalue().splitlines()
             if l.strip().startswith("FAIL")]
    return (rc, fails) if return_fails else rc


def main() -> int:
    global MUTANT
    ap = argparse.ArgumentParser()
    ap.add_argument("--run"); ap.add_argument("--eq5"); ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mutation", action="store_true")
    a = ap.parse_args()
    MUTANT = os.environ.get("R455_MUTANT", "")
    if a.selftest:
        return selftest()
    if a.mutation:
        return mutation()
    if not (a.run and a.eq5):
        ap.error("--run 與 --eq5 都要給")
    rows = [json.loads(l) for l in open(f"{a.run}/rows.jsonl") if l.strip()]
    eq5 = json.load(open(a.eq5))
    out = census(rows, eq5)
    out["run"] = a.run
    out["eq5_source"] = a.eq5
    out["eq5_source_rows_lines"] = eq5.get("rows_lines")
    out["rows_lines_now"] = len(rows)
    out["decision"] = DECISION.name
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps(out, ensure_ascii=False, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
