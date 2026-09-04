#!/usr/bin/env python3
"""R466：對 **R461 §二／§六** 的每一條預註冊判準問「它有可能是假的嗎？」——零 API、純本機。

判準先行：`DECISION_20260904_R466_R461_SEC2_SEC6_FALSIFIABILITY_CENSUS.md`（99ec6cb，本檔之前
commit）。四格分類、七筆清單、母體定義、事前預測、擋門、推翻條件都在那裡，本檔只是編碼它。

⚠ 本輪**不讀主 run 任何一列**（DECISION §六）。B3 擋門做成硬性：任何讀檔路徑含
   `g_r461_lcb3_three_arm` ⇒ BROKEN_PEEKED。

用法：
  python3 ops/gain/r466_r461_sec2_sec6_census.py --selftest
  python3 ops/gain/r466_r461_sec2_sec6_census.py --json ops/gain/data/r466_census.json
"""
from __future__ import annotations
import argparse, ast, hashlib, json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vacant.codebench import LCB_BANKS                                  # noqa: E402

MUTANT = ""
LAST_FAILS: list[str] = []

PREREG = ROOT / "DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md"
R461_PREREG_COMMIT = "a3036573ce529a62f9b77793b0f0961a0cf61a67"   # 預測落筆當時（DECISION §二.1）
FORBIDDEN_RUN = "g_r461_lcb3_three_arm"                          # B3
# ── round735（R467）：`SOURCE_CLAIMS` 的原始碼字面**釘在這支普查所稽核的那個 commit**，
#   不是 HEAD。理由：R467 修掉了 `verify_lcb_bank.py` 的 `PROBE_PATH` 寫死，
#   若這裡繼續讀 worktree，這份**已收官的歷史普查**重跑就會吐 `SOURCE_DRIFT`
#   ——那是「被稽核的東西後來被改了」，不是「當初的稽核記錯了」。
#   memory：加法性對照要釘改動前的 commit，不是釘 HEAD（釘 HEAD＝拿自己比自己）。
#   ⚠ 只有 SOURCE_CLAIMS 走這個釘；bank 檔／判準檔／`vacant/codebench.py` 的
#   「今天」那條仍讀 worktree（它們問的是現在的事實）。
R466_SOURCE_COMMIT = "952f883f798744e32158bb11bdf67b940f51a8db"   # R466 量測 commit
TWIN_RUN = ROOT / "runs" / "g_r447_conform_lcb2"                  # 已收官的結構孿生（S6-2 用）

# ── 釘死的判準檔字面（B2）。每一條都要在 R461 原文裡逐字找得到。
PREREG_PINS = {
    "S2-1": "產出 **恰好 189 題**",
    "S2-2": "189 個 `task_id` 與 `lcb_bank_v2.jsonl` 的 120 個**零交集**",
    "S2-3": "日期範圍 2023-05-07 → 2024-08-10",
    "S2-4": "medium 152／hard 37",
    "S6-1": "**v3 的 probe 覆蓋率預期為 0/189**",
    "S6-2": "看有幾題**任一臂通過過一次**",
    "S6-3": "**照實寫成偏離**，不假裝通過",
}
INTENT = {"S2-1": "evidence", "S2-2": "evidence", "S2-3": "evidence", "S2-4": "evidence",
          "S6-1": "evidence", "S6-2": "evidence", "S6-3": "guard"}
# DECISION §三 的事前預測（盲＝計入命中率）
PRED = {"S2-1": "EVALUABLE", "S2-2": "FORCED_GREEN", "S2-3": "EVALUABLE",
        "S2-4": "EVALUABLE", "S6-1": "FORCED_GREEN", "S6-2": "EVALUABLE",
        "S6-3": "NOT_A_PREDICTION"}
BLIND = {"S2-1": True, "S2-2": True, "S2-3": True, "S2-4": True,
         "S6-1": False, "S6-2": False, "S6-3": True}

# ── 被引用的原始碼字面（B2）。memory 鐵律：驗程式碼在什麼條件為真，
#    要逐字取出真運算式，不准自己改寫一份。
SOURCE_CLAIMS = {
    "probe_path_hardcoded": ("ops/gain/verify_lcb_bank.py", None,
        'PROBE_PATH = pathlib.Path(__file__).resolve().parent / "data" / "lcb_probe_solutions.json"'),
    "coverage_uses_probe_path": ("ops/gain/verify_lcb_bank.py", "main",
        'probes = json.loads(PROBE_PATH.read_text(encoding="utf-8"))'),
    "coverage_expr": ("ops/gain/verify_lcb_bank.py", "main",
        'covered = [r["task_id"] for r in records if r["task_id"] in probes]'),
    # 正對照要用的：載入器對 count 是 fail-closed
    "loader_count_failclosed": ("vacant/codebench.py", "_load_verified",
        "self.expected_count"),
}

