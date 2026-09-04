#!/usr/bin/env python3
"""R456：對 R451 的六條子句做可證偽性普查——零 API、純本機。

判準先行：`DECISION_20260904_R456_R451_FALSIFIABILITY_EXTENSION.md`（本檔之前 commit）。
分類規則、事前預測表、`intent`、推翻條件、B7 都在那裡，本檔只是編碼它。

三格分類沿用 R453 §二／R454 §二／R455（**不新增格子**）：
    EVALUABLE    witness ≥ 1                   ⇒ HIT 帶資訊
    FORCED_GREEN 寫得出恆等式 ∧ witness = 0     ⇒ HIT 不帶資訊；intent=evidence 才是警告
    UNRESOLVED   兩者皆無                       ⇒ 照實寫「判不出來」

⚠ **B7（本輪特有的自我約束）**：§四A 的 witness 要比對 `analyze()` 的既有 28 鍵，
而那些值含 b／c／Δ／比率＝`TRIPWIRE_FORBIDDEN`，期中讀它就是序貫決策污染。
所以逐鍵只比 `sha256(canonical_json(value))`，**輸出只有鍵名與布林**。
一條自檢負對照看著它（把已知數字塞進假快照，斷言它不出現在序列化輸出裡）。

用法：
  python3 ops/gain/r456_r451_census.py --selftest
  python3 ops/gain/r456_r451_census.py --mutation
  python3 ops/gain/r456_r451_census.py --snap /dev/shm/r712/snap \
      --json ops/gain/data/r456_census.json
"""
from __future__ import annotations
import argparse, ast, contextlib, hashlib, io, json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MUTANT = ""
DECISION = ROOT / "DECISION_20260904_R456_R451_FALSIFIABILITY_EXTENSION.md"
# R451 §四A 凍結快照（DECISION §五-3）
SNAP_ROWS_SHA16 = "39d3b5dc50a6ba44"
SNAP_ROWS_LINES = 229
# R451 之前的 analyze_r447.py（該檔最後一個非 R451 的 commit）
PRE_R451_COMMIT = "4edb7dc"
NEW_KEY = "power_conform_vs_off5"

# 事前預測表（DECISION §三）。量完不准改。key -> (預測類別, intent)
R456_PREDICTIONS = {
    "R451-§四A": ("FORCED_GREEN", "guard"),
    "R451-§四B": ("FORCED_GREEN", "guard"),
    "R451-§四C": ("UNRESOLVED",   "guard"),
    "R451-§五1": ("FORCED_GREEN", "guard"),
    "R451-§五2": ("FORCED_GREEN", "guard"),
    "R451-§五3": ("UNRESOLVED",   "evidence"),
}


# ────────────────────────────── 分類器（唯一一處） ──────────────────────────────
def classify(identity_holds: bool, witnesses: int) -> str:
    if MUTANT == "Z1_classify_ignores_witness":
        return "FORCED_GREEN" if identity_holds else "UNRESOLVED"
    if identity_holds and witnesses > 0:
        return "CONTRADICTION"
    if identity_holds:
        return "FORCED_GREEN"
    return "EVALUABLE" if witnesses > 0 else "UNRESOLVED"


# ────────────────────────────── §四A 的恆等式證明器 ──────────────────────────────
def _fn_node(src: str, name: str):
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _norm(stmt) -> str:
    """敘述的正規化字串——只比結構，不比行號。"""
    return ast.dump(stmt, annotate_fields=True, include_attributes=False)


