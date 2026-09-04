#!/usr/bin/env python3
"""EQ5（等預算臂）的收官分析尺——**在資料落地之前寫死**（round691）。

為什麼是這一輪寫（記憶鐵律：判準規則要寫在量測之前）：
  r446（`runs/g_r446_eq5_mbpp`）01:54 UTC 發射、預估 6–8 小時，本輪只有 15/371 題。
  收官那一輪會同時面對「數字」與「怎麼判」，那正是判準最容易被數字誘導的時刻。
  DECISION_20260904_R446_EQUAL_BUDGET_ARM.md §四/§五/§六 已把窗口與推翻條件寫死，
  本工具把那份文件**逐條編碼**，並在**只有合成夾具**的條件下驗證——
  刻意不跑在活著的 run 上（DECISION §五：中途不准算 Δ）。

估計量宣稱（DECISION §二，收官不准換詞彙）：
  EQ5 答的是「**給定同一組候選，哪一條選擇規則交付得多**」。
  b = 只有閘門交付對、c = 只有多數決交付對，配對單位是 task。
  它**不**答「兩個各自獨立抽樣的系統誰贏」（r445 的估計量，已收官）。

零新估計量、零新旋鈕：
  區間走 round656 已雙向驗證的 `paired_ci.diff_ci`（Clopper-Pearson 條件區間），
  MDE／N₈₀ 走 round260 的 `power_paired.mde_at_n` / `n_needed_for_power`，
  `deliv` 口徑 = accepted ∧ meets_demand（R667 :40 凍結），
  ±5pp 實務門檻沿用 `paired_ci.PRACTICAL_PP`。本檔沒有任何新的可調參數。

「安靜量不到」兩型都要擋（記憶鐵律，判準不是 rc≠0）：
  型一 缺欄位：任何一列缺 `gate_deliv`／`vote_deliv`／`calls_used` ⇒ BROKEN，
       **不准**當 False 算過去（那是方向性偏誤，不是雜訊）。
  型二 量到的列數掉下來：rows 行數 + void ≠ processed ⇒ BROKEN（帳對不上）。

用法：
  python3 ops/gain/analyze_eq5.py --selftest          # 合成夾具＋突變體
  python3 ops/gain/analyze_eq5.py --run runs/g_r446_eq5_mbpp --json out.json
"""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from ops.gain.replay.paired_ci import diff_ci, PRACTICAL_PP, n_needed  # noqa: E402
from ops.gain.power_paired import mde_at_n, n_needed_for_power        # noqa: E402

MUTANT = ""

# AMEND-1：`gate_code_sha256`/`vote_code_sha256` 是 same_choice_effective 的離線重算
# 輸入。突變體 M8 就是「少了它們也照跑，退回 raw」——那是安靜量錯東西。
REQUIRED = ("gate_deliv", "vote_deliv", "calls_used", "same_choice", "accepted",
            "gate_code_sha256", "vote_code_sha256")

# DECISION_20260904_R446_EQUAL_BUDGET_ARM.md §四 的事前窗口，逐條照抄。
# 這些數字的仲裁者是那份 DECISION，不是本檔；改這裡等於改事前註冊 ⇒ 不准。
PREREG = {
    "P-R446-1": ("calls_per_task 恰好 5.00", 5.0, 5.0),
    "P-R446-2": ("閘門拒交率 1-coverage (%)", 3.0, 13.0),
    "P-R446-3": ("閘門 deliv%（分母 measured）", 68.0, 84.0),
    "P-R446-4": ("多數決 deliv%（分母 measured）", 64.0, 80.0),
    "P-R446-5": ("same_choice_effective_rate (%)（AMEND-1 起的仲裁量）", 40.0, 95.0),
    "P-R446-7": ("discordant pair 數 n_d", 15.0, float("inf")),
    "P-R446-8": ("infra_void 率 (%)", 0.0, 5.0),
}


