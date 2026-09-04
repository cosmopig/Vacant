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


# ────────────────────────────── R458：§五3 的解封（加法式） ──────────────────────────────
# 判準：DECISION_20260904_R458_WU3_UNBLOCK.md（本段程式碼之前 commit）。
# 觸發量 n_needed_for_5pp 是 TRIPWIRE_FORBIDDEN 成員 ⇒ 只在 run terminal 之後才讀。
PRE_R458_COMMIT = "6a8aa7a"   # R458 判準 commit＝本尺改動前的最後一版（C13 用，釘死不隨 HEAD 漂）
R451_COMMIT = "113f747"          # R451 判準落地時的 commit（兩件文字證物的基準版本）
W3_BANKS = {"lcb2": "ops/gain/data/lcb_bank_v2.jsonl",
            "lcb1": "ops/gain/data/lcb_bank_v1.jsonl"}
W3_DOCS = [("DECISION_20260904_R440Z_LCB2_PREREG.md", "P-Z3"),
           ("CRITERION_20260903_R670_DELIV_DIFFERENCE_INTERVAL.md", "UNINFORMATIVE")]


def w3_trigger(n_needed: int, bank_size: int) -> bool:
    """R451 §五3 的觸發量：要 5pp 解析度所需的配對題數 > 題庫規模。"""
    if MUTANT == "Y1_w3_trigger_ignores_bank":
        return True
    return int(n_needed) > int(bank_size)


def _lines_with(text: str, needle: str) -> list[str]:
    return [l for l in text.splitlines() if needle in l]


def w3_doc_witness(pairs: list[tuple] | None = None) -> dict:
    """證物 A／B：逐行比對 R451 落地版本與現況。pairs 只給自檢用（合成）。"""
    if pairs is None:
        pairs = []
        for path, needle in W3_DOCS:
            r = subprocess.run(["git", "show", f"{R451_COMMIT}:{path}"],
                               cwd=ROOT, capture_output=True, text=True)
            if r.returncode != 0:
                return {"checked": False, "reason": f"SOURCE_DRIFT:git_show_failed:{path}"}
            cur = ROOT / path
            if not cur.exists():
                return {"checked": False, "reason": f"SOURCE_DRIFT:missing_now:{path}"}
            pairs.append((path, needle, r.stdout, cur.read_text(encoding="utf-8")))
    changed, empty, detail = [], [], {}
    for name, needle, old_t, new_t in pairs:
        o, n = _lines_with(old_t, needle), _lines_with(new_t, needle)
        if MUTANT == "Y2_w3_ignores_doc_drift":
            o = n
        detail[name] = {"needle": needle, "n_lines_r451": len(o),
                        "n_lines_now": len(n), "same": o == n}
        if not o and not n:                       # 第三型「安靜量不到」：needle 掃到 0 行
            empty.append(name)
        elif o != n:
            changed.append(name)
    if empty:
        return {"checked": False, "reason": f"EMPTY_NEEDLE:{','.join(empty)}", "detail": detail}
    return {"checked": True, "changed": changed, "detail": detail}


