#!/usr/bin/env python3
"""R462：對 **R461 §三／§四** 的每一條預註冊判準問「它有可能是假的嗎？」——零 API、純本機。

判準先行：`DECISION_20260904_R462_R461_PREREG_FALSIFIABILITY_CENSUS.md`（c70851f，本檔之前
commit）。三格分類、七筆清單、事前預測、擋門、推翻條件都在那裡，本檔只是編碼它。

⚠ 本輪**不看閘門 run 的任何比率**（DECISION §一）。B6 擋門把它做成硬性的：
   任何讀檔路徑含 `g_r461_off_gate_lcb3` ⇒ BROKEN。

用法：
  python3 ops/gain/r462_r461_census.py --selftest
  python3 ops/gain/r462_r461_census.py --json ops/gain/data/r462_census.json
"""
from __future__ import annotations
import argparse, ast, json, math, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ops.gain.power_paired import exact_mcnemar_p                       # noqa: E402

MUTANT = ""
PREREG = ROOT / "DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md"
FORBIDDEN_RUN = "g_r461_off_gate_lcb3"          # B6

# ── 釘死的判準檔字面（B3）。每一條都要在 R461 原文裡逐字找得到。
PREREG_PINS = {
    "X1": "Δ ∈ [+3, +20]pp、p<0.05、判 `OFF5_WINS`",
    "X2": "Δ ∈ [+8, +28]pp、p<0.05、判 `CONFORM_WINS`",
    "X3": "- P-R461-1 若 `p ≥ 0.05` 或 `c ≥ b`：",
    "X4": "**事前就判 `UNRESOLVED`**",
    "X5": "**事前預測：失敗率 38–52%（點估計 45%），判 `GATE_PASS` 或 `GATE_MARGINAL`。**",
    "X6": "- 任一臂 `infra_void` > 20%：整份判 `UNSCANNED`，不是判「沒有差異」。",
    "X7": "worker `gemma-4-12b-it-qat`",
}

# ── 被引用的原始碼運算式（B2）：key -> (檔案, 函式, 期望的逐字字串)
#    memory 鐵律：驗程式碼在什麼條件為真，要用 ast 逐字取出真運算式，不准自己改寫一份。
SOURCE_CLAIMS = {
    "mcnemar_two_sided": ("ops/gain/power_paired.py", "exact_mcnemar_p",
                          "min(1.0, 2 * tail)"),
    "mcnemar_symmetric": ("ops/gain/power_paired.py", "exact_mcnemar_p",
                          "min(b, c)"),
}

# ── R461 自己寫死的數字（從判準檔正文取，不是我在這裡發明的）
GATE_PASS_LO, GATE_PASS_HI = 40.0, 60.0         # §三 判決表
GATE_MARGINAL_LO = 30.0                          # §三 判決表
PRED_RATE_LO, PRED_RATE_HI = 38.0, 52.0          # §三 事前預測
VOID_THRESH_PCT = 20.0                           # §四 推翻條件
N_MAIN = 189                                     # §四 主 run 題數
# r447 實測（R461 §四 表格逐字引用的三個 disc rate 與效果）
R447_EQ5_DISC_RATE = 0.1917                      # P-R461-3 的 disc
R447_EQ5_EFFECT_PP = 4.17                        # P-R461-3 的 r447 觀測效果
R447_EQ5_N = 120

LAST_FAILS: list[str] = []


# ---------------------------------------------------------------- 擋門工具
def _safe_read(p: pathlib.Path) -> str:
    """B6：本輪不准讀閘門 run。"""
    if MUTANT != "M6_drop_b6_gate_isolation" and FORBIDDEN_RUN in str(p):
        raise RuntimeError(f"B6 違規：本輪不准讀 {FORBIDDEN_RUN}（{p}）")
    return p.read_text(encoding="utf-8")


def _func_src(relpath: str, funcname: str) -> str:
    src = _safe_read(ROOT / relpath)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == funcname:
            return ast.get_source_segment(src, node) or ""
    return ""