def four_cell(lo_pp: float, hi_pp: float) -> str:
    """R670 §三 的區間位置表，用 **EQ5 的詞彙**（DECISION §二禁止沿用「系統誰贏」）。

    與 `paired_ci.verdict()` 是同一張表、同一組邊界；這裡只換標籤，
    所以 selftest 條 V 逐格比對兩者必須同構（不准變成第二套判準）。
    """
    if lo_pp > 0:
        return "GATE_RULE_WINS"
    if hi_pp <= PRACTICAL_PP:
        return "RULED_OUT"          # 資料容不下 +5pp ⇒ 閘門規則沒有實務增益
    if lo_pp < -PRACTICAL_PP:
        return "UNINFORMATIVE"      # 區間兩頭都超過實務門檻 ⇒ 沒量出來
    return "NON_INFERIOR_BUT_UNRESOLVED"


def analyze(rows: list[dict], summary: dict, rows_meta: dict | None = None) -> dict:
    eq5 = [r for r in rows if r.get("arm") == "EQ5"]
    broken: list[str] = []
    required = (tuple(f for f in REQUIRED if not f.endswith("_code_sha256"))
                if MUTANT == "M8" else REQUIRED)

    # ── 「安靜量不到」型一：缺欄位不准當 False ────────────────────────────
    if MUTANT == "M4":
        missing = []
    else:
        missing = [r.get("task_id") for r in eq5
                   if any(f not in r for f in required)]
    if missing:
        broken.append(f"{len(missing)} 列缺 {'/'.join(required)} 其中之一"
                      f"（例：{missing[:3]}）——這不是通過，是量不到")
    eq5 = [r for r in eq5 if all(f in r for f in required)]

    measured = len(eq5)
    arm_summ = (summary.get("arms") or {}).get("EQ5", {})
    # 欄位名逐字取自 gain_run.py:finalize()（`processed`／`infra_void`／`terminal`），
    # 不是照下游變數名猜的（記憶鐵律：輸出契約要讀原始碼）。
    processed = arm_summ.get("processed")
    void = arm_summ.get("infra_void")
    terminal = arm_summ.get("terminal")
    if MUTANT != "M6" and terminal is not True:
        broken.append(f"EQ5.terminal={terminal!r} ⇒ run 還沒把每題都處理過一次，"
                      "這不是收官資料（DECISION §五：中途不准算 Δ）")

    # ── 「安靜量不到」型二：帳要對得上 ────────────────────────────────────
    if processed is None or void is None:
        broken.append("summary.json 的 EQ5 沒有 processed／infra_void——量不到，不是 0")
    elif MUTANT != "M5" and measured + void != processed:
        broken.append(f"帳對不上：rows(EQ5)={measured} + void={void} ≠ processed={processed}")

    void_rate = (100.0 * void / processed) if processed else None

    # ── 預算：等預算是結構性的，一列不等於 5 就是實作缺陷 ─────────────────
    calls = [r["calls_used"] for r in eq5]
    calls_per_task = (sum(calls) / measured) if measured else None
    if MUTANT == "M2":
        budget_all_5 = all(c <= 5 for c in calls)
    else:
        budget_all_5 = bool(calls) and all(c == 5 for c in calls)

    # ── 兩條選擇規則（deliv 口徑 R667 :40 凍結） ──────────────────────────
    if MUTANT == "M3":
        gate_ok = [bool(r.get("meets_demand")) for r in eq5]          # 漏掉 accepted
    else:
        gate_ok = [bool(r["gate_deliv"]) for r in eq5]
    vote_ok = [bool(r["vote_deliv"]) for r in eq5]
    n_accepted = sum(1 for r in eq5 if r["accepted"])

    if MUTANT == "M1":
        b = sum(1 for g, v in zip(gate_ok, vote_ok) if v and not g)   # b/c 顛倒
        c = sum(1 for g, v in zip(gate_ok, vote_ok) if g and not v)
    else:
        b = sum(1 for g, v in zip(gate_ok, vote_ok) if g and not v)
        c = sum(1 for g, v in zip(gate_ok, vote_ok) if v and not g)

    r = diff_ci(b, c, measured) if measured else None
    lo_pp = r["lo"] * 100 if r else None
    hi_pp = r["hi"] * 100 if r else None
    d_pp = r["delta"] * 100 if r else None

    # ── same_choice：raw 與 effective 兩個都算（AMEND-1；raw 保留、不是仲裁者）──
    n_same_raw = sum(1 for x in eq5 if x["same_choice"])
    same_choice_rate = (100.0 * n_same_raw / measured) if measured else None
    def _sha_eq(x):
        return x.get("gate_code_sha256") == x.get("vote_code_sha256")

    if MUTANT == "M7":
        # 退回 AMEND-1 之前：拒交格的 fallback 相同也算「選到同一份」
        eff_flags = [bool(x["same_choice"]) for x in eq5]
    else:
        eff_flags = [bool(x["accepted"]) and _sha_eq(x) for x in eq5]
    same_choice_eff_rate = (100.0 * sum(eff_flags) / measured) if measured else None
    false_same_choice_n = sum(1 for x in eq5
                              if (not x["accepted"]) and x["same_choice"])
    # raw 欄位自己也要對得上 sha（擋掉「same_choice 與兩份 sha 互相矛盾」的漂移）
    drift = [x["task_id"] for x in eq5 if bool(x["same_choice"]) != _sha_eq(x)]
    if drift:
        broken.append(f"same_choice 與 gate/vote sha 不一致 {len(drift)} 筆：{drift[:5]}")
    # 未來的 run 會自己落盤 same_choice_effective；有就必須與重算逐筆相同（AMEND-1 §七）
    landed = [(x, f) for x, f in zip(eq5, eff_flags) if "same_choice_effective" in x]
    if MUTANT != "M9":
        bad_eff = [x["task_id"] for x, f in landed if bool(x["same_choice_effective"]) != f]
        if bad_eff:
            broken.append("落盤的 same_choice_effective 與離線重算不一致 "
                          f"{len(bad_eff)} 筆：{bad_eff[:5]}（AMEND-1 §七：不准取其一）")
    gate_deliv_pp = 100.0 * sum(gate_ok) / measured if measured else None
    gate_deliv_accepted_pp = (100.0 * sum(gate_ok) / n_accepted) if n_accepted else None
    vote_deliv_pp = 100.0 * sum(vote_ok) / measured if measured else None
    coverage_pp = 100.0 * n_accepted / measured if measured else None

    # ── 事前預測逐條判 HIT／MISS（窗口取自 DECISION §四，本檔不得改） ─────
    observed = {
        "P-R446-1": calls_per_task,
        "P-R446-2": (100.0 - coverage_pp) if coverage_pp is not None else None,
        "P-R446-3": gate_deliv_pp,
        "P-R446-4": vote_deliv_pp,
        "P-R446-5": same_choice_eff_rate,
        "P-R446-7": float(r["n_discordant"]) if r else None,
        "P-R446-8": void_rate,
    }
    preds = {}
    for k, (what, lo, hi) in PREREG.items():
        v = observed[k]
        preds[k] = {"what": what, "window": [lo, hi], "observed": v,
                    "verdict": "NOT_MEASURED" if v is None
                    else ("HIT" if lo - 1e-9 <= v <= hi + 1e-9 else "MISS")}
    # P-R446-5-raw：AMEND-1 之後不是仲裁者，但無條件印、無條件判，
    # 讓後輪能不重跑就自行改判（AMEND-1 §五-2）。
    preds["P-R446-5-raw"] = {
        "what": "same_choice_rate (%)（raw；AMEND-1 之後不是仲裁者）",
        "window": [40.0, 95.0], "observed": same_choice_rate,
        "verdict": "NOT_MEASURED" if same_choice_rate is None
        else ("HIT" if 40.0 <= same_choice_rate <= 95.0 else "MISS")}
    # P-R446-6 是方向預測（點估計 > 0），不是窗口
    preds["P-R446-6"] = {"what": "Δ = 閘門 − 多數決 的點估計 > 0", "window": None,
                         "observed": d_pp,
                         "verdict": "NOT_MEASURED" if d_pp is None
                         else ("HIT" if d_pp > 0 else "MISS")}

    # ── DECISION §六 的推翻條件（事前寫，觸發就照實寫、不當場補判準） ─────
    overturned = []
    if same_choice_eff_rate is not None and same_choice_eff_rate > 95.0:
        overturned.append("§六-1 same_choice_effective_rate>95% ⇒ 兩條規則幾乎等價，"
                          "結論只准寫「測不出來」，不准寫「等預算下打平」")
    if (same_choice_rate is not None and same_choice_eff_rate is not None
            and same_choice_rate > 95.0 >= same_choice_eff_rate):
        overturned.append("§六-1 raw 與 effective 給出相反判決（raw "
                          f"{same_choice_rate:.2f}% > 95 ≥ effective "
                          f"{same_choice_eff_rate:.2f}%）⇒ AMEND-1 §七：兩個判決都寫進"
                          "結論，該信哪個留給人類，本輪不代答")
    if r and r["n_discordant"] < 15:
        overturned.append("§六-2 n_d<15 ⇒ 檢定力不足，寫 UNRESOLVED 並**同時**報 MDE／N₈₀"
                          "（round678：UNRESOLVED 是「沒量出來」不是「沒有差異」）")
    if gate_deliv_pp is not None and not (68.0 <= gate_deliv_pp <= 84.0):
        overturned.append("§六-3 閘門 deliv% 掉出 [68,84] ⇒ 先查實作（EQ5 閘門與 CONFORM "
                          "只差早停），不解讀結果")
    if not budget_all_5:
        broken.append("DECISION §五：有 row 的 calls_used ≠ 5 ⇒ 實作缺陷，不當資料用")

    disc_rate = (r["n_discordant"] / measured) if (r and measured) else 0.0
    out = {
        "estimator_claim": "同一組候選下，閘門規則 vs 多數決規則的交付差（配對單位＝task）",
        "not_this_estimator": "不是「兩個獨立抽樣的系統誰贏」（r445 的估計量，已收官）",
        "measured": measured, "processed": processed, "infra_void": void,
        "void_rate_pp": void_rate,
        "third_category_missing_fields": missing,
        "calls_per_task": calls_per_task, "budget_all_exactly_5": budget_all_5,
        "gate": {"accepted": n_accepted, "coverage_pp": coverage_pp,
                 "deliv_n": sum(gate_ok), "deliv_pp_denom_measured": gate_deliv_pp,
                 "deliv_pp_denom_accepted": gate_deliv_accepted_pp},
        "vote": {"deliv_n": sum(vote_ok), "deliv_pp_denom_measured": vote_deliv_pp},
        "same_choice_rate_pp": same_choice_rate,
        "same_choice_effective_rate_pp": same_choice_eff_rate,
        "false_same_choice_n": false_same_choice_n,
        "paired": {"b_gate_only": b, "c_vote_only": c,
                   "n_discordant": r["n_discordant"] if r else None,
                   "delta_pp": d_pp, "ci95_lo_pp": lo_pp, "ci95_hi_pp": hi_pp,
                   "p_mcnemar_exact": r["p_mcnemar"] if r else None},
        "practical_pp": PRACTICAL_PP,
        "verdict_four_cell": four_cell(lo_pp, hi_pp) if r else "BROKEN",
        "power": {
            "mde_at_n_pp": mde_at_n(measured, disc_rate)["mde_pp"] if measured else None,
            "n_needed_halfwidth_5pp": n_needed(r["n_discordant"], measured) if r else None,
            "n80_if_true_effect_is_observed": (
                n_needed_for_power(r["b"] / r["n_discordant"])
                if r and r["n_discordant"] else None),
        },
        "prereg": preds,
        "overturn_conditions_triggered": overturned,
        "broken_reasons": broken,
    }
    if rows_meta:
        out.update(rows_meta)
    if broken:
        out["verdict_four_cell"] = "BROKEN"
    return out