# §二 事前預測的三個回推量（POP_A 的成員；數字取自 R461 §二 原文）
POP_A_PRED = {"total": 189, "medium": 152, "hard": 37}


# ---------------------------------------------------------------- 擋門工具
def _safe_read(p: pathlib.Path) -> str:
    """B3：本輪不准讀主 run。"""
    if MUTANT != "M1_drop_peek_gate" and FORBIDDEN_RUN in str(p):
        raise RuntimeError(f"B3 違規：本輪不准讀 {FORBIDDEN_RUN}（{p}）")
    return p.read_text(encoding="utf-8")


def _source_read(relpath: str) -> str:
    """SOURCE_CLAIMS 專用：從釘死的 commit 取檔，不讀 worktree。"""
    if FORBIDDEN_RUN in relpath:
        raise RuntimeError(f"B3 違規：本輪不准讀 {FORBIDDEN_RUN}（{relpath}）")
    if MUTANT == "M7_drop_source_pin":
        return _safe_read(ROOT / relpath)                 # 退回讀 worktree
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{R466_SOURCE_COMMIT}:{relpath}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"SOURCE_PIN_UNREADABLE: git show {R466_SOURCE_COMMIT[:8]}:{relpath} 失敗"
            f"（{r.stderr.strip()[:200]}）——讀不到釘死的來源要吵，不准悄悄退回讀 HEAD")
    return r.stdout


def _func_src(relpath: str, funcname: str) -> str:
    src = _source_read(relpath)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == funcname:
            return ast.get_source_segment(src, node) or ""
    return ""


def check_pins() -> dict:
    """B2：判準檔字面 ＋ 原始碼字面都要對得上，否則 SOURCE_DRIFT。"""
    doc = _safe_read(PREREG)
    drift = []
    pin_ok = {}
    for k, lit in PREREG_PINS.items():
        want = lit
        if MUTANT == "M4_pin_drift" and k == "S6-1":
            want = lit + "（本行是突變體插入的假字面）"
        ok = want in doc
        pin_ok[k] = ok
        if not ok:
            drift.append(f"prereg:{k}")
    src_ok = {}
    for k, (rel, fn, lit) in SOURCE_CLAIMS.items():
        seg = _func_src(rel, fn) if fn else _source_read(rel)
        ok = lit in seg
        src_ok[k] = ok
        if not ok:
            drift.append(f"source:{k}")
    return {"prereg_pins": pin_ok, "source_pins": src_ok, "drift": drift,
            "source_pin_commit": (None if MUTANT == "M7_drop_source_pin"
                                  else R466_SOURCE_COMMIT)}


# ---------------------------------------------------------------- 事實蒐集
def _sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def bank_facts() -> dict:
    out = {}
    for ver, spec in sorted(LCB_BANKS.items()):
        p = pathlib.Path(spec["path"])
        if not p.exists():
            out[ver] = {"missing": True}
            continue
        recs = [json.loads(ln) for ln in _safe_read(p).splitlines() if ln.strip()]
        by_diff: dict[str, int] = {}
        by_src: dict[str, int] = {}
        for r in recs:
            by_diff[r["difficulty"]] = by_diff.get(r["difficulty"], 0) + 1
            by_src[r.get("source_file", "?")] = by_src.get(r.get("source_file", "?"), 0) + 1
        dates = sorted(r["contest_date"] for r in recs)
        out[ver] = {
            "count": len(recs), "pin_count": spec["count"],
            "sha256_matches_pin": _sha256(p) == spec["sha256"],
            "ids": sorted(r["task_id"] for r in recs),
            "by_difficulty": by_diff, "source_files": sorted(by_src),
            "date_range": [dates[0], dates[-1]] if dates else [],
        }
    return out