def check_source_pins() -> dict:
    out, drift = {}, []
    for key, (rel, fn, literal) in SOURCE_CLAIMS.items():
        seg = _func_src(rel, fn)
        want = literal
        if MUTANT == "M5_source_pin_drift" and key == "mcnemar_two_sided":
            want = "min(1.0, 3 * tail)"
        ok = want in seg
        out[key] = {"file": rel, "func": fn, "literal": want, "found": ok}
        if not ok:
            drift.append(key)
    return {"claims": out, "drift": drift}


def check_prereg_pins() -> dict:
    txt = _safe_read(PREREG)
    out, drift = {}, []
    for key, pin in PREREG_PINS.items():
        want = pin
        if MUTANT == "M4_prereg_pin_drift" and key == "X3":
            want = "- P-R461-1 若 `p < 0.05` 且 `c < b`："
        ok = want in txt
        out[key] = {"pin": want, "found": ok}
        if not ok:
            drift.append(key)
    return {"pins": out, "drift": drift}


# ---------------------------------------------------------------- X1／X2
def verdict_vocabulary() -> list[str]:
    """仲裁者的詞彙表＝`paired_ci.verdict` 實際 return 的字串字面，用 ast 逐字取。"""
    src = _safe_read(ROOT / "ops/gain/replay/paired_ci.py")
    tree = ast.parse(src)
    vocab: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "verdict":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Constant) \
                        and isinstance(sub.value.value, str):
                    vocab.append(sub.value.value)
    return sorted(set(vocab))


def emitters_of(literal: str) -> list[str]:
    """全庫掃：有沒有**任何**工具會吐出這個字串（給 X1/X2 一個公平的第二次機會）。"""
    hits = []
    for p in sorted((ROOT / "ops" / "gain").rglob("*.py")):
        if p.name == pathlib.Path(__file__).name:
            continue                      # 不算自己（本檔的釘值裡就有這個字串）
        try:
            src = _safe_read(p)
        except (RuntimeError, OSError):
            continue
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == literal:
                hits.append(str(p.relative_to(ROOT)))
                break
    return hits


def census_vocab(code: str, literal: str) -> dict:
    vocab = verdict_vocabulary()
    emit = emitters_of(literal)
    in_vocab = literal in vocab
    if in_vocab or emit:
        cls, why = "EVALUABLE", f"`{literal}` 有仲裁者（vocab={in_vocab}、emitters={emit}）"
    else:
        cls = "UNRESOLVED"
        why = (f"`{literal}` 既不在 `paired_ci.verdict` 的詞彙表 {vocab}，"
               f"也沒有任何 ops/gain 工具吐得出來 ⇒ 這個合取項**沒有仲裁者**，"
               f"照字面永遠判不出真假（不是綠燈也不是紅燈）")
    return {"code": code, "intent": "evidence", "class": cls, "why": why,
            "vocabulary": vocab, "literal": literal, "emitters": emit}


# ---------------------------------------------------------------- X3
def census_x3() -> dict:
    """`p ≥ 0.05 或 c ≥ b`：第二個析取項是死碼嗎？
    死碼 ⟺ 不存在 (b,c) 使得 `c ≥ b` 且 `p < 0.05`（那時它被第一項完全吸收）。"""
    witnesses = []
    total = 0
    for nd in range(0, N_MAIN + 1):
        for c in range(0, nd + 1):
            b = nd - c
            total += 1
            p = exact_mcnemar_p(b, c)
            if MUTANT == "M1_one_sided_p":
                # 單尾化：c>=b 時直接給 1.0（＝那個析取項會變成死碼）
                p = 1.0 if c >= b else p
            if c >= b and p < 0.05:
                if len(witnesses) < 5:
                    witnesses.append({"b": b, "c": c, "p": round(p, 6)})
    dead = not witnesses
    return {"code": "X3", "intent": "guard",
            "class": "FORCED_GREEN" if dead else "EVALUABLE",
            "why": ("`c ≥ b` 被 `p ≥ 0.05` 完全吸收＝死碼（恆等式：c≥b ⇒ p≥0.05）"
                    if dead else
                    "`c ≥ b` **不是**死碼：exact_mcnemar_p 是雙尾且對 (b,c) 對稱 ⇒ "
                    "反方向也可能顯著，那時只有第二個析取項擋得住"),
            "pairs_enumerated": total, "witnesses": witnesses,
            "n_witness_pairs": sum(1 for nd in range(N_MAIN + 1) for c in range(nd + 1)
                                   if c >= nd - c and exact_mcnemar_p(nd - c, c) < 0.05
                                   and MUTANT != "M1_one_sided_p")}