# ------------------------------------------------------------------ selftest
def _row(gate, vote, **kw):
    same = kw.pop("same", gate == vote)
    d = {"arm": "EQ5", "task_id": kw.pop("tid", "t"), "calls_used": 5,
         "same_choice": same,
         "accepted": kw.pop("accepted", True),
         "meets_demand": kw.pop("meets_demand", gate),
         # sha 由 same 導出，raw 欄位與 sha 永遠自洽（漂移擋門測的是別的東西）
         "gate_code_sha256": "aa" * 32,
         "vote_code_sha256": ("aa" if same else "bb") * 32,
         "gate_deliv": gate, "vote_deliv": vote}
    d.update(kw)
    return d


def _set_same(row, val: bool):
    """夾具用：同時改 `same_choice` 與兩份 sha，讓 raw 欄位與 sha 保持自洽。
    （漂移擋門測的是「欄位與 sha 打架」，不該被別條自檢的夾具誤觸發。）"""
    row["same_choice"] = val
    row["vote_code_sha256"] = ("aa" if val else "bb") * 32
    return row


def _fx(n_bb, n_bc, n_cb, n_cc, void=0, **kw):
    """夾具：n_bb 兩邊都對、n_bc 只有閘門對(b)、n_cb 只有多數決對(c)、n_cc 兩邊都錯。"""
    rows, i = [], 0
    for kind, cnt in (("bb", n_bb), ("bc", n_bc), ("cb", n_cb), ("cc", n_cc)):
        for _ in range(cnt):
            i += 1
            g, v = {"bb": (True, True), "bc": (True, False),
                    "cb": (False, True), "cc": (False, False)}[kind]
            rows.append(_row(g, v, tid=f"t{i}", **kw))
    n = n_bb + n_bc + n_cb + n_cc
    summ = {"arms": {"EQ5": {"processed": n + void, "infra_void": void,
                             "terminal": True}}}
    return rows, summ