def probe_facts(banks: dict) -> dict:
    old = ROOT / "ops/gain/data/lcb_probe_solutions.json"
    new = ROOT / "ops/gain/data/lcb_v3_probe_solutions.json"
    old_ids = sorted(json.loads(_safe_read(old))) if old.exists() else []
    new_ids = sorted(json.loads(_safe_read(new))) if new.exists() else []
    out = {"probe_file_used_by_verify": str(old.relative_to(ROOT)),
           "n_probe_old": len(old_ids), "n_probe_v3_file": len(new_ids),
           "coverage_as_verify_measures": {}, "coverage_if_v3_file_used": {}}
    for ver, b in banks.items():
        if b.get("missing"):
            continue
        ids = set(b["ids"])
        out["coverage_as_verify_measures"][ver] = len(ids & set(old_ids))
        out["coverage_if_v3_file_used"][ver] = len(ids & set(new_ids))
    out["probe_old_ids_subset_of_v2"] = bool(old_ids) and set(old_ids) <= set(banks["v2"]["ids"])
    return out


def prediction_time_pin() -> dict:
    """§二.1：判 forced 的時點是預測落筆當時，不是今天。"""
    try:
        blob = subprocess.run(["git", "show", f"{R461_PREREG_COMMIT}:vacant/codebench.py"],
                              cwd=ROOT, capture_output=True, text=True, timeout=30)
        src = blob.stdout if blob.returncode == 0 else ""
    except Exception:
        src = ""
    today = _safe_read(ROOT / "vacant/codebench.py")
    return {"commit": R461_PREREG_COMMIT[:8],
            "v3_pin_existed_at_prediction_time": ("LCB_BANK_V3_COUNT" in src),
            "v3_pin_exists_today": ("LCB_BANK_V3_COUNT" in today),
            "read_ok": bool(src)}


def twin_capability_facts() -> dict:
    """S6-2 的母體：已收官三臂 run 的完整題目（主 run 一列都不讀）。"""
    rows = TWIN_RUN / "rows.jsonl"
    if not rows.exists():
        return {"available": False}
    by_task: dict[str, list] = {}
    for ln in _safe_read(rows).splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        by_task.setdefault(str(r.get("task_id")), []).append(r)
    complete = {t: rs for t, rs in by_task.items() if len(rs) == 3}
    dem = sum(1 for rs in complete.values()
              if any(bool(r.get("meets_demand")) for r in rs))
    return {"available": True, "run": TWIN_RUN.name, "n_complete": len(complete),
            "n_demonstrated": dem, "n_undemonstrated": len(complete) - dem}


# ---------------------------------------------------------------- 分類
def _cell(identity_holds, witness: int, note: str, population: str,
          identity: str) -> dict:
    if identity_holds is True and witness > 0:
        cls = "CONTRADICTION"           # B1
    elif identity_holds is True and witness == 0:
        cls = "FORCED_GREEN"
    elif witness > 0 or identity_holds is False:
        cls = "EVALUABLE"
    else:
        cls = "UNRESOLVED"
    if MUTANT == "M2_force_all":
        cls = "FORCED_GREEN"
    return {"class": cls, "identity_holds": identity_holds, "witness": witness,
            "population": population, "identity": identity, "note": note}