def prove_additive(old_src: str, new_src: str, fn: str = "analyze") -> dict:
    """R451-§四A 的恆等式：改動**只增不改**、新增敘述只寫一個新鍵、
    且新增敘述傳給函式的引數都不是可變的既有輸出物件
    ⇒「既有鍵的值改變」在結構上不可能發生。

    三個必要條件（缺一即 holds=False）：
      1. 子序列：舊 `analyze` 的每一條頂層敘述，都在新版裡按原順序逐一出現（結構相同）。
      2. 賦值目標：新增敘述的賦值目標只有局部名字，或 `out[<新鍵>]`。
      3. 引數形狀：新增敘述的呼叫，不得把「被存進 out 的那些名字」裸著傳進去
         （傳進去就可能被就地改動 ⇒ 既有鍵的值會跟著變）。
    """
    o, n = _fn_node(old_src, fn), _fn_node(new_src, fn)
    if o is None or n is None:
        return {"holds": False, "reason": f"SOURCE_DRIFT:fn_not_found:{fn}"}
    old_b, new_b = [_norm(s) for s in o.body], [_norm(s) for s in n.body]
    # 1. 子序列比對
    i, matched = 0, []
    for j, s in enumerate(new_b):
        if i < len(old_b) and s == old_b[i]:
            matched.append(j)
            i += 1
    subseq_ok = i == len(old_b)
    if MUTANT == "Z7_additivity_prover_ignores_removed_stmts":
        subseq_ok = True
        matched = [j for j, s in enumerate(new_b) if s in set(old_b)]
    if not subseq_ok:
        return {"holds": False, "reason": "SOURCE_DRIFT:old_stmts_not_subsequence",
                "old_stmts": len(old_b), "new_stmts": len(new_b), "matched": i}
    added_idx = [j for j in range(len(new_b)) if j not in set(matched)]
    added = [n.body[j] for j in added_idx]
    # 「被存進 out 的名字」＝ out[...] = <Name> 的那些 Name（它們是可變物件）
    out_names = set()
    for st in ast.walk(n):
        if isinstance(st, ast.Assign) and isinstance(st.value, ast.Name):
            for t in st.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == "out":
                    out_names.add(st.value.id)
    out_names.add("out")
    # 2. 賦值目標
    new_keys, bad_targets = set(), []
    for st in added:
        for a in ast.walk(st):
            if not isinstance(a, (ast.Assign, ast.AugAssign)):
                continue
            tgts = a.targets if isinstance(a, ast.Assign) else [a.target]
            for t in tgts:
                if isinstance(t, ast.Name):
                    continue
                if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                        and t.value.id == "out" and isinstance(t.slice, ast.Constant)):
                    new_keys.add(t.slice.value)
                    continue
                bad_targets.append(ast.dump(t)[:60])
    # 別名：`pp = p2` 之後 `f(pp)` 一樣可能就地改到 out 裡的物件 ⇒ 別名也算 out_names
    for st in added:
        for a in ast.walk(st):
            if isinstance(a, ast.Assign) and len(a.targets) == 1 and isinstance(a.targets[0], ast.Name):
                srcs = [a.value] if not isinstance(a.value, ast.IfExp) else [a.value.body, a.value.orelse]
                if any(isinstance(x, ast.Name) and x.id in out_names for x in srcs):
                    out_names.add(a.targets[0].id)
    # 3. 引數形狀
    bad_args = []
    for st in added:
        for c in ast.walk(st):
            if isinstance(c, ast.Call):
                for arg in list(c.args) + [k.value for k in c.keywords]:
                    if isinstance(arg, ast.Name) and arg.id in out_names:
                        bad_args.append(f"{getattr(c.func,'id',None) or ast.dump(c.func)[:24]}({arg.id})")
    if MUTANT == "Z8_additivity_prover_ignores_arg_shape":
        bad_args = []
    holds = subseq_ok and not bad_targets and not bad_args and new_keys and NEW_KEY in new_keys
    return {"holds": bool(holds), "old_stmts": len(old_b), "new_stmts": len(new_b),
            "added_stmts": len(added), "new_out_keys": sorted(new_keys),
            "bad_targets": bad_targets, "bad_args_mutable_passed": bad_args,
            "note": "只增不改 ∧ 只寫新鍵 ∧ 不把可變的既有輸出物件傳進呼叫 ⇒ 既有鍵不可能變"}


# ────────────────────── §四A 的 witness 掃描（B7：只吐鍵名與布林） ──────────────────────
def _digest(v) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()[:12]