def eval_w3(run_dir: pathlib.Path | None) -> dict:
    """§五3 的實測。run 沒給／非 terminal／題庫對不上 ⇒ UNSCANNED（不准報成 witness=0）。"""
    if run_dir is None:
        return {"scanned": False, "reason": "no_run_given"}
    sf = run_dir / "summary.json"
    rf = run_dir / "rows.jsonl"
    if not sf.exists() or not rf.exists():
        return {"scanned": False, "reason": f"missing_run_files:{run_dir}"}
    summ = json.loads(sf.read_text(encoding="utf-8"))
    terminal = bool(summ.get("run_terminal"))
    if MUTANT == "Y3_w3_blocked_even_when_terminal":
        terminal = False
    if not terminal:
        return {"scanned": False, "reason": "run_not_terminal"}
    # 題庫：DECISION §二 寫的是 summary.json:sampling.bank，但**該欄位不存在於 summary.json**
    # （本輪實測）。改由 seed 後綴解析，對不上就 UNSCANNED——「不准拿另一個題庫的數字頂替」
    # 這條判準的實質不變；來源不同這件事逐字記在 bank_resolution 裡（STATE 也記）。
    seed = str(summ.get("seed") or "")
    bank = next((b for b in W3_BANKS if seed.endswith("-" + b) or seed.endswith(b)), None)
    if bank is None:
        return {"scanned": False, "reason": f"bank_unresolved_from_seed:{seed!r}"}
    bank_file = ROOT / W3_BANKS[bank]
    if not bank_file.exists():
        return {"scanned": False, "reason": f"bank_file_missing:{W3_BANKS[bank]}"}
    bank_size = sum(1 for l in bank_file.read_text(encoding="utf-8").splitlines() if l.strip())
    import importlib
    A = importlib.import_module("ops.gain.analyze_r447")
    rows = [json.loads(l) for l in rf.read_text(encoding="utf-8").splitlines() if l.strip()]
    a = A.analyze(rows, summ)
    pw = a.get("power_conform_vs_off5") or {}
    if "n_needed_for_5pp" not in pw:
        return {"scanned": False, "reason": "power_conform_vs_off5_missing"}
    n_needed = pw["n_needed_for_5pp"]
    docs = w3_doc_witness()
    return {"scanned": True, "bank": bank, "bank_size": bank_size,
            "n_needed_for_5pp": n_needed,
            "trigger_fired": w3_trigger(n_needed, bank_size),
            "docs": docs,
            "bank_resolution": {"source": "summary.json:seed 後綴",
                                "declared_in_decision": "sampling.bank（summary.json 沒有這個欄位）",
                                "on_mismatch": "UNSCANNED"}}


# ────────────────────────────── 主普查 ──────────────────────────────
def census(snap: pathlib.Path, rows: list[dict], run_dir: pathlib.Path | None = None) -> dict:
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
    # R458：run terminal 之後才評估（加法式——run_dir=None 時上面那 6 個鍵一字不動）
    w3 = eval_w3(run_dir)
    if w3.get("scanned"):
        r3 = rec["R451-§五3"]
        r3["blocked_by_tripwire"] = False
        r3["witnesses"] = 1 if w3["trigger_fired"] else 0
        r3["w3_n_needed_for_5pp"] = w3["n_needed_for_5pp"]
        r3["w3_bank"] = w3["bank"]
        r3["w3_bank_size"] = w3["bank_size"]
        r3["w3_trigger_fired"] = w3["trigger_fired"]
        r3["w3_docs"] = w3["docs"]
        r3["w3_bank_resolution"] = w3["bank_resolution"]
        if not w3["docs"].get("checked"):
            broken.append(f"R458_doc_witness_unscanned:{w3['docs'].get('reason')}")
        elif w3["docs"]["changed"] and w3["trigger_fired"]:
            broken.append("R458_clause_violated:R451-§五3")
        elif w3["docs"]["changed"]:
            r3["witness_docs_changed_without_trigger"] = w3["docs"]["changed"]
    elif w3.get("reason") != "no_run_given":
        rec["R451-§五3"]["w3_scan"] = w3

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


def _first_diff(a, b, path="") -> str:
    """C13 失敗時指出第一個不同的鍵路徑（診斷用，不影響判準）。"""
    if type(a) is not type(b):
        return f"{path}: type {type(a)} vs {type(b)}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}.{k}: 只在一邊"
            d = _first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return ""
    return "" if a == b else f"{path}: {a!r} vs {b!r}"