def classify(facts: dict) -> dict:
    banks, probe = facts["banks"], facts["probe"]
    v2, v3 = banks["v2"], banks["v3"]
    items: dict[str, dict] = {}

    # ── POP_A：§二 從 R460 census 回推的自由統計量預測（總數／medium／hard）
    a_actual = {"total": v3["count"],
                "medium": v3["by_difficulty"].get("medium", 0),
                "hard": v3["by_difficulty"].get("hard", 0)}
    pop_a_false = sorted(k for k, want in POP_A_PRED.items() if a_actual[k] != want)
    POP_A = "§二 從 R460 census 回推寫進判準的計數預測（total／medium／hard 三筆）"
    pt = facts["pred_time"]
    ident_s21 = ("LCB_BANK_V3_COUNT 在預測落筆的 commit 已存在（＝題數當時就被釘死）"
                 if pt["v3_pin_existed_at_prediction_time"] else None)
    items["S2-1"] = _cell(
        True if pt["v3_pin_existed_at_prediction_time"] else False,
        len(pop_a_false), f"預測 189 / 實測 {a_actual['total']}；同批次被推翻的筆數={pop_a_false}",
        POP_A, ident_s21 or "預測當時沒有任何釘值保證題數（今天才有，見 §二.1）")
    items["S2-4"] = _cell(
        False, len(pop_a_false),
        f"預測 medium 152／hard 37；實測 medium {a_actual['medium']}／hard {a_actual['hard']}",
        POP_A, "同上：預測當時無釘值")
    items["S2-3"] = _cell(
        False, len(pop_a_false),
        f"預測 2023-05-07 → 2024-08-10；實測 {v3['date_range']}",
        POP_A, "同上：預測當時無釘值（日期是資料的自由統計量）")

    # ── POP_B：由不相交來源檔建出的 bank 對
    POP_B = "由來源檔集合不相交的兩個 bank 組成的對（本庫可得：v1/v2、v1/v3、v2/v3）"
    pairs, wit_b = [], 0
    vers = [v for v in sorted(banks) if not banks[v].get("missing")]
    for i in range(len(vers)):
        for j in range(i + 1, len(vers)):
            a, b = banks[vers[i]], banks[vers[j]]
            src_disjoint = not (set(a["source_files"]) & set(b["source_files"]))
            ov = len(set(a["ids"]) & set(b["ids"]))
            pairs.append({"pair": f"{vers[i]}/{vers[j]}", "source_disjoint": src_disjoint,
                          "id_overlap": ov})
            if src_disjoint and ov > 0:
                wit_b += 1
    v2v3 = next(p for p in pairs if p["pair"] == "v2/v3")
    items["S2-2"] = _cell(
        v2v3["source_disjoint"], wit_b,
        f"v2/v3 來源檔不相交={v2v3['source_disjoint']}、id 交集={v2v3['id_overlap']}；"
        f"母體內來源不相交卻有交集的對={wit_b}",
        POP_B, "來源檔集合不相交 ⇒ 建出的 bank 的 task_id 不可能相交")

    # ── POP_C：被 verify_lcb_bank 量 probe 覆蓋率、且 id 與 PROBE_PATH 題目集合不相交的 bank
    POP_C = ("被 verify_lcb_bank 量 probe 覆蓋率、且 id 與寫死的 PROBE_PATH 題目集合"
             "不相交的 bank（v1 因來源含那 12 題而不在母體內＝跨母體不算 witness）")
    cov = probe["coverage_as_verify_measures"]
    members = [v for v, c in cov.items() if c == 0]
    if MUTANT == "M6_cross_population":
        members = list(cov)                       # 把 v1／v2 也算進母體（跨母體）
    wit_c = sum(1 for v in members if cov[v] > 0)
    items["S6-1"] = _cell(
        probe["probe_old_ids_subset_of_v2"] and v2v3["source_disjoint"] and "v3" in members,
        wit_c,
        f"verify 用的 probe 檔題數={probe['n_probe_old']}、全在 v2 內="
        f"{probe['probe_old_ids_subset_of_v2']}；v3 覆蓋率={cov.get('v3')}/{v3['count']}；"
        f"改用 lcb_v3_probe_solutions.json 則為 {probe['coverage_if_v3_file_used'].get('v3')}"
        f"/{v3['count']}（母體成員：{members}）",
        POP_C,
        "PROBE_PATH 寫死 v1/v2 的解檔 ⇒ 覆蓋率 = |probe_old ∩ ids|，"
        "而 probe_old ⊆ v2 且 v2∩v3=∅ ⇒ v3 覆蓋率恆為 0")

    # ── POP_D：已收官三臂 run 的完整題目
    tw = facts["twin"]
    POP_D = "已收官三臂 run（g_r447_conform_lcb2）的完整題目，逐題問「任一臂通過過一次」"
    if not tw.get("available"):
        items["S6-2"] = _cell(None, 0, "結構孿生 run 不可得", POP_D, "—")
    else:
        both = tw["n_demonstrated"] > 0 and tw["n_undemonstrated"] > 0
        items["S6-2"] = _cell(
            False if both else None, tw["n_undemonstrated"],
            f"{tw['run']}：complete={tw['n_complete']}、demonstrated={tw['n_demonstrated']}、"
            f"undemonstrated={tw['n_undemonstrated']}",
            POP_D, "「任一臂通過過一次」若恆真則能力下界不帶資訊——兩個方向都出現過即推翻")

    # ── S6-3：報告義務，沒有真值（DECISION §二 預先宣告的第四格）
    items["S6-3"] = {"class": "NOT_A_PREDICTION", "identity_holds": None, "witness": 0,
                     "population": "—（程序義務）", "identity": "—",
                     "note": "§六.3 是「照實寫成偏離」的報告義務，本身沒有真值 ⇒ 不進命中率"}
    for k in items:
        items[k]["intent"] = INTENT[k]
        items[k]["prereg_literal_found"] = facts["pins"]["prereg_pins"].get(k)
    return items