def _project_key_equality(old_out: dict, new_out: dict) -> dict:
    """B7：**只**回傳鍵名與布林。任何值都不准出現在輸出裡（連摘要都不吐——
    摘要雖不可逆，但沒有必要，少一個洩漏面）。"""
    od = {k: _digest(v) for k, v in old_out.items()}
    nd = {k: _digest(v) for k, v in new_out.items()}
    differing = sorted(k for k in od if k in nd and od[k] != nd[k])
    if MUTANT == "Z9_leak_raw_values":
        return {"keys_old": len(od), "keys_new": len(nd), "differing_keys": differing,
                "new_keys": sorted(set(nd) - set(od)), "dropped_keys": sorted(set(od) - set(nd)),
                "raw_old": old_out, "raw_new": new_out}
    return {"keys_old": len(od), "keys_new": len(nd), "differing_keys": differing,
            "new_keys": sorted(set(nd) - set(od)), "dropped_keys": sorted(set(od) - set(nd)),
            "B7_values_withheld": "逐鍵比 sha256 摘要；輸出只有鍵名與計數"}


def scan_additive_witness(snap: pathlib.Path) -> dict:
    """在凍結快照上跑「改動前」與「改動後」兩版 analyze，逐鍵比對。
    快照缺席或 sha 對不上 ⇒ UNSCANNED（第三型「安靜量不到」），**不准**報成 witness=0。"""
    rowsf = snap / "rows.jsonl"
    if not rowsf.exists():
        return {"scanned": False, "reason": f"snapshot_missing:{rowsf}"}
    raw = rowsf.read_bytes()
    sha16 = hashlib.sha256(raw).hexdigest()[:16]
    lines = [l for l in raw.decode("utf-8").splitlines() if l.strip()]
    if MUTANT != "Z11_unscanned_reported_as_zero" and (
            sha16 != SNAP_ROWS_SHA16 or len(lines) != SNAP_ROWS_LINES):
        return {"scanned": False, "reason": "snapshot_sha_mismatch",
                "sha16": sha16, "lines": len(lines)}
    old_src = subprocess.run(["git", "show", f"{PRE_R451_COMMIT}:ops/gain/analyze_r447.py"],
                             cwd=ROOT, capture_output=True, text=True)
    if old_src.returncode != 0:
        return {"scanned": False, "reason": f"git_show_failed:{old_src.stderr.strip()[:80]}"}
    tmp = ROOT / "ops" / "gain" / "_r456_old_analyze_tmp.py"   # 同一個 import 環境（parents[2]＝ROOT）
    try:
        tmp.write_text(old_src.stdout, encoding="utf-8")
        import importlib
        A_new = importlib.import_module("ops.gain.analyze_r447")
        A_old = importlib.import_module("ops.gain._r456_old_analyze_tmp")
        rows = [json.loads(l) for l in lines]
        summary = json.loads((snap / "summary.json").read_text(encoding="utf-8"))
        with contextlib.redirect_stdout(io.StringIO()):
            out_old, out_new = A_old.analyze(rows, summary), A_new.analyze(rows, summary)
    finally:
        tmp.unlink(missing_ok=True)
    proj = _project_key_equality(out_old, out_new)
    proj.update({"scanned": True, "snapshot_sha16": sha16, "snapshot_lines": len(lines),
                 "old_source_commit": PRE_R451_COMMIT})
    return proj