def _pre_r458_census(snap: pathlib.Path, rows: list[dict]):
    """把 R458 改動前的本尺放回**同一個 import 環境**跑一次（C13 的加法性對照）。"""
    import importlib.util
    r = subprocess.run(["git", "show", f"{PRE_R458_COMMIT}:ops/gain/r456_r451_census.py"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        return None, f"SOURCE_DRIFT:git_show_failed:{PRE_R458_COMMIT}"
    tmp = ROOT / "ops/gain/_r458_pre_tmp.py"          # parents[2] == ROOT
    tmp.write_text(r.stdout, encoding="utf-8")
    try:
        spec = importlib.util.spec_from_file_location("ops.gain._r458_pre_tmp", tmp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.MUTANT = MUTANT                            # 兩邊同條件，差異才只可能來自 R458
        return mod.census(snap, rows), None
    finally:
        tmp.unlink(missing_ok=True)


def _syn_terminal_run() -> pathlib.Path:
    """合成的 terminal run（schema 用 analyze_r447 的真夾具，才不會退化成 crash 測試）。"""
    import importlib
    A = importlib.import_module("ops.gain.analyze_r447")
    rows, summ = A._fixture()
    d = pathlib.Path("/dev/shm/r458_syn_run")
    d.mkdir(parents=True, exist_ok=True)
    (d / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (d / "summary.json").write_text(
        json.dumps(dict(summ, run_terminal=True, seed="g-syn-lcb2"), ensure_ascii=False),
        encoding="utf-8")
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
    # ── C13 R458 加法性：run_dir=None ⇒ 與改動前版本**逐鍵逐值**相同（不是比 sha）
    pre, pre_err = _pre_r458_census(_bogus_snap(), syn_rows)
    ck("C13 R458 加法性：run_dir=None 的輸出與改動前版本逐鍵逐值相同",
       pre_err is None and pre == bog, str(pre_err or _first_diff(pre, bog))[:200])
    # ── C14 觸發量真的比題庫規模（Y1 指名）
    ck("C14 n_needed ≤ 題庫 ⇒ 不觸發；> 才觸發",
       w3_trigger(100, 120) is False and w3_trigger(400, 120) is True,
       f"{w3_trigger(100, 120)}/{w3_trigger(400, 120)}")
    # ── C15 證物漂移看得見；needle 掃到 0 行要判 EMPTY_NEEDLE（Y2 指名）
    drift = w3_doc_witness([("fakedoc", "P-Z3", "| P-Z3 | +2 到 +8pp |", "| P-Z3 | +2 到 +20pp |")])
    same = w3_doc_witness([("fakedoc", "P-Z3", "| P-Z3 | +2 到 +8pp |", "| P-Z3 | +2 到 +8pp |")])
    empty = w3_doc_witness([("fakedoc", "NO_SUCH_NEEDLE", "aaa", "aaa")])
    ck("C15 證物有差異 ⇒ changed 指名；相同 ⇒ 空；needle 掃到 0 行 ⇒ EMPTY_NEEDLE",
       drift["changed"] == ["fakedoc"] and same["changed"] == []
       and empty["checked"] is False and str(empty["reason"]).startswith("EMPTY_NEEDLE"),
       f"{drift.get('changed')}/{same.get('changed')}/{empty.get('reason')}")
    # ── C16 terminal ⇒ 必須解封（Y3 指名）
    syn = census(_bogus_snap(), syn_rows, _syn_terminal_run())
    r3 = syn["records"]["R451-§五3"]
    ck("C16 run terminal ⇒ §五3 解封（blocked_by_tripwire False 且有 w3_ 量）",
       r3["blocked_by_tripwire"] is False and "w3_n_needed_for_5pp" in r3,
       f"blocked={r3.get('blocked_by_tripwire')} keys={[k for k in r3 if k.startswith('w3_')]}")
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
    "Y1_w3_trigger_ignores_bank":               "C14",
    "Y2_w3_ignores_doc_drift":                  "C15",
    "Y3_w3_blocked_even_when_terminal":         "C16",
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
    out = census(pathlib.Path(args.snap), rows,
                 pathlib.Path(args.run) if args.run else None)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return 0 if out["verdict"] == "CENSUSED" else 1


if __name__ == "__main__":
    sys.exit(main())