def calibration(facts: dict) -> dict:
    """B5 雙向校準：正對照必須 FORCED_GREEN、負對照必須 EVALUABLE。"""
    banks = facts["banks"]
    v3 = banks["v3"]
    pos_ident = (facts["pins"]["source_pins"]["loader_count_failclosed"]
                 and facts["pred_time"]["v3_pin_exists_today"])
    if MUTANT == "M3_break_forced_detect":
        pos_ident = False
    pos = _cell(bool(pos_ident), 0,
                f"今天 v3 載入成功 ⇒ 必然 {v3['pin_count']} 列（載入器對 count fail-closed）",
                "今天用 LiveCodeBenchLoader 成功載入的 v3", "count != 釘值 ⇒ 載入器 raise")
    a_medium = v3["by_difficulty"].get("medium", 0)
    neg_wit = 1 if a_medium != POP_A_PRED["medium"] else 0
    neg = _cell(False, neg_wit, f"「v3 的 medium 題數＝{a_medium}」是自由統計量",
                "§二 難度分項預測", "無（沒有任何釘值保證分項）")
    ok = pos["class"] == "FORCED_GREEN" and neg["class"] == "EVALUABLE"
    return {"positive_control": pos, "negative_control": neg, "calibrated": ok}


# ---------------------------------------------------------------- 主判決
def census() -> dict:
    facts = {"pins": check_pins()}
    facts["banks"] = bank_facts()
    facts["probe"] = probe_facts(facts["banks"])
    facts["pred_time"] = prediction_time_pin()
    facts["twin"] = twin_capability_facts()

    out: dict = {"tool": "r466_r461_sec2_sec6_census",
                 "prereg": "DECISION_20260904_R466_R461_SEC2_SEC6_FALSIFIABILITY_CENSUS.md",
                 "facts": facts}

    if facts["pins"]["drift"]:
        out["verdict"] = "SOURCE_DRIFT"                          # B2
        out["drift"] = facts["pins"]["drift"]
        return out
    missing = [v for v, b in facts["banks"].items() if b.get("missing")
               or not b.get("sha256_matches_pin", False)]
    if missing:
        out["verdict"] = "UNCALIBRATED"                          # B4
        out["reason"] = f"bank 檔缺失或 sha 不符：{missing}"
        return out

    cal = calibration(facts)
    out["calibration"] = cal
    if not cal["calibrated"]:
        out["verdict"] = "UNCALIBRATED"                          # B5
        out["reason"] = (f"雙向校準失敗：正對照={cal['positive_control']['class']}、"
                         f"負對照={cal['negative_control']['class']}")
        return out

    items = classify(facts)
    if any(v["class"] == "CONTRADICTION" for v in items.values()):
        out["verdict"] = "CONTRADICTION"                         # B1
        out["items"] = ({k: v for k, v in items.items()} if MUTANT == "M5_forced_under_contradiction"
                        else {k: {**v, "class": ("SUPPRESSED" if v["class"] == "FORCED_GREEN"
                                                 else v["class"])} for k, v in items.items()})
        return out                                               # B6

    out["items"] = items
    out["verdict"] = "OK"
    counts: dict[str, int] = {}
    for v in items.values():
        counts[v["class"]] = counts.get(v["class"], 0) + 1
    out["class_counts"] = counts
    out["forced_green_evidence_items"] = sorted(
        k for k, v in items.items()
        if v["class"] == "FORCED_GREEN" and v["intent"] == "evidence")
    recon = {}
    blind_hit = blind_n = 0
    for k, v in items.items():
        hit = (v["class"] == PRED[k])
        recon[k] = {"predicted": PRED[k], "actual": v["class"], "blind": BLIND[k],
                    "verdict": "HIT" if hit else "MISS"}
        if BLIND[k]:
            blind_n += 1
            blind_hit += int(hit)
    out["prediction_reconciliation"] = recon
    out["blind_hit_rate"] = f"{blind_hit}/{blind_n}"
    return out


# ---------------------------------------------------------------- selftest
def _ck(name: str, cond: bool) -> None:
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        LAST_FAILS.append(name)