# ────────────────────────────── §四B 的恆等式證明器 ──────────────────────────────
def prove_m11_forced() -> dict:
    """R451-§四B 的恆等式：夾具**無隨機性** ⇒ 「M11 有沒有被指名的那一條抓到」
    是一個常數，跑一次就對所有時候成立。乾淨＝ok 且 M11＝該條紅 ⇒ 證偽事件不可達。"""
    import importlib
    A = importlib.import_module("ops.gain.analyze_r447")
    src = (ROOT / "ops/gain/analyze_r447.py").read_text(encoding="utf-8")
    rng = [n for n in ast.walk(ast.parse(src))
           if (isinstance(n, ast.Import) and any(a.name.startswith("random") for a in n.names))
           or (isinstance(n, ast.ImportFrom) and (n.module or "").startswith("random"))]
    deterministic = not rng
    MC = importlib.import_module("ops.gain.r447_mutation_check")
    want = MC.EXPECT.get("M11_power_off5_uses_off_pair")
    if not want:
        return {"holds": False, "reason": "SOURCE_DRIFT:M11_not_in_EXPECT"}
    rc0, f0 = MC.run("", A)
    rc1, f1 = MC.run("M11_power_off5_uses_off_pair", A)
    named = any(x.startswith(want) for x in f1)
    crashed = any(x.startswith("CRASH:") for x in f1)
    clean_ok = rc0 == 0 and not f0
    holds = bool(deterministic and clean_ok and rc1 != 0 and named and not crashed)
    return {"holds": holds, "deterministic_fixture": deterministic, "clean_baseline_ok": clean_ok,
            "named_clause": want, "mutant_named_caught": named, "mutant_crashed": crashed,
            "note": "夾具無 RNG ⇒ 結果是常數 ⇒「M11 沒被指名條抓到」不可達"}


# ────────────────────────────── §四C 的 witness 掃描 ──────────────────────────────
def scan_regression_witness() -> dict:
    """既有突變體是否仍全 `:Y`、乾淨 selftest 是否仍 PASS。witness ＝ 任一 `:N` 或 FAIL。"""
    import importlib
    A = importlib.import_module("ops.gain.analyze_r447")
    MC = importlib.import_module("ops.gain.r447_mutation_check")
    rc0, f0 = MC.run("", A)
    marks, misses = [], []
    for m, want in MC.EXPECT.items():
        rc, fails = MC.run(m, A)
        ok = (rc != 0) and any(x.startswith(want) for x in fails) \
            and not any(x.startswith("CRASH:") for x in fails)
        marks.append(f"{m}:{'Y' if ok else 'N'}")
        if not ok:
            misses.append(f"{m} rc={rc} 指名條={want!r}")
    if rc0 != 0 or f0:
        misses.append(f"baseline_selftest_fail:{f0}")
    return {"mutants_scanned": len(MC.EXPECT), "marks": marks,
            "baseline_selftest_pass": rc0 == 0 and not f0, "witnesses": len(misses),
            "misses": misses}


# ────────────────────────────── 雙向校準（B6） ──────────────────────────────
def _fn_source(path: str, fn_name: str):
    src = (ROOT / path).read_text(encoding="utf-8")
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fn_name:
            seg = ast.get_source_segment(src, n)
            return (seg, "") if seg else (None, f"no_source_segment:{path}:{fn_name}")
    return None, f"fn_not_found:{path}:{fn_name}"


def calibration_bidirectional(rows: list[dict]) -> dict:
    """正對照＝R450 §八 已證的恆假死碼（必須判 FORCED_GREEN）；
    負對照＝自由統計量（必須判 EVALUABLE）。只有正對照時「什麼都判 FORCED」也會全綠。"""
    seg, err = _fn_source("ops/gain/analyze_r447.py", "_deliv")
    if seg is None:
        return {"holds": False, "reason": f"SOURCE_DRIFT:{err}"}
    ret = [n for n in ast.walk(ast.parse(seg)) if isinstance(n, ast.Return)]
    ret.sort(key=lambda n: (n.lineno, n.col_offset))      # ast.walk 是 BFS
    expr = ast.get_source_segment(seg, ret[-1].value) if ret else None
    if not expr:
        return {"holds": False, "reason": "SOURCE_DRIFT:_deliv_no_return"}
    op = "or" if MUTANT == "Z2_positive_control_broken" else "and"
    clause = f"({expr}) {op} not bool(r.get('meets_demand'))"
    fires = [bool(eval(clause, {"bool": bool}, {"r": {"accepted": a, "meets_demand": m}}))
             for a in (True, False) for m in (True, False)]
    pos_cls = classify(identity_holds=not any(fires), witnesses=sum(fires))
    md_vals = {bool(r.get("meets_demand")) for r in rows}
    neg_wit = sum(1 for r in rows if bool(r.get("meets_demand")))
    neg_cls = classify(identity_holds=(len(md_vals) < 2), witnesses=neg_wit)
    return {"holds": pos_cls == "FORCED_GREEN" and neg_cls == "EVALUABLE",
            "positive": {"clause": clause, "class": pos_cls,
                         "known_answer": "FORCED_GREEN（R450 §八 已證恆假）"},
            "negative": {"stat": "bool(row.meets_demand)", "class": neg_cls,
                         "distinct_values": sorted(md_vals), "witnesses": neg_wit,
                         "known_answer": "EVALUABLE（自由統計量）"}}