# ---------------------------------------------------------------- X4
def _binom_pmf(n: int, k: int, p: float) -> float:
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def census_x4() -> dict:
    """P-R461-3「事前就判 UNRESOLVED」有可能為假嗎？基準率＝在 r447 觀測效果下
    n=189 拿到 p<0.05 的機率（＝這條預測被證偽的機率）。全部用列舉，不模擬。"""
    nd_447 = round(R447_EQ5_N * R447_EQ5_DISC_RATE)          # 23
    gap_447 = round(R447_EQ5_N * R447_EQ5_EFFECT_PP / 100)   # 5
    b447 = (nd_447 + gap_447) // 2
    pi = b447 / nd_447                                        # b/(b+c)
    disc = R447_EQ5_DISC_RATE
    power = 0.0
    for nd in range(0, N_MAIN + 1):
        pnd = _binom_pmf(N_MAIN, nd, disc)
        if pnd < 1e-12:
            continue
        for b in range(0, nd + 1):
            if exact_mcnemar_p(b, nd - b) < 0.05:
                power += pnd * _binom_pmf(nd, b, pi)
    return {"code": "X4", "intent": "evidence", "class": "EVALUABLE",
            "why": ("「事前就判 UNRESOLVED」可以為假（新資料顯著就推翻它）"
                    "⇒ 帶資訊，但基準率高 ⇒ 命中不強"),
            "assumed_from_r447": {"n": R447_EQ5_N, "disc_rate": disc, "n_disc": nd_447,
                                  "b": b447, "c": nd_447 - b447, "pi": round(pi, 4),
                                  "effect_pp": R447_EQ5_EFFECT_PP},
            "falsification_prob_at_n189": round(power, 4),
            "greenlight_base_rate": round(1 - power, 4)}


# ---------------------------------------------------------------- X5
def gate_verdict_of(rate_pct: float) -> str:
    if GATE_PASS_LO <= rate_pct <= GATE_PASS_HI:
        return "GATE_PASS"
    if GATE_MARGINAL_LO <= rate_pct < GATE_PASS_LO:
        return "GATE_MARGINAL"
    return "GATE_FAIL_TOO_EASY" if rate_pct < GATE_MARGINAL_LO else "GATE_FAIL_TOO_HARD"


def census_x5() -> dict:
    """§三 的兩個事前預測強度不同：數字級 38–52%，判決級 GATE_PASS∪GATE_MARGINAL＝30–60%。
    在 0–100 的結果空間上（0.1pp 網格）算兩者的基準率與互相矛盾的區間。"""
    grid = [i / 10 for i in range(0, 1001)]
    green_verdict = [x for x in grid if gate_verdict_of(x) in ("GATE_PASS", "GATE_MARGINAL")]
    green_number = [x for x in grid if PRED_RATE_LO <= x <= PRED_RATE_HI]
    conflict = [x for x in green_verdict if not (PRED_RATE_LO <= x <= PRED_RATE_HI)]
    return {"code": "X5", "intent": "evidence", "class": "EVALUABLE",
            "why": ("兩個預測都可能為假 ⇒ 帶資訊；但**判決級比數字級寬**，"
                    "收官只准報數字級那個，否則等於事後挑寬的那條"),
            "grid_pts": len(grid),
            "base_rate_verdict_level": round(len(green_verdict) / len(grid), 4),
            "base_rate_number_level": round(len(green_number) / len(grid), 4),
            "conflict_pp_width": round(len(conflict) / 10, 1),
            "conflict_ranges": "[30.0,38.0) ∪ (52.0,60.0]" if conflict else "無"}


