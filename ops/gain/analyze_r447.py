#!/usr/bin/env python3
"""R447（CONFORM on LCB v2）的收官分析尺——**在資料落地之前寫死**（round701）。

為什麼是這一輪寫（記憶鐵律：判準規則要寫在量測之前）：
  `runs/g_r447_conform_lcb2` 06:22 UTC 發射、120 題三臂、實測 ~38s/列 ⇒ 約 3.5 小時。
  本輪只有 11 列。收官那一輪會同時面對「數字」與「怎麼判」，那正是判準最容易
  被數字誘導的時刻。DECISION_20260904_R440Z_LCB2_PREREG.md §三/§四/§六 已把窗口與
  推翻條件寫死，本工具把那份文件**逐條編碼**，並且只在**合成夾具**上驗證。

估計量宣稱（收官不准換詞彙）：
  R447 答的是「**在 LCB v2 這個更難的題庫上，早停驗收閘門（CONFORM）比單抽（OFF）
  多交付多少**」，配對單位是 task。P-Z3 的 CONFORM vs OFF5 **不是等預算**
  （CONFORM ~1.8 呼叫 vs OFF5 5.00）⇒ 那一格不准寫成「等預算下誰贏」，
  等預算的答案在 r446/EQ5，不在這裡。

── 落地前就要裁掉的三個歧義（**都在看到任何比率之前裁定**，理由不含任何本 run 的數字）

  歧義 1：P-Z2／P-Z3 的 Δ 用哪個分母？（記憶鐵律：拒交臂 coverage<1 ⇒ 兩個分母
    會給出相反判決，仲裁者必須是事前文件。）DECISION §三 沒有明寫，但它引用的兩個
    錨點數字自己把分母講完了：
      E3 早停 vs 單抽 +20.88pp，b=19 c=0 ⇒ 19/91 = 20.879%  ⇒ 分母 = 兩臂共同量到的題數
      E3 CONFORM vs OFF5 +4.40pp，b−c=4  ⇒  4/91 =  4.396%  ⇒ 同一個分母
    ⇒ **仲裁分母 = n_common（兩臂都量到的格子）**，即 `paired_ci.diff_ci` 的 n。
    分母 accepted（只算交出去的）另外印，標 `NOT_ARBITER`，不參與任何判決。

  歧義 2：「P-Z2 成立」是指 §三 的點預測窗口，還是 §六 的推翻門檻？兩者不同
    （窗口 p<0.01 且 Δ∈[12,25]；§六 說「P-Z2 不成立」＝ p≥0.05 或 c≥b/2）。
    ⇒ 採用**文件自己給的操作型定義**：`pz2_holds` = (p < 0.05) 且 (c < b/2)。
    §三「本階足夠有效 ＝ P-Z2 成立 且 P-Z6 成立」用的是這個 `pz2_holds`；
    §三 表格那個 [12,25]pp／p<0.01 窗口單獨記成 `P-Z2-window` 的 HIT/MISS，不當閘門。
    （「b ≫ c」不另外發明門檻——文件自己的量化子句就是 p<0.01／c<b/2，新增旋鈕零。）

  歧義 3：P-Z5 的第二子句「拒交的題目裡『五份全錯』佔 ≥80%」**在 rows.jsonl 上
    結構性不可評估**。`arm_conform` 拒交時只把**最後一位**候選丟給 hidden_check
    計分（gain_run.py:578「拒交時仍然要回傳一份程式碼」），前 4 位候選從來沒被
    hidden 檢查過 ⇒ 5 份裡只觀察得到 1 份。E3 那個「6/91 全部本來就無解」是
    **離線重放 OFF5 的候選**，五份的 hidden 結果本來就都在，兩者不是同一種資料。
    ⇒ 本尺對 P-Z5b 一律回 `UNEVALUABLE_FROM_ROWS`，**不准當成通過**（round700 對
    M9 擋門的同一條規矩）。可用 `ops/gain/r447_reject_reconstruct.py` 從 calls.jsonl
    的全文回應離線重建那 4 份候選（零 API），重建結果是**補充證據**、
    要標明它不是 rows 直接量到的。

「安靜量不到」兩型都要擋（判準不是 rc≠0）：
  型一 缺欄位：任一列缺 REQUIRED 任一欄 ⇒ BROKEN，**不准**當 False 算過去。
  型二 量到的列數掉下來：rows 行數 + infra_void ≠ processed ⇒ BROKEN（帳對不上）。
  另外：run 未 terminal ⇒ BROKEN（期中資料不是收官資料）。

零新估計量、零新旋鈕：區間走 round656 已雙向驗證的 `paired_ci.diff_ci`
（Clopper-Pearson 條件區間），MDE／N₈₀ 走 `power_paired`，`deliv` 口徑 =
accepted ∧ meets_demand（R667 凍結），±5pp 沿用 `paired_ci.PRACTICAL_PP`。

用法：
  python3 ops/gain/analyze_r447.py --selftest
  python3 ops/gain/analyze_r447.py --run runs/g_r447_conform_lcb2 --json out.json
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from ops.gain.replay.paired_ci import diff_ci, verdict as raw_verdict, PRACTICAL_PP, n_needed  # noqa: E402
from ops.gain.power_paired import mde_at_n, n_needed_for_power  # noqa: E402

MUTANT = ""
LAST_FAILS: list[str] = []   # selftest 的失敗標籤，給 r447_mutation_check.py 逐條比對

REQUIRED = ("arm", "task_id", "meets_demand", "accepted", "calls_used", "visible_ok")
REQUIRED_CONFORM = ("conform_attempts", "conform_calls", "receipt_head")

# DECISION_20260904_R440Z_LCB2_PREREG.md §三 的事前窗口，逐條照抄。
# 這些數字的仲裁者是那份 DECISION，不是本檔；改這裡等於改事前註冊 ⇒ 不准。
PREREG = {
    "P-Z1":       ("OFF 失敗率 (%)",                         40.0, 60.0),
    "P-Z2-window": ("CONFORM−OFF Δ (pp, 分母 n_common)",     12.0, 25.0),
    "P-Z3":       ("CONFORM−OFF5 Δ (pp, 分母 n_common)",      2.0,  8.0),
    "P-Z4":       ("CONFORM calls_per_task",                  1.5,  2.2),
    "P-Z5":       ("CONFORM 拒交率 (%)",                      5.0, 12.0),
    "P-Z7a":      ("任一臂 infra_void 率的最大值 (%)",         0.0, 20.0),
    "P-Z7b":      ("CONFORM 臂 infra_void 率 (%)",            0.0,  5.0),
}
PZ2_WINDOW_P = 0.01   # §三 表格：p < 0.01（點預測，非閘門）
PZ2_HOLD_P = 0.05     # §六：p ≥ 0.05 ⇒ P-Z2 不成立（閘門用這個）


def window_hit(key: str, val: float | None) -> str:
    if val is None:
        return "UNEVALUABLE"
    _, lo, hi = PREREG[key]
    if MUTANT == "M10_widen_windows":
        lo, hi = -1e9, 1e9
    return "HIT" if lo <= val <= hi else "MISS"


def _rows_by_arm(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r.get("arm"), []).append(r)
    return out


def _deliv(r: dict) -> bool:
    """R667 凍結的口徑：交付成功 ＝ 交出去了(accepted) 且 真的對(meets_demand)。"""
    if MUTANT == "M1_deliv_ignores_accepted":
        return bool(r.get("meets_demand"))
    return bool(r.get("accepted")) and bool(r.get("meets_demand"))


def _paired(a_rows: list[dict], b_rows: list[dict]) -> dict:
    """A 相對 B 的配對計數。b = 只有 A 交付對、c = 只有 B 交付對，分母 n_common。"""
    A = {r["task_id"]: _deliv(r) for r in a_rows}
    B = {r["task_id"]: _deliv(r) for r in b_rows}
    common = sorted(set(A) & set(B))
    if MUTANT == "M2_union_denominator":
        common = sorted(set(A) | set(B))
    b = sum(1 for t in common if A.get(t) and not B.get(t))
    c = sum(1 for t in common if B.get(t) and not A.get(t))
    d = diff_ci(b, c, len(common))
    d["n_common"] = len(common)
    return d


def analyze(rows: list[dict], summary: dict) -> dict:
    out: dict = {"broken": [], "notes": []}
    arms = _rows_by_arm(rows)
    sarms = (summary.get("arms") or {})

    # ── 型一：缺欄位（不准當 False 算過去）
    missing: dict[str, int] = {}
    for r in rows:
        for k in REQUIRED:
            if k not in r:
                missing[k] = missing.get(k, 0) + 1
        if r.get("arm") == "CONFORM":
            for k in REQUIRED_CONFORM:
                if k not in r:
                    missing[k] = missing.get(k, 0) + 1
    out["missing_fields"] = missing
    if missing and MUTANT != "M3_ignore_missing_fields":
        out["broken"].append(f"missing_fields:{sorted(missing)}")

    # ── 型二：帳對不上（rows + void != processed）
    recon = {}
    for a, s in sarms.items():
        n_rows = len(arms.get(a, []))
        void = int(s.get("infra_void") or 0)
        proc = int(s.get("processed") or 0)
        recon[a] = {"rows": n_rows, "infra_void": void, "processed": proc,
                    "ok": n_rows + void == proc}
        if not recon[a]["ok"] and MUTANT != "M4_ignore_row_accounting":
            out["broken"].append(f"row_accounting:{a}:{n_rows}+{void}!={proc}")
    out["row_accounting"] = recon

    # ── run 必須 terminal（期中資料不是收官資料）
    terminal = bool(summary.get("run_terminal"))
    out["run_terminal"] = terminal
    if not terminal and MUTANT != "M5_ignore_terminal":
        out["broken"].append("run_not_terminal")

    if not rows:
        out["broken"].append("zero_rows")

    # ── 每臂描述量
    per: dict[str, dict] = {}
    for a, rs in sorted(arms.items()):
        n = len(rs)
        acc = sum(1 for r in rs if r.get("accepted"))
        dn = sum(1 for r in rs if _deliv(r))
        calls = [r.get("calls_used") for r in rs if isinstance(r.get("calls_used"), (int, float))]
        s = sarms.get(a) or {}
        proc = int(s.get("processed") or 0)
        void = int(s.get("infra_void") or 0)
        per[a] = {
            "measured": n, "accepted": acc, "deliv_n": dn,
            "deliv_pct_measured": 100.0 * dn / n if n else None,
            "deliv_pct_accepted_NOT_ARBITER": 100.0 * dn / acc if acc else None,
            "coverage_pct": 100.0 * acc / n if n else None,
            "calls_per_task": sum(calls) / len(calls) if calls else None,
            "infra_void": void, "processed": proc,
            "void_pct": 100.0 * void / proc if proc else None,
        }
    out["per_arm"] = per

    # ── P-Z1
    off = per.get("OFF")
    pz1 = (100.0 - off["deliv_pct_measured"]) if off and off["deliv_pct_measured"] is not None else None
    out["pz1_off_fail_pct"] = pz1

    # ── P-Z2 / P-Z3（分母 n_common，見 docstring 歧義 1）
    def _pair(a, b):
        if a in arms and b in arms:
            return _paired(arms[a], arms[b])
        return None
    p2 = _pair("CONFORM", "OFF")
    p3 = _pair("CONFORM", "OFF5")
    out["paired_conform_vs_off"] = p2
    out["paired_conform_vs_off5"] = p3

    pz2_holds = None
    if p2 is not None:
        pz2_holds = (p2["p_mcnemar"] < PZ2_HOLD_P) and (p2["c"] < p2["b"] / 2)
        if MUTANT == "M6_pz2_holds_ignores_direction":
            pz2_holds = p2["p_mcnemar"] < PZ2_HOLD_P
    out["pz2_holds"] = pz2_holds

    # ── P-Z6：rows 裡不准有 visible_ok=False 且 meets_demand=True 的列
    viol = [{"arm": r.get("arm"), "task_id": r.get("task_id")}
            for r in rows if r.get("visible_ok") is False and r.get("meets_demand") is True]
    if MUTANT == "M7_pz6_only_conform":
        viol = [v for v in viol if v["arm"] == "CONFORM"]
    out["pz6_violations"] = viol
    out["pz6_holds"] = (len(viol) == 0)

    # ── P-Z5：拒交率；第二子句結構上不可評估（見 docstring 歧義 3）
    conf = per.get("CONFORM")
    out["pz5_reject_pct"] = (100.0 - conf["coverage_pct"]) if conf and conf["coverage_pct"] is not None else None
    out["pz5b_all_five_wrong"] = (
        "EVALUABLE_ONLY_BY_RECONSTRUCTION" if MUTANT == "M8_pz5b_pass"
        else "UNEVALUABLE_FROM_ROWS")
    out["pz5b_reason"] = ("arm_conform 拒交時只有最後一位候選被 hidden_check 計分；"
                          "前 4 位候選的 hidden 結果不在 rows.jsonl ⇒ 不准判通過")

    # ── P-Z7
    voids = [v["void_pct"] for v in per.values() if v["void_pct"] is not None]
    out["pz7a_max_void_pct"] = max(voids) if voids else None
    out["pz7b_conform_void_pct"] = conf["void_pct"] if conf else None

    # ── P-Z8：收據
    crows = arms.get("CONFORM", [])
    out["pz8_receipt_head_present"] = (
        all(bool(r.get("receipt_head")) for r in crows) if crows else None)

    # ── 窗口 HIT/MISS
    hits = {
        "P-Z1": window_hit("P-Z1", pz1),
        "P-Z2-window": window_hit("P-Z2-window", p2["delta"] * 100 if p2 else None),
        "P-Z3": window_hit("P-Z3", p3["delta"] * 100 if p3 else None),
        "P-Z4": window_hit("P-Z4", conf["calls_per_task"] if conf else None),
        "P-Z5": window_hit("P-Z5", out["pz5_reject_pct"]),
        "P-Z7a": window_hit("P-Z7a", out["pz7a_max_void_pct"]),
        "P-Z7b": window_hit("P-Z7b", out["pz7b_conform_void_pct"]),
    }
    if p2 is not None:
        # §三 表格的 p<0.01 是點預測的一部分，與窗口一起才算 HIT
        if hits["P-Z2-window"] == "HIT" and not (p2["p_mcnemar"] < PZ2_WINDOW_P and p2["b"] > p2["c"]):
            hits["P-Z2-window"] = "MISS"
    out["prereg_hits"] = hits

    # ── §六 推翻條件
    ot = []
    if p2 is not None and not pz2_holds:
        ot.append("P-Z2_overturned(p>=0.05_or_c>=b/2)")
    if not out["pz6_holds"]:
        ot.append("P-Z6_overturned(visible_fail_but_hidden_pass)")
    if pz1 is not None and pz1 > 70.0:
        ot.append("bank_too_hard(off_fail>70%)")
    if out["pz7a_max_void_pct"] is not None and out["pz7a_max_void_pct"] > 20.0:
        ot.append("infra_void>20%")
    if MUTANT == "M9_drop_overturn":
        ot = []
    out["overturn_conditions_triggered"] = ot

    # ── §三「本階足夠有效」＝ P-Z2 成立 且 P-Z6 成立
    if out["broken"]:
        out["verdict_stage"] = "BROKEN"
    elif pz2_holds is None:
        out["verdict_stage"] = "BROKEN"
    else:
        out["verdict_stage"] = ("STAGE_EFFECTIVE" if (pz2_holds and out["pz6_holds"])
                                else "STAGE_NOT_EFFECTIVE")

    # ── 區間位置表（R670 §三／paired_ci.verdict 同一張表）
    if p2 is not None:
        out["verdict_four_cell_conform_vs_off"] = raw_verdict(p2["lo"] * 100, p2["hi"] * 100)
    if p3 is not None:
        out["verdict_four_cell_conform_vs_off5"] = raw_verdict(p3["lo"] * 100, p3["hi"] * 100)
        out["note_pz3_not_equal_budget"] = (
            "CONFORM ~1.8 呼叫 vs OFF5 5.00 ⇒ 這一格不是等預算比較，"
            "不准寫成『等預算下誰贏』（等預算的答案在 r446/EQ5）")

    # ── 檢定力
    if p2 is not None and p2["n_common"]:
        out["power_conform_vs_off"] = {
            "mde_at_n": mde_at_n(p2["n_common"], p2["n_discordant"] / p2["n_common"]),
            "n_needed_for_5pp": n_needed(p2["n_discordant"], p2["n_common"]),
        }
    return out


# ────────────────────────────────────────────────────────────────────────────
# 自檢夾具：**刻意不共用** analyze() 內部任何 helper，欄位名在這裡獨立寫死一次。
# （round699 的教訓是「夾具與被測端同源 ⇒ 全綠不構成證據」；這裡兩邊都寫死
#   同一組字面字串，任何一邊改名 selftest 就會紅。）
def _r(arm, tid, *, deliv=True, accepted=True, visible_ok=True, calls=1, conform=False):
    d = {"arm": arm, "task_id": tid, "meets_demand": bool(deliv),
         "accepted": bool(accepted), "calls_used": calls, "visible_ok": visible_ok}
    if conform or arm == "CONFORM":
        d.update({"conform_attempts": [{"attempt": 1, "visible_ok": visible_ok}],
                  "conform_calls": calls, "receipt_head": "deadbeef"})
    return d


def _summary(counts: dict[str, tuple[int, int]], terminal=True):
    """counts: arm -> (processed, infra_void)。processed 含 void（gain_run.py:1474）。"""
    return {"run_terminal": terminal,
            "arms": {a: {"processed": p, "infra_void": v} for a, (p, v) in counts.items()}}


def _fixture(n=100, b_only=20, c_only=2, both=40):
    """CONFORM 贏 b_only 格、OFF 贏 c_only 格、both 格兩邊都對，其餘兩邊都錯。"""
    rows = []
    for i in range(n):
        t = f"t{i:03d}"
        if i < b_only:
            cd, od = True, False
        elif i < b_only + c_only:
            cd, od = False, True
        elif i < b_only + c_only + both:
            cd, od = True, True
        else:
            cd, od = False, False
        rows.append(_r("CONFORM", t, deliv=cd, calls=2))
        rows.append(_r("OFF", t, deliv=od, calls=1))
        rows.append(_r("OFF5", t, deliv=od, calls=5))
    return rows, _summary({"CONFORM": (n, 0), "OFF": (n, 0), "OFF5": (n, 0)})


def selftest() -> int:
    global MUTANT, LAST_FAILS
    fails = []
    LAST_FAILS = fails

    def ck(label, cond, extra=""):
        print(f"  {'ok  ' if cond else 'FAIL'} {label} {extra}")
        if not cond:
            fails.append(label)

    rows, summ = _fixture()
    a = analyze(rows, summ)
    ck("A 乾淨夾具不 BROKEN", a["broken"] == [], a["broken"])
    ck("A2 b/c 正確", a["paired_conform_vs_off"]["b"] == 20 and a["paired_conform_vs_off"]["c"] == 2,
       f"b={a['paired_conform_vs_off']['b']} c={a['paired_conform_vs_off']['c']}")
    ck("A3 Δ = (b-c)/n_common", abs(a["paired_conform_vs_off"]["delta"] * 100 - 18.0) < 1e-9,
       f"{a['paired_conform_vs_off']['delta']*100:.4f}pp")
    ck("A4 STAGE_EFFECTIVE", a["verdict_stage"] == "STAGE_EFFECTIVE", a["verdict_stage"])
    ck("A5 P-Z2-window HIT", a["prereg_hits"]["P-Z2-window"] == "HIT")

    # B 型一：缺欄位 ⇒ BROKEN，不准當 False
    r2 = [dict(x) for x in rows]
    r2[0].pop("meets_demand")
    ck("B 缺欄位 ⇒ BROKEN", "BROKEN" == analyze(r2, summ)["verdict_stage"])

    # B2 CONFORM 專屬欄位也要擋
    r2b = [dict(x) for x in rows]
    for x in r2b:
        if x["arm"] == "CONFORM":
            x.pop("receipt_head"); break
    ck("B2 缺 receipt_head ⇒ BROKEN", "BROKEN" == analyze(r2b, summ)["verdict_stage"])

    # C 型二：帳對不上
    ck("C rows+void!=processed ⇒ BROKEN",
       "BROKEN" == analyze(rows, _summary({"CONFORM": (100, 0), "OFF": (100, 0), "OFF5": (105, 0)}))["verdict_stage"])
    ck("C2 void 算進 processed 時帳要對",
       analyze(rows, _summary({"CONFORM": (101, 1), "OFF": (100, 0), "OFF5": (100, 0)}))["broken"] == [])

    # D 未 terminal
    ck("D run_terminal=False ⇒ BROKEN",
       "BROKEN" == analyze(rows, _summary({"CONFORM": (100, 0), "OFF": (100, 0), "OFF5": (100, 0)}, terminal=False))["verdict_stage"])

    # E 零列
    ck("E 0 列 ⇒ BROKEN（不是全綠）", "BROKEN" == analyze([], _summary({}))["verdict_stage"])

    # F P-Z6 反例
    r3 = [dict(x) for x in rows]
    r3[1]["visible_ok"] = False; r3[1]["meets_demand"] = True
    f = analyze(r3, summ)
    ck("F P-Z6 反例被抓到", len(f["pz6_violations"]) == 1 and not f["pz6_holds"])
    ck("F2 P-Z6 反例 ⇒ 觸發推翻條件", "P-Z6_overturned(visible_fail_but_hidden_pass)" in f["overturn_conditions_triggered"])
    ck("F3 P-Z6 反例 ⇒ 不算 STAGE_EFFECTIVE", f["verdict_stage"] == "STAGE_NOT_EFFECTIVE")
    # 反例故意放在 OFF 列上：只掃 CONFORM 的實作要在這裡紅，而且**不准用 crash 紅**
    # （crash 收場不算偵測到，見 r447_mutation_check.py 的判準）。
    ck("F4 P-Z6 掃全部臂不只 CONFORM", [v["arm"] for v in f["pz6_violations"]] == ["OFF"],
       str(f["pz6_violations"]))

    # G deliv 必須同時要 accepted
    r4 = [dict(x) for x in rows]
    n_before = analyze(r4, summ)["per_arm"]["CONFORM"]["deliv_n"]
    for x in r4:
        if x["arm"] == "CONFORM" and x["meets_demand"]:
            x["accepted"] = False; break
    ck("G accepted=False 不算交付", analyze(r4, summ)["per_arm"]["CONFORM"]["deliv_n"] == n_before - 1)

    # H 分母是 n_common（只出現在單臂的 task 要被排除）
    r5 = rows + [_r("CONFORM", "extra", deliv=True, calls=2)]
    s5 = _summary({"CONFORM": (101, 0), "OFF": (100, 0), "OFF5": (100, 0)})
    h = analyze(r5, s5)
    ck("H n_common 排除單臂題", h["paired_conform_vs_off"]["n_common"] == 100,
       str(h["paired_conform_vs_off"]["n_common"]))

    # I pz2_holds 的兩個條件各自有牙齒
    r6, s6 = _fixture(n=100, b_only=6, c_only=5, both=40)   # p 大 ⇒ 不成立
    i1 = analyze(r6, s6)
    ck("I p>=0.05 ⇒ pz2_holds False", i1["pz2_holds"] is False,
       f"p={i1['paired_conform_vs_off']['p_mcnemar']:.4f}")
    ck("I2 pz2 不成立 ⇒ 觸發推翻條件", "P-Z2_overturned(p>=0.05_or_c>=b/2)" in i1["overturn_conditions_triggered"])
    r7, s7 = _fixture(n=300, b_only=40, c_only=20, both=40)  # p 小但 c>=b/2
    i2 = analyze(r7, s7)
    ck("I3 c>=b/2 ⇒ pz2_holds False 即使 p 小",
       i2["pz2_holds"] is False and i2["paired_conform_vs_off"]["p_mcnemar"] < 0.05,
       f"p={i2['paired_conform_vs_off']['p_mcnemar']:.6f}")

    # J 窗口邊界（含 inclusive）
    ck("J P-Z4 邊界 1.5 是 HIT", window_hit("P-Z4", 1.5) == "HIT")
    ck("J2 P-Z4 邊界 2.2 是 HIT", window_hit("P-Z4", 2.2) == "HIT")
    ck("J3 P-Z4 2.21 是 MISS", window_hit("P-Z4", 2.21) == "MISS")
    ck("J4 None ⇒ UNEVALUABLE 不是 HIT", window_hit("P-Z1", None) == "UNEVALUABLE")
    ck("J5 窗口數字與 DECISION 同步（P-Z1 40–60）", PREREG["P-Z1"][1:] == (40.0, 60.0))

    # K P-Z5b 永遠不准判通過
    ck("K P-Z5b = UNEVALUABLE_FROM_ROWS", a["pz5b_all_five_wrong"] == "UNEVALUABLE_FROM_ROWS")

    # L 拒交率與 void
    r8 = [dict(x) for x in rows]
    nrej = 0
    for x in r8:
        if x["arm"] == "CONFORM" and nrej < 8:
            x["accepted"] = False; x["meets_demand"] = False; nrej += 1
    l = analyze(r8, summ)
    ck("L 拒交率 = 100-coverage", abs(l["pz5_reject_pct"] - 8.0) < 1e-9, f"{l['pz5_reject_pct']}")
    v = analyze(rows, _summary({"CONFORM": (100, 0), "OFF": (130, 30), "OFF5": (100, 0)}))
    ck("L2 void>20% ⇒ 觸發推翻條件", "infra_void>20%" in v["overturn_conditions_triggered"],
       f"max_void={v['pz7a_max_void_pct']:.2f}%")
    # 邊界：§四 寫的是「> 20%」，恰好 20.00% 不觸發（25/125）——方向不准放寬
    vb = analyze(rows, _summary({"CONFORM": (100, 0), "OFF": (125, 25), "OFF5": (100, 0)}))
    ck("L3 恰好 20.00% 不觸發（§四 是嚴格大於）",
       "infra_void>20%" not in vb["overturn_conditions_triggered"]
       and abs(vb["pz7a_max_void_pct"] - 20.0) < 1e-9)

    # M 四格判決與 paired_ci.verdict 同一張表
    ck("M 四格 = paired_ci.verdict",
       a["verdict_four_cell_conform_vs_off"] == raw_verdict(
           a["paired_conform_vs_off"]["lo"] * 100, a["paired_conform_vs_off"]["hi"] * 100))

    # N OFF 失敗率與題庫太難的擋門
    r9, s9 = _fixture(n=100, b_only=20, c_only=0, both=5)   # OFF 只對 5 格 ⇒ 失敗率 95%
    n9 = analyze(r9, s9)
    ck("N OFF 失敗率算對", abs(n9["pz1_off_fail_pct"] - 95.0) < 1e-9, f"{n9['pz1_off_fail_pct']}")
    ck("N2 OFF 失敗率>70% ⇒ 觸發推翻條件", "bank_too_hard(off_fail>70%)" in n9["overturn_conditions_triggered"])

    # O tripwire 投影不准漏出任何比率
    tw = tripwire(a)
    leaked = [k for k in tw if k in TRIPWIRE_FORBIDDEN]
    ck("O tripwire 不漏比率（鍵名逐字）", not leaked, str(leaked))
    ck("O1b tripwire 鍵是白名單子集",
       set(tw) <= set(TRIPWIRE_KEYS), str(sorted(set(tw) - set(TRIPWIRE_KEYS))))
    _blob = json.dumps(tw, ensure_ascii=False, default=str)
    ck("O1c 序列化輸出裡沒有 delta／p_mcnemar／deliv 字樣",
       not any(w in _blob for w in ("delta", "p_mcnemar", "deliv_")), _blob[:120])
    ck("O2 tripwire 保留 §四 四項",
       all(k in tw for k in ("pz6_holds", "pz7a_max_void_pct", "run_terminal",
                             "overturn_conditions_triggered")))
    n9b = analyze(*_fixture(n=100, b_only=20, c_only=0, both=5))
    ck("O2b tripwire 不准漏 P-Z2 推翻與否（那是 b/c/p 導出的）",
       not any(x.startswith("P-Z2") for x in tripwire(analyze(*_fixture(n=100, b_only=6, c_only=5, both=40)))
               ["overturn_conditions_triggered"]))
    ck("O2c 被延後的條目有具名列出、不是安靜丟掉",
       set(tripwire(a)["deferred_to_collapse"]) == set(TRIPWIRE_DEFERRED))
    _live = analyze(rows, _summary({"CONFORM": (100, 0), "OFF": (100, 0), "OFF5": (100, 0)}, terminal=False))
    ck("O2d run 活著時 row_accounting 標成不適用",
       isinstance(tripwire(_live)["row_accounting"], str))
    ck("O3 tripwire 遮掉『題庫太難』（那是 OFF 失敗率導出的）",
       "bank_too_hard(off_fail>70%)" in n9b["overturn_conditions_triggered"]
       and not any(x.startswith("bank_too_hard") for x in
                   tripwire(n9b)["overturn_conditions_triggered"]))

    print(f"SELFTEST {'PASS' if not fails else 'FAIL'} ({len(fails)} failed) MUTANT={MUTANT or 'none'}")
    return 1 if fails else 0


# §四 中止準則的白名單投影：監看輪用這個，**看不到** Δ／b／c／任何交付率。
# 期中偷看比率會誘導後續決定（序貫問題），所以擋在工具層而不是靠自律。
TRIPWIRE_KEYS = ("deferred_to_collapse", "pz6_violations", "pz6_holds", "pz7a_max_void_pct",
                 "pz7b_conform_void_pct", "row_accounting", "missing_fields",
                 "run_terminal", "overturn_conditions_triggered")
# 逐字的**鍵名**黑名單（不准用子字串比對：'c' 會匹配到 'pz7a_max_void_pct'，
# 第一版就是這樣把整條判準弄成恆為真）。
TRIPWIRE_FORBIDDEN = ("paired_conform_vs_off", "paired_conform_vs_off5", "per_arm",
                      "pz1_off_fail_pct", "prereg_hits", "verdict_stage", "pz2_holds",
                      "pz5_reject_pct", "verdict_four_cell_conform_vs_off",
                      "verdict_four_cell_conform_vs_off5", "power_conform_vs_off")


# 期中**不評估**的推翻條件，連「有沒有觸發」都不准漏（觸發與否本身就是比率的訊息）。
# 兩條都是這樣被擋掉的：
#   bank_too_hard  ── 從 OFF 失敗率導出
#   P-Z2_overturned ── 從配對 b/c/p 導出，而且它是 §六（收官）不是 §四（中止）
# 代價寫明：§四「OFF 失敗率 > 70% ⇒ 題庫太難」因此**期中無法據以中止**，
# 延到收官那一輪判。這是刻意的取捨——期中看比率再決定要不要繼續＝序貫決策污染，
# 而這個 run $0 且 3.5 小時就跑完，中止省下的東西比污染便宜。
TRIPWIRE_DEFERRED = ("bank_too_hard(off_fail>70%)", "P-Z2_overturned(p>=0.05_or_c>=b/2)")


def tripwire(full: dict) -> dict:
    out = {k: full[k] for k in TRIPWIRE_KEYS if k in full}
    out["overturn_conditions_triggered"] = [
        x for x in out.get("overturn_conditions_triggered", [])
        if not any(x.startswith(d.split("(")[0]) for d in TRIPWIRE_DEFERRED)]
    # 不是安靜丟掉：無條件列出「本模式不評估哪幾條」，值不印。
    out["deferred_to_collapse"] = list(TRIPWIRE_DEFERRED)
    # run 還活著時 summary.json 是週期性快照、rows.jsonl 是即時追加 ⇒ rows > processed
    # 是**正常的**，不是帳對不上。只有 terminal 的 run 這條才有意義。
    if not full.get("run_terminal"):
        out["row_accounting"] = "NOT_APPLICABLE_WHILE_RUNNING（summary 快照落後 rows）"
    return out


def main() -> int:
    global MUTANT
    MUTANT = os.environ.get("MUTANT", "")
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--tripwire", action="store_true",
                    help="只印 DECISION §四 的中止準則，不印任何比率（監看輪用）")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.run:
        ap.error("--run 或 --selftest 二選一")
    d = pathlib.Path(args.run)
    raw = (d / "rows.jsonl").read_bytes()
    rows = [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    out = analyze(rows, summary)
    if args.tripwire:
        tw = tripwire(out)
        tw["rows_lines"] = len(rows)
        tw["rows_sha256_16"] = hashlib.sha256(raw).hexdigest()[:16]
        print(json.dumps(tw, ensure_ascii=False, indent=2, default=str))
        return 0
    out["rows_lines"] = len(rows)
    out["rows_sha256_16"] = hashlib.sha256(raw).hexdigest()[:16]
    out["run"] = str(d)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return 0 if out["verdict_stage"] != "BROKEN" else 1


if __name__ == "__main__":
    sys.exit(main())