# ────────────────────────────── 主普查 ──────────────────────────────
def census(snap: pathlib.Path, rows: list[dict]) -> dict:
    broken: list[str] = []
    new_src = (ROOT / "ops/gain/analyze_r447.py").read_text(encoding="utf-8")
    old = subprocess.run(["git", "show", f"{PRE_R451_COMMIT}:ops/gain/analyze_r447.py"],
                         cwd=ROOT, capture_output=True, text=True)
    if old.returncode != 0:
        p_add = {"holds": False, "reason": "SOURCE_DRIFT:git_show_failed"}
    else:
        p_add = prove_additive(old.stdout, new_src)
    if str(p_add.get("reason", "")).startswith("SOURCE_DRIFT"):
        broken.append(f"additive_prover:{p_add['reason']}")

    scan = scan_additive_witness(snap)
    p_m11 = prove_m11_forced()
    if str(p_m11.get("reason", "")).startswith("SOURCE_DRIFT"):
        broken.append(f"m11_prover:{p_m11['reason']}")
    reg = scan_regression_witness()

    rec: dict[str, dict] = {}
    a_unscanned = not scan.get("scanned")
    rec["R451-§四A"] = {
        "clause": "加法性：既有鍵的值逐一相同，差異恰好只有 power_conform_vs_off5",
        "falsifier": "任一既有鍵的值改變",
        "identity": "只增不改 ∧ 只寫新鍵 ∧ 不把可變的既有輸出物件傳進呼叫",
        "identity_holds": bool(p_add.get("holds")),
        "witnesses": len(scan.get("differing_keys") or []),
        "unscanned": a_unscanned, "proof": p_add, "scan": scan,
    }
    rec["R451-§四B"] = {
        "clause": "M11 讓 selftest 紅，且指名的那一條紅（crash 不算）",
        "falsifier": "M11 沒被指名條抓到",
        "identity": "夾具無 RNG ⇒ 結果是常數 ⇒ 證偽事件不可達",
        "identity_holds": bool(p_m11.get("holds")),
        "witnesses": 0 if p_m11.get("mutant_named_caught") else 1,
        "proof": p_m11,
    }
    rec["R451-§四C"] = {
        "clause": "不回歸：既有突變體仍全 :Y、乾淨 selftest 仍 PASS",
        "falsifier": "任一 :N 或 baseline selftest FAIL",
        "identity": None, "identity_holds": False,
        "witnesses": reg["witnesses"], "scan": reg,
    }
    parent_a = rec["R451-§四A"]["identity_holds"] and not a_unscanned
    parent_b = rec["R451-§四B"]["identity_holds"]
    if MUTANT == "Z10_derived_clause_ignores_parent":
        parent_a = parent_b = True
    rec["R451-§五1"] = {
        "clause": "A 對不上 ⇒ 回退這個改動", "falsifier": "A 對不上卻沒回退",
        "identity": "前提（§四A 的證偽事件）本身結構不可達 ⇒ 本條的證偽事件也不可達",
        "identity_holds": bool(parent_a), "witnesses": 0,
        "derived_from": "R451-§四A（導出關係寫在 DECISION §三，由 Z10 看著）",
    }
    rec["R451-§五2"] = {
        "clause": "B 沒牙齒 ⇒ 記 M11:N", "falsifier": "B 沒牙齒卻沒記",
        "identity": "前提（§四B 的證偽事件）本身結構不可達 ⇒ 本條的證偽事件也不可達",
        "identity_holds": bool(parent_b), "witnesses": 0,
        "derived_from": "R451-§四B（導出關係寫在 DECISION §三，由 Z10 看著）",
    }
    rec["R451-§五3"] = {
        "clause": "N₈₀ > 題庫規模 ⇒ 是結論、不准放寬 P-Z3",
        "falsifier": "觸發了卻被拿去放寬 P-Z3 的窗口",
        "identity": None, "identity_holds": False, "witnesses": 0,
        "blocked_by_tripwire": True,
        "why": "觸發量 n_needed_for_5pp 在 TRIPWIRE_FORBIDDEN 裡，期中不准讀（B7）"
               "⇒ 本輪是『掃不到』不是『掃到 0 個』；收官輪必須重跑本尺。",
    }

    for k, v in rec.items():
        v["class"] = classify(bool(v["identity_holds"]), int(v["witnesses"]))
        if v["class"] == "CONTRADICTION":
            broken.append(f"B1_contradiction:{k}")
    # B4：§四A 的 witness 沒掃到 ⇒ 不准當 witness=0（第三型「安靜量不到」）
    if a_unscanned:
        rec["R451-§四A"]["class"] = "UNRESOLVED_UNSCANNED"
        broken.append(f"B4_unscanned:{scan.get('reason')}")
    cal = calibration_bidirectional(rows)
    if not cal.get("holds"):
        broken.append("B6_calibration_failed")
    if broken:                                    # B5／B6：不准吐 FORCED_GREEN
        for v in rec.values():
            if v["class"] == "FORCED_GREEN":
                v["class"] = "UNRESOLVED_CALIBRATION_FAILED"

    ledger = {}
    for k, (pred, intent) in R456_PREDICTIONS.items():
        rec[k]["intent"] = intent
        ledger[k] = {"predicted": pred, "observed": rec[k]["class"],
                     "hit": pred == rec[k]["class"], "intent": intent}
    counts: dict[str, int] = {}
    for v in rec.values():
        counts[v["class"]] = counts.get(v["class"], 0) + 1
    forced_evidence = [k for k, v in rec.items()
                       if v["class"] == "FORCED_GREEN" and v.get("intent") == "evidence"]
    return {"verdict": "CENSUSED" if not broken else "BROKEN", "broken": broken,
            "records": rec, "prediction_ledger": ledger,
            "n_predictions_hit": sum(1 for v in ledger.values() if v["hit"]),
            "n_predictions": len(ledger), "counts": counts,
            "forced_green_with_intent_evidence": forced_evidence,
            "R456_calibration_bidirectional": cal,
            "decision_sha256": hashlib.sha256(DECISION.read_bytes()).hexdigest()
            if DECISION.exists() else None}