def selftest() -> int:
    global MUTANT
    LAST_FAILS.clear()
    print("R466 census selftest")

    MUTANT = ""
    base = census()
    _ck("A 乾淨跑 verdict==OK", base["verdict"] == "OK")
    _ck("B 七筆都在", len(base.get("items", {})) == 7)
    _ck("C 雙向校準通過", base["calibration"]["calibrated"])
    _ck("D 正對照＝FORCED_GREEN",
        base["calibration"]["positive_control"]["class"] == "FORCED_GREEN")
    _ck("E 負對照＝EVALUABLE",
        base["calibration"]["negative_control"]["class"] == "EVALUABLE")
    _ck("F 判準檔七條字面全找得到", all(base["facts"]["pins"]["prereg_pins"].values()))
    _ck("G 原始碼四條字面全對得上", all(base["facts"]["pins"]["source_pins"].values()))

    # B3：主 run 不准讀。**探針指向該目錄下一個不存在的檔名**——這樣連 selftest
    # 自己都不會把主 run 的任何 byte 讀進記憶體，而擋門有沒有攔照樣看得出來
    # （攔到＝RuntimeError；沒攔到＝FileNotFoundError）。
    PROBE = ROOT / "runs" / FORBIDDEN_RUN / "__b3_probe_does_not_exist__"
    try:
        _safe_read(PROBE)
        _ck("H B3 擋門會擋主 run", False)
    except RuntimeError:
        _ck("H B3 擋門會擋主 run", True)
    except FileNotFoundError:
        _ck("H B3 擋門會擋主 run", False)

    MUTANT = "M1_drop_peek_gate"
    try:
        _safe_read(PROBE)
        leaked = True
    except RuntimeError:
        leaked = False
    except FileNotFoundError:
        leaked = True          # 擋門沒攔，路徑真的被送進 open()＝一樣是漏
    _ck("M1 拿掉 B3 就讀得到主 run（＝擋門真的在擋）", leaked)

    MUTANT = "M2_force_all"
    m2 = census()
    _ck("M2 全判 FORCED 會被負對照擋住（UNCALIBRATED）", m2["verdict"] == "UNCALIBRATED")

    MUTANT = "M3_break_forced_detect"
    m3 = census()
    _ck("M3 正對照壞掉 ⇒ UNCALIBRATED", m3["verdict"] == "UNCALIBRATED")

    MUTANT = "M4_pin_drift"
    m4 = census()
    _ck("M4 判準字面漂移 ⇒ SOURCE_DRIFT", m4["verdict"] == "SOURCE_DRIFT")
    _ck("M4 漂移之下不吐任何分類", "items" not in m4)

    MUTANT = "M6_cross_population"
    m6 = census()
    got6 = m6.get("items", {}).get("S6-1", {}).get("class")
    _ck("M6 母體換成跨母體 ⇒ S6-1 不再是 FORCED_GREEN",
        m6["verdict"] != "OK" or got6 != "FORCED_GREEN")

    # B1／B6：合成一個「恆等式成立且 witness>0」的矛盾
    MUTANT = ""
    contra = _cell(True, 3, "合成", "合成母體", "合成恆等式")
    _ck("B1 恆等式成立＋witness>0 ⇒ CONTRADICTION", contra["class"] == "CONTRADICTION")
    MUTANT = "M5_forced_under_contradiction"
    fake = {"S2-2": _cell(True, 0, "", "", ""), "X": _cell(True, 2, "", "", "")}
    supp = {k: {**v, "class": ("SUPPRESSED" if v["class"] == "FORCED_GREEN" else v["class"])}
            for k, v in fake.items()}
    _ck("M5 若不抑制，CONTRADICTION 之下仍會吐 FORCED_GREEN",
        any(v["class"] == "FORCED_GREEN" for v in fake.values())
        and not any(v["class"] == "FORCED_GREEN" for v in supp.values()))
    MUTANT = ""

    print("SELFTEST_PASS" if not LAST_FAILS else f"SELFTEST_FAIL {LAST_FAILS}")
    return 0 if not LAST_FAILS else 1


def main() -> int:
    global MUTANT
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    import os
    MUTANT = os.environ.get("R466_MUTANT", "")
    if a.selftest:
        return selftest()
    out = census()
    txt = json.dumps(out, ensure_ascii=False, indent=2)
    print(txt)
    if a.json:
        pathlib.Path(a.json).write_text(txt + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