# ---------------------------------------------------------------- X6
def scan_void(runs_root: pathlib.Path | None = None) -> dict:
    root = runs_root or (ROOT / "runs")
    scanned, over, mx = 0, [], 0.0
    for sp in sorted(root.glob("*/summary.json")):
        if FORBIDDEN_RUN in str(sp) and MUTANT != "M6_drop_b6_gate_isolation":
            continue                                   # B6：連掃都不掃
        try:
            d = json.loads(_safe_read(sp))
        except Exception:
            continue
        arms = d.get("arms") or {}
        if not isinstance(arms, dict):
            continue
        counted = False
        for arm, a in arms.items():
            if not isinstance(a, dict):
                continue
            proc = a.get("processed") or a.get("tasks") or 0
            void = a.get("infra_void")
            if void is None or not proc:
                continue
            counted = True
            pct = 100.0 * void / (proc + void) if MUTANT == "M2_void_denominator" else 100.0 * void / proc
            mx = max(mx, pct)
            if pct > VOID_THRESH_PCT:
                over.append({"run": sp.parent.name, "arm": arm,
                             "infra_void": void, "processed": proc, "pct": round(pct, 2)})
        if counted:
            scanned += 1
    return {"runs_scanned": scanned, "max_void_pct": round(mx, 2), "over": over}


def census_x6(runs_root: pathlib.Path | None = None) -> dict:
    s = scan_void(runs_root)
    if s["runs_scanned"] == 0 and MUTANT != "M3_drop_unscanned_branch":
        return {"code": "X6", "intent": "guard", "class": "UNSCANNED",
                "why": "B4：掃描到 0 個有 infra_void 的 run ⇒ 是「沒量到」不是「沒發生過」", **s}
    if s["over"]:
        return {"code": "X6", "intent": "guard", "class": "EVALUABLE",
                "why": "歷史上真的出現過 >20% 的臂 ⇒ 這條擋門不是強制綠燈", **s}
    return {"code": "X6", "intent": "guard", "class": "FORCED_GREEN",
            "why": (f"掃過 {s['runs_scanned']} 個 run，最高 {s['max_void_pct']}% < {VOID_THRESH_PCT}% "
                    "⇒ witness=0。intent=guard ⇒ **設計如此，不是缺陷**；"
                    "但收官不准把「void 沒超標」寫成證據"), **s}


# ---------------------------------------------------------------- X7
def census_x7() -> dict:
    names = {}
    try:
        from ops.gain import power_paired as PP
        names["power_paired.mde_at_n"] = callable(getattr(PP, "mde_at_n", None))
    except Exception:
        names["power_paired.mde_at_n"] = False
    gr = _safe_read(ROOT / "ops/gain/gain_run.py")
    for arm in ("OFF", "CONFORM", "OFF5"):
        names[f"arm:{arm}"] = f'"{arm}"' in gr or f"'{arm}'" in gr
    # round729：第一版把 bank 名的落點寫成 codebench.py ⇒ 判 missing。**那是本量具的定位錯誤，
    # 不是產物不存在**：`"lcb3"` 的 dispatch 在 gain_run.py（codebench.py 記的是 version="v3"）。
    # 加法式修正：舊的那格原樣留著（`bank:lcb3@codebench`，實測 False），新增正確的那格。
    # 修正理由是**語意**（dispatch 的真實落點，且能零 API 載出 189 題），不是「結果比較好看」。
    names["bank:lcb3@codebench"] = '"lcb3"' in _safe_read(ROOT / "vacant/codebench.py")
    _gr_ok = '"lcb3"' in gr
    names["bank:lcb3@gain_run"] = _gr_ok
    names["bank:lcb3"] = _gr_ok
    names["bank_file:lcb_bank_v3.jsonl"] = (ROOT / "ops/gain/data/lcb_bank_v3.jsonl").exists()
    names["worker:gemma-4-12b-it-qat"] = "gemma-4-12b-it-qat" in _safe_read(PREREG)
    # `bank:lcb3@codebench` 是被推翻的舊定位，留作紀錄、不計入 missing
    missing = [k for k, v in names.items() if not v and k != "bank:lcb3@codebench"]
    return {"code": "X7", "intent": "guard",
            "class": "EVALUABLE" if not missing else "UNRESOLVED",
            "why": "§四 引用的名字都存在" if not missing else f"缺：{missing}",
            "names": names, "missing": missing,
            "lcb3_locator_note": ("事前預測對帳時 `bank:lcb3@codebench` 判 False ⇒ X7 記 MISS；"
                                  "查證後那是本量具的定位錯誤（dispatch 在 gain_run.py），"
                                  "**MISS 照實留在帳上**，見 GAIN_STATE round729")}