# ────────────────────────────── 自檢（合成雙向，不對真原始碼斷言） ──────────────────────────────
_SYN_OLD = '''
def analyze(rows, summary):
    out = {}
    p2 = pair(rows)
    out["a"] = p2
    return out
'''
_SYN_NEW_OK = '''
def analyze(rows, summary):
    out = {}
    p2 = pair(rows)
    out["a"] = p2
    pp = p2
    out["power_conform_vs_off5"] = {"m": mde(pp["n"], 0.5)}
    return out
'''
_SYN_NEW_DELETED = '''
def analyze(rows, summary):
    out = {}
    p2 = pair(rows)
    pp = p2
    out["power_conform_vs_off5"] = {"m": mde(pp["n"], 0.5)}
    return out
'''
_SYN_NEW_MUTABLE_ARG = '''
def analyze(rows, summary):
    out = {}
    p2 = pair(rows)
    out["a"] = p2
    out["power_conform_vs_off5"] = {"m": mde(p2)}
    return out
'''

LAST_FAILS: list[str] = []


def _bogus_snap() -> pathlib.Path:
    """合法但**不是**凍結快照的 rows／summary（sha 對不上）——UNSCANNED 的夾具。
    用 analyze_r447 的夾具產列（它們的 schema 是真的，才不會退化成 crash 測試）。"""
    import importlib
    A = importlib.import_module("ops.gain.analyze_r447")
    rows, summ = A._fixture()
    d = pathlib.Path("/dev/shm/r456_bogus_snap")
    d.mkdir(parents=True, exist_ok=True)
    (d / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (d / "summary.json").write_text(json.dumps(summ), encoding="utf-8")
    return d


def selftest() -> int:
    global LAST_FAILS
    fails: list[str] = []
    LAST_FAILS = fails

    def ck(label, cond, extra=""):
        print(f"  {'ok  ' if cond else 'FAIL'} {label} {extra}")
        if not cond:
            fails.append(label)

    # ── C1–C4 分類器四格窮舉（唯一一處分類規則）
    ck("C1 恆等式成立 ∧ witness=0 ⇒ FORCED_GREEN", classify(True, 0) == "FORCED_GREEN")
    ck("C2 恆等式不成立 ∧ witness>0 ⇒ EVALUABLE", classify(False, 3) == "EVALUABLE",
       f"實得 {classify(False, 3)}")
    ck("C3 兩者皆無 ⇒ UNRESOLVED", classify(False, 0) == "UNRESOLVED")
    ck("C4 恆等式成立 ∧ witness>0 ⇒ CONTRADICTION（B1）", classify(True, 2) == "CONTRADICTION")
    # ── C5 與 R455 的分類器逐格一致（兩份實作分歧會被抓到）
    try:
        import importlib
        R455 = importlib.import_module("ops.gain.r455_r452_census")
        same = all(classify(i, w) == R455.classify(i, w)
                   for i in (True, False) for w in (0, 1, 5))
    except Exception as e:                                  # noqa: BLE001
        same = False
        print(f"       （R455 匯入失敗：{type(e).__name__}）")
    ck("C5 分類規則與 R455 逐格一致", same)
    # ── C6 雙向校準（正對照＝已知恆假；負對照＝自由統計量）
    syn_rows = [{"accepted": True, "meets_demand": True}, {"accepted": True, "meets_demand": False}]
    cal = calibration_bidirectional(syn_rows)
    ck("C6 雙向校準：正對照 FORCED_GREEN ∧ 負對照 EVALUABLE", bool(cal.get("holds")),
       f"pos={cal.get('positive', {}).get('class')} neg={cal.get('negative', {}).get('class')}")
    # ── C7 加法性證明器的合成雙向（真原始碼的答案只當量測，不在這裡斷言）
    ck("C7a 純新增 ⇒ holds=True", prove_additive(_SYN_OLD, _SYN_NEW_OK)["holds"] is True)
    ck("C7b 舊敘述被刪 ⇒ holds=False", prove_additive(_SYN_OLD, _SYN_NEW_DELETED)["holds"] is False,
       str(prove_additive(_SYN_OLD, _SYN_NEW_DELETED))[:90])
    ck("C7c 把可變的既有輸出物件裸著傳進呼叫 ⇒ holds=False",
       prove_additive(_SYN_OLD, _SYN_NEW_MUTABLE_ARG)["holds"] is False,
       str(prove_additive(_SYN_OLD, _SYN_NEW_MUTABLE_ARG).get("bad_args_mutable_passed"))[:60])
    # ── C8 B7 洩漏負對照：已知數字不准出現在序列化輸出裡
    leak_probe = 918273.645
    proj = _project_key_equality({"paired_conform_vs_off": {"delta_pp": leak_probe}},
                                 {"paired_conform_vs_off": {"delta_pp": leak_probe},
                                  "power_conform_vs_off5": {"n": 1}})
    blob = json.dumps(proj, ensure_ascii=False, default=str)
    ck("C8 B7：值不得出現在輸出（只准鍵名與布林）", "918273.645" not in blob,
       blob[:80])
    ck("C8b B7 投影仍看得出新鍵與差異", proj["new_keys"] == ["power_conform_vs_off5"]
       and proj["differing_keys"] == [])
    # ── C9／C10 用**同一次** census（假快照）：UNSCANNED 與導出關係
    bog = census(_bogus_snap(), syn_rows)
    ck("C9 快照 sha 對不上 ⇒ UNRESOLVED_UNSCANNED（不准報成 witness=0）",
       bog["records"]["R451-§四A"]["class"] == "UNRESOLVED_UNSCANNED"
       and bog["records"]["R451-§四A"]["unscanned"] is True,
       f"實得 {bog['records']['R451-§四A']['class']}")
    ck("C10 §五1 從 §四A 導出：前提掃不到時 identity 不得成立",
       bog["records"]["R451-§五1"]["identity_holds"] is False)
    ck("C11 B5：出現 broken 時不准吐任何 FORCED_GREEN",
       all(v["class"] != "FORCED_GREEN" for v in bog["records"].values()) and bog["broken"])
    ck("C12 §五3 標成 blocked_by_tripwire（期中掃不到，不是掃到 0）",
       bog["records"]["R451-§五3"]["blocked_by_tripwire"] is True)
    print(f"SELFTEST {'PASS' if not fails else 'FAIL'} ({len(fails)} failed) MUTANT={MUTANT or 'none'}")
    return 1 if fails else 0


EXPECT = {
    "Z1_classify_ignores_witness":              "C2",
    "Z2_positive_control_broken":               "C6",
    "Z7_additivity_prover_ignores_removed_stmts": "C7b",
    "Z8_additivity_prover_ignores_arg_shape":   "C7c",
    "Z9_leak_raw_values":                       "C8",
    "Z10_derived_clause_ignores_parent":        "C10",
    "Z11_unscanned_reported_as_zero":           "C9",
}


def mutation() -> int:
    """每個突變體都要被**指名的那一條**看見；crash 收場不算抓到。"""
    global MUTANT
    MUTANT = ""
    with contextlib.redirect_stdout(io.StringIO()):
        rc0 = selftest()
    base = list(LAST_FAILS)
    if rc0 != 0 or base:
        print(f"BASELINE FAIL rc={rc0} fails={base}")
        return 1
    print("baseline (MUTANT=none) SELFTEST PASS")
    marks, bad = [], []
    for m, want in EXPECT.items():
        MUTANT = m
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = selftest()
            fails = list(LAST_FAILS)
            crashed = False
        except Exception as e:                              # noqa: BLE001
            rc, fails, crashed = 2, [f"CRASH:{type(e).__name__}:{e}"], True
        MUTANT = ""
        ok = rc != 0 and any(x.startswith(want) for x in fails) and not crashed
        marks.append(f"{m}:{'Y' if ok else 'N'}")
        if not ok:
            bad.append(f"  {m} rc={rc} 指名條={want!r} 實際失敗={fails}")
    print("MUTATION " + ("PASS" if not bad else "FAIL") + " caught=" + " ".join(marks))
    for b in bad:
        print(b)
    return 0 if not bad else 1


def main() -> int:
    global MUTANT
    ap = argparse.ArgumentParser()
    ap.add_argument("--snap", default="/dev/shm/r712/snap")
    ap.add_argument("--run", help="取 rows 給雙向校準的負對照用（唯讀）")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mutation", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.mutation:
        return mutation()
    rows = []
    if args.run:
        raw = (pathlib.Path(args.run) / "rows.jsonl").read_bytes()
        rows = [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]
    out = census(pathlib.Path(args.snap), rows)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return 0 if out["verdict"] == "CENSUSED" else 1


if __name__ == "__main__":
    sys.exit(main())