def selftest() -> int:
    from ops.gain.replay.paired_ci import verdict as raw_verdict
    fails = []

    # A：手算對照——b/c 的定義與方向
    rows, summ = _fx(50, 20, 8, 22)
    a = analyze(rows, summ)
    if (a["paired"]["b_gate_only"], a["paired"]["c_vote_only"]) != (20, 8):
        fails.append(f"A: b/c 抽錯 -> {a['paired']}")
    if abs(a["paired"]["delta_pp"] - (20 - 8) / 100 * 100) > 1e-9:
        fails.append(f"A: Δ 不等於手算 (20-8)/100 -> {a['paired']['delta_pp']}")
    if a["broken_reasons"]:
        fails.append(f"A: 乾淨夾具卻 BROKEN -> {a['broken_reasons']}")
    if abs(a["gate"]["deliv_pp_denom_measured"] - 70.0) > 1e-9:
        fails.append(f"A: 閘門 deliv% 手算 70.0 -> {a['gate']['deliv_pp_denom_measured']}")
    if abs(a["vote"]["deliv_pp_denom_measured"] - 58.0) > 1e-9:
        fails.append(f"A: 多數決 deliv% 手算 58.0 -> {a['vote']['deliv_pp_denom_measured']}")

    # V：四格表與 paired_ci.verdict 同構（換標籤，不是第二套判準）
    lab = {"ON_WINS": "GATE_RULE_WINS", "RULED_OUT": "RULED_OUT",
           "UNINFORMATIVE": "UNINFORMATIVE",
           "NON_INFERIOR_BUT_UNRESOLVED": "NON_INFERIOR_BUT_UNRESOLVED"}
    bad = [(lo, hi) for lo in [x / 2 for x in range(-30, 31)]
           for hi in [x / 2 for x in range(-30, 31)]
           if lab[raw_verdict(lo, hi)] != four_cell(lo, hi)]
    if bad:
        fails.append(f"V: 四格表與 paired_ci.verdict 不同構 {len(bad)} 格，例：{bad[:3]}")

    # 註：突變體由 `EQ5_ANALYZE_MUTANT` 環境變數驅動，由
    # `ops/gain/eq5_analyze_mutation_check.py` 逐個跑並指名「哪一條該叫」。
    # 夾具刻意不對稱（b=20≠c=8），否則 M1（b/c 顛倒）在對稱夾具上會是 MISSED。

    # B：void 要從分母裡拿掉，而且帳要對得上
    rows, summ = _fx(10, 5, 5, 10, void=4)
    a = analyze(rows, summ)
    if a["measured"] != 30 or a["processed"] != 34 or abs(a["void_rate_pp"] - 400 / 34) > 1e-9:
        fails.append(f"B: void 記帳錯 -> measured={a['measured']} processed={a['processed']} "
                     f"void_rate={a['void_rate_pp']}")
    if a["broken_reasons"]:
        fails.append(f"B: 帳對得上卻 BROKEN -> {a['broken_reasons']}")

    # C：帳對不上必須 BROKEN（型二「安靜量不到」）
    rows, summ = _fx(10, 5, 5, 10)
    summ["arms"]["EQ5"]["processed"] = 45            # rows 少了 15 列
    a = analyze(rows, summ)
    if not any("帳對不上" in x for x in a["broken_reasons"]) or a["verdict_four_cell"] != "BROKEN":
        fails.append(f"C: rows 少 15 列竟然不是 BROKEN -> {a['broken_reasons']}")

    # D：缺欄位必須 BROKEN，不准當 False（型一）
    rows, summ = _fx(10, 5, 5, 10)
    rows[0].pop("vote_deliv")
    a = analyze(rows, summ)
    if not a["third_category_missing_fields"] or a["verdict_four_cell"] != "BROKEN":
        fails.append(f"D: 缺 vote_deliv 竟然放行 -> {a['broken_reasons']}")

    # E：deliv 口徑必須是 accepted ∧ meets_demand——拒交但 meets_demand=True 的那格
    #    在 gate 上必須算「沒交付」（r444 兩個分母給出相反判決的那個坑）
    rows, summ = _fx(0, 0, 0, 6)
    for x in rows[:3]:
        x["accepted"] = False
        x["meets_demand"] = True          # 拒交了，但如果照 meets_demand 算就會變成交付
        x["gate_deliv"] = False
    a = analyze(rows, summ)
    if a["gate"]["deliv_n"] != 0:
        fails.append(f"E: 拒交格被算成交付 -> {a['gate']}")
    if a["gate"]["coverage_pp"] != 50.0:
        fails.append(f"E: coverage 算錯 -> {a['gate']['coverage_pp']}")

    # F：預算不是恆 5 必須 BROKEN（DECISION §五）
    rows, summ = _fx(10, 5, 5, 10)
    rows[3]["calls_used"] = 4
    a = analyze(rows, summ)
    if a["budget_all_exactly_5"] or a["verdict_four_cell"] != "BROKEN":
        fails.append(f"F: calls_used=4 竟然放行 -> {a['budget_all_exactly_5']}")

    # G：推翻條件 §六-1（same_choice>95%）要觸發
    rows, summ = _fx(96, 1, 1, 2)
    for x in rows:
        _set_same(x, True)
    a = analyze(rows, summ)
    if not any("§六-1" in x for x in a["overturn_conditions_triggered"]):
        fails.append(f"G: same_choice=100% 沒觸發 §六-1 -> {a['overturn_conditions_triggered']}")

    # H：推翻條件 §六-2（n_d<15）要觸發，且 MDE／N₈₀ 要有數字（不准只報 UNRESOLVED）
    rows, summ = _fx(60, 4, 3, 33)
    a = analyze(rows, summ)
    if not any("§六-2" in x for x in a["overturn_conditions_triggered"]):
        fails.append(f"H: n_d=7<15 沒觸發 §六-2 -> {a['overturn_conditions_triggered']}")
    if a["power"]["mde_at_n_pp"] is None or a["power"]["n_needed_halfwidth_5pp"] is None:
        fails.append(f"H: 觸發 §六-2 卻沒有 MDE／N₈₀ -> {a['power']}")

    # I：事前窗口逐條判——造一組全部落在窗內的夾具
    rows, summ = _fx(58, 16, 8, 18)        # gate 74%, vote 66%, n_d=24
    for i, x in enumerate(rows):
        _set_same(x, i % 2 == 0)           # 50%
        if i >= 92:                        # 8% 拒交（挑本來 gate 就沒交付的 cc 格，
            x["accepted"] = False          # 拒交不改變 b/c，只改 coverage）
    a = analyze(rows, summ)
    miss = [k for k, v in a["prereg"].items() if v["verdict"] != "HIT"]
    if miss:
        fails.append(f"I: 全窗內夾具卻有 MISS {miss} -> "
                     f"{ {k: a['prereg'][k] for k in miss} }")

    # J：run 還沒跑完（terminal=False）必須 BROKEN——擋住「拿半截 run 當收官資料」
    rows, summ = _fx(30, 10, 5, 15)
    summ["arms"]["EQ5"]["terminal"] = False
    summ["arms"]["EQ5"]["processed"] = 60
    a = analyze(rows, summ)
    if not any("terminal" in x for x in a["broken_reasons"]) or a["verdict_four_cell"] != "BROKEN":
        fails.append(f"J: terminal=False 竟然放行 -> {a['broken_reasons']}")

    # K：AMEND-1 的本體——拒交格的 fallback 相同**不算**「選到同一份」。
    #    夾具刻意讓 raw 與 effective 給出相反的 §六-1 判決（raw 96% > 95 ≥ eff 86%），
    #    否則 M7（退回 raw）在對稱夾具上看不見。
    rows, summ = _fx(96, 1, 1, 2)
    for i, x in enumerate(rows):             # 96 筆 raw 同選、4 筆不同選 ⇒ raw = 96%
        _set_same(x, i < 96)
    for x in rows[:10]:                      # 其中 10 筆是拒交（fallback 撞上同一份 sha）
        x["accepted"] = False                # ⇒ effective = 86%，與 raw 跨過 95 的兩邊
        x["gate_deliv"] = False
    a = analyze(rows, summ)
    if a["broken_reasons"]:
        fails.append(f"K: 乾淨夾具卻 BROKEN -> {a['broken_reasons']}")
    if a["false_same_choice_n"] != 10:
        fails.append(f"K: 偽同選筆數手算 10 -> {a['false_same_choice_n']}")
    if abs((a["same_choice_effective_rate_pp"] or -1) - 86.0) > 1e-9:
        fails.append(f"K: effective 手算 86.0 -> {a['same_choice_effective_rate_pp']}")
    if abs((a["same_choice_rate_pp"] or -1) - 96.0) > 1e-9:
        fails.append(f"K: raw 手算 96.0 -> {a['same_choice_rate_pp']}")
    if any("effective_rate>95%" in x for x in a["overturn_conditions_triggered"]):
        fails.append(f"K: eff=86% 竟觸發 §六-1 -> {a['overturn_conditions_triggered']}")
    if not any("相反判決" in x for x in a["overturn_conditions_triggered"]):
        fails.append(f"K: raw>95≥eff 沒寫出「兩個判決都要寫」 -> "
                     f"{a['overturn_conditions_triggered']}")
    if a["prereg"]["P-R446-5"]["observed"] != a["same_choice_effective_rate_pp"]:
        fails.append("K: P-R446-5 的仲裁量不是 effective（AMEND-1 §五）")
    if a["prereg"]["P-R446-5-raw"]["observed"] != a["same_choice_rate_pp"]:
        fails.append("K: raw 沒有無條件留在 prereg 裡（AMEND-1 §五-2）")

    # L：少了 sha 欄位 ⇒ BROKEN（安靜量不到 型一，AMEND-1 的重算輸入不見了）
    rows, summ = _fx(30, 10, 5, 15)
    for x in rows[:3]:
        x.pop("vote_code_sha256")
    a = analyze(rows, summ)
    if not a["third_category_missing_fields"] or a["verdict_four_cell"] != "BROKEN":
        fails.append(f"L: 缺 vote_code_sha256 竟然放行 -> "
                     f"{a['third_category_missing_fields']}／{a['verdict_four_cell']}")

    # M：未來 run 落盤的 same_choice_effective 與離線重算打架 ⇒ BROKEN（不准取其一）
    rows, summ = _fx(30, 10, 5, 15)
    for x in rows:
        x["same_choice_effective"] = bool(x["accepted"]) and x["same_choice"]
    rows[7]["same_choice_effective"] = not rows[7]["same_choice_effective"]
    a = analyze(rows, summ)
    if not any("離線重算不一致" in x for x in a["broken_reasons"]):
        fails.append(f"M: 落盤欄位與重算打架竟然放行 -> {a['broken_reasons']}")

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST", "FAIL" if fails else "PASS",
          f"(A手算 V四格同構 B_void C帳 D缺欄位 E_deliv口徑 F預算 G§六-1 H§六-2 I事前窗 J未跑完"
          f" K偽同選 L缺sha M落盤打架)"
          f" MUTANT={MUTANT or 'none'}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.run:
        print("需要 --run 或 --selftest"); return 2
    d = pathlib.Path(args.run)
    rows = [json.loads(l) for l in (d / "rows.jsonl").open(encoding="utf-8") if l.strip()]
    summ = json.load((d / "summary.json").open(encoding="utf-8"))
    meta = {"run": str(d),
            "rows_lines": sum(1 for _ in (d / "rows.jsonl").open(encoding="utf-8")),
            "rows_sha256_16": hashlib.sha256((d / "rows.jsonl").read_bytes()).hexdigest()[:16]}
    out = analyze(rows, summ, meta)
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if args.json:
        pathlib.Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.json).write_text(js + "\n", encoding="utf-8")
    print(js)
    return 1 if out["broken_reasons"] else 0


if __name__ == "__main__":
    MUTANT = os.environ.get("EQ5_ANALYZE_MUTANT", "")
    raise SystemExit(main())