# ---------------------------------------------------------------- 主體
def census(runs_root: pathlib.Path | None = None) -> dict:
    sp = check_source_pins()
    pp = check_prereg_pins()
    out: dict = {"source_pins": sp, "prereg_pins": pp}
    if sp["drift"]:
        out["verdict"] = "SOURCE_DRIFT"
        out["why"] = f"B2：釘死的原始碼字面對不上 {sp['drift']} ⇒ 不吐任何分類"
        return out
    if pp["drift"]:
        out["verdict"] = "PREREG_DRIFT"
        out["why"] = f"B3：釘死的判準檔字面對不上 {pp['drift']} ⇒ 不吐任何分類"
        return out
    items = [census_vocab("X1", "OFF5_WINS"), census_vocab("X2", "CONFORM_WINS"),
             census_x3(), census_x4(), census_x5(), census_x6(runs_root), census_x7()]
    out["items"] = items
    out["counts"] = {k: sum(1 for i in items if i["class"] == k)
                     for k in ("EVALUABLE", "FORCED_GREEN", "UNRESOLVED", "UNSCANNED")}
    # B1：恆等式成立且 witness>0 ⇒ CONTRADICTION
    x3 = items[2]
    if x3["class"] == "FORCED_GREEN" and x3["witnesses"]:
        out["verdict"] = "CONTRADICTION"
        out["why"] = "B1：X3 同時判死碼卻列得出反例"
        return out
    bad = [i["code"] for i in items if i["class"] == "FORCED_GREEN" and i["intent"] == "evidence"]
    out["forced_green_evidence"] = bad
    out["verdict"] = "AMEND_REQUIRED" if bad else "OK"
    out["why"] = (f"推翻條件 1 觸發：{bad} 是 evidence 卻強制綠燈 ⇒ 主 run 發射前要修"
                  if bad else "沒有 intent=evidence 的強制綠燈")
    return out


# ---------------------------------------------------------------- selftest
def _ck(name: str, cond: bool, extra: str = "") -> None:
    print(f"  {'✓' if cond else '✗'} {name}{(' — ' + str(extra)) if not cond else ''}")
    if not cond:
        LAST_FAILS.append(name)


