#!/usr/bin/env python3
"""R460（harness 六臂 on LCB v2）的收官分析尺——**在資料落地之前寫死**（round460c）。

這支在架構裡承重什麼
────────────────────
`DECISION_20260907_R460_HARNESS_PREREG.md` 的每一條預測都指名「它讀 analyzer 輸出的
哪一個 key」。判準指名了一個不存在的 key，收官時 `.get()` 會安靜地回 `None`，
然後被讀成「量到 0」——記憶鐵律：判準要指名欄位，不准靠「工具印了什麼字串」。
所以本檔與那份 DECISION 是**同一輪、在資料之前**一起寫的，
而 `tests/test_r460_launcher_prereg.py` 會逐條驗兩邊指的是同一個東西。

估計量宣稱（收官不准換詞彙）
──────────────────────────
R460 答的是：**在 LCB v2 這 120 題上、同一顆 12B worker、同樣 5 通呼叫預算，
把預算花在「跑客戶的驗收測資、把失敗原文貼回去、讓同一個人改」（H 臂）
比花在「換人重抽」（CONFORM）或「多數決」（OFF5）多交付多少。**
配對單位是 task，成功的定義是 `deliv = accepted ∧ meets_demand`
（R667 凍結口徑，`ops/gain/replay/paired_ci.py:25` 逐字）。

D3 把三件事**分開**定義，本檔逐條照做（HARNESS_STUDY §5.4）：
  (1) **分母＝complete case**：兩臂都非 void 的題（`n_common`）。
      不是聯集、不是 `processed`、不是各臂自己的 `measured`——H 臂的 void 曝險
      比 OFF 高 3–5 倍，三個分母在這個 run 上會給出不同答案。
  (2) **顯著性＝Holm 調整後的精確 McNemar p**，家族固定 6 個檢定
      （3 條 H 臂 × {OFF, CONFORM}）。H 對 H 的比較**不在家族內**，
      它們是 P-H9 的探索量，印出來時逐格標 `EXPLORATORY`。
  (3) **區間＝未調整的 95% Clopper–Pearson 條件區間**（`paired_ci.diff_ci`，
      與 `analyze_r447.py` 同一支）。
      ⇒ 每次印區間都逐字附上：**「區間未做多重比較調整；仲裁以 analyzer 為準」**。
      於是「未調整區間排除 0，但 Holm 後 p ≥ 0.05」是**事前就知道可能發生**的情形，
      不是矛盾：顯著性以 `holm.<pair>.p_adj` 為準，RULED_OUT 仍讀未調整的 `ci95_hi_pp`。

「安靜量不到」兩型都要擋（判準不是 rc≠0）
  型一 缺欄位：任一列缺 REQUIRED 任一欄 ⇒ BROKEN，**不准**當 False 算過去。
  型二 帳對不上：rows 行數 + infra_void ≠ processed ⇒ BROKEN。
  另外：run 未 terminal ⇒ BROKEN（期中資料不是收官資料）；
  同一條臂出現兩種 `harness_wire_mode` ⇒ BROKEN（G6，兩種模式不得混算）。

D7（本 repo 第一次，稽核時不要當成漏洞）
──────────────────────────────────────
H 臂的回饋訊息裡有 `args=… got=… want=…`，那是**客戶自己交出來的可見驗收測資**的
內容，按設計就會進 worker prompt。所以 V/GT 稽核的對象是 `hidden \\ visible`，
不是「所有測資」；本檔只讀 rows/calls，真正的洩漏稽核在
`ops/gain/harness_vgt_audit.py`。

零 API、零 ssh。預設零沙箱；只有 `--rescore-turn1` 會跑沙箱
（D5 的歸因分解要把「第一輪那份碼」重新用 `meets_demand(hidden)` 評一次，
走的是與 dispatch 端逐字相同的路徑，仍然是事後評分、臂內看不到 hidden）。
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.gain.replay.paired_ci import diff_ci, verdict as raw_verdict  # noqa: E402
from ops.gain.power_paired import mde_at_n, n_needed_for_power  # noqa: E402
from vacant.research import holm_bonferroni, mcnemar_exact  # noqa: E402

# ── 突變點（測試用；正式跑一律空字串）────────────────────────────────
# 記憶鐵律：偵測條要有牙齒。每一個突變體都對應 selftest 裡一條具名檢查。
MUTANT = os.environ.get("R460_MUTANT", "")
LAST_FAILS: list[str] = []

H_ARMS = ("HPI", "HOC", "HMIX")
BASELINES = ("OFF", "CONFORM")
ALL_ARMS = ("OFF", "CONFORM", "OFF5") + H_ARMS

# ── D9（round460e 修訂：**六塊**、兩個後端、每台三塊）───────────────────
# 2026-09-07 15:40 實測：8765 這顆 hub **把 100% 的請求都路由到 1003**
# （6 次探針：1003 +6、1004 +0），而且 n=8/12 併發打 hub 時吞吐**退化**
# （206 → 175 → 144 tok/s）；兩顆直連後端各自在 n=4 熱身後約 110–120 tok/s，
# 兩邊服務的都是 gemma-4-12b-it-qat。⇒ 走 hub 等於只用一張卡而且越併發越慢。
#
# **為什麼從兩塊變六塊**（round460e，2026-09-08，資料之前）：R460 的 n=3 冒煙量到
# 每通呼叫 **160–560 s**、單通完成 token 最多 ~13k——LCB 這批題目比 r447 當時貴得多。
# 一塊 60 題、序列送出 ⇒ 兩塊各要 **> 2 天**。而**直連**後端實測可以同時服務
# 3 個請求而每個請求都不變慢（1 個 1.3 s／3 個併發各 1.3 s；6 個併發才開始退化）
# ⇒ 一台後端掛三個序列 runner，吞吐 ×3，**每個請求的行為一個字沒變**。
# 所以切成六塊、每台三塊、每塊 20 題。
#
# 關鍵設計**沒有變**：**後端是 task 層級的干擾項，永遠不是 arm 層級的混淆**——
# 同一題的六條臂仍然在同一塊、同一個行程、同一個後端上跑完（塊內交錯），
# 所以每一組配對比較的兩臂都在同一顆 GPU 上。塊間難度組成可以差
# （a1 medium12/hard8、a2 13/7、a3 15/5、b1 10/10、b2 12/8、b3 10/10），
# 那不影響**塊內配對**，也不影響**合併後的配對**。合併仍然按 `task_id`（R445 先例）。
AUTHORIZED_BLOCKS = ("g_r460_harness_lcb2_a1", "g_r460_harness_lcb2_a2",
                     "g_r460_harness_lcb2_a3", "g_r460_harness_lcb2_b1",
                     "g_r460_harness_lcb2_b2", "g_r460_harness_lcb2_b3")
HUB_MARKERS = (":8765",)          # D9 明文禁止：任何一塊都不准走 hub
BLOCKS_EXPECTED = 6
BLOCKS_PER_ENDPOINT = 3           # 兩顆端點時每顆恰好三塊——多了就是在同一張卡上超賣
TASKS_EXPECTED = 120              # 六塊 task_id 的**聯集**（＝ r447 的那 120 題）

# ── round460h 修訂（2026-09-09，a 組第三次任何資料之前）─────────────────
# 舊規則是「**恰好** 2 個端點、每個 3 塊」。那一格是**平衡規則不是科學規則**：
# 它管的只是「六個 runner 攤在兩張卡上」，而 E-7 真正承重的是別的四條——
# 同一題的六條臂在同一塊、同一行程、同一顆後端上跑完；塊間 task_id 零交集且聯集 120；
# 沒有一塊走 hub；塊數 6。**六塊全在同一顆後端上跑，反而把「後端」這個干擾項整個消掉。**
# ⇒ 允許的拓撲收斂成兩種，收官必須把是哪一種、為什麼**記下來**（`topology.variant`）：
#   `two_backends_3_3`  兩顆相異端點，每顆恰好三塊（round460e 的原設計）
#   `one_backend_6`     一顆端點掛滿六塊（1003 兩次崩潰後，a 組第三次改掛 1004）
# 其餘（0、3 顆以上、或塊數不對）一律是違規。
ENDPOINTS_ALLOWED = (1, 2)
TOPOLOGY_VARIANTS = {2: "two_backends_3_3", 1: "one_backend_6"}
BLOCKS_PER_ENDPOINT_SOLO = BLOCKS_EXPECTED   # one_backend_6：那一顆要掛滿六塊

#: P-H0 的錨塊：offset 0/20/40 的三塊，聯集恰好是 r447 的**前 60 題**
#: （§九-1 實測 `a1+a2+a3 == r447 OFF 的前 60 個 task_id`，錨 32/60 ＝ 53.33%）。
#: round460h 之前這三塊在 1003 上，所以 P-H0 也是「1003 有沒有漂」的探針；
#: 改掛 1004 之後它探的是**同一顆後端在 b 組跑完約 17 小時後有沒有漂**
#: （兩半不同時、後端漂移成了新的干擾項，見 DECISION §四 E-7 修訂與 §八-14）。
PH0_BLOCKS = AUTHORIZED_BLOCKS[:BLOCKS_PER_ENDPOINT]

REQUIRED = ("arm", "task_id", "meets_demand", "accepted", "calls_used", "visible_ok")
REQUIRED_H = ("harness_variant", "harness_wire_mode", "harness_calls",
              "harness_tokens_total", "stop_reason", "first_pass_turn",
              "n_turns", "harness_turns")

# D3 的門檻，**在資料之前凍結**。這些數字的仲裁者是
# DECISION_20260907_R460_HARNESS_PREREG.md，不是本檔；改這裡等於改事前註冊 ⇒ 不准。
DELTA_O_MIN_PP = 25.0
DELTA_C_MIN_PP = 10.0
ALPHA = 0.05
FALSE_DELIV_SLACK_PP = 5.0

# HARNESS_STUDY §5.10 的十條預測窗（同上：本檔只是編碼，仲裁者是 DECISION）。
# ⚠ P-H0 的窗因 D9 改過一次，**改在資料之前**（錨 32/60、窗 ±15pp），
# round460e 切成六塊之後**窗與錨都不動**，但它讀的東西換了、而且變弱了：
#   * 讀的東西：`ph0_pool` ＝ **a1+a2+a3 的聯集**（offset 0/20/40，各 20 題）。
#     那個聯集逐題逐序等於 r447 的前 60 題 ⇒ 錨仍然是 32/60 ＝ 53.33%。
#   * **變弱在哪（誠實邊界）**：每臂的 `random.Random(f"{seed}:{arm}")`
#     在**每一塊各自從頭抽**（`gain_run.py:1490`）⇒ 兩塊時只有 block a 的 60 題
#     與 r447 逐格同 persona；**六塊時只剩 a1 的前 20 題**還對得上。
#     a2／a3 的 persona 指派會與 r447 錯開（邊際分佈相同、逐格不同）。
#     ⇒ P-H0 從「配對比較」退化成「同一批 60 題上的兩個非配對估計」，
#     噪音變大。**窗不因此再放寬**——放寬會讓它更容易 HIT，那不是誠實的方向；
#     真的 MISS 時照 §三 P-H0 的 `scope`：只作廢與 r447 的橫向比較，
#     本 run 內部六臂的比較仍然有效（同一題六臂共享同一塊、同一個後端）。
PREREG = {
    "P-H0": ("OFF 交付率 (%)（後端漂移探針；只在 a1+a2+a3 的 60 題上判）", 38.3, 68.3),
    "P-H3": ("H 臂 calls_per_task", 1.8, 3.2),
    "P-H4": ("H 臂假交付率 (%) 上界", None, 35.0),
    "P-H5": ("HOC/HMIX 以 loader 收尾的輪次比例 (%)", None, 0.5),
    "P-H6": ("tokens/task(HMIX) ÷ tokens/task(HPI)", None, 0.8),
    "P-H7": ("H 臂 budget_wall 比例 (%)", None, 5.0),
    "P-H8": ("H 臂 nocode 輪次比例 (%)", None, 3.0),
}

CI_DISCLAIMER = "區間未做多重比較調整；仲裁以 analyzer 為準"
WINNERS_CURSE = (
    "winner's curse：n=120 對 +10pp 的檢定力只有 0.43–0.63（HARNESS_STUDY §5.5），"
    "能被判顯著的點估計本來就被截斷在 MDE 以上 ⇒ 任何被判 EFFECTIVE 的臂，"
    "其點估計是效果量的**上偏**估計；跨 run／跨臂比幅度一律報區間重疊，不報點估計誰大。"
)


# ── 基本量 ────────────────────────────────────────────────────────────
def _deliv(r: dict) -> bool:
    """R667 凍結口徑：交付成功 ＝ 交出去了(accepted) 且 真的對(meets_demand)。"""
    if MUTANT == "M1_deliv_ignores_accepted":
        return bool(r.get("meets_demand"))
    return bool(r.get("accepted")) and bool(r.get("meets_demand"))


def _rows_by_arm(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r.get("arm"), []).append(r)
    return out


def _pct(a: float, b: float) -> float | None:
    return 100.0 * a / b if b else None


def _paired(a_rows: list[dict], b_rows: list[dict]) -> dict:
    """A 相對 B 的配對計數。b＝只有 A 交付對、c＝只有 B 交付對。

    分母 `n_common` ＝ **complete case**：兩臂都寫了 rows 的題。
    `gain_run` 只在非 void 的格子寫 rows（void 走 `continue`），所以交集
    就是「兩臂都量到」。D3 §5.4-(1)。
    """
    A = {r["task_id"]: _deliv(r) for r in a_rows}
    B = {r["task_id"]: _deliv(r) for r in b_rows}
    common = sorted(set(A) & set(B))
    if MUTANT == "M2_union_denominator":
        common = sorted(set(A) | set(B))
    b = sum(1 for t in common if A.get(t) and not B.get(t))
    c = sum(1 for t in common if B.get(t) and not A.get(t))
    d = diff_ci(b, c, len(common)) if common else {
        "b": 0, "c": 0, "n": 0, "n_discordant": 0, "delta": 0.0,
        "lo": 0.0, "hi": 0.0}
    out = {
        "b": b, "c": c, "n_discordant": b + c, "n_common": len(common),
        "delta_pp": 100.0 * d["delta"],
        "ci95_lo_pp": 100.0 * d["lo"], "ci95_hi_pp": 100.0 * d["hi"],
        "p_mcnemar_exact": mcnemar_exact(b, c),
        "verdict_paired_ci": raw_verdict(100.0 * d["lo"], 100.0 * d["hi"]),
        "ci_note": CI_DISCLAIMER,
        "b_only_task_ids": [t for t in common if A.get(t) and not B.get(t)],
        "c_only_task_ids": [t for t in common if B.get(t) and not A.get(t)],
    }
    return out


def _paired_subset(a_rows, b_rows, keep: set[str]) -> dict:
    return _paired([r for r in a_rows if r["task_id"] in keep],
                   [r for r in b_rows if r["task_id"] in keep])


# ── calls.jsonl 的成本歸戶 ────────────────────────────────────────────
def _call_arm(rec: dict) -> str | None:
    return (rec.get("meta") or {}).get("arm") or None


def _tokens(rec: dict) -> int:
    u = rec.get("usage") or {}
    return int(u.get("total_tokens") or 0)


def cost_by_arm(calls: list[dict], measured_ids: dict[str, set[str]]) -> dict:
    """逐臂的呼叫數與 token 總量，**含 void 與排除 void 兩個版本都算**。

    R7 的不對稱：void 格的呼叫已經燒掉 token 但那一格不進分母 ⇒
    只報「排除 void」會**低估** H 臂的成本。D3 的 (iii) 用含 void 的那個。
    """
    out: dict[str, dict] = {}
    for rec in calls:
        arm = _call_arm(rec)
        if arm is None:
            continue
        d = out.setdefault(arm, {"calls_total": 0, "calls_ok": 0,
                                 "tokens_incl_void": 0, "tokens_excl_void": 0,
                                 "calls_ok_excl_void": 0})
        d["calls_total"] += 1
        if not rec.get("ok"):
            continue
        d["calls_ok"] += 1
        tok = _tokens(rec)
        d["tokens_incl_void"] += tok
        tid = (rec.get("meta") or {}).get("task_id")
        if tid in measured_ids.get(arm, set()):
            d["calls_ok_excl_void"] += 1
            d["tokens_excl_void"] += tok
    if MUTANT == "M3_tpc_ignores_void_calls":
        for d in out.values():
            d["tokens_incl_void"] = d["tokens_excl_void"]
    return out


# ── H 臂的逐輪量 ──────────────────────────────────────────────────────
def harness_turn_stats(rs: list[dict]) -> dict:
    """逐輪日誌的聚合。所有比率的分母都是**輪次**，不是題數（§5.3 協定失敗率）。"""
    n_turns = sum(int(r.get("n_turns") or 0) for r in rs)
    agg = {
        "n_turns_total": n_turns,
        "nocode_turns": sum(int(r.get("nocode_turns") or 0) for r in rs),
        "loader_refusals": sum(int(r.get("loader_refusals") or 0) for r in rs),
        "entry_point_missing": sum(int(r.get("entry_point_missing") or 0) for r in rs),
        "first_block_non_python": sum(int(r.get("first_block_non_python") or 0) for r in rs),
        "extractor_divergences": sum(int(r.get("extractor_divergences") or 0) for r in rs),
        "truncated_retries": sum(int(r.get("truncated_retries") or 0) for r in rs),
        "doom_nudges": sum(int(r.get("doom_nudges") or 0) for r in rs),
        "doom_triggered_n": sum(1 for r in rs if r.get("doom_triggered")),
        "selftests_parsed": sum(int(r.get("selftests_parsed") or 0) for r in rs),
        "selftests_unparsable": sum(int(r.get("selftests_unparsable") or 0) for r in rs),
    }
    agg["nocode_turn_rate_pp"] = _pct(agg["nocode_turns"], n_turns)
    agg["loader_turn_rate_pp"] = _pct(agg["loader_refusals"], n_turns)
    agg["entry_point_missing_rate_pp"] = _pct(agg["entry_point_missing"], n_turns)
    agg["first_block_non_python_rate_pp"] = _pct(agg["first_block_non_python"], n_turns)
    agg["extractor_divergence_rate_pp"] = _pct(agg["extractor_divergences"], n_turns)

    # 逐題直方圖（G5：呼叫數不能只報平均——E19 的 whitewash 29/30 前例）
    calls_hist = collections.Counter(int(r.get("harness_calls") or r.get("calls_used") or 0)
                                     for r in rs)
    turn_hist = collections.Counter(int(r.get("n_turns") or 0) for r in rs)
    fpt_hist = collections.Counter(
        ("none" if r.get("first_pass_turn") in (None, "") else int(r["first_pass_turn"]))
        for r in rs)
    stop = collections.Counter(str(r.get("stop_reason")) for r in rs)
    agg["calls_hist"] = {str(k): v for k, v in sorted(calls_hist.items())}
    agg["turn_hist"] = {str(k): v for k, v in sorted(turn_hist.items())}
    agg["first_pass_turn_hist"] = {str(k): v for k, v in sorted(fpt_hist.items(), key=str)}
    agg["stop_reason_counts"] = dict(sorted(stop.items()))
    agg["stop_reason_pp"] = {k: _pct(v, len(rs)) for k, v in sorted(stop.items())}
    agg["fail_kind_counts"] = dict(collections.Counter(
        str(t.get("fail_kind")) for r in rs for t in (r.get("harness_turns") or [])))
    agg["precheck_reason_counts"] = dict(collections.Counter(
        str(t.get("precheck_reason")) for r in rs
        for t in (r.get("harness_turns") or []) if t.get("precheck_reason")))
    agg["wire_modes"] = sorted({str(r.get("harness_wire_mode")) for r in rs})
    return agg


# ── 主分析 ────────────────────────────────────────────────────────────
def analyze(rows: list[dict], summary: dict, calls: list[dict],
            bank: dict[str, dict] | None = None,
            turn1: dict[str, dict[str, bool]] | None = None,
            blocks: list[dict] | None = None) -> dict:
    """rows/calls/summary → 收官報表 dict。`turn1` 只有 --rescore-turn1 時才有。

    `blocks`（D9）給了的話，`rows`／`calls`／`summary` 必須已經是 `pool_runs()`
    併好的合併版；本函式**主體算的一律是合併後的量**（仲裁欄位的路徑因此
    一個字都沒變），另外把每一塊各自跑一遍放在 `out["blocks"]`。
    """
    out: dict = {"broken_reasons": [], "notes": [],
                 "ci_note": CI_DISCLAIMER,
                 "winners_curse_disclaimer": WINNERS_CURSE}
    arms = _rows_by_arm(rows)
    sarms = summary.get("arms") or {}

    # ── 型一：缺欄位 ─────────────────────────────────────────────────
    missing: dict[str, int] = {}
    for r in rows:
        for k in REQUIRED:
            if k not in r:
                missing[k] = missing.get(k, 0) + 1
        if r.get("arm") in H_ARMS:
            for k in REQUIRED_H:
                if k not in r:
                    missing[k] = missing.get(k, 0) + 1
    out["missing_fields"] = missing
    if missing and MUTANT != "M4_ignore_missing_fields":
        out["broken_reasons"].append(f"missing_fields:{sorted(missing)}")

    # ── 型二：帳對不上 ───────────────────────────────────────────────
    recon = {}
    for a, s in sarms.items():
        n_rows = len(arms.get(a, []))
        void = int(s.get("infra_void") or 0)
        proc = int(s.get("processed") or 0)
        recon[a] = {"rows": n_rows, "infra_void": void, "processed": proc,
                    "ok": n_rows + void == proc}
        if not recon[a]["ok"]:
            out["broken_reasons"].append(f"row_accounting:{a}:{n_rows}+{void}!={proc}")
    out["row_accounting"] = recon

    out["run_terminal"] = bool(summary.get("run_terminal"))
    if not out["run_terminal"]:
        out["broken_reasons"].append("run_not_terminal")
    if not rows:
        out["broken_reasons"].append("zero_rows")

    # ── 逐臂描述量 ───────────────────────────────────────────────────
    measured_ids = {a: {r["task_id"] for r in rs} for a, rs in arms.items()}
    per: dict[str, dict] = {}
    for a, rs in sorted(arms.items()):
        n = len(rs)
        acc = sum(1 for r in rs if r.get("accepted"))
        dn = sum(1 for r in rs if _deliv(r))
        false_n = sum(1 for r in rs if r.get("accepted") and not r.get("meets_demand"))
        lossless_n = sum(1 for r in rs if r.get("meets_demand") and not r.get("accepted"))
        s = sarms.get(a) or {}
        proc, void = int(s.get("processed") or 0), int(s.get("infra_void") or 0)
        calls_used = [r.get("calls_used") for r in rs
                      if isinstance(r.get("calls_used"), (int, float))]
        d = {
            "measured": n, "processed": proc, "infra_void": void,
            "void_pp": _pct(void, proc),
            "accepted": acc,
            "deliv_n": dn,
            "deliv_pp_denom_measured": _pct(dn, n),
            "deliv_pp_denom_accepted_NOT_ARBITER": _pct(dn, acc),
            "false_delivery_n": false_n,
            "false_delivery_pp": _pct(false_n, n),
            "accept_precision_pp": _pct(dn, acc),
            "refusal_pp": _pct(n - acc, n),
            "lossless_violation_n": lossless_n,
            "visible_ok_n": sum(1 for r in rs if r.get("visible_ok")),
            "calls_per_task": (sum(calls_used) / len(calls_used)) if calls_used else None,
            "wall_s_per_task": (float(s["wall_s"]) / n) if s.get("wall_s") and n else None,
            "calls_hist": {str(k): v for k, v in
                           sorted(collections.Counter(int(x) for x in calls_used).items())},
        }
        if a in H_ARMS:
            d.update(harness_turn_stats(rs))
        per[a] = d
    out["per_arm"] = per

    # ── G6：wire mode 不得混算 ───────────────────────────────────────
    wire = {a: per[a].get("wire_modes") for a in H_ARMS if a in per}
    out["gates"] = {}
    out["gates"]["G6_wire_mode"] = {"per_arm": wire,
                                    "single_mode_per_arm": all(len(v or []) <= 1
                                                               for v in wire.values()),
                                    "all_arms_same_mode": len({m for v in wire.values()
                                                               for m in (v or [])}) <= 1}
    if not out["gates"]["G6_wire_mode"]["single_mode_per_arm"]:
        out["broken_reasons"].append("wire_mode_mixed_within_arm")

    # ── 成本 ─────────────────────────────────────────────────────────
    cost = cost_by_arm(calls, measured_ids)
    tokens: dict[str, dict] = {}
    for a in sorted(set(arms) | set(cost)):
        c = cost.get(a, {})
        n = per.get(a, {}).get("measured") or 0
        dn = per.get(a, {}).get("deliv_n") or 0
        tokens[a] = {
            "calls_total": c.get("calls_total"), "calls_ok": c.get("calls_ok"),
            "tokens_total_incl_void": c.get("tokens_incl_void"),
            "tokens_total_excl_void": c.get("tokens_excl_void"),
            "tokens_per_task": (c.get("tokens_excl_void") / n) if n else None,
            "tpc_incl_void": (c.get("tokens_incl_void") / dn) if dn else None,
            "tpc_excl_void": (c.get("tokens_excl_void") / dn) if dn else None,
        }
    base_off = tokens.get("OFF", {}).get("tokens_per_task")
    base_con = tokens.get("CONFORM", {}).get("tokens_per_task")
    for a, t in tokens.items():
        tpt = t.get("tokens_per_task")
        t["multiple_vs_off"] = (tpt / base_off) if (tpt and base_off) else None
        t["multiple_vs_conform"] = (tpt / base_con) if (tpt and base_con) else None
    tpc_off5 = tokens.get("OFF5", {}).get("tpc_incl_void")
    for a, t in tokens.items():
        t["tpc_ratio_vs_off5"] = (t["tpc_incl_void"] / tpc_off5) \
            if (t.get("tpc_incl_void") and tpc_off5) else None
    out["tokens"] = tokens
    out["tpc_off5_incl_void"] = tpc_off5

    # ── 配對比較：家族 6 個（H × {OFF, CONFORM}）─────────────────────
    paired: dict[str, dict] = {}
    family: list[tuple[str, float]] = []
    for h in H_ARMS:
        for base in BASELINES:
            if h not in arms or base not in arms:
                continue
            key = f"{h}_vs_{base}"
            paired[key] = _paired(arms[h], arms[base])
            paired[key]["in_holm_family"] = True
            family.append((key, paired[key]["p_mcnemar_exact"]))
    # 探索量（**不在家族內**）：H 對 H、以及對 OFF5 的成本旁證。
    for a, b in (("HOC", "HPI"), ("HMIX", "HPI"), ("HMIX", "HOC"),
                 ("HPI", "OFF5"), ("HOC", "OFF5"), ("HMIX", "OFF5"),
                 ("CONFORM", "OFF"), ("OFF5", "OFF")):
        if a in arms and b in arms:
            key = f"{a}_vs_{b}"
            paired[key] = _paired(arms[a], arms[b])
            paired[key]["in_holm_family"] = False
            paired[key]["EXPLORATORY"] = True
    out["paired"] = paired

    if MUTANT == "M5_holm_family_drops_nonsignificant":
        family = [f for f in family if f[1] < 0.05]
    adj = holm_bonferroni([p for _, p in family]) if family else []
    out["holm"] = {"family_size": len(family),
                   "family_definition": "3 條 H 臂 × {OFF, CONFORM}；H 對 H 不在家族內",
                   "alpha": ALPHA}
    for (key, p), pa in zip(family, adj):
        out["holm"][key] = {"p_raw": p, "p_adj": pa, "significant": pa < ALPHA}
    if out["holm"]["family_size"] != 6 and not out["broken_reasons"]:
        out["notes"].append(
            f"holm.family_size={out['holm']['family_size']}（預註冊是 6）——"
            "少了臂或某臂零列；收官必須解釋，不准當成通過")

    # ── 檢定力（事後報，非事前註冊）───────────────────────────────────
    power: dict[str, dict] = {}
    for key, d in paired.items():
        n, nd = d["n_common"], d["n_discordant"]
        if not n:
            continue
        m = mde_at_n(n, nd / n if n else 0.0)
        pb = (d["b"] / nd) if nd else 0.5
        power[key] = {"mde_at_n_pp": m.get("mde_pp"),
                      "n_disc_expected": m.get("n_disc_expected"),
                      "n80_if_true_effect_is_observed": n_needed_for_power(pb)
                      if abs(pb - 0.5) > 1e-9 else -1}
    out["power"] = power

    # ── D5 歸因 ──────────────────────────────────────────────────────
    attribution: dict[str, dict] = {}
    for h in H_ARMS:
        if h not in arms:
            continue
        rs = arms[h]
        fpt1 = [r for r in rs if r.get("first_pass_turn") == 1]
        loop_needed = [r for r in rs if r.get("first_pass_turn") not in (1,)]
        gained = [r for r in rs
                  if r.get("first_pass_turn") not in (None, 1) and _deliv(r)]
        a = {
            "first_pass_turn_hist": per[h].get("first_pass_turn_hist"),
            "turn1_visible_pass_n": len(fpt1),
            "turn1_visible_pass_pp": _pct(len(fpt1), len(rs)),
            "loop_touched_n": len(loop_needed),
            "loop_gain_n": len(gained),
            "loop_gain_pp": _pct(len(gained), len(rs)),
            "rescored": False,
            "delta_turn1_minus_off_pp": None,
            "delta_turn1_minus_off_ci95_lo_pp": None,
            "delta_turn1_minus_off_ci95_hi_pp": None,
            "delta_final_minus_turn1_pp": None,
            "delta_final_minus_turn1_looponly_pp": None,
            "rescore_note": "未跑 --rescore-turn1 ⇒ D5 的兩個差值不可得（不是 0）",
        }
        if turn1 and h in turn1 and "OFF" in arms:
            a["rescored"] = True
            a["rescore_note"] = (
                "turn-1 的碼由 calls.jsonl 全文回應離線重取（初稿輪用 "
                "gain_run.extract_code，D4），再走與 dispatch 端逐字相同的 "
                "meets_demand(hidden)。無條件計分（沒有 accepted 語意），形狀與 OFF 相同。")
            t1 = turn1[h]
            off_map = {r["task_id"]: _deliv(r) for r in arms["OFF"]}
            common = sorted(set(t1) & set(off_map))
            b = sum(1 for t in common if t1[t] and not off_map[t])
            c = sum(1 for t in common if off_map[t] and not t1[t])
            d1 = diff_ci(b, c, len(common)) if common else None
            if d1:
                a.update({
                    "delta_turn1_minus_off_pp": 100.0 * d1["delta"],
                    "delta_turn1_minus_off_ci95_lo_pp": 100.0 * d1["lo"],
                    "delta_turn1_minus_off_ci95_hi_pp": 100.0 * d1["hi"],
                    "delta_turn1_minus_off_n_common": len(common),
                    "delta_turn1_minus_off_b": b, "delta_turn1_minus_off_c": c,
                    "delta_turn1_minus_off_p_mcnemar_exact": mcnemar_exact(b, c),
                })
            fin = {r["task_id"]: _deliv(r) for r in rs}
            com2 = sorted(set(t1) & set(fin))
            b2 = sum(1 for t in com2 if fin[t] and not t1[t])
            c2 = sum(1 for t in com2 if t1[t] and not fin[t])
            d2 = diff_ci(b2, c2, len(com2)) if com2 else None
            if d2:
                a.update({
                    "delta_final_minus_turn1_pp": 100.0 * d2["delta"],
                    "delta_final_minus_turn1_ci95_lo_pp": 100.0 * d2["lo"],
                    "delta_final_minus_turn1_ci95_hi_pp": 100.0 * d2["hi"],
                    "delta_final_minus_turn1_n_common": len(com2),
                })
            loop_ids = {r["task_id"] for r in loop_needed}
            com3 = sorted(set(com2) & loop_ids)
            b3 = sum(1 for t in com3 if fin[t] and not t1[t])
            c3 = sum(1 for t in com3 if t1[t] and not fin[t])
            if com3:
                d3 = diff_ci(b3, c3, len(com3))
                a.update({
                    "delta_final_minus_turn1_looponly_pp": 100.0 * d3["delta"],
                    "delta_final_minus_turn1_looponly_n_common": len(com3),
                })
            a["identity_warning"] = (
                "Δ_O ≈ prompt 效果 ＋ 迴圈效果，**不是恆等式**："
                "turn-1 那一份無條件計分（沒有拒交語意），最終那一份有 accepted。")
        attribution[h] = a
    out["attribution"] = attribution

    # ── G1..G5 ───────────────────────────────────────────────────────
    conform_fd = per.get("CONFORM", {}).get("false_delivery_pp")
    out["gates"]["G1_false_delivery"] = {
        "per_arm_n": {a: per[a]["false_delivery_n"] for a in sorted(per)},
        "per_arm_pp": {a: per[a]["false_delivery_pp"] for a in sorted(per)},
        "conform_false_delivery_pp": conform_fd,
        "threshold_pp": (conform_fd + FALSE_DELIV_SLACK_PP) if conform_fd is not None else None,
        "note": "SPEC_GAIN §4-5：可見通過但 hidden 錯，**絕對件數**也要報",
    }
    out["gates"]["G2_refusal_losslessness"] = {
        "refusal_pp": {a: per[a]["refusal_pp"] for a in sorted(per)},
        "lossless_violation_n": {a: per[a]["lossless_violation_n"] for a in sorted(per)},
        "refusal_stop_reasons": {a: {k: v for k, v in
                                     (per[a].get("stop_reason_counts") or {}).items()
                                     if k != "visible_pass"}
                                 for a in H_ARMS if a in per},
        "note": "H 臂多了 doom／budget_* 兩種新的拒交理由，必須與 CONFORM 的分開列",
    }

    # G3：OFF 臂被載入器擋掉的題（N3 的 7 題）——分層讀數
    off_refused = off_loader_refusals(calls, arms.get("OFF", []))
    keep = {r["task_id"] for r in arms.get("OFF", [])} - off_refused
    g3: dict = {"off_loader_refused_n": len(off_refused),
                "off_loader_refused_task_ids": sorted(off_refused),
                "off_loader_refused_pp": _pct(len(off_refused), len(arms.get("OFF", []))),
                "note": ("ITT 是主指標；artifact-excluded 是必報次要。"
                         "若 H 臂優勢在排除後掉超過一半，裁決書必須逐字寫"
                         "「這條臂買到的主要是我們自己的禁用屬性表太嚴"
                         "（_FORBIDDEN_ATTRS 含 remove），不是產出變好」")}
    for h in H_ARMS:
        for base in BASELINES:
            key = f"{h}_vs_{base}"
            if h in arms and base in arms:
                g3[f"{key}_itt_delta_pp"] = paired[key]["delta_pp"]
                sub = _paired_subset(arms[h], arms[base], keep)
                g3[f"{key}_excl_delta_pp"] = sub["delta_pp"]
                g3[f"{key}_excl_n_common"] = sub["n_common"]
                itt, ex = paired[key]["delta_pp"], sub["delta_pp"]
                g3[f"{key}_shrink_over_half"] = bool(
                    itt > 0 and ex < itt / 2.0)
    out["gates"]["G3_loader_artifact"] = g3

    # G4：難度與日期分層
    g4: dict = {"bank_loaded": bool(bank)}
    if bank:
        for a, rs in sorted(arms.items()):
            for diff in ("medium", "hard"):
                sel = [r for r in rs if (bank.get(r["task_id"]) or {}).get("difficulty") == diff]
                g4[f"{a}_{diff}_n"] = len(sel)
                g4[f"{a}_{diff}_deliv_pp"] = _pct(sum(1 for r in sel if _deliv(r)), len(sel))
        outlier = [t for t, m in bank.items()
                   if str(m.get("contest_date", ""))[:4] == "2023"]
        g4["pre_2024_task_ids"] = sorted(outlier)
        g4["pre_2024_deliv"] = {
            a: {t: _deliv(r) for r in rs for t in [r["task_id"]] if t in set(outlier)}
            for a, rs in sorted(arms.items())}
        g4["note"] = ("LCB v2 視窗 2023-08-26 → 2025-04-05；`lcb_3026` 是離群值。"
                      "對外一律用 RESULTS §5.2 的口徑，不宣稱「未汙染」")
    out["gates"]["G4_difficulty_date"] = g4

    out["gates"]["G5_calls_per_task"] = {
        "hist": {a: per[a].get("calls_hist") for a in sorted(per)},
        "mean": {a: per[a].get("calls_per_task") for a in sorted(per)},
        "note": "SPEC_GAIN §3：呼叫數要逐題記錄並報出來，不能只報平均（E19 前例）",
    }

    # ── D3 裁決 ──────────────────────────────────────────────────────
    decision: dict[str, dict] = {}
    for h in H_ARMS:
        ko, kc = f"{h}_vs_OFF", f"{h}_vs_CONFORM"
        if ko not in paired or kc not in paired:
            continue
        d_o, d_c = paired[ko]["delta_pp"], paired[kc]["delta_pp"]
        p_o = (out["holm"].get(ko) or {}).get("p_adj")
        p_c = (out["holm"].get(kc) or {}).get("p_adj")
        tpc = tokens.get(h, {}).get("tpc_incl_void")
        fd = per[h]["false_delivery_pp"]
        cond_i = (d_o is not None and d_c is not None
                  and d_o >= DELTA_O_MIN_PP and d_c >= DELTA_C_MIN_PP)
        cond_ii = (p_o is not None and p_c is not None
                   and p_o < ALPHA and p_c < ALPHA)
        cond_iii = (tpc is not None and tpc_off5 is not None and tpc <= tpc_off5)
        cond_iv = (fd is not None and conform_fd is not None
                   and fd <= conform_fd + FALSE_DELIV_SLACK_PP)
        cond_ii_conform = (p_c is not None and p_c < ALPHA)
        hi_c = paired[kc]["ci95_hi_pp"]
        order = ["EFFECTIVE", "COSTLY_BUT_REAL", "RULED_OUT", "INCONCLUSIVE"]
        # 突變體 M6：把判定順序調成 COSTLY 先判，**並且**拿掉它「排除 EFFECTIVE」的
        # 那個守衛。只調順序是等價突變體（COSTLY 的守衛本來就排除了 EFFECTIVE），
        # 兩件事一起做才是真的會把 EFFECTIVE 吃掉的那個滑坡。
        swallow = False
        if MUTANT == "M6_costly_swallows_effective":
            order = ["COSTLY_BUT_REAL", "EFFECTIVE", "RULED_OUT", "INCONCLUSIVE"]
            swallow = True
        v = None
        for cand in order:
            if cand == "EFFECTIVE" and (cond_i and cond_ii and cond_iii and cond_iv):
                v = cand
                break
            if cand == "COSTLY_BUT_REAL" and cond_ii_conform and (
                    swallow or not (cond_i and cond_ii and cond_iii and cond_iv)):
                v = cand
                break
            if cand == "RULED_OUT" and hi_c is not None and hi_c < DELTA_C_MIN_PP:
                v = cand
                break
            if cand == "INCONCLUSIVE":
                v = cand
                break
        decision[h] = {
            "delta_o_pp": d_o, "delta_c_pp": d_c,
            "p_adj_vs_off": p_o, "p_adj_vs_conform": p_c,
            "ci95_lo_pp_vs_conform": paired[kc]["ci95_lo_pp"],
            "ci95_hi_pp_vs_conform": hi_c,
            "tpc_incl_void": tpc, "tpc_off5": tpc_off5,
            "tpc_ratio_vs_off5": tokens.get(h, {}).get("tpc_ratio_vs_off5"),
            "multiple_vs_off": tokens.get(h, {}).get("multiple_vs_off"),
            "multiple_vs_conform": tokens.get(h, {}).get("multiple_vs_conform"),
            "false_delivery_pp": fd, "false_delivery_conform_pp": conform_fd,
            "cond_i_point_estimates": cond_i,
            "cond_ii_holm_both": cond_ii,
            "cond_ii_holm_conform_only": cond_ii_conform,
            "cond_iii_tokens": cond_iii,
            "cond_iv_false_delivery": cond_iv,
            "verdict": v,
            "ci_note": CI_DISCLAIMER,
        }
    out["decision"] = decision
    # 階段二的觸發條件在 DECISION §十一 逐字寫的是「**H-MIX** 落在 INCONCLUSIVE」
    # （主要假設指定為 H-MIX vs CONFORM，§六-(4)）。這裡就照那一條，
    # 不用「任一臂 INCONCLUSIVE」——那個較鬆的版本會讓消融臂替主要假設決定要不要
    # 再花一次機時，而 DECISION 沒有這樣寫。另一個較鬆的讀數照樣印出來，但不當觸發鍵。
    out["stage2_triggered"] = (
        any(d.get("verdict") == "INCONCLUSIVE" for d in decision.values())
        if MUTANT == "M9_stage2_any_arm" else
        (decision.get("HMIX") or {}).get("verdict") == "INCONCLUSIVE")
    out["stage2_triggered_any_arm_NOT_TRIGGER"] = any(
        d.get("verdict") == "INCONCLUSIVE" for d in decision.values())
    out["stage2_plan"] = ("H-MIX INCONCLUSIVE ⇒ 階段二 runs/g_r461h_harness_lcb3_a"
                          "＋runs/g_r461h_harness_lcb3_b（LCB v3 189 題切成 95+94、"
                          "seed g-r461-lcb3、與 v2 零交集、同六臂同門檻；"
                          "門檻不得在看到階段一之後修改）")

    # ── D9：分塊報表與拓撲檢查 ───────────────────────────────────────
    if blocks is not None:
        topo = topology_report(blocks)
        out["topology"] = topo
        out["block_order"] = [b["name"] for b in blocks]
        out["blocks"] = {
            b["name"]: analyze(b["rows"], b["summary"], b["calls"],
                               bank=bank, turn1=turn1, blocks=None)
            for b in blocks}
        # P-H0 的錨塊池：a1+a2+a3 的聯集（＝ r447 的前 60 題）。三塊缺一塊就
        # **不算**——「拿兩塊當 60 題」會安靜地換一個錨，而錨換了窗就沒有意義。
        ph0 = [b for b in blocks if b["name"] in PH0_BLOCKS]
        if len(ph0) == len(PH0_BLOCKS):
            out["ph0_pool"] = analyze(
                [r for b in ph0 for r in b["rows"]],
                merge_summaries([b["summary"] for b in ph0]),
                [c for b in ph0 for c in b["calls"]],
                bank=bank, turn1=turn1, blocks=None)
            out["ph0_pool_blocks"] = [b["name"] for b in ph0]
        else:
            out["ph0_pool"] = None
            out["ph0_pool_blocks"] = [b["name"] for b in ph0]
        # ⚠ 逐塊的 BROKEN 要往上帶。合併是**相加**，而相加會讓兩塊反向的錯誤互相抵銷：
        #   block a 的 `processed` 多算一題、block b 少算一題 ⇒ 合併帳剛好對得上，
        #   逐塊才看得出來。所以帳本身逐塊查，違規往上冒。
        #   （holm.family_size 那類「合併後才有意義」的抱怨不往上帶——
        #    逐塊的 6 臂配對本來就可能因為某臂在該塊零列而少一格，
        #    那不是資料壞掉；它已經表現在合併後的 n_common 上。）
        if MUTANT != "M10_block_broken_not_propagated":
            for name, sub in out["blocks"].items():
                for reason in sub.get("broken_reasons", []):
                    out["broken_reasons"].append(f"block:{name}:{reason}")
        if enforce_topology(blocks):
            out["broken_reasons"].extend(topo["violations"])
        elif topo["violations"]:
            out["notes"].append(
                "topology_violations_not_enforced:" + ",".join(topo["violations"]))
        if len(blocks) > 1:
            out["notes"].append(
                "分塊只是機時拓撲；仲裁一律取合併後的量（per_arm／paired／holm／decision），"
                "塊內數字是描述性的。六塊的難度組成不同"
                "（a1 medium12/hard8、a2 13/7、a3 15/5、b1 10/10、b2 12/8、b3 10/10）"
                "⇒ **塊間點估計不得互相比較**，配對比較只在塊內或合併後成立。")
            out["notes"].append(
                "⚠ 合併後每臂的 `wall_s` 是**六塊相加**＝該臂燒掉的總算力時間，"
                "**不是**牆鐘經過時間（六塊是併發跑的：兩台後端各三個行程）。"
                "`wall_s_per_task` 因此仍然是對的（每題平均算力時間），"
                "但「這個 run 花了幾小時」要看發射器的 log，不要讀這一格。")
        else:
            out["notes"].append(
                f"單塊分析（{blocks[0]['name']}）：這不是 R460 的收官讀法。"
                "仲裁要六塊一起餵 --run。")

    # ── 事前預測 ─────────────────────────────────────────────────────
    out["prereg"] = prereg_hits(out)
    return out


def window_hit(key: str, val: float | None) -> str:
    if val is None:
        return "UNEVALUABLE"
    _, lo, hi = PREREG[key]
    if MUTANT == "M7_widen_windows":
        lo, hi = None, None
    if lo is not None and val < lo:
        return "MISS"
    if hi is not None and val > hi:
        return "MISS"
    return "HIT"


def prereg_hits(out: dict) -> dict:
    per, paired, tokens = out["per_arm"], out["paired"], out["tokens"]
    res: dict = {}
    # D9（round460e）：P-H0 只在 **a1+a2+a3 的聯集**上判——那 60 題逐題逐序
    # 就是 r447 的前 60 題，錨 32/60＝53.33%。b* 那三塊是另外 60 題，不併進來。
    order = out.get("block_order") or []
    pool = out.get("ph0_pool")
    if order and pool:
        v_h0 = ((pool.get("per_arm") or {}).get("OFF")
                or {}).get("deliv_pp_denom_measured")
        h0_src = "ph0_pool.per_arm.OFF.deliv_pp_denom_measured"
        h0_note = ("只在 " + "＋".join(out.get("ph0_pool_blocks") or []) +
                   " 的聯集（offset 0/20/40，共 60 題）上判；"
                   "錨＝r447 前 60 題的 32/60＝53.33%，窗 ±15pp。"
                   "b* 那三塊是另外 60 題 ⇒ **不判、也不併進這一條**。"
                   "⚠ 誠實邊界：每臂的 rng 在每一塊各自從頭抽 ⇒ 六塊之下"
                   "只有 a1 的前 20 題與 r447 逐格同 persona，a2／a3 會錯開；"
                   "本條因此是非配對比較，噪音比兩塊版大，**窗不因此再放寬**。")
    elif order:
        v_h0 = None
        h0_src = "ph0_pool.per_arm.OFF.deliv_pp_denom_measured"
        h0_note = ("錨塊不齊（需要 " + "／".join(PH0_BLOCKS) + "，實際只有 " +
                   "／".join(out.get("ph0_pool_blocks") or ["(無)"]) +
                   "）⇒ **不判**。缺一塊就換了一個錨，而錨換了窗沒有意義。")
    else:
        v_h0 = (per.get("OFF") or {}).get("deliv_pp_denom_measured")
        h0_src = "per_arm.OFF.deliv_pp_denom_measured"
        h0_note = "單塊分析（未切塊）⇒ 直接讀本 run 的 OFF 交付率。"
    res["P-H0"] = {"value": v_h0, "hit": window_hit("P-H0", v_h0),
                   "source_field": h0_src, "note": h0_note,
                   "pooled_off_deliv_pp_NOT_ARBITER":
                       (per.get("OFF") or {}).get("deliv_pp_denom_measured"),
                   "scope": ("MISS 只作廢與 r447 的橫向比較；本 run 內部六臂比較仍有效"
                             "（同一題的六臂共享同一個後端、逐題交錯）")}
    d_o = {h: (paired.get(f"{h}_vs_OFF") or {}).get("delta_pp") for h in H_ARMS}
    res["P-H1"] = {"value": d_o,
                   "hit": "HIT" if all(v is not None and v > 0 for v in d_o.values()) else "MISS"}
    d_c = {h: (paired.get(f"{h}_vs_CONFORM") or {}).get("delta_pp") for h in H_ARMS}
    res["P-H2"] = {"value": d_c,
                   "hit": "HIT" if any(v is not None and v > 0 for v in d_c.values()) else "MISS"}
    cpt = {h: (per.get(h) or {}).get("calls_per_task") for h in H_ARMS}
    res["P-H3"] = {"value": cpt,
                   "hit": ("HIT" if all(window_hit("P-H3", v) == "HIT" for v in cpt.values())
                           else "MISS")}
    conform_fd = (per.get("CONFORM") or {}).get("false_delivery_pp")
    fd = {h: (per.get(h) or {}).get("false_delivery_pp") for h in H_ARMS}
    res["P-H4"] = {"value": fd, "conform_false_delivery_pp": conform_fd,
                   "hit": ("HIT" if conform_fd is not None and all(
                       v is not None and v > conform_fd and v <= 35.0 for v in fd.values())
                       else "MISS"),
                   "note": "窗＝(CONFORM 的假交付率, 35]；這是**預測會變差一點**，不是門檻"}
    lr = {h: (per.get(h) or {}).get("loader_turn_rate_pp") for h in H_ARMS}
    res["P-H5"] = {"value": lr,
                   "hit": ("HIT" if all(window_hit("P-H5", lr.get(h)) == "HIT"
                                        for h in ("HOC", "HMIX")) else "MISS"),
                   "note": "只判 HOC／HMIX（有靜態診斷的兩條）；HPI 沒有診斷，預期仍在 2% 上下"}
    tp_mix = (tokens.get("HMIX") or {}).get("tokens_per_task")
    tp_pi = (tokens.get("HPI") or {}).get("tokens_per_task")
    ratio = (tp_mix / tp_pi) if (tp_mix and tp_pi) else None
    res["P-H6"] = {"value": ratio, "hmix_tokens_per_task": tp_mix,
                   "hpi_tokens_per_task": tp_pi, "hit": window_hit("P-H6", ratio)}
    # 臂不存在 ⇒ None（UNEVALUABLE）；臂存在但沒有 budget_wall ⇒ 真的是 0.0。
    bw = {h: (((per.get(h) or {}).get("stop_reason_pp") or {}).get("budget_wall", 0.0)
              if h in per else None)
          for h in H_ARMS}
    res["P-H7"] = {"value": bw,
                   "hit": ("HIT" if all(window_hit("P-H7", v) == "HIT" for v in bw.values())
                           else "MISS"),
                   "sensitivity_required": any((v or 0) > 5.0 for v in bw.values())}
    nc = {h: (per.get(h) or {}).get("nocode_turn_rate_pp") for h in H_ARMS}
    res["P-H8"] = {"value": nc,
                   "hit": ("HIT" if all(window_hit("P-H8", v) == "HIT" for v in nc.values())
                           else "MISS")}
    hoc = (paired.get("HOC_vs_HPI") or {})
    mix = (paired.get("HMIX_vs_HPI") or {})
    both_beat = bool(hoc.get("delta_pp", 0) > 0 and mix.get("delta_pp", 0) > 0
                     and (hoc.get("p_mcnemar_exact") or 1.0) < ALPHA
                     and (mix.get("p_mcnemar_exact") or 1.0) < ALPHA)
    res["P-H9"] = {"hoc_vs_hpi": {k: hoc.get(k) for k in
                                  ("delta_pp", "p_mcnemar_exact", "n_common")},
                   "hmix_vs_hpi": {k: mix.get(k) for k in
                                   ("delta_pp", "p_mcnemar_exact", "n_common")},
                   "followup_h4_required": both_beat,
                   "note": ("H 對 H 的兩個檢定**不在 Holm 家族內**（家族固定 6），"
                            "這裡的 p 是未調整的探索量，只用來觸發 P-H9 的後續臂："
                            "H-PI ＋ 只加靜態診斷。若 HOC 與 HMIX 都贏 HPI，"
                            "計畫輪的獨立效果在本設計裡不可辨識（§4.4）")}
    return res


# ── OFF 臂的載入器拒收（G3）：零沙箱，只用 ast ─────────────────────────
def off_loader_refusals(calls: list[dict], off_rows: list[dict]) -> set[str]:
    """重跑 `static_precheck` 找出 OFF 臂那幾份「連載都載不進去」的草稿（N3 的 7 題）。

    零沙箱、零 API：只有 `ast.parse` ＋ 既有白名單。取碼一律走
    `gain_run.extract_code`（OFF 臂用的就是它）。
    """
    try:
        from ops.gain.gain_run import extract_code
        from ops.gain.harness_arms import DEFAULT_ALLOWED_IMPORTS, static_precheck
    except Exception:                                        # noqa: BLE001
        return set()
    ep = {r["task_id"]: r.get("entry_point") for r in off_rows}
    latest: dict[str, str] = {}
    for rec in calls:
        if _call_arm(rec) != "OFF" or not rec.get("ok"):
            continue
        tid = (rec.get("meta") or {}).get("task_id")
        if tid in ep:
            latest[tid] = rec.get("response") or ""
    bad = set()
    for tid, text in latest.items():
        ok, _ = static_precheck(extract_code(text), DEFAULT_ALLOWED_IMPORTS, ep.get(tid))
        if not ok:
            bad.add(tid)
    return bad


# ── D5 的 turn-1 重評（唯一會跑沙箱的路徑）────────────────────────────
def rescore_turn1(rows: list[dict], calls: list[dict], bank_tasks: dict[str, dict]
                  ) -> dict[str, dict[str, bool]]:
    """把 H 臂**初稿輪**的碼重新用 `meets_demand(hidden)` 評一次。

    「初稿輪」＝第一個 `kind == "build"` 的輪次（H-OC 的第 1 輪是計畫輪，不出碼）。
    取碼一律走 `gain_run.extract_code`（D4：初稿輪與 OFF 同一個取碼器）。
    ⚠ 零模型呼叫，但**會跑沙箱**（每題一次），與 dispatch 端同一條路徑。
    """
    from ops.gain.gain_run import extract_code, meets_demand
    by_key: dict[tuple[str, str, int], str] = {}
    for rec in calls:
        arm = _call_arm(rec)
        if arm not in H_ARMS or not rec.get("ok"):
            continue
        meta = rec.get("meta") or {}
        tid, turn = meta.get("task_id"), meta.get("turn")
        if tid is None or turn is None:
            continue
        by_key[(arm, tid, int(turn))] = rec.get("response") or ""
    out: dict[str, dict[str, bool]] = {}
    for r in rows:
        arm = r.get("arm")
        if arm not in H_ARMS:
            continue
        build = next((t for t in (r.get("harness_turns") or [])
                      if t.get("kind") == "build" and t.get("used_output")), None)
        if build is None:
            continue
        text = by_key.get((arm, r["task_id"], int(build["turn"])))
        task = bank_tasks.get(r["task_id"])
        if text is None or task is None:
            continue
        truth, _ = meets_demand(extract_code(text), task["hidden_check"]["code"],
                                entry_point=task.get("entry_point"))
        out.setdefault(arm, {})[r["task_id"]] = bool(truth)
    return out


# ── I/O ──────────────────────────────────────────────────────────────
def load_run(run: pathlib.Path) -> tuple[list[dict], dict, list[dict]]:
    rows = [json.loads(l) for l in (run / "rows.jsonl").open(encoding="utf-8") if l.strip()]
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    cp = run / "calls.jsonl"
    calls = [json.loads(l) for l in cp.open(encoding="utf-8") if l.strip()] if cp.exists() else []
    return rows, summary, calls


def endpoints_of(calls: list[dict]) -> list[str]:
    """一塊實際打過的端點集合。來源是 `calls.jsonl` 的 `api` 欄位。

    ⚠ **端點身分不在 `summary.json` 裡**，而 D8 不准為了加它去改 `gain_run.py`
    （只准動 import／KNOWN_ARMS／_gate_arms／dispatch elif 四處）。
    幸好 `brain_cline.ClineBrain._log` 早就逐次寫 `"api": self.api`
    （`ops/gain/brain_cline.py:160/201/346/387`）⇒ 端點身分是**逐呼叫**落盤的，
    比 summary 裡放一個設定值還嚴：它記的是**真的送去哪裡**，不是「打算送去哪裡」。
    本函式把它讀回來，`topology_report` 再據此判 D9 的三條硬規則。
    """
    return sorted({(r.get("api") or "").strip() for r in calls if (r.get("api") or "").strip()})


def merge_summaries(summaries: list[dict]) -> dict:
    """把數塊的 summary 併成一份給 `analyze()` 用的合併帳。

    只併 `analyze()` 真的會讀的欄位：每臂的 `processed`／`infra_void`／`wall_s`
    與整體的 `run_terminal`。**沒讀的欄位一律不併**——併了會讓收官的人以為
    那些數字有合併意義（例如 `calls_per_task` 是比率，直接相加是錯的）。
    `run_terminal` 取 **all()**：有一塊沒收官，合併資料就不是收官資料。
    """
    if len(summaries) == 1:
        return summaries[0]
    arms: dict[str, dict] = {}
    for s in summaries:
        for a, v in (s.get("arms") or {}).items():
            t = arms.setdefault(a, {"processed": 0, "infra_void": 0, "wall_s": 0.0,
                                    "complete": True, "terminal": True})
            t["processed"] += int(v.get("processed") or 0)
            t["infra_void"] += int(v.get("infra_void") or 0)
            t["wall_s"] += float(v.get("wall_s") or 0.0)
            t["complete"] = bool(t["complete"] and v.get("complete"))
            t["terminal"] = bool(t["terminal"] and v.get("terminal"))
    return {"arms": arms,
            "run_terminal": all(bool(s.get("run_terminal")) for s in summaries),
            "seed": (summaries[0] or {}).get("seed"),
            "n": sum(int(s.get("n") or 0) for s in summaries),
            "offset": None,          # 合併之後沒有單一 offset；刻意留 None
            "pooled_from": len(summaries)}


def pool_runs(paths: list[pathlib.Path]) -> tuple[list[dict], dict, list[dict], list[dict]]:
    """讀入一或多個 run 目錄，依 `offset` 排序後合併（R445 先例：按 task_id 併）。

    回傳 `(rows, summary, calls, blocks)`；`blocks` 依 offset 由小到大，
    所以 `blocks[0]` 就是 **block a**（offset 0），P-H0 只看它。
    """
    blocks: list[dict] = []
    for p in paths:
        rows, summary, calls = load_run(p)
        blocks.append({
            "name": p.name, "path": str(p), "rows": rows, "summary": summary,
            "calls": calls, "endpoints": endpoints_of(calls),
            "offset": int(summary.get("offset") or 0),
            "n": int(summary.get("n") or 0),
            "seed": summary.get("seed"),
            "arms": sorted((summary.get("arms") or {}).keys()),
            "task_ids": {r["task_id"] for r in rows if "task_id" in r},
        })
    blocks.sort(key=lambda b: (b["offset"], b["name"]))
    rows = [r for b in blocks for r in b["rows"]]
    calls = [c for b in blocks for c in b["calls"]]
    return rows, merge_summaries([b["summary"] for b in blocks]), calls, blocks


def topology_report(blocks: list[dict]) -> dict:
    """D9 的硬規則（round460e：六塊版），逐條可判、違反就進 `broken_reasons`。

    1. **塊之間 task_id 兩兩零交集**，且**聯集恰好 120 題**——併不了的東西不准併
       （`CRITERION_20260903_R680_POOL_PRECONDITIONS.md` 的 Q1）。
       ⚠ 交集的判準必須是**聯集大小**不是各塊題數相加：兩塊重疊 5 題時
       「相加」仍然是 120，只有聯集會掉到 115。
    2. **一塊一端點**：同一塊裡出現兩個 `api` ⇒ 那一塊自己就是混的，不可分析。
    3. **不准走 hub**：D9 量到 hub 把 100% 請求路由到同一顆後端、且併發越高越慢。
    4. **拓撲只准是兩種之一**（round460h 修訂；round460e 版是「恰好兩個端點、每個三塊」）：
       `two_backends_3_3`（兩顆相異端點各三塊）或 `one_backend_6`（一顆端點六塊）。
       判到哪一種就記在 `variant` 裡，**並逐塊記端點**（`endpoint_of_block`）——
       收官引用時不准只說「拓撲合法」，要說清楚是哪一種。
       六塊之下「同端點」不是違規——**是設計**（一台後端三個序列 runner，
       實測 3 併發不掉速）。真正要擋的變成**超賣**：兩顆端點卻被塞成 4／2，
       那台就從「3 併發不掉速」掉進「6 併發開始退化」的區間，而那**看起來只是比較慢**，
       沒有任何既有欄位會變紅。所以逐端點數塊數，兩顆時不等於 3、一顆時不等於 6 就判。
       ⚠ `one_backend_6` 之下**併發**這件事不由本函式管：`calls.jsonl` 記的是
       「打去哪裡」不是「同時幾個」。同時六個 runner 的擋門在發射器
       （`abort_endpoint_oversubscribed`，對「這一刻」算）。
       本 run 的 one_backend_6 是**時間上錯開**的：b 組先跑完、a 組隔約 17 小時再跑
       ⇒ 換來的代價是**後端漂移變成新的干擾項**（DECISION §四 E-7 修訂、§八-14）。
    5. 塊數必須是 6：只跑得完一部分就結算＝安靜地換一個 n。

    另外查 seed／臂集合一致。`enforce` 為 False 時只描述不判——
    那是給「拿這支去看 r447 這類歷史單塊資料」用的診斷路徑。
    """
    rep: dict = {"blocks_n": len(blocks), "blocks_expected": BLOCKS_EXPECTED,
                 "endpoints_allowed": list(ENDPOINTS_ALLOWED),
                 "blocks_per_endpoint_expected": BLOCKS_PER_ENDPOINT,
                 "blocks_per_endpoint_expected_solo": BLOCKS_PER_ENDPOINT_SOLO,
                 "tasks_expected": TASKS_EXPECTED,
                 "variant": None, "variant_why": None, "endpoint_of_block": {},
                 "by_block": {}, "violations": []}
    for b in blocks:
        rep["by_block"][b["name"]] = {
            "offset": b["offset"], "n": b["n"], "n_rows": len(b["rows"]),
            "seed": b["seed"], "endpoints": b["endpoints"],
            "n_tasks": len(b["task_ids"]), "arms": b["arms"],
            "run_terminal": bool((b["summary"] or {}).get("run_terminal")),
        }
    # 1) task_id 零交集
    for i, a in enumerate(blocks):
        for b in blocks[i + 1:]:
            inter = a["task_ids"] & b["task_ids"]
            if inter:
                rep["violations"].append(
                    f"block_task_overlap:{a['name']}|{b['name']}:{len(inter)}")
    # 2) 一塊一端點
    for b in blocks:
        if not b["endpoints"]:
            rep["violations"].append(f"block_endpoint_unrecorded:{b['name']}")
        elif len(b["endpoints"]) > 1:
            rep["violations"].append(
                f"block_multi_endpoint:{b['name']}:{'|'.join(b['endpoints'])}")
    # 3) hub 與同端點
    for b in blocks:
        for ep in b["endpoints"]:
            if any(m in ep for m in HUB_MARKERS):
                rep["violations"].append(f"block_used_hub:{b['name']}:{ep}")
    # 4) 端點數與每端點塊數（round460h：兩種允許的拓撲，判到哪一種要記下來）
    by_ep: dict[str, list[str]] = {}
    for b in blocks:
        for ep in b["endpoints"]:
            by_ep.setdefault(ep, []).append(b["name"])
    rep["blocks_per_endpoint"] = {ep: sorted(v) for ep, v in sorted(by_ep.items())}
    rep["endpoint_of_block"] = {
        b["name"]: (b["endpoints"][0] if len(b["endpoints"]) == 1
                    else "|".join(b["endpoints"]) or None)
        for b in blocks}
    n_ep = len(by_ep)
    rep["endpoints_n"] = n_ep
    rep["variant"] = TOPOLOGY_VARIANTS.get(n_ep)
    want_per_ep = BLOCKS_PER_ENDPOINT_SOLO if n_ep == 1 else BLOCKS_PER_ENDPOINT
    rep["variant_why"] = (
        f"{n_ep} 個相異端點、每個 {want_per_ep} 塊"
        if rep["variant"] else f"{n_ep} 個相異端點——不在允許的 {list(ENDPOINTS_ALLOWED)} 裡")
    if MUTANT != "M11_endpoint_balance_not_checked":
        if n_ep not in ENDPOINTS_ALLOWED:
            rep["violations"].append(
                f"endpoints_n_not_in_{'_'.join(map(str, ENDPOINTS_ALLOWED))}:{n_ep}")
        for ep, names in sorted(by_ep.items()):
            if len(set(names)) != want_per_ep:
                rep["violations"].append(
                    f"endpoint_block_count_not_{want_per_ep}:{ep}:{len(set(names))}")
    # 5) seed／臂／塊數
    seeds = {b["seed"] for b in blocks}
    if len(seeds) > 1:
        rep["violations"].append(f"block_seed_mismatch:{sorted(map(str, seeds))}")
    armsets = {tuple(b["arms"]) for b in blocks}
    if len(armsets) > 1:
        rep["violations"].append("block_arms_mismatch")
    offsets = [b["offset"] for b in blocks]
    if len(set(offsets)) != len(offsets):
        rep["violations"].append(f"block_offset_collision:{offsets}")
    if len(blocks) != BLOCKS_EXPECTED:
        rep["violations"].append(f"block_count_not_{BLOCKS_EXPECTED}:{len(blocks)}")
    # 6) 聯集恰好 120 題（＝ r447 的那 120 題；同 seed 同 bank ⇒ 同一批）
    union: set = set()
    for b in blocks:
        union |= b["task_ids"]
    rep["endpoints_all"] = sorted(by_ep)
    rep["task_ids_pooled"] = sum(len(b["task_ids"]) for b in blocks)
    rep["task_ids_union"] = len(union)
    if len(union) != TASKS_EXPECTED:
        rep["violations"].append(
            f"pooled_task_count_not_{TASKS_EXPECTED}:{len(union)}")
    return rep


def enforce_topology(blocks: list[dict]) -> bool:
    """要不要把 topology 的違規算成 BROKEN。

    兩種情形要判：(a) 真的給了多塊（那就是 D9 的設計，規則全套適用）；
    (b) 只給一塊、但那一塊的名字是本檔授權的 r460 塊名——
    「只分析 block a」會安靜地變成「n=60 的另一個實驗」，那正是要擋的東西。
    其餘（例如拿這支去描述 r447）只描述、不判。
    """
    if MUTANT == "M8_topology_not_enforced":
        return False
    return len(blocks) > 1 or any(b["name"] in AUTHORIZED_BLOCKS for b in blocks)


def load_bank_meta(bank: str) -> dict[str, dict]:
    f = ROOT / "ops" / "gain" / "data" / f"lcb_bank_{'v2' if bank == 'lcb2' else 'v3'}.jsonl"
    if not f.exists():
        return {}
    out = {}
    for line in f.open(encoding="utf-8"):
        if line.strip():
            d = json.loads(line)
            out[d["task_id"]] = {"difficulty": d.get("difficulty"),
                                 "contest_date": d.get("contest_date")}
    return out


# ── 報表 ─────────────────────────────────────────────────────────────
def _f(v, nd=2, suffix=""):
    return "n/a" if v is None else f"{v:.{nd}f}{suffix}"


def render(out: dict) -> str:
    L: list[str] = []
    L.append("═══ R460 harness 六臂收官報表 ═══")
    L.append(f"broken_reasons: {out['broken_reasons'] or '[]'}")
    L.append(f"run_terminal: {out['run_terminal']}   notes: {out['notes'] or '[]'}")
    topo = out.get("topology")
    if topo:
        L.append("")
        L.append("── D9 機時拓撲（六塊直連後端；round460h：{兩顆各三塊} 或 {一顆六塊}；"
                 "仲裁一律取合併後的量）")
        L.append(f"{'block':26}{'offset':>8}{'n':>5}{'rows':>7}{'題數':>7}  端點")
        for name, b in topo["by_block"].items():
            L.append(f"{name:26}{b['offset']:>8}{b['n']:>5}{b['n_rows']:>7}"
                     f"{b['n_tasks']:>7}  {'|'.join(b['endpoints']) or '(未落盤)'}")
        L.append(f"拓撲 variant = {topo.get('variant') or '(不合法)'}"
                 f"（{topo.get('variant_why')}）")
        L.append(f"塊數 {topo['blocks_n']}/{topo['blocks_expected']}　"
                 f"合併題數(聯集) {topo.get('task_ids_union')}/{topo.get('tasks_expected')}　"
                 f"違規 {topo['violations'] or '[]'}")
        for ep, names in (topo.get("blocks_per_endpoint") or {}).items():
            L.append(f"  {ep}  ←  {len(names)} 塊：{', '.join(names)}")
        if topo.get("variant") == "one_backend_6":
            L.append("  ⚠ one_backend_6：六塊同一顆後端 ⇒ **後端不再是干擾項**。"
                     "代價是兩半不同時跑（b 組先、a 組隔約 17 小時）"
                     "⇒ **後端漂移**變成新的干擾項；P-H0（a 組那三塊）就是它的探針。")
        for name, sub in (out.get("blocks") or {}).items():
            po = (sub.get("per_arm") or {})
            cells = "  ".join(
                f"{a} {(po.get(a) or {}).get('deliv_n', '-')}/"
                f"{(po.get(a) or {}).get('measured', '-')}" for a in ALL_ARMS if a in po)
            L.append(f"  [{name}] {cells}")
        if topo["blocks_n"] > 1:
            L.append("  ⚠ 六塊題目難度組成不同（lcb2：a1 12/8、a2 13/7、a3 15/5、"
                     "b1 10/10、b2 12/8、b3 10/10，medium/hard）⇒ 塊間點估計不得互相比較。")
        ph0b = out.get("ph0_pool_blocks")
        if ph0b is not None:
            L.append(f"  P-H0 錨塊池：{'＋'.join(ph0b) or '(不齊，不判)'}"
                     f"（＝ r447 前 60 題；錨 32/60＝53.33%，窗 ±15pp）")
    L.append("")
    L.append("── 逐臂主指標（分母 measured ＝ processed − infra_void）")
    L.append(f"{'arm':8}{'n':>5}{'void':>6}{'acc':>6}{'deliv':>7}{'deliv%':>9}"
             f"{'false%':>9}{'prec%':>8}{'refuse%':>9}{'calls':>8}{'wall/題':>9}")
    for a in ALL_ARMS:
        p = out["per_arm"].get(a)
        if not p:
            continue
        L.append(f"{a:8}{p['measured']:>5}{p['infra_void']:>6}{p['accepted']:>6}"
                 f"{p['deliv_n']:>7}{_f(p['deliv_pp_denom_measured']):>9}"
                 f"{_f(p['false_delivery_pp']):>9}{_f(p['accept_precision_pp']):>8}"
                 f"{_f(p['refusal_pp']):>9}{_f(p['calls_per_task']):>8}"
                 f"{_f(p['wall_s_per_task'], 1, 's'):>9}")
    L.append("")
    L.append("── token 倍數表（D3 的 (iii) 旁邊必須有這張；缺表＝裁決不得結算）")
    L.append(f"{'arm':8}{'tok/題':>10}{'×OFF':>8}{'×CONFORM':>11}"
             f"{'TPC(含void)':>13}{'TPC(排除)':>12}{'÷OFF5':>8}")
    for a in ALL_ARMS:
        t = out["tokens"].get(a)
        if not t:
            continue
        L.append(f"{a:8}{_f(t['tokens_per_task'], 0):>10}{_f(t['multiple_vs_off']):>8}"
                 f"{_f(t['multiple_vs_conform']):>11}{_f(t['tpc_incl_void'], 0):>13}"
                 f"{_f(t['tpc_excl_void'], 0):>12}{_f(t['tpc_ratio_vs_off5']):>8}")
    L.append(f"  TPC_OFF5（同 run，含 void 呼叫）＝ {_f(out.get('tpc_off5_incl_void'), 0)}")
    L.append("")
    L.append("── 配對比較（家族 6 個；H 對 H 標 EXPLORATORY，不在家族內）")
    L.append(f"  ⚠ {CI_DISCLAIMER}")
    L.append(f"{'pair':22}{'n':>5}{'b':>5}{'c':>5}{'Δpp':>9}{'lo':>9}{'hi':>9}"
             f"{'p_raw':>10}{'p_holm':>10}")
    for k, d in out["paired"].items():
        h = out["holm"].get(k) or {}
        tag = "" if d.get("in_holm_family") else "  [EXPLORATORY]"
        L.append(f"{k:22}{d['n_common']:>5}{d['b']:>5}{d['c']:>5}{_f(d['delta_pp']):>9}"
                 f"{_f(d['ci95_lo_pp']):>9}{_f(d['ci95_hi_pp']):>9}"
                 f"{_f(d['p_mcnemar_exact'], 4):>10}{_f(h.get('p_adj'), 4):>10}{tag}")
    L.append(f"  holm.family_size = {out['holm']['family_size']}（預註冊是 6）")
    L.append("")
    L.append("── D5 歸因（prompt 效果 vs 迴圈效果）")
    for h, a in out["attribution"].items():
        L.append(f"  {h}: turn1 通過 {a['turn1_visible_pass_n']} 題"
                 f"（{_f(a['turn1_visible_pass_pp'])}%）、迴圈才對 {a['loop_gain_n']} 題"
                 f"（{_f(a['loop_gain_pp'])}%）")
        L.append(f"      first_pass_turn 直方圖: {a['first_pass_turn_hist']}")
        L.append(f"      Δ(turn1−OFF) = {_f(a['delta_turn1_minus_off_pp'])}pp"
                 f"   Δ(final−turn1) = {_f(a['delta_final_minus_turn1_pp'])}pp"
                 f"   （只算迴圈題）= {_f(a['delta_final_minus_turn1_looponly_pp'])}pp")
        if not a["rescored"]:
            L.append(f"      ⚠ {a['rescore_note']}")
    L.append("")
    L.append("── 逐臂輪次與停止理由（G5：不能只報平均）")
    for h in H_ARMS:
        p = out["per_arm"].get(h)
        if not p:
            continue
        L.append(f"  {h}: calls 直方圖 {p.get('calls_hist')}  turn 直方圖 {p.get('turn_hist')}")
        L.append(f"      stop_reason {p.get('stop_reason_counts')}")
        L.append(f"      協定：nocode {p.get('nocode_turns')}（{_f(p.get('nocode_turn_rate_pp'))}%）、"
                 f"loader {p.get('loader_refusals')}（{_f(p.get('loader_turn_rate_pp'))}%）、"
                 f"其中 entry_point_missing {p.get('entry_point_missing')}、"
                 f"first_block_non_python {p.get('first_block_non_python')}")
        L.append(f"      取碼器分歧 {p.get('extractor_divergences')}"
                 f"（{_f(p.get('extractor_divergence_rate_pp'))}% 的輪次）、"
                 f"截斷重發 {p.get('truncated_retries')}、doom {p.get('doom_triggered_n')}")
        L.append(f"      precheck reason 分佈 {p.get('precheck_reason_counts')}")
        L.append(f"      wire_mode {p.get('wire_modes')}")
    L.append("")
    L.append("── G1–G6 守門指標")
    g = out["gates"]
    L.append(f"  G1 假交付（件數）: {g['G1_false_delivery']['per_arm_n']}")
    L.append(f"     門檻（CONFORM＋5pp）: {_f(g['G1_false_delivery']['threshold_pp'])}%")
    L.append(f"  G2 拒交率: {({k: _f(v) for k, v in g['G2_refusal_losslessness']['refusal_pp'].items()})}")
    L.append(f"     無損性違反（hidden 過但沒交）: {g['G2_refusal_losslessness']['lossless_violation_n']}")
    L.append(f"  G3 OFF 臂載入器拒收 {g['G3_loader_artifact']['off_loader_refused_n']} 題"
             f"（{_f(g['G3_loader_artifact']['off_loader_refused_pp'])}%）:"
             f" {g['G3_loader_artifact']['off_loader_refused_task_ids']}")
    for h in H_ARMS:
        for base in BASELINES:
            k = f"{h}_vs_{base}"
            if f"{k}_itt_delta_pp" in g["G3_loader_artifact"]:
                L.append(f"     {k}: ITT {_f(g['G3_loader_artifact'][f'{k}_itt_delta_pp'])}pp"
                         f" → 排除後 {_f(g['G3_loader_artifact'][f'{k}_excl_delta_pp'])}pp"
                         f"  掉超過一半={g['G3_loader_artifact'][f'{k}_shrink_over_half']}")
    L.append(f"  G4 難度／日期分層: bank_loaded={g['G4_difficulty_date']['bank_loaded']}")
    for a in ALL_ARMS:
        if f"{a}_medium_deliv_pp" in g["G4_difficulty_date"]:
            L.append(f"     {a}: medium {_f(g['G4_difficulty_date'][f'{a}_medium_deliv_pp'])}%"
                     f"（n={g['G4_difficulty_date'][f'{a}_medium_n']}）"
                     f" / hard {_f(g['G4_difficulty_date'][f'{a}_hard_deliv_pp'])}%"
                     f"（n={g['G4_difficulty_date'][f'{a}_hard_n']}）")
    if g["G4_difficulty_date"].get("pre_2024_task_ids"):
        L.append(f"     2023 年的離群題: {g['G4_difficulty_date']['pre_2024_task_ids']}")
    L.append(f"  G5 calls/題 平均: {({k: _f(v) for k, v in g['G5_calls_per_task']['mean'].items()})}")
    L.append(f"  G6 wire mode: {g['G6_wire_mode']['per_arm']}"
             f"  單一模式={g['G6_wire_mode']['single_mode_per_arm']}")
    L.append("")
    L.append("── D3 裁決（判定順序 EFFECTIVE → COSTLY_BUT_REAL → RULED_OUT → INCONCLUSIVE）")
    for h, d in out["decision"].items():
        L.append(f"  {h}: Δ_O={_f(d['delta_o_pp'])}pp  Δ_C={_f(d['delta_c_pp'])}pp"
                 f"  [{_f(d['ci95_lo_pp_vs_conform'])}, {_f(d['ci95_hi_pp_vs_conform'])}]"
                 f"  p_holm(OFF)={_f(d['p_adj_vs_off'], 4)}"
                 f"  p_holm(CONFORM)={_f(d['p_adj_vs_conform'], 4)}")
        L.append(f"      (i)點估計={d['cond_i_point_estimates']}"
                 f"  (ii)Holm 兩邊={d['cond_ii_holm_both']}"
                 f"  (iii)token={d['cond_iii_tokens']}"
                 f"（TPC {_f(d['tpc_incl_void'], 0)} vs OFF5 {_f(d['tpc_off5'], 0)}；"
                 f"×OFF {_f(d['multiple_vs_off'])}、×CONFORM {_f(d['multiple_vs_conform'])}）"
                 f"  (iv)假交付={d['cond_iv_false_delivery']}")
        L.append(f"      ⇒ **{d['verdict']}**")
    L.append(f"  階段二觸發: {out['stage2_triggered']}　{out['stage2_plan']}")
    L.append("")
    L.append("── 事前預測 P-H0..P-H9")
    for k, v in out["prereg"].items():
        L.append(f"  {k}: {v.get('hit', '-')}  {json.dumps({kk: vv for kk, vv in v.items() if kk != 'hit'}, ensure_ascii=False)[:260]}")
    L.append("")
    L.append(f"⚠ {WINNERS_CURSE}")
    L.append(f"⚠ {CI_DISCLAIMER}")
    return "\n".join(L)


# ── selftest ─────────────────────────────────────────────────────────
def _row(arm, tid, *, deliv=True, accepted=True, visible_ok=True, calls=1, **kw):
    r = {"arm": arm, "task_id": tid, "meets_demand": deliv, "accepted": accepted,
         "calls_used": calls, "visible_ok": visible_ok}
    if arm in H_ARMS:
        r.update({"harness_variant": arm, "harness_wire_mode": "multiturn",
                  "harness_calls": calls, "harness_tokens_total": 1000 * calls,
                  "stop_reason": "visible_pass" if accepted else "budget_calls",
                  "first_pass_turn": 1 if accepted else None,
                  "n_turns": calls, "harness_turns": [{"turn": i + 1, "kind": "build",
                                                       "used_output": True}
                                                      for i in range(calls)],
                  "loader_refusals": 0, "entry_point_missing": 0, "nocode_turns": 0,
                  "first_block_non_python": 0, "truncated_retries": 0,
                  "extractor_divergences": 0, "doom_nudges": 0,
                  "doom_triggered": False, "selftests_parsed": 0,
                  "selftests_unparsable": 0})
    r.update(kw)
    return r


def _calls_for(rows: list[dict], per_call_tokens: int = 1000) -> list[dict]:
    out = []
    for r in rows:
        for j in range(int(r["calls_used"])):
            out.append({"ok": True, "usage": {"total_tokens": per_call_tokens},
                        "meta": {"arm": r["arm"], "task_id": r["task_id"],
                                 "turn": j + 1}, "response": ""})
    return out


def _fixture():
    """主夾具（三種裁決各出現一次，且家族裡刻意留一個不顯著的檢定）。

    形狀是刻意排的，每一條都對應 selftest 的一條具名檢查：
      OFF      deliv 50/120
      CONFORM  deliv 70/120、accepted 110 ⇒ 假交付 40；其中 3 題
               `accepted=False ∧ meets_demand=True`（無損性違反）⇒ M1 咬得到
      OFF5     deliv 60/120、5 通 ⇒ TPC 基準
      HPI/HMIX deliv 95/120、accepted 100 ⇒ Δ_O +37.5pp、Δ_C +20.83pp ⇒ EFFECTIVE
      HOC      deliv 72/120 ⇒ 對 CONFORM b=2 c=0、p=0.5 **不顯著**
               ⇒ 家族仍是 6（M5 會把它丟掉 ⇒ 咬得到），且它自己判 RULED_OUT
    """
    rows = []
    n = 120
    for i in range(n):
        tid = f"t{i}"
        rows.append(_row("OFF", tid, deliv=i < 50))
        rows.append(_row("CONFORM", tid, deliv=(i < 70) or (110 <= i < 113),
                         accepted=i < 110, calls=2))
        rows.append(_row("OFF5", tid, deliv=i < 60, calls=5))
        rows.append(_row("HPI", tid, deliv=i < 95, accepted=i < 100, calls=2))
        rows.append(_row("HOC", tid, deliv=i < 72, accepted=i < 110, calls=2))
        rows.append(_row("HMIX", tid, deliv=i < 95, accepted=i < 100, calls=2))
    summ = {"run_terminal": True,
            "arms": {a: {"processed": n, "infra_void": 0, "wall_s": 100.0}
                     for a in ALL_ARMS}}
    return rows, summ, _calls_for(rows)


def _fixture_void():
    """HPI 有 10 題 infra_void（rows 少 10 列，但那 10 題的呼叫已經燒掉 token）。

    這是 R7 那個不對稱的最小重現：complete-case 分母（M2）與
    「TPC 含不含 void 呼叫」（M3）兩件事都只有在這個形狀上才分得開。
    """
    rows, summ, _ = _fixture()
    void_ids = {f"t{i}" for i in range(110, 120)}
    kept = [r for r in rows if not (r["arm"] == "HPI" and r["task_id"] in void_ids)]
    calls = _calls_for(kept)
    for tid in sorted(void_ids):                  # void 格燒掉的呼叫仍在 calls.jsonl
        calls.append({"ok": True, "usage": {"total_tokens": 1000},
                      "meta": {"arm": "HPI", "task_id": tid, "turn": 1},
                      "response": ""})
    summ = json.loads(json.dumps(summ))
    summ["arms"]["HPI"] = {"processed": 120, "infra_void": 10, "wall_s": 100.0}
    return kept, summ, calls


def _fixture_windows():
    """OFF 交付率 90% ⇒ P-H0 必須 MISS（後端漂移探針的窗是 [40.8, 60.8]）。"""
    rows, summ, _ = _fixture()
    for r in rows:
        if r["arm"] == "OFF":
            r["meets_demand"] = int(r["task_id"][1:]) < 108
    return rows, summ, _calls_for(rows)


API_A_FIXTURE = "http://100.119.113.56:1234/v1/chat/completions"
API_B_FIXTURE = "http://100.86.226.21:1234/v1/chat/completions"
API_C_FIXTURE = "http://100.86.226.22:1234/v1/chat/completions"
API_HUB_FIXTURE = "http://100.119.113.56:8765/v1/chat/completions"


def _fixture_blocks(*, overlap: bool = False, hub: bool = False,
                    same_endpoint: bool = False,
                    imbalance: bool = False,
                    three_endpoints: bool = False) -> list[dict]:
    """D9 的**六塊**夾具：把主夾具的 120 題切成 6 × 20（offset 0/20/…/100）。

    旗標各自造出一種形狀，其中三種**必須被抓到**、一種是 round460h 之後的**合法**拓撲：
      `overlap`         a2 往前挪 5 題 ⇒ 與 a1 有交集，而且聯集掉到 115（違規）；
      `hub`             b1 走 8765（違規）；
      `imbalance`       b3 改打 api_a ⇒ 端點還是 2 顆，但變成 4／2 超賣（違規）；
      `three_endpoints` 2／2／2 攤在三顆端點上 ⇒ 端點數不在 {1,2}（違規）；
      `same_endpoint`   六塊全部打 api_a ⇒ **`one_backend_6`，round460h 起合法**
                        （所以它現在是一條「不准變紅」的正向檢查，不是牙齒）。
    """
    rows, _, _ = _fixture()
    offsets = [0, 20, 40, 60, 80, 100]
    apis = [API_A_FIXTURE] * 3 + [API_B_FIXTURE] * 3
    if same_endpoint:
        apis = [API_A_FIXTURE] * 6
    if imbalance:
        apis = [API_A_FIXTURE] * 3 + [API_B_FIXTURE] * 2 + [API_A_FIXTURE]
    if three_endpoints:
        apis = [API_A_FIXTURE] * 2 + [API_B_FIXTURE] * 2 + [API_C_FIXTURE] * 2
    if hub:
        apis[3] = API_HUB_FIXTURE
    if overlap:
        offsets[1] = 15

    def idx(r):
        return int(r["task_id"][1:])

    out = []
    for name, off, api in zip(AUTHORIZED_BLOCKS, offsets, apis):
        rs = [r for r in rows if off <= idx(r) < off + 20]
        n = len({r["task_id"] for r in rs})
        calls = _calls_for(rs)
        for c in calls:
            c["api"] = api
        summ = {"run_terminal": True, "seed": "g-r440-lcb2", "n": n, "offset": off,
                "arms": {a: {"processed": n, "infra_void": 0, "wall_s": 50.0,
                             "complete": True, "terminal": True} for a in ALL_ARMS}}
        out.append({"name": name, "path": f"runs/{name}", "rows": rs,
                    "summary": summ, "calls": calls, "endpoints": endpoints_of(calls),
                    "offset": off, "n": n, "seed": "g-r440-lcb2",
                    "arms": sorted(ALL_ARMS),
                    "task_ids": {r["task_id"] for r in rs}})
    out.sort(key=lambda b: (b["offset"], b["name"]))
    return out


def _fixture_stage2():
    """階段二觸發鍵的牙齒：**H-PI 落在 INCONCLUSIVE，H-MIX 仍是 EFFECTIVE**。

    DECISION §十一 的觸發條件逐字是「階段一的 **H-MIX** 落在 INCONCLUSIVE」。
    這個形狀讓「H-MIX 專屬」與「任一臂」兩種讀法給出相反答案 ⇒ M9 咬得到。
    HPI 的 deliv 排成 b=15／c=5（Δ_C=+8.33pp、未調整 CI 上界 13.78pp）：
    既不顯著、上界又高於 +10pp ⇒ 四個狀態裡只剩 INCONCLUSIVE。
    """
    rows, summ, _ = _fixture()
    rs = []
    for r in rows:
        r = dict(r)
        if r["arm"] == "HPI":
            i = int(r["task_id"][1:])
            r["meets_demand"] = (5 <= i < 70) or (70 <= i < 85)
        rs.append(r)
    return rs, summ, _calls_for(rs)


def _pooled(blocks: list[dict]) -> dict:
    rows = [r for b in blocks for r in b["rows"]]
    calls = [c for b in blocks for c in b["calls"]]
    summ = merge_summaries([b["summary"] for b in blocks])
    return analyze(rows, summ, calls, blocks=blocks)


def selftest() -> int:
    fails: list[str] = []

    def ck(label, cond, extra=""):
        if not cond:
            fails.append(f"{label}{(' — ' + extra) if extra else ''}")

    rows, summ, calls = _fixture()
    out = analyze(rows, summ, calls)
    ck("A_no_broken", out["broken_reasons"] == [], str(out["broken_reasons"]))
    ck("B_family_size_6", out["holm"]["family_size"] == 6, str(out["holm"]["family_size"]))
    ck("C_complete_case_denominator",
       all(d["n_common"] == 120 for d in out["paired"].values()))
    ck("D_verdict_effective", out["decision"]["HMIX"]["verdict"] == "EFFECTIVE",
       str(out["decision"]["HMIX"]["verdict"]))
    ck("D2_verdict_ruled_out", out["decision"]["HOC"]["verdict"] == "RULED_OUT",
       str(out["decision"]["HOC"]["verdict"]))
    ck("E_tokens_both_versions",
       out["tokens"]["HPI"]["tpc_incl_void"] is not None
       and out["tokens"]["HPI"]["tpc_excl_void"] is not None)
    ck("F_disclaimers_present",
       CI_DISCLAIMER in out["ci_note"] and "winner" in out["winners_curse_disclaimer"])
    ck("G_hoc_hpi_not_in_family",
       out["paired"]["HOC_vs_HPI"]["in_holm_family"] is False)
    # M1 的牙齒：deliv 必須是 accepted ∧ meets_demand，不是 meets_demand。
    ck("L_deliv_requires_accepted",
       out["per_arm"]["CONFORM"]["deliv_n"] == 70
       and out["per_arm"]["CONFORM"]["lossless_violation_n"] == 3,
       f"deliv_n={out['per_arm']['CONFORM']['deliv_n']}")
    # M5 的牙齒：家族裡刻意有一個不顯著的檢定，它也必須留在家族裡。
    ck("M_nonsignificant_stays_in_family",
       (out["holm"].get("HOC_vs_CONFORM") or {}).get("significant") is False,
       str(out["holm"].get("HOC_vs_CONFORM")))

    # ── void 形狀：complete-case 分母（M2）與 TPC 含不含 void（M3）─────
    vr, vs, vc = _fixture_void()
    vo = analyze(vr, vs, vc)
    ck("N_complete_case_excludes_void",
       vo["paired"]["HPI_vs_OFF"]["n_common"] == 110,
       str(vo["paired"]["HPI_vs_OFF"]["n_common"]))
    ck("N2_other_pairs_unaffected",
       vo["paired"]["HMIX_vs_OFF"]["n_common"] == 120)
    ck("O_tpc_incl_void_is_larger",
       vo["tokens"]["HPI"]["tokens_total_incl_void"]
       > vo["tokens"]["HPI"]["tokens_total_excl_void"]
       and vo["tokens"]["HPI"]["tpc_incl_void"] > vo["tokens"]["HPI"]["tpc_excl_void"],
       str(vo["tokens"]["HPI"]))
    ck("O2_void_accounting_ok", vo["broken_reasons"] == [], str(vo["broken_reasons"]))

    # ── 窗的牙齒（M7）：P-H0 在 90% 上必須 MISS ────────────────────────
    wr, ws, wc = _fixture_windows()
    wo = analyze(wr, ws, wc)
    ck("P_window_ph0_miss", wo["prereg"]["P-H0"]["hit"] == "MISS",
       str(wo["prereg"]["P-H0"]))

    # ── D9：兩塊合併（M8）────────────────────────────────────────────
    bo = _pooled(_fixture_blocks())
    ck("Q_pooling_is_lossless",
       bo["broken_reasons"] == []
       and all(bo["per_arm"][a]["deliv_n"] == out["per_arm"][a]["deliv_n"]
               for a in ALL_ARMS)
       and all(d["n_common"] == 120 for d in bo["paired"].values()),
       str(bo["broken_reasons"]))
    ck("Q2_block_reports_present",
       sorted(bo["blocks"]) == sorted(AUTHORIZED_BLOCKS)
       and bo["block_order"][0] == AUTHORIZED_BLOCKS[0]
       and all(v["measured"] == 20
               for v in bo["blocks"][AUTHORIZED_BLOCKS[0]]["per_arm"].values()),
       str(sorted(bo.get("blocks") or {})))
    ck("Q3_ph0_reads_the_anchor_blocks",
       bo["prereg"]["P-H0"]["source_field"]
       == "ph0_pool.per_arm.OFF.deliv_pp_denom_measured"
       and bo["ph0_pool_blocks"] == list(PH0_BLOCKS)
       and bo["prereg"]["P-H0"]["value"]
       == bo["ph0_pool"]["per_arm"]["OFF"]["deliv_pp_denom_measured"]
       and bo["ph0_pool"]["per_arm"]["OFF"]["measured"] == 60,
       str(bo["prereg"]["P-H0"]))
    ck("Q4_hub_use_is_caught",
       any(s.startswith("block_used_hub")
           for s in _pooled(_fixture_blocks(hub=True))["broken_reasons"]),
       str(_pooled(_fixture_blocks(hub=True))["broken_reasons"]))
    ck("Q5_block_overlap_is_caught",
       any(s.startswith("block_task_overlap")
           for s in _pooled(_fixture_blocks(overlap=True))["broken_reasons"]))
    # round460h：端點數只准是 1 或 2。三顆（2／2／2）沒有任何既有欄位會變紅。
    ck("Q6_endpoint_count_is_caught",
       any(s.startswith("endpoints_n_not_in_1_2")
           for s in _pooled(_fixture_blocks(three_endpoints=True))["broken_reasons"]),
       str(_pooled(_fixture_blocks(three_endpoints=True))["broken_reasons"]))
    # round460h：六塊同一顆後端是**合法**拓撲（1003 兩次崩潰後 a 組改掛 1004）。
    # 這一條的方向與其他 Q 條相反：它要求**不變紅**，而且 variant 要記對。
    solo = _pooled(_fixture_blocks(same_endpoint=True))
    ck("Q6b_one_backend_6_is_legal_and_recorded",
       solo["broken_reasons"] == []
       and solo["topology"]["variant"] == "one_backend_6"
       and solo["topology"]["endpoints_n"] == 1
       and set(solo["topology"]["endpoint_of_block"].values()) == {API_A_FIXTURE},
       f"{solo['broken_reasons']} variant={solo['topology'].get('variant')}")
    # 兩顆端點時 variant 也要記對，而且仍然是舊的那一種。
    two = _pooled(_fixture_blocks())
    ck("Q6c_two_backends_3_3_is_recorded",
       two["topology"]["variant"] == "two_backends_3_3"
       and two["topology"]["endpoints_n"] == 2,
       str(two["topology"].get("variant")))
    # one_backend_6 的塊數牙齒：一顆端點卻只掛五塊 ⇒ 那一顆的塊數不對也要紅。
    solo5 = _pooled(_fixture_blocks(same_endpoint=True)[:5])
    ck("Q6d_solo_endpoint_block_count_is_caught",
       any(s.startswith(f"endpoint_block_count_not_{BLOCKS_PER_ENDPOINT_SOLO}")
           for s in solo5["broken_reasons"]),
       str(solo5["broken_reasons"]))
    ck("Q7_partial_block_set_is_caught",
       any(s.startswith(f"block_count_not_{BLOCKS_EXPECTED}")
           for s in _pooled(_fixture_blocks()[:1])["broken_reasons"]))
    # round460e 的新牙齒：端點還是兩顆、塊數還是六——但被塞成 4／2（超賣）。
    # 這個世界裡沒有任何既有欄位會變紅，只會「比較慢」。
    ck("Q9_endpoint_imbalance_is_caught",
       any(s.startswith(f"endpoint_block_count_not_{BLOCKS_PER_ENDPOINT}")
           for s in _pooled(_fixture_blocks(imbalance=True))["broken_reasons"]),
       str(_pooled(_fixture_blocks(imbalance=True))["broken_reasons"]))
    ck("Q10_pooled_task_union_is_120",
       _pooled(_fixture_blocks())["topology"]["task_ids_union"] == TASKS_EXPECTED
       and any(s.startswith(f"pooled_task_count_not_{TASKS_EXPECTED}")
               for s in _pooled(_fixture_blocks(overlap=True))["broken_reasons"]))
    # 逐塊帳要逐塊查：兩塊反向的錯誤在合併帳上會互相抵銷。
    bal = _fixture_blocks()
    bal[0]["summary"]["arms"]["OFF"]["processed"] += 1
    bal[1]["summary"]["arms"]["OFF"]["processed"] -= 1
    balo = _pooled(bal)
    ck("Q8_block_accounting_errors_do_not_cancel",
       any(s.startswith("block:") and "row_accounting" in s
           for s in balo["broken_reasons"]),
       str(balo["broken_reasons"]))
    # 階段二的觸發鍵是 H-MIX（DECISION §十一），不是「任一臂」。
    s2r, s2s, s2c = _fixture_stage2()
    s2 = analyze(s2r, s2s, s2c)
    ck("R_stage2_follows_hmix_only",
       s2["decision"]["HPI"]["verdict"] == "INCONCLUSIVE"
       and s2["decision"]["HMIX"]["verdict"] == "EFFECTIVE"
       and s2["stage2_triggered"] is False
       and s2["stage2_triggered_any_arm_NOT_TRIGGER"] is True,
       f"hmix={s2['decision']['HMIX']['verdict']} "
       f"hpi={s2['decision']['HPI']['verdict']} "
       f"trig={s2['stage2_triggered']}")

    # 缺欄位／帳對不上／未 terminal 各要被抓
    bad = [dict(r) for r in rows]
    bad[0].pop("visible_ok")
    ck("H_missing_field_caught",
       any(s.startswith("missing_fields") for s in analyze(bad, summ, calls)["broken_reasons"]))
    summ2 = json.loads(json.dumps(summ))
    summ2["arms"]["OFF"]["processed"] = 121
    ck("I_row_accounting_caught",
       any(s.startswith("row_accounting") for s in analyze(rows, summ2, calls)["broken_reasons"]))
    summ3 = json.loads(json.dumps(summ))
    summ3["run_terminal"] = False
    ck("J_terminal_caught", "run_not_terminal" in analyze(rows, summ3, calls)["broken_reasons"])
    rows4 = [dict(r) for r in rows]
    for r in rows4:
        if r["arm"] == "HPI":
            r["harness_wire_mode"] = "flattened" if r["task_id"] == "t0" else "multiturn"
    ck("K_wire_mode_mixed_caught",
       "wire_mode_mixed_within_arm" in analyze(rows4, summ, calls)["broken_reasons"])

    # r447：三條既有臂的交付數必須逐字重現 61／84／76
    r447 = ROOT / "runs" / "g_r447_conform_lcb2"
    if (r447 / "rows.jsonl").exists():
        rr, ss, cc = load_run(r447)
        o = analyze(rr, ss, cc)
        want = {"OFF": 61, "CONFORM": 84, "OFF5": 76}
        for a, w in want.items():
            got = o["per_arm"].get(a, {}).get("deliv_n")
            ck(f"R447_{a}_deliv_{w}", got == w, f"got={got}")
        ck("R447_no_broken", o["broken_reasons"] == [], str(o["broken_reasons"]))
        # N4 的 token 總量也一起釘（tokens 歸戶沒漂）
        for a, w in (("OFF", 322963), ("CONFORM", 732086), ("OFF5", 1692219)):
            got = o["tokens"].get(a, {}).get("tokens_total_incl_void")
            ck(f"R447_{a}_tokens", got == w, f"got={got}")
        # N3：OFF 臂被載入器擋掉 7 題
        got = o["gates"]["G3_loader_artifact"]["off_loader_refused_n"]
        ck("R447_off_loader_7", got == 7, f"got={got}")
    else:
        print("  (skip) runs/g_r447_conform_lcb2 不在本 checkout ⇒ 61/84/76 那一段沒跑")

    LAST_FAILS[:] = fails
    for f in fails:
        print(f"  FAIL {f}")
    print(f"selftest: {'PASS' if not fails else f'{len(fails)} FAILED'}")
    return 1 if fails else 0


# 突變體 → 「必須因此變紅的那條具名檢查」。記憶鐵律：偵測條要有牙齒，
# 而「有牙齒」的判準是**指名哪一條會紅**，不是 rc≠0。
MUTANTS = {
    "M1_deliv_ignores_accepted": "L_deliv_requires_accepted",
    "M2_union_denominator": "N_complete_case_excludes_void",
    "M3_tpc_ignores_void_calls": "O_tpc_incl_void_is_larger",
    "M4_ignore_missing_fields": "H_missing_field_caught",
    "M5_holm_family_drops_nonsignificant": "B_family_size_6",
    "M6_costly_swallows_effective": "D_verdict_effective",
    "M7_widen_windows": "P_window_ph0_miss",
    "M8_topology_not_enforced": "Q4_hub_use_is_caught",
    "M9_stage2_any_arm": "R_stage2_follows_hmix_only",
    "M10_block_broken_not_propagated": "Q8_block_accounting_errors_do_not_cancel",
    # round460e：每端點三塊那一格如果沒有牙齒，「一台四塊、一台兩塊」會全綠通過。
    "M11_endpoint_balance_not_checked": "Q9_endpoint_imbalance_is_caught",
}


def mutation_check() -> int:
    """逐個突變體重跑 selftest，要求**指名的那條**檢查變紅。"""
    global MUTANT
    saved = MUTANT
    bad: list[str] = []
    try:
        MUTANT = ""
        if selftest() != 0:
            print("mutation_check: 原版 selftest 就不過，先修那個")
            return 1
        for m, label in MUTANTS.items():
            MUTANT = m
            selftest()
            hit = any(f.split(" — ")[0] == label for f in LAST_FAILS)
            print(f"  {m:38} → 期望 {label:34} {'CAUGHT' if hit else 'ESCAPED'}"
                  f"  (實際變紅: {[f.split(' — ')[0] for f in LAST_FAILS]})")
            if not hit:
                bad.append(m)
    finally:
        MUTANT = saved
    print(f"mutation_check: {'PASS' if not bad else 'ESCAPED ' + str(bad)}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs="+",
                    help="一或多個 run 目錄。D9 的正式收官是兩塊一起給："
                         "--run runs/g_r460_harness_lcb2_a runs/g_r460_harness_lcb2_b"
                         "（依 task_id 合併，仲裁取合併後的量；每一塊另外印一份）")
    ap.add_argument("--json", help="把完整報表 dict 寫成 JSON")
    ap.add_argument("--bank", default="lcb2", choices=["lcb2", "lcb3"])
    ap.add_argument("--rescore-turn1", action="store_true",
                    help="D5 歸因：把 H 臂初稿輪的碼重新用 meets_demand(hidden) 評一次"
                         "（零模型呼叫，但會跑沙箱）")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mutation-check", action="store_true",
                    help="逐個突變體重跑 selftest，要求指名的那條檢查變紅")
    args = ap.parse_args()
    if args.mutation_check:
        return mutation_check()
    if args.selftest:
        return selftest()
    if not args.run:
        ap.error("要嘛 --run，要嘛 --selftest")
    runs = [pathlib.Path(r) for r in args.run]
    missing = [str(r) for r in runs if not (r / "rows.jsonl").exists()]
    if missing:
        ap.error(f"這些 run 目錄沒有 rows.jsonl：{missing}")
    rows, summary, calls, blocks = pool_runs(runs)
    turn1 = None
    if args.rescore_turn1:
        from ops.gain.gain_run import load_tasks
        # 每一塊有自己的 offset/n；題目字典取各塊的聯集，不能只用合併 summary
        # （合併之後 offset 是 None，拿它去 load_tasks 會安靜地載錯一批題）。
        tasks: dict[str, dict] = {}
        for b in blocks:
            for t in load_tasks(args.bank, b["seed"], b["n"], offset=b["offset"]):
                tasks[t["task_id"]] = t
        turn1 = rescore_turn1(rows, calls, tasks)
    out = analyze(rows, summary, calls, bank=load_bank_meta(args.bank),
                  turn1=turn1, blocks=blocks)
    print(render(out))
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON → {args.json}")
    return 1 if out["broken_reasons"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