def selftest() -> int:
    global MUTANT
    LAST_FAILS.clear()
    print("== 乾淨 ==")
    a = census()
    _ck("A1 七筆都在", len(a.get("items", [])) == 7, a.get("verdict"))
    _ck("A2 沒有 SOURCE_DRIFT/PREREG_DRIFT", a["verdict"] in ("OK", "AMEND_REQUIRED"), a["verdict"])
    _ck("A3 X3 有反例（不是死碼）", a["items"][2]["class"] == "EVALUABLE", a["items"][2]["class"])
    _ck("A4 X4 基準率在 (0,1) 之間", 0.0 < a["items"][3]["greenlight_base_rate"] < 1.0)
    _ck("A5 X5 判決級 ≥ 數字級（寬）",
        a["items"][4]["base_rate_verdict_level"] >= a["items"][4]["base_rate_number_level"])
    _ck("A6 X6 掃到的 run 數 > 0", a["items"][5].get("runs_scanned", 0) > 0)
    _ck("A7 沒有 CONTRADICTION", a["verdict"] != "CONTRADICTION")

    print("== B6：閘門 run 隔離 ==")
    try:
        _safe_read(ROOT / "runs" / FORBIDDEN_RUN / "rows.jsonl")
        _ck("B6 讀閘門 run 會被擋", False, "沒擋住")
    except RuntimeError:
        _ck("B6 讀閘門 run 會被擋", True)
    _ck("B6b X6 的掃描沒有納入閘門 run",
        all(FORBIDDEN_RUN not in o["run"] for o in a["items"][5].get("over", [])))

    print("== B4：0 個 run ⇒ UNSCANNED 不是 FORCED_GREEN ==")
    empty = ROOT / "ops" / "gain" / "data" / "_r462_empty_runs"
    empty.mkdir(parents=True, exist_ok=True)
    e = census_x6(empty)
    _ck("B4 空目錄 ⇒ UNSCANNED", e["class"] == "UNSCANNED", e["class"])

    print("== 具名突變體 ==")
    cases = [
        ("M1_one_sided_p", lambda: census()["items"][2]["class"] == "FORCED_GREEN",
         "X3 在單尾 p 下應該變成死碼"),
        ("M2_void_denominator", lambda: census()["items"][5].get("max_void_pct") != a["items"][5].get("max_void_pct"),
         "X6 換分母後 max_void_pct 必須改變"),
        ("M3_drop_unscanned_branch", lambda: census_x6(empty)["class"] != "UNSCANNED",
         "刪掉 B4 分支後空目錄不再是 UNSCANNED"),
        ("M4_prereg_pin_drift", lambda: census()["verdict"] == "PREREG_DRIFT",
         "判準檔字面被改 ⇒ PREREG_DRIFT"),
        ("M5_source_pin_drift", lambda: census()["verdict"] == "SOURCE_DRIFT",
         "原始碼字面被改 ⇒ SOURCE_DRIFT"),
    ]
    for name, probe, desc in cases:
        MUTANT = name
        try:
            ok = probe()
        except Exception as ex:                       # crash 收場不算偵測到
            ok, desc = False, f"{desc}（改成 crash：{ex!r}）"
        MUTANT = ""
        _ck(f"{name} 被具名捕獲（{desc}）", ok)

    print("== M6：把 B6 拿掉之後隔離就失效（證明 B6 有牙齒）==")
    MUTANT = "M6_drop_b6_gate_isolation"
    try:
        _safe_read(ROOT / "runs" / FORBIDDEN_RUN / "rows.jsonl")
        m6 = True
    except RuntimeError:
        m6 = False
    except OSError:
        m6 = False                                    # 檔案不在＝測不到，不算捕獲
    MUTANT = ""
    _ck("M6_drop_b6_gate_isolation 被具名捕獲（拿掉 B6 就讀得到閘門 run）", m6)

    print("== 突變後 verdict 不變也要釘住（避免假測試）==")
    MUTANT = "M2_void_denominator"
    v2 = census()["verdict"]
    MUTANT = ""
    _ck("M2 不改 verdict（它動的是量不是判決）", v2 == a["verdict"], v2)

    print(f"\n{'FAIL: ' + ', '.join(LAST_FAILS) if LAST_FAILS else 'ALL PASS'}")
    return 1 if LAST_FAILS else 0


def main() -> int:
    global MUTANT
    MUTANT = os.environ.get("MUTANT", "")
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    out = census()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    return 0 if out["verdict"] not in ("SOURCE_DRIFT", "PREREG_DRIFT", "CONTRADICTION") else 1


if __name__ == "__main__":
    raise SystemExit(main())
