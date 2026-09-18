#!/usr/bin/env python3
"""R532（worker 換成 qwen3.8-27b，五個題組、三臂 OFF／CONFORM／HMIX）的收官分析尺。

這支在架構裡承重什麼
────────────────────
`DECISION_20260917_R532_STRONGER_MODEL_PREREG.md` 把每一條判準都綁在
「analyzer 輸出的哪一個 key」上：§四-1 的 P-1～P-11 逐條寫了仲裁欄位、
§四-2 寫死了主指標家族（**2**）與四狀態、§十 事前凍結了檢定力表。
判準指名了一個不存在的 key，`.get()` 會安靜地回 `None`，然後被讀成「量到 0」
——記憶鐵律：**判準要指名欄位，不准靠「工具印了什麼字串」**。這支就是把
那份預註冊編譯成程式，好讓收官的每一句話都能被指回一個欄位。

⚠ **本檔與那份 DECISION 的關係，誠實版**：預註冊在 2026-09-17 發射前凍結，
本檔是 2026-09-18、**資料跑完之後**才寫的。之所以還能算數，是因為
**仲裁欄位、門檻、家族大小、四狀態、檢定力表全部逐字寫死在 DECISION 裡**，
本檔只是把它們搬進程式；「看過數字再寫 analyzer」能動的空間只剩實作 bug，
而那由 `--selftest`（手算對照）與 `--mutation-check`（每一種突變都要變紅）擋。
**這一段不准被刪**——它是這份分析可信度的邊界，不是免責聲明。
（同一條紀律的先例：`ops/gain/analyze_r529.py` 的同名段落。）

估計量宣稱（收官不准換詞彙）
──────────────────────────
R532 答的是：**在五個互斥題目集（LCB v2、LCB v3 medium／hard、HumanEval+、
MBPP+，共 836 題）上、同一顆 27B 本地 worker（`qwen/qwen3.8-27b`、Q4_K_M、
非 thinking）、同樣的呼叫預算，把預算花在「跑客戶的驗收測資、把失敗原文貼回去、
讓同一個人改」（HMIX）比花在「換人重抽」（CONFORM）或「隨機路由交回來就收」
（OFF）多交付多少。** 配對單位是 `task_id`；分子是 `rows.meets_demand`
（隱藏測資判定）與 `accepted` 的合取（R667 凍結口徑：東西要真的交出去了才算）。

⚠ **差值就是差值。** 本檔任何地方都不把 Δ 寫成「提升／改善／improvement」，
也不把「不顯著」寫成「效果消失／複製失敗／等價」——§四-6 與 §十 逐字禁止。

三層結構
────────
  §四-2 **主指標**：跨五集**分層**的配對精確 McNemar，家族 **2**
        （`HMIX−CONFORM`、`HMIX−OFF`），Holm，α=0.05。
        ⚠ 家族由預註冊釘死，**本檔不重分家族**。`CONFORM−OFF`（閘門＋重抽的
        增益，Δ_G）**不在**那個家族裡 ⇒ 放在 `secondary_outside_family`，
        p 值**未校正**、逐格帶 `outside_preregistered_family: true`
        （先例：`docs/paper_2026-09-14/manuscript.md` 對同一個對比的處置）。
  §四-2 **次指標**：逐題組的配對 McNemar 與 Clopper-Pearson 條件區間，
        **只當描述**，區間不做多重比較調整。
  §四-2 **四狀態**：`INVALID`／`EFFECTIVE`／`RULED_OUT`／`INCONCLUSIVE`
        （逐字照抄，見 `STATES_VERBATIM`）。⚠ `RULED_OUT` 的線是 **+2.0 pp**，
        在發射前訂死，不准看完資料再改。

「安靜量不到」兩型都要擋（判準不是 rc≠0）
  型一 缺欄位：任一列缺 REQUIRED 任一欄 ⇒ BROKEN，**不准**當 False 算過去。
  型二 帳對不上：某臂 rows 行數 + infra_void ≠ processed ⇒ BROKEN。
  另外：block 未 terminal ⇒ 該 block BROKEN（期中資料不是收官資料）；
  某一集少一塊 ⇒ 那一集 INVALID 且從主指標的 N 裡拿掉，但 **Holm 家族仍然是 2**。

檢定力（§十，收官必須一起讀）
────────────────────────────
事前檢定力表（`ops/gain/r532/power_table.json`）說了：**+2 pp 的真效果在五個
題組全部測不出來（0.027–0.237）**，+5 pp 只有 MBPP+（0.961）與 HumanEval+
（0.701）有牙齒。⇒ 「沒顯著」在大部分格子是**事前就註定的**，
`power.prereg` 與用實測 `p_disc` 重算的 `power.observed` 兩張表一起印，
收官不得把不顯著讀成「沒有效果」。

零 API、零 ssh、零沙箱、零模型呼叫。只讀 `runs/<block>/{rows,calls}.jsonl`
與 `summary.json`。確定性：同一份資料跑兩次逐位元相同。

用法：
    python3 ops/gain/r532/analyze_r532.py --json ops/gain/r532/results_r532.json
    python3 ops/gain/r532/analyze_r532.py --selftest
    python3 ops/gain/r532/analyze_r532.py --mutation-check
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ops.gain.replay.paired_ci import diff_ci  # noqa: E402
from vacant.research import (  # noqa: E402
    bc_heterogeneity_chisq, holm_bonferroni, mcnemar_exact, mcnemar_power,
    stratified_mcnemar_exact, wilcoxon_signed_rank_exact,
)

#: 突變開關（只給 `--mutation-check` 用；正式跑一定是 None）。
#: ⚠ 必須在**被測函式內部**讀（模組層讀 ⇒ 子行程以外永遠不生效，
#:   長得跟「偵測條沒牙齒」一模一樣，`paired_ci.py:42` 記過同一個坑）。
def _mutant() -> str | None:
    return os.environ.get("R532_MUTANT") or None


ARMS = ("OFF", "CONFORM", "HMIX")
#: §四-2：**預註冊家族固定 2**。不准因為某一集 void 太多就抽掉它再重算，
#: 也不准把 `CONFORM_vs_OFF` 加進來——那會讓兩個已凍結的 p_adj 全部變大。
PAIRS = (("HMIX", "CONFORM"), ("HMIX", "OFF"))
#: 家族**外**的對比（Δ_G＝閘門＋重抽的增益）。p 未校正，逐格自帶警語。
PAIRS_OUTSIDE = (("CONFORM", "OFF"),)
FAMILY_SIZE = 2
ALPHA = 0.05
#: §四-2 寫死：`RULED_OUT` 的線是 +2.0 pp（**不是** R460 的 +10 pp、
#: 也不是 `paired_ci.PRACTICAL_PP` 的 +5 pp——那三個同名門檻不可互引）。
RULED_OUT_PP = 2.0

#: 五個題目集 → 它的塊（順序＝offset 遞增；佇列的**發射**順序是五集交錯的，
#: 但合併時照 offset 排，與 R445／R460 §六-(0)／R529 的先例相同）。
SETS: dict[str, tuple[str, ...]] = {
    "lcb2": tuple(f"g_r532_lcb2_a{i}" for i in range(1, 7)),
    "lcb3_medium": tuple(f"g_r532_lcb3m_a{i}" for i in range(1, 8)),
    "lcb3_hard": tuple(f"g_r532_lcb3h_a{i}" for i in range(1, 4)),
    "humanevalplus": tuple(f"g_r532_hep_a{i}" for i in range(1, 9)),
    "evalplus": tuple(f"g_r532_mbpp_a{i}" for i in range(1, 20)),
}
#: 每一集的**預期題數**（§二-1）。對不上就是取樣錯了，不是「少跑幾題」。
#: HumanEval+ 156/164（8 題因沙箱信封排除）、MBPP+ 371/378（7 題因資源信封排除）
#: ——與 12B 那輪逐字相同（§八-6）。
SET_N = {"lcb2": 120, "lcb3_medium": 135, "lcb3_hard": 54,
         "humanevalplus": 156, "evalplus": 371}
SET_PREFIX = {"lcb2": "lcb_", "lcb3_medium": "lcb_", "lcb3_hard": "lcb_",
              "humanevalplus": "humanevalplus_", "evalplus": "mbppplus_"}
SET_FAMILY = {"lcb3_medium": "lcb_leetcode_medium", "lcb3_hard": "lcb_leetcode_hard"}
#: §十 的題組代號（power_table.json 的 `set` 欄）。
SET_LABEL = {"lcb2": "S0 LCB v2", "lcb3_medium": "S1 LCB v3 medium",
             "lcb3_hard": "S2 LCB v3 hard", "humanevalplus": "S3 HumanEval+",
             "evalplus": "S4 MBPP+"}

#: 12B 那一輪的對照 run（**同一批 task_id、同一顆 seed**；已逐題核對過交集＝滿集）。
#: ⚠ lcb2 對的是 R460 主 run（seed `g-r440-lcb2`）；R460R 的五次複製是**換過 seed**
#:   的，所以只當 token 的描述性帶，不進逐題並列。
TWELVE_B: dict[str, tuple[str, ...]] = {
    "lcb2": tuple(f"g_r460_harness_lcb2_{s}" for s in
                  ("a1", "a2", "a3", "b1", "b2", "b3")),
    "lcb3_medium": tuple(f"g_r529_lcb3m_a{i}" for i in range(1, 8)),
    "lcb3_hard": tuple(f"g_r529_lcb3h_a{i}" for i in range(1, 4)),
    "humanevalplus": tuple(f"g_r529_hep_a{i}" for i in range(1, 9)),
    "evalplus": tuple(f"g_r529_mbpp_a{i}" for i in range(1, 20)),
}
TWELVE_B_SOURCE = {
    "lcb2": "R460 主 run（DECISION_20260907_R460_HARNESS_PREREG.md）",
    "lcb3_medium": "R529（DECISION_20260911_R529_CROSS_BANK_PREREG.md）",
    "lcb3_hard": "R529",
    "humanevalplus": "R529",
    "evalplus": "R529",
}
#: R460R 的五次複製（**新 seed**，同一個 120 題 lcb2 題庫）——只用來給 token
#: 比值一條 12B 的帶（論文摘要引的 2.23–2.78×／1.65–2.11× 就是這五次）。
R460R_SETS = {f"r{i}": tuple(f"g_r460r{i}_harness_lcb2_{s}" for s in
                             ("a1", "a2", "a3", "b1", "b2", "b3"))
              for i in range(1, 6)}

REQUIRED = ("arm", "task_id", "meets_demand", "accepted", "calls_used")

#: 任一臂的 void 率超過這條線 ⇒ 那一塊不進分析（沿用 R460 §十／R529 §一〇-1）。
VOID_RATE_ABORT = 0.20

#: `<block>.endpoint` 的 IP → 主機名。兩台 LM Studio 版本不同（§八-1）⇒
#: 逐後端要能分堆。R532 沒有 sidecar（直接發 runner，§十一），所以從
#: `calls.jsonl` 的 `api` 欄推——那是**實際打出去的位址**，比 sidecar 更接近事實。
ENDPOINT_HOST = {"100.119.113.56": "1003", "100.86.226.21": "1004"}
LMSTUDIO_VERSION = {"1003": "0.4.24.0", "1004": "0.4.17.0"}

# ── 逐字警語（收官照抄，不准改寫成比較好聽的版本）────────────────────
STATES_VERBATIM = {
    "INVALID": "§五 任一擋門紅（含 V/GT 有 violation、E-11 事後發現 reasoning ≠ 0、"
               "E-13 context 偏斜）⇒「這個 run 不當資料用」",
    "EFFECTIVE": "兩個主指標 Holm 後**都**成立，**且**合併 `tpc` HMIX ≤ CONFORM",
    "RULED_OUT": f"`primary.HMIX_vs_CONFORM.ci95_hi_pp` < +{RULED_OUT_PP} pp ⇒"
                 "「排除了 ≥+2 pp 的實務增益」。**這是結論不是失敗**",
    "INCONCLUSIVE": "其餘 ⇒「**沒量出來**，不是沒有差異」"
                    "——必須同時報 `mde_at_n_pp` 與事前檢定力",
}
STATE_NOTE = (
    "R532 四狀態逐字照抄 DECISION_20260917 §四-2，**與 R460 §六-(4)、R529 §六-3 的"
    "同名狀態不是同一個東西**（本 run 無 OFF5 臂、RULED_OUT 的線是 +2.0 pp），不可互引。")
#: R529 的形狀多一格 `COSTLY_BUT_REAL`（兩個主指標都過、但 tpc 更貴）。
#: R532 §四-2 的表沒有列它 ⇒ 那一格在本檔會落進 `INCONCLUSIVE`。
#: 為了不讓資訊消失，另外印一個**描述性**布林，明講它不是 R532 的狀態。
COSTLY_NOTE = (
    "`costly_but_real_shape`＝R529 §六-3 的第三狀態（兩個主指標 Holm 都過、"
    "但合併 tpc HMIX > CONFORM）。**R532 §四-2 的四狀態表沒有這一格**，"
    "所以它不是本 run 的裁決值，只是描述；真正的裁決在 `state`。")
CI_DISCLAIMER = "區間未做多重比較調整；仲裁以 analyzer 的 primary 區塊為準"
POOLING_IDENTITY_NOTE = (
    "分層統計量與「把五集的不一致對直接加起來做一次 McNemar」**數值相同**；"
    "分層買到的是解釋（H0＝每一集都沒有效果、逐集必須照實列、異質性另外量），"
    "不是更嚴的檢定。不准寫成「我們做了分層校正所以比較穩」。")
HETEROGENEITY_NOTE = (
    "描述性：2×K 的 b/c 卡方沒有精確版本，期望次數小的時候近似本來就不準"
    "（min_expected 一起印，<5 要在報告裡講）。不進 Holm 家族、不改任何一格裁決。")
OUTSIDE_FAMILY_NOTE = (
    "`CONFORM − OFF`（Δ_G，閘門＋重抽買到的東西）**不在** DECISION §四-2 的預註冊"
    "家族裡（家族只有 HMIX−CONFORM 與 HMIX−OFF）⇒ 這裡的 p **未經多重比較校正**，"
    "區間也沒有。引用時必須寫出這一句（先例：manuscript.md 對同一個對比的處置）。"
    "把它塞進 Holm 家族會讓兩個已凍結的 p_adj 變大＝事後改家族，明文禁止。")
POWER_NOTE = (
    "§十 事前檢定力（12B 的 p_disc）：+2 pp 的真效果在五個題組**全部測不出來**"
    "（0.027–0.237）；+5 pp 只有 MBPP+（0.961）與 HumanEval+（0.701）有牙齒。"
    "⇒ 「沒顯著」在大部分格子是**事前就註定的**，**不得**讀成「沒有效果」。"
    "`observed` 那一張用本 run 實測的不一致率重算（§十-3 要求兩張並列）。")
CEILING_NOTE = (
    "§四-1 寫死：S1（lcb3 medium）與 S3（HumanEval+）的 Δ_C **幾乎沒有鑑別力**"
    "——對照的 CONFORM 已在 85–95%，天花板讓大的正差在算術上幾乎不可能發生。"
    "收官**不准**拿 S1／S3 的小數字當「增益不見了的證據」。"
    "S2（lcb3 hard，n=54）事前即宣告無鑑別力（檢定力 0.079 @+5pp）。")
NOT_A_TEST_NOTE = (
    "跨模型（27B vs 12B）的差值**不是檢定**：它跨 run、跨時間、跨後端負載、"
    "跨 context 大小，混淆項多到 p 值沒有意義（§四-3-2）。**不准**把兩輪的 836 題"
    "併成 1,672 題的 n，**不准**把五集的點估計平均成一個數，"
    "**不准**用 R532 的結果去改 R460／R460R／R529 的既有裁決。")
R440P_NOTE = (
    "R440P 前提句：整件事建立在「需求可被編譯成可執行的驗收測資」之上。"
    "沒有可執行驗收的需求，本檔量到的任何差值都不適用。")
CALLS_SOURCE_NOTE = (
    "`calls_wire_total`＝`calls.jsonl` 的列數（含 `wire_probe`、含失敗後的每一次"
    "重試）；`calls_logical_total`＝`rows.calls_used` 的和（臂在預算帳上花掉的"
    "呼叫數）＝`calls_per_task` × `n_measured`。兩個都對、**意思不同**，"
    "引用時要指名是哪一個。")
TOKEN_NOTE = (
    "token＝後端回報的 `usage.total_tokens`（prompt＋completion，含 reasoning）。"
    "`wire_probe` 只出現在 HMIX ⇒ 對 HMIX 的成本**單邊上偏**（占比一起印）。"
    "`tpc`＝每一件**正確交付**的 token（分母是 deliv_n，不是 n）。"
    "本 run infra_void＝0 ⇒ 含／不含 void 兩版相同。")
INFERENCE_MODE_NOTE = (
    "`inference_mode` 是從 `usage.completion_tokens_details.reasoning_tokens` "
    "**推斷**的，不是後端自己報的設定：>0 的呼叫占比 ≥50% ⇒ thinking、"
    "==0% ⇒ non_thinking、其間 ⇒ mixed；一通成功呼叫都沒有 ⇒ unknown"
    "（**不是** non_thinking——量不到不是通過）。這一格是 E-11 的事後查核："
    "非 non_thinking ⇒ §四-2 的 INVALID。")
PER_BACKEND_NOTE = (
    "**描述性，不進任何仲裁**：本區塊的每一個數字都不改 primary／decision_state／"
    "aggregate 的任何一格。它存在的理由是 §八-1：兩台 LM Studio 版本不同"
    "（1003 `0.4.24.0`／1004 `0.4.17.0`），已驗一致的只有推論模式，不是所有版本差。"
    "⚠ 配對主指標不受影響：每一塊的三臂跑在**同一台**上，b/c 是塊內配對。")
WINNERS_CURSE = (
    "winner's curse：R460 的 +13.33 pp 是**能被判顯著**的點估計 ⇒ 上偏；"
    "它的五次複製掉到 +0.83～+5.83。R532 是**一次** run（§八-9），"
    "每一個點估計都要當單次值讀，不是複製。")
CONTAMINATION_NOTE = (
    "§八-3：污染這次比 12B 那輪嚴重。LCB v3 的日期窗是 ≤2024-08-10、LCB v2 是"
    "2023-08-26→2025-04-05；Qwen3.6／3.8 的訓練資料截止時間**查不到**但顯然遠晚於 "
    "gemma-4；HumanEval+／MBPP+（2021）幾乎確定在所有現代模型的訓練集裡。"
    "⇒ 交付率上升**無法區分**「模型更強」與「這批題進了訓練集」。"
    "本 run 的主張只能是「增益如何隨單發強度變化」，不能是「模型 A 比模型 B 強」。")


# ── 基本量 ────────────────────────────────────────────────────────────
def _deliv(r: dict) -> bool:
    """R667 凍結口徑：交付成功 ＝ 交出去了(accepted) 且 真的對(meets_demand)。

    ⚠ 分子是**隱藏測資**判定（`meets_demand`），不是 `visible_ok`（可見驗收）
      也不是 `accepted`（交出去了）。拒交臂（CONFORM／HMIX）上單看
      `meets_demand` 會**高估**：gain_run 在閘門拒交時仍會對最後一份候選評分，
      `accepted=False ∧ meets_demand=True` 可達，而那一格東西根本沒交出去。
    """
    if _mutant() == "M1_deliv_ignores_accepted":
        return bool(r.get("meets_demand"))
    if _mutant() == "M10_deliv_uses_visible_ok":
        return bool(r.get("visible_ok"))
    return bool(r.get("accepted")) and bool(r.get("meets_demand"))


def _pct(a: float, b: float) -> float | None:
    return 100.0 * a / b if b else None


def _read_jsonl(p: pathlib.Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _read_json(p: pathlib.Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return None


def paired(a_rows: list[dict], b_rows: list[dict], *, outside: bool = False) -> dict:
    """A 相對 B 的配對計數。`b`＝只有 A 交付對、`c`＝只有 B 交付對。

    分母 `n_common` ＝ **complete case**：兩臂都寫了 rows 的題。
    `gain_run` 只在非 void 的格子寫 rows（void 走 `continue`），所以交集
    就是「兩臂都量到」。本 run void＝0 ⇒ complete case ＝ 全集。
    """
    A = {r["task_id"]: _deliv(r) for r in a_rows}
    B = {r["task_id"]: _deliv(r) for r in b_rows}
    common = sorted(set(A) & set(B))
    if _mutant() == "M2_union_denominator":
        common = sorted(set(A) | set(B))
    b = sum(1 for t in common if A.get(t) and not B.get(t))
    c = sum(1 for t in common if B.get(t) and not A.get(t))
    d = (diff_ci(b, c, len(common)) if common
         else {"delta": 0.0, "lo": 0.0, "hi": 0.0})
    out = {
        "b": b, "c": c, "n_discordant": b + c, "n_common": len(common),
        "p_disc": ((b + c) / len(common)) if common else None,
        "delta_pp": 100.0 * d["delta"],
        "ci95_lo_pp": 100.0 * d["lo"], "ci95_hi_pp": 100.0 * d["hi"],
        "p_mcnemar_exact": mcnemar_exact(b, c),
        "ci_note": CI_DISCLAIMER,
        "b_only_task_ids": [t for t in common if A.get(t) and not B.get(t)][:40],
        "c_only_task_ids": [t for t in common if B.get(t) and not A.get(t)][:40],
    }
    if outside:
        out["outside_preregistered_family"] = True
        out["p_is_uncorrected"] = True
        out["note"] = OUTSIDE_FAMILY_NOTE
    return out


def _host_of_call(rec: dict) -> str:
    api = str(rec.get("api") or "")
    for ip, h in ENDPOINT_HOST.items():
        if ip in api:
            return h
    return "unknown"


def reasoning_stats(calls: list[dict]) -> dict:
    """一堆呼叫的 reasoning token 帳。只看**成功**的呼叫（失敗的沒有 usage）。

    這是 E-11 的**事後**查核（§五-0 的探針只證明了發射那一刻的那一通）。
    """
    ok = [c for c in calls if c.get("ok")]
    n = len(ok)
    with_r = 0
    r_sum = c_sum = t_sum = 0
    p_max = 0
    for c in ok:
        u = c.get("usage") or {}
        det = u.get("completion_tokens_details") or {}
        rt = int(det.get("reasoning_tokens") or 0)
        if _mutant() == "M9_reasoning_ignored":
            rt = 0
        if rt > 0:
            with_r += 1
        r_sum += rt
        c_sum += int(u.get("completion_tokens") or 0)
        t_sum += int(u.get("total_tokens") or 0)
        p_max = max(p_max, int(u.get("prompt_tokens") or 0))
    pp = _pct(with_r, n)
    mode = ("unknown" if pp is None else
            "non_thinking" if pp == 0.0 else
            "thinking" if pp >= 50.0 else "mixed")
    return {
        "calls_ok": n,
        "calls_with_reasoning": with_r,
        "reasoning_call_pp": pp,
        "reasoning_tokens_total": r_sum,
        "reasoning_tokens_mean": (r_sum / n) if n else None,
        "completion_tokens_mean": (c_sum / n) if n else None,
        "total_tokens_mean": (t_sum / n) if n else None,
        "prompt_tokens_max": p_max,
        "inference_mode": mode,
        "note": INFERENCE_MODE_NOTE,
    }


def tokens_by_arm(calls: list[dict]) -> dict:
    """逐臂的呼叫數與 token 總量，外加**逐題**的 token（Wilcoxon 要用）。

    ⚠ `calls_wire_total` 是 **wire 層**（`calls.jsonl` 的列數，含 `wire_probe`、
      含失敗後重試的每一次）。它**不等於**臂在預算帳上花掉的呼叫數
      （那是 `rows.calls_used` 的和）。兩個都對、意思不同；R529 之前它們共用
      `calls_total` 一個名字，於是「每題幾通」與「總共幾通」除出來對不上——
      那不是 bug 在數字上，是 bug 在**名字**上。
    """
    out: dict[str, dict] = {}
    for rec in calls:
        meta = rec.get("meta") or {}
        arm = meta.get("arm")
        if arm is None:
            continue                       # preflight：不屬於任何一臂
        d = out.setdefault(arm, {"calls_wire_total": 0, "calls_wire_ok": 0,
                                 "tokens": 0, "probe_calls": 0, "probe_tokens": 0,
                                 "by_task": {}})
        d["calls_wire_total"] += 1
        if not rec.get("ok"):
            continue
        d["calls_wire_ok"] += 1
        tok = int((rec.get("usage") or {}).get("total_tokens") or 0)
        d["tokens"] += tok
        if rec.get("role") == "wire_probe":
            d["probe_calls"] += 1
            d["probe_tokens"] += tok
        tid = meta.get("task_id")
        if tid:
            d["by_task"][tid] = d["by_task"].get(tid, 0) + tok
    return out


# ── 載入與 BROKEN 判定 ────────────────────────────────────────────────
def load_blocks(blocks: tuple[str, ...], root: pathlib.Path,
                *, prefix: str | None = None, family: str | None = None,
                n_expected: int | None = None) -> dict:
    """把一組塊合併起來。**不吞任何錯**：每一種「安靜量不到」都寫進 broken。"""
    rows: list[dict] = []
    calls: list[dict] = []
    info_blocks: list[dict] = []
    broken: list[str] = []
    seen_ids: set[str] = set()
    rows_by_block: dict[str, list[dict]] = {}
    calls_by_block: dict[str, list[dict]] = {}
    for blk in blocks:
        d = root / "runs" / blk
        summary = _read_json(d / "summary.json")
        info = {"block": blk, "present": d.exists(), "terminal": None,
                "void_rate_max": None, "n_rows": 0}
        if not summary:
            info["missing_summary"] = True
            info_blocks.append(info)
            broken.append(f"{blk}:no_summary")
            continue
        info["terminal"] = bool(summary.get("run_terminal"))
        info["run_complete"] = bool(summary.get("run_complete"))
        info["seed"] = summary.get("seed")
        info["offset"] = summary.get("offset")
        info["n"] = summary.get("n")
        info["gauge_scope"] = summary.get("gauge_scope")
        info["reasoning_effort"] = (summary.get("request_policy") or {}).get(
            "reasoning_effort")
        if not info["terminal"]:
            broken.append(f"{blk}:not_terminal")
        arms_s = summary.get("arms") or {}
        worst = 0.0
        void_total = 0
        for arm, v in arms_s.items():
            processed = float(v.get("processed") or 0)
            void_total += int(v.get("infra_void") or 0)
            if processed > 0:
                worst = max(worst, float(v.get("infra_void") or 0) / processed)
        info["void_rate_max"] = round(worst, 4)
        info["infra_void_total"] = void_total
        if worst > VOID_RATE_ABORT:
            broken.append(f"{blk}:void_rate_{worst:.3f}")
        brows = _read_jsonl(d / "rows.jsonl")
        for r in brows:
            miss = [k for k in REQUIRED if k not in r]
            if miss:
                broken.append(f"{blk}:row_missing_fields:{miss}")
                break
        by_arm: dict[str, int] = {}
        for r in brows:
            by_arm[r.get("arm")] = by_arm.get(r.get("arm"), 0) + 1
        for arm, v in arms_s.items():
            if arm not in ARMS:
                continue                       # R460 有 6 臂，只查我們要的三臂
            want = int(v.get("processed") or 0) - int(v.get("infra_void") or 0)
            got = by_arm.get(arm, 0)
            if want != got:
                broken.append(
                    f"{blk}:{arm}:rows_{got}_vs_processed_minus_void_{want}")
        dup = [r["task_id"] for r in brows
               if r.get("arm") == "OFF" and r["task_id"] in seen_ids]
        if dup:
            broken.append(f"{blk}:duplicate_task_ids:{dup[:3]}")
        seen_ids |= {r["task_id"] for r in brows if r.get("arm") == "OFF"}
        info["n_rows"] = len(brows)
        rows += brows
        bcalls = _read_jsonl(d / "calls.jsonl")
        calls += bcalls
        rows_by_block[blk] = brows
        calls_by_block[blk] = bcalls
        info_blocks.append(info)
    present = [b for b in info_blocks if b["present"]]
    if len(present) != len(blocks):
        broken.append(f"block_count_mismatch:{len(present)}/{len(blocks)}")
    ids = sorted({r["task_id"] for r in rows})
    if prefix:
        bad = [t for t in ids if not t.startswith(prefix)]
        if bad:
            broken.append(f"wrong_task_prefix:{bad[:3]}")
    if family:
        bad_fam = sorted({r.get("family") for r in rows
                          if r.get("family") != family})
        if bad_fam:
            broken.append(f"wrong_family:{bad_fam[:3]}")
    if n_expected is not None and len(ids) != n_expected:
        broken.append(f"n_tasks_{len(ids)}_expected_{n_expected}")
    return {"rows": rows, "calls": calls, "blocks": info_blocks,
            "broken_reasons": broken, "n_tasks": len(ids),
            "blocks_present": len(present), "blocks_expected": len(blocks),
            "n_tasks_expected": n_expected,
            "rows_by_block": rows_by_block, "calls_by_block": calls_by_block}


def load_set(name: str, root: pathlib.Path) -> dict:
    return load_blocks(SETS[name], root, prefix=SET_PREFIX[name],
                       family=SET_FAMILY.get(name), n_expected=SET_N[name])


def included_sets(per_set: dict) -> list[str]:
    """哪幾集進主指標的 N。**只有 `valid` 的才進**（§四-2 的家族仍是 2）。

    ⚠ 這一步單獨抽成函式，是為了讓 `--mutation-check` 咬得到它：
      「安靜地少算一集」會讓主指標的 N 變小而 log 上完全看不出來。
    """
    out = [s for s in SETS if per_set[s]["valid"]]
    if _mutant() == "M5_drop_a_set_silently":
        out = [x for x in out if x != "lcb3_hard"]
    return out


# ── 逐題組 ────────────────────────────────────────────────────────────
def _reject_reasons(rows: list[dict]) -> dict:
    """§八-2／P-10：context 與預算相關的拒交要逐臂逐集落盤。

    rows 的 `err` 是唯一一個逐題的失敗理由欄。分三桶：
    `budget_or_context`（預算／context／截斷）、`sandbox_check_failed`、其他。
    ⚠ 桶子是**字串比對**，不是後端回報的錯誤碼——比對不到不等於沒發生。
    """
    out: dict[str, int] = {}
    budget = 0
    for r in rows:
        e = (r.get("err") or "").strip()
        if not e:
            continue
        out[e[:60]] = out.get(e[:60], 0) + 1
        low = e.lower()
        if any(k in low for k in ("budget", "context", "truncat", "max_token",
                                 "length", "too long", "overflow")):
            budget += 1
    return {"by_err": out, "budget_or_context_n": budget,
            "note": "桶子是字串比對，比對不到不等於沒發生（單邊）。"}


def per_set_stats(name: str, loaded: dict) -> dict:
    rows = loaded["rows"]
    by_arm: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("arm") in ARMS:
            by_arm.setdefault(r["arm"], []).append(r)
    tok = tokens_by_arm(loaded["calls"])
    per_arm: dict[str, dict] = {}
    for a in ARMS:
        rs = by_arm.get(a, [])
        n = len(rs)
        dn = sum(1 for r in rs if _deliv(r))
        acc = sum(1 for r in rs if r.get("accepted"))
        md = sum(1 for r in rs if r.get("meets_demand"))
        vis = sum(1 for r in rs if r.get("visible_ok"))
        false_n = sum(1 for r in rs
                      if r.get("accepted") and not r.get("meets_demand"))
        logical = sum(int(r.get("calls_used") or 0) for r in rs)
        if _mutant() == "M6_calls_per_task_from_wire":
            logical = -1
        per_arm[a] = {
            "n_measured": n,
            "deliv_n": dn,
            # P-1 逐字指名這一格（比例，不是 pp）
            "correct_delivery_rate": (dn / n) if n else None,
            "deliv_pp": _pct(dn, n),
            "accepted_n": acc,
            "meets_demand_n": md,
            "visible_ok_n": vis,
            "false_delivery_n": false_n,
            "false_delivery_pp": _pct(false_n, n),
            "calls_logical_total": logical,
            "calls_per_task": (logical / n) if n else None,
            "reject_reasons": _reject_reasons(rs),
        }
    tokens: dict[str, dict] = {}
    for a in ARMS:
        t = tok.get(a, {})
        dn = per_arm[a]["deliv_n"]
        n = per_arm[a]["n_measured"]
        ti = t.get("tokens", 0)
        tokens[a] = {
            "tokens_total": ti,
            "tokens_incl_void": ti,        # 本 run void=0 ⇒ 兩版相同（欄名保留給對帳）
            "calls_wire_total": t.get("calls_wire_total", 0),
            "calls_wire_ok": t.get("calls_wire_ok", 0),
            "calls_logical_total": per_arm[a]["calls_logical_total"],
            "wire_probe_calls": t.get("probe_calls", 0),
            "wire_probe_tokens": t.get("probe_tokens", 0),
            "wire_probe_share_pp": _pct(t.get("probe_tokens", 0), ti),
            "tokens_per_task": (ti / n) if n else None,
            "tpc_incl_void": (ti / dn) if dn else None,
            "calls_source_note": CALLS_SOURCE_NOTE,
        }
    pairs: dict[str, dict] = {}
    for a, b in PAIRS:
        pairs[f"{a}_vs_{b}"] = paired(by_arm.get(a, []), by_arm.get(b, []))
    for a, b in PAIRS_OUTSIDE:
        pairs[f"{a}_vs_{b}"] = paired(by_arm.get(a, []), by_arm.get(b, []),
                                      outside=True)
    return {
        "label": SET_LABEL[name],
        "n_tasks": loaded["n_tasks"], "n_tasks_expected": loaded["n_tasks_expected"],
        "blocks_present": loaded["blocks_present"],
        "blocks_expected": loaded["blocks_expected"],
        "broken_reasons": loaded["broken_reasons"],
        "valid": not loaded["broken_reasons"],
        "per_arm": per_arm, "tokens": tokens, "paired": pairs,
        "token_wilcoxon": token_wilcoxon(tok),
        "blocks": loaded["blocks"],
        "arbiter_note": "逐題組**不下裁決**，只給數字（§四-2「次指標只當描述」）。",
    }


def token_wilcoxon(tok: dict) -> dict:
    """逐題 token 的配對 Wilcoxon signed-rank（§四-2：Wilcoxon 用在 token／題）。

    ⚠ **不是**交付率的主指標。交付率是二元配對 ⇒ McNemar；
      把 Wilcoxon 套到交付率上是換一把尺去量同一件事。
    """
    out: dict[str, dict] = {}
    for a, b in (("HMIX", "CONFORM"), ("HMIX", "OFF"), ("CONFORM", "OFF")):
        A = (tok.get(a) or {}).get("by_task") or {}
        B = (tok.get(b) or {}).get("by_task") or {}
        common = sorted(set(A) & set(B))
        diffs = [float(A[t] - B[t]) for t in common]
        if not diffs:
            out[f"{a}_vs_{b}"] = {"n": 0, "note": "無配對資料"}
            continue
        w = wilcoxon_signed_rank_exact(diffs)
        out[f"{a}_vs_{b}"] = {
            "n": len(diffs),
            "median_diff_tokens": sorted(diffs)[len(diffs) // 2],
            "mean_diff_tokens": sum(diffs) / len(diffs),
            **{k: v for k, v in w.items()},
            "note": "逐題 token 差的配對檢定，**不是**交付率的主指標；"
                    "未進 Holm 家族。",
        }
    return out


# ── 逐後端（§八-1；描述性，不進仲裁）──────────────────────────────────
def per_backend_stats(loaded: dict) -> dict:
    """把一集的塊照**後端主機**分堆（主機從 calls 的 `api` 推）。

    為什麼可以在後端內部做配對：一塊的三臂跑在**同一台**上，而不同塊的題目互斥
    ⇒ 「同一台上的 b/c」是完整的塊內配對，只是把塊分成兩群各自加起來。
    ⚠ 它**不是**另一個檢定：不算 p、不進 Holm、不改四狀態。
    """
    by_host: dict[str, dict] = {}
    for blk, brows in loaded.get("rows_by_block", {}).items():
        bcalls = loaded.get("calls_by_block", {}).get(blk, [])
        hosts = {_host_of_call(c) for c in bcalls} or {"unknown"}
        host = sorted(hosts)[0] if len(hosts) == 1 else "mixed:" + "+".join(sorted(hosts))
        if _mutant() == "M8_per_backend_merges_hosts":
            host = "1004"
        d = by_host.setdefault(host, {"blocks": [], "rows": [], "calls": []})
        d["blocks"].append(blk)
        d["rows"] += brows
        d["calls"] += bcalls
    out: dict[str, dict] = {}
    for host in sorted(by_host):
        d = by_host[host]
        by_arm: dict[str, list[dict]] = {}
        for r in d["rows"]:
            if r.get("arm") in ARMS:
                by_arm.setdefault(r["arm"], []).append(r)
        tok = tokens_by_arm(d["calls"])
        per_arm: dict[str, dict] = {}
        for a in ARMS:
            rs = by_arm.get(a, [])
            n = len(rs)
            dn = sum(1 for r in rs if _deliv(r))
            ti = (tok.get(a) or {}).get("tokens", 0)
            per_arm[a] = {
                "n_measured": n, "deliv_n": dn, "deliv_pp": _pct(dn, n),
                "deliv_fraction": f"{dn}/{n}",
                "tokens_total": ti,
                "tokens_per_task": (ti / n) if n else None,
                "tpc_incl_void": (ti / dn) if dn else None,
            }
        pairs: dict[str, dict] = {}
        for a, b in PAIRS + PAIRS_OUTSIDE:
            pr = paired(by_arm.get(a, []), by_arm.get(b, []))
            pairs[f"{a}_vs_{b}"] = {
                "b": pr["b"], "c": pr["c"],
                "b_minus_c_descriptive": pr["b"] - pr["c"],
                "n_common": pr["n_common"], "delta_pp": pr["delta_pp"],
                "not_a_test": True,
            }
        out[host] = {
            "host": host,
            "lmstudio_version": LMSTUDIO_VERSION.get(host),
            "lmstudio_version_source": "人回報的宣稱（`lms version`），analyzer 查證不到",
            "blocks": sorted(d["blocks"]), "blocks_n": len(d["blocks"]),
            "per_arm": per_arm, "paired": pairs,
            "reasoning": reasoning_stats(d["calls"]),
            "not_a_test": True,
            "note": PER_BACKEND_NOTE,
        }
    return out


# ── 主指標（§四-2）────────────────────────────────────────────────────
def primary(per_set: dict, included: list[str]) -> dict:
    """跨五集分層的配對精確 McNemar，家族 2，Holm，α=0.05。

    合併區間：以合併後的 (b, c, N_common) 做同一個條件化的 Clopper-Pearson
    映射（`diff_ci`）——與分層統計量同一個條件化，所以「區間排除 0」與
    「精確 p<0.05」一致。P-4／`RULED_OUT` 讀的就是這個 `ci95_hi_pp`。
    """
    out: dict[str, dict] = {}
    raw_p: list[float] = []
    keys: list[str] = []
    for a, b in PAIRS:
        key = f"{a}_vs_{b}"
        strata = []
        named = []
        n_common_total = 0
        for s in included:
            pr = per_set[s]["paired"][key]
            strata.append((pr["b"], pr["c"]))
            n_common_total += pr["n_common"]
            named.append({"set": s, "label": SET_LABEL[s],
                          "b": pr["b"], "c": pr["c"],
                          "n_common": pr["n_common"],
                          "delta_pp": pr["delta_pp"],
                          "p_unadjusted": pr["p_mcnemar_exact"]})
        st = stratified_mcnemar_exact(strata)
        het = bc_heterogeneity_chisq(strata)
        d = diff_ci(st["b"], st["c"], n_common_total)
        out[key] = {
            "b": st["b"], "c": st["c"], "n_discordant": st["n_discordant"],
            "n_common": n_common_total,
            "p_disc": (st["n_discordant"] / n_common_total) if n_common_total else None,
            "delta_pp": 100.0 * d["delta"],
            "ci95_lo_pp": 100.0 * d["lo"], "ci95_hi_pp": 100.0 * d["hi"],
            "p": st["p"], "k_strata": st["k_strata"],
            "sets_included": list(included),
            "per_stratum": named,
            "pooling_identity_check": mcnemar_exact(st["b"], st["c"]),
            "pooling_identity_note": POOLING_IDENTITY_NOTE,
            "heterogeneity": dict(het, note=HETEROGENEITY_NOTE),
            "ci_note": CI_DISCLAIMER,
        }
        raw_p.append(st["p"])
        keys.append(key)
    adj = holm_bonferroni(raw_p)
    if _mutant() == "M11_no_holm":
        adj = list(raw_p)
    for k, p in zip(keys, adj):
        out[k]["p_adj"] = p
        out[k]["significant"] = p < ALPHA
    out["family_size"] = FAMILY_SIZE
    out["alpha"] = ALPHA
    out["family_note"] = (
        "家族固定 2（HMIX−CONFORM、HMIX−OFF），由 DECISION §四-2 凍結。"
        "某一集 INVALID 只把它從 N 裡拿掉，**不改家族大小**；"
        "`CONFORM−OFF` 在家族外（見 secondary_outside_family）。")
    if len(included) != len(SETS):
        out["excluded_sets"] = [s for s in SETS if s not in included]
        out["exclusion_note"] = (
            f"主指標的 N 少了 {len(SETS) - len(included)} 集："
            f"{out['excluded_sets']}——這幾集 INVALID（見 per_set.<set>.broken_reasons）。")
    return out


def secondary_outside_family(per_set: dict, included: list[str]) -> dict:
    """家族外的 Δ_G（CONFORM − OFF）：分層合併，p **未校正**。"""
    out: dict[str, dict] = {}
    for a, b in PAIRS_OUTSIDE:
        key = f"{a}_vs_{b}"
        strata = []
        named = []
        n_common_total = 0
        for s in included:
            pr = per_set[s]["paired"][key]
            strata.append((pr["b"], pr["c"]))
            n_common_total += pr["n_common"]
            named.append({"set": s, "label": SET_LABEL[s], "b": pr["b"],
                          "c": pr["c"], "n_common": pr["n_common"],
                          "delta_pp": pr["delta_pp"],
                          "p_unadjusted": pr["p_mcnemar_exact"]})
        st = stratified_mcnemar_exact(strata)
        d = diff_ci(st["b"], st["c"], n_common_total)
        out[key] = {
            "b": st["b"], "c": st["c"], "n_discordant": st["n_discordant"],
            "n_common": n_common_total,
            "delta_pp": 100.0 * d["delta"],
            "ci95_lo_pp": 100.0 * d["lo"], "ci95_hi_pp": 100.0 * d["hi"],
            "p_unadjusted": st["p"],
            "p_adj": None,
            "outside_preregistered_family": True,
            "per_stratum": named,
            "note": OUTSIDE_FAMILY_NOTE,
        }
    return out


# ── 檢定力（§十）──────────────────────────────────────────────────────
#: `mcnemar_power` 是全枚舉（對 K 與 B），n=371 一次約 13 秒 ⇒ 同參數只算一次。
#: ⚠ 這是**記憶化不是近似**：同一組 (n, p_disc, ψ, α) 的回傳值逐位元相同。
_POWER_CACHE: dict[tuple, float] = {}


def _power(n: int, p_disc: float, psi: float) -> float:
    key = (n, p_disc, psi, ALPHA)
    if key not in _POWER_CACHE:
        _POWER_CACHE[key] = mcnemar_power(n, p_disc, psi, alpha=ALPHA)
    return _POWER_CACHE[key]


#: MDE 二分的迭代數。檢定力對 ψ 單調 ⇒ 二分即可；每一次迭代是一個全枚舉呼叫
#: （n=371 約 13 秒），所以迭代數是**成本與解析度的取捨**，寫死在這裡好讓
#: 「這個數字有多細」可被引用：解析度 ＝ 100×p_disc / 2^MDE_BISECT_ITERS pp。
MDE_BISECT_ITERS = 8


def power_tables(per_set: dict, included: list[str], root: pathlib.Path) -> dict:
    """事前（12B 的 p_disc）與實測（本 run 的 p_disc）兩張表並列（§十-3 要求）。"""
    prereg = _read_json(root / "ops" / "gain" / "r532" / "power_table.json")
    observed: list[dict] = []
    for s in included:
        pr = per_set[s]["paired"]["HMIX_vs_CONFORM"]
        n = pr["n_common"]
        p_disc = pr["p_disc"] or 0.0
        row = {"set": SET_LABEL[s], "key": s, "n": n,
               "p_disc_observed": p_disc}
        for pp in (2.0, 5.0):
            delta = pp / 100.0
            if p_disc <= 0:
                row[f"psi_{int(pp)}pp"] = None
                row[f"power_{int(pp)}pp"] = None
                continue
            psi = (delta / p_disc + 1.0) / 2.0
            row[f"psi_{int(pp)}pp"] = psi
            row[f"power_{int(pp)}pp"] = (
                _power(n, p_disc, psi) if psi <= 1.0 else None)
        observed.append(row)
    # MDE：在本 run 實測的不一致率下，要多大的真效果才有 80% 檢定力。
    # ⚠ 檢定力對 ψ 單調遞增 ⇒ 用二分找臨界點（全枚舉 mcnemar_power 是 O(n²)，
    #   線性掃 5,000 格會把這支從秒級拖到小時級；二分 40 次 ⇒ 精度 <0.01pp）。
    for row in observed:
        n, p_disc = row["n"], row["p_disc_observed"]
        mde = None
        if p_disc and n:
            pp_max = 100.0 * p_disc          # ψ=1 時的最大可達效果
            if _power(n, p_disc, 1.0) >= 0.80:
                lo, hi = 0.0, pp_max
                for _ in range(MDE_BISECT_ITERS):
                    mid = (lo + hi) / 2.0
                    psi = min(((mid / 100.0) / p_disc + 1.0) / 2.0, 1.0)
                    if _power(n, p_disc, psi) >= 0.80:
                        hi = mid
                    else:
                        lo = mid
                mde = hi
        row["mde_at_n_pp_power80"] = mde
        row["mde_max_reachable_pp"] = 100.0 * (p_disc or 0.0)
        row["mde_resolution_pp"] = (100.0 * (p_disc or 0.0)) / (2 ** MDE_BISECT_ITERS)
        row["mde_note"] = ("在實測不一致率下要有 80% 檢定力所需的真效果（pp）；"
                           "None＝即使 ψ=1（每一對不一致都倒向 HMIX）也達不到。")
    return {"prereg": prereg, "observed": observed, "note": POWER_NOTE,
            "ceiling_note": CEILING_NOTE}


# ── 四狀態（§四-2）────────────────────────────────────────────────────
def decide(prim: dict, pooled_tokens: dict, gates: dict) -> dict:
    """R532 四狀態，逐字照抄 §四-2 的表。"""
    c_ok = prim["HMIX_vs_CONFORM"].get("significant")
    o_ok = prim["HMIX_vs_OFF"].get("significant")
    cond_i = bool(c_ok and o_ok)
    tpc_h = pooled_tokens.get("HMIX", {}).get("tpc_incl_void")
    tpc_c = pooled_tokens.get("CONFORM", {}).get("tpc_incl_void")
    cond_ii = (tpc_h is not None and tpc_c is not None and tpc_h <= tpc_c)
    ci_hi = prim["HMIX_vs_CONFORM"].get("ci95_hi_pp")
    ruled_out = (ci_hi is not None and ci_hi < RULED_OUT_PP)
    if _mutant() == "M4_ruled_out_line_moved":
        ruled_out = (ci_hi is not None and ci_hi < 5.0)
    gates_red = [k for k, v in gates.items() if v.get("red")]
    if gates_red:
        state = "INVALID"
    elif cond_i and cond_ii:
        state = "EFFECTIVE"
    elif ruled_out:
        state = "RULED_OUT"
    else:
        state = "INCONCLUSIVE"
    return {
        "state": state,
        "states_verbatim": STATES_VERBATIM,
        "gates_red": gates_red,
        "cond_i_both_primary_holm": cond_i,
        "cond_ii_tpc_hmix_le_conform": cond_ii,
        "ruled_out_condition_ci_hi_lt_2pp": ruled_out,
        "ci95_hi_pp_HMIX_vs_CONFORM": ci_hi,
        "ruled_out_line_pp": RULED_OUT_PP,
        "tpc_incl_void": {"HMIX": tpc_h, "CONFORM": tpc_c},
        # R529 的形狀多一格；R532 的表沒有它 ⇒ 只描述，不裁決。
        "costly_but_real_shape": bool(cond_i and not cond_ii),
        "costly_but_real_note": COSTLY_NOTE,
        "note": STATE_NOTE,
        "pooled_tpc_note": (
            "合併 tpc 是本檔**唯一**一處把五集加起來算比值的地方，而且只用來判一個"
            "布林值；不准被引用成「HMIX 的成本是 CONFORM 的 x 倍」——那個比值逐集差很多。"),
    }


# ── 擋門的事後查核（§五／§八-2）────────────────────────────────────────
def gates_post(all_calls: list[dict], per_set: dict, vgt_dir: pathlib.Path | None) -> dict:
    """E-11（推論模式）、E-13a（context／預算拒交）、V/GT 的事後查核。

    ⚠ V/GT 沒給 `--vgt-dir` ⇒ `applied=False`＝**這一格沒量**，不是 CLEAN。
      analyzer 只讀 rows/calls/summary，**結構上看不到隱藏測資有沒有洩漏**。
    """
    rs = reasoning_stats(all_calls)
    e11 = {
        "inference_mode": rs["inference_mode"],
        "reasoning_call_pp": rs["reasoning_call_pp"],
        "reasoning_tokens_total": rs["reasoning_tokens_total"],
        "calls_ok": rs["calls_ok"],
        "red": rs["inference_mode"] != "non_thinking",
        "criterion": "§四-2 INVALID 的觸發條件之一：事後發現 reasoning ≠ 0",
        "note": INFERENCE_MODE_NOTE,
    }
    budget = {a: 0 for a in ARMS}
    for s in SETS:
        for a in ARMS:
            budget[a] += (per_set[s]["per_arm"][a]["reject_reasons"]
                          ["budget_or_context_n"])
    not_ok = sum(1 for c in all_calls if not c.get("ok"))
    length_finish = sum(1 for c in all_calls if c.get("finish_reason") == "length")
    e13 = {
        "budget_or_context_rejects_by_arm": budget,
        "calls_not_ok": not_ok,
        "calls_finish_reason_length": length_finish,
        "prompt_tokens_max": rs["prompt_tokens_max"],
        "context_per_slot": 65536,
        "max_tokens_budget": 32000,
        # §八-2 已把 E-13a–d 降為**事後查核而不是擋門**（context 條件已對齊）
        "red": False,
        "gate_status": "事後查核，不自動判 INVALID（§八-2 發射前已修正 context 對齊）",
        "note": "P-10 讀這一格：12B 那輪每臂 ≤2 件。",
    }
    vgt = {"applied": vgt_dir is not None, "dir": str(vgt_dir) if vgt_dir else None,
           "blocks_expected": sum(len(v) for v in SETS.values()),
           "clean_n": 0, "not_clean": [], "clean": None,
           "red": False,
           "note": "analyzer 只讀 rows/calls/summary，**結構上看不到隱藏測資有沒有"
                   "洩漏** ⇒ 沒給 --vgt-dir 時這一格是「沒量」不是 CLEAN。"
                   "⚠ 這道閘門是**單邊**的：全 CLEAN 只代表那一套 needle 沒命中，"
                   "不代表沒有洩漏。"}
    if vgt_dir is not None:
        for name, blks in SETS.items():
            for blk in blks:
                f = vgt_dir / f"vgt_v2_{blk}.json"
                d = _read_json(f)
                if d is None:
                    vgt["not_clean"].append(f"{blk}:MISSING")
                    continue
                if d.get("verdict") == "CLEAN" and _mutant() != "M7_vgt_not_checked":
                    vgt["clean_n"] += 1
                else:
                    vgt["not_clean"].append(f"{blk}:{d.get('verdict')}")
        if _mutant() == "M7_vgt_not_checked":
            vgt["not_clean"] = []
        vgt["clean"] = not vgt["not_clean"]
        vgt["red"] = not vgt["clean"]
    broken = {s: per_set[s]["broken_reasons"] for s in SETS
              if per_set[s]["broken_reasons"]}
    data = {"broken_sets": broken, "red": bool(broken),
            "note": "任一集 BROKEN（缺欄位／帳對不上／未 terminal／void 超線）"
                    "⇒ 那一集不進主指標；**五集全 BROKEN** 才會讓整個 run INVALID。"}
    if broken and len(broken) < len(SETS):
        data["red"] = False        # 單集 BROKEN 只是把它拿掉，不翻整個 run
    return {"E11_inference_mode": e11, "E13a_context_pressure": e13,
            "vgt": vgt, "data_integrity": data}


# ── 跨模型並列（§四-3：**不是檢定**）──────────────────────────────────
def arm_summary(rows: list[dict], calls: list[dict]) -> dict:
    by_arm: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("arm") in ARMS:
            by_arm.setdefault(r["arm"], []).append(r)
    tok = tokens_by_arm(calls)
    out: dict[str, dict] = {}
    for a in ARMS:
        rsw = by_arm.get(a, [])
        n = len(rsw)
        dn = sum(1 for r in rsw if _deliv(r))
        ti = (tok.get(a) or {}).get("tokens", 0)
        out[a] = {"n_measured": n, "deliv_n": dn, "deliv_pp": _pct(dn, n),
                  "tokens_total": ti,
                  "tokens_per_task": (ti / n) if n else None,
                  "tpc_incl_void": (ti / dn) if dn else None}
    pairs = {}
    for a, b in PAIRS + PAIRS_OUTSIDE:
        pr = paired(by_arm.get(a, []), by_arm.get(b, []))
        pairs[f"{a}_vs_{b}"] = {"b": pr["b"], "c": pr["c"],
                                "delta_pp": pr["delta_pp"],
                                "n_common": pr["n_common"]}
    return {"per_arm": out, "paired": pairs}


def vs_12b(per_set: dict, root: pathlib.Path) -> dict:
    """同題組、同 seed、同一批 task_id 的 27B vs 12B 並列。

    ⚠ **每一列都是描述，不是檢定**（§四-3-2）。差值跨 run、跨時間、跨後端負載、
      跨 context 大小；`not_a_test` 寫在**列**上而不是區塊上，因為被複製貼進
      報告的是列，警語留在區塊層級會掉（R529 §十三-3 的先例）。
    """
    out: dict[str, dict] = {"note": NOT_A_TEST_NOTE, "by_set": {}}
    for s in SETS:
        blocks = TWELVE_B[s]
        loaded = load_blocks(blocks, root)
        if not loaded["rows"]:
            out["by_set"][s] = {"available": False, "blocks": list(blocks),
                                "not_a_test": True}
            continue
        ids_12 = {r["task_id"] for r in loaded["rows"] if r.get("arm") == "OFF"}
        ids_27 = set()
        for blk in SETS[s]:
            for r in _read_jsonl(root / "runs" / blk / "rows.jsonl"):
                if r.get("arm") == "OFF":
                    ids_27.add(r["task_id"])
        a12 = arm_summary(loaded["rows"], loaded["calls"])
        a27 = {"per_arm": {a: {k: per_set[s]["per_arm"][a].get(k)
                               for k in ("n_measured", "deliv_n", "deliv_pp")}
                           | {k: per_set[s]["tokens"][a].get(k)
                              for k in ("tokens_per_task", "tpc_incl_void")}
                           for a in ARMS},
               "paired": {k: {kk: v.get(kk) for kk in
                              ("b", "c", "delta_pp", "n_common")}
                          for k, v in per_set[s]["paired"].items()}}
        row = {
            "available": True,
            "label": SET_LABEL[s],
            "source_12b": TWELVE_B_SOURCE[s],
            "blocks_12b": list(blocks),
            "task_id_overlap": len(ids_12 & ids_27),
            "task_id_n_12b": len(ids_12), "task_id_n_27b": len(ids_27),
            "same_seed": sorted({b.get("seed") for b in loaded["blocks"]
                                 if b.get("seed")}),
            "arms_27b": a27["per_arm"], "arms_12b": a12["per_arm"],
            "deliv_pp_diff_27b_minus_12b": {
                a: (a27["per_arm"][a]["deliv_pp"] - a12["per_arm"][a]["deliv_pp"])
                if (a27["per_arm"][a]["deliv_pp"] is not None
                    and a12["per_arm"][a]["deliv_pp"] is not None) else None
                for a in ARMS},
            "delta_c_pp": {"r532_27b": a27["paired"]["HMIX_vs_CONFORM"]["delta_pp"],
                           "r_12b": a12["paired"]["HMIX_vs_CONFORM"]["delta_pp"]},
            "delta_g_pp": {"r532_27b": a27["paired"]["CONFORM_vs_OFF"]["delta_pp"],
                           "r_12b": a12["paired"]["CONFORM_vs_OFF"]["delta_pp"]},
            "delta_o_pp": {"r532_27b": a27["paired"]["HMIX_vs_OFF"]["delta_pp"],
                           "r_12b": a12["paired"]["HMIX_vs_OFF"]["delta_pp"]},
            "not_a_test": True,
            "contamination_note": CONTAMINATION_NOTE,
        }
        out["by_set"][s] = row
    return out


def token_ratios(per_set: dict, pooled: dict, root: pathlib.Path) -> dict:
    """§四-1 P-9 與論文摘要引的 token 比值：HMIX÷OFF、HMIX÷CONFORM。

    12B 的對照帶是 R460R 的五次複製（**換過 seed**、同一個 120 題 lcb2 題庫）
    ——論文摘要引的「每題 token 2.23–2.78×、每件正確交付 1.65–2.11×」就是那五次。
    這裡**重算**而不是抄數字，抄數字會在第二次被引用時漂掉。
    """
    def _ratio(x, y):
        return (x / y) if (x and y) else None
    by_set = {}
    for s in SETS:
        t = per_set[s]["tokens"]
        by_set[s] = {
            "label": SET_LABEL[s],
            "tokens_per_task": {a: t[a]["tokens_per_task"] for a in ARMS},
            "tpc_incl_void": {a: t[a]["tpc_incl_void"] for a in ARMS},
            "hmix_over_off_per_task": _ratio(t["HMIX"]["tokens_per_task"],
                                             t["OFF"]["tokens_per_task"]),
            "hmix_over_off_tpc": _ratio(t["HMIX"]["tpc_incl_void"],
                                        t["OFF"]["tpc_incl_void"]),
            "hmix_over_conform_per_task": _ratio(t["HMIX"]["tokens_per_task"],
                                                 t["CONFORM"]["tokens_per_task"]),
            "hmix_over_conform_tpc": _ratio(t["HMIX"]["tpc_incl_void"],
                                            t["CONFORM"]["tpc_incl_void"]),
            "conform_over_off_tpc": _ratio(t["CONFORM"]["tpc_incl_void"],
                                           t["OFF"]["tpc_incl_void"]),
        }
    pooled_ratios = {
        "hmix_over_off_per_task": _ratio(pooled["HMIX"]["tokens_per_task"],
                                         pooled["OFF"]["tokens_per_task"]),
        "hmix_over_off_tpc": _ratio(pooled["HMIX"]["tpc_incl_void"],
                                    pooled["OFF"]["tpc_incl_void"]),
        "hmix_over_conform_per_task": _ratio(pooled["HMIX"]["tokens_per_task"],
                                             pooled["CONFORM"]["tokens_per_task"]),
        "hmix_over_conform_tpc": _ratio(pooled["HMIX"]["tpc_incl_void"],
                                        pooled["CONFORM"]["tpc_incl_void"]),
    }
    band = {}
    for rep, blocks in R460R_SETS.items():
        loaded = load_blocks(blocks, root)
        if not loaded["rows"]:
            continue
        a = arm_summary(loaded["rows"], loaded["calls"])["per_arm"]
        band[rep] = {
            "hmix_over_off_per_task": _ratio(a["HMIX"]["tokens_per_task"],
                                             a["OFF"]["tokens_per_task"]),
            "hmix_over_off_tpc": _ratio(a["HMIX"]["tpc_incl_void"],
                                        a["OFF"]["tpc_incl_void"]),
            "deliv_pp": {k: a[k]["deliv_pp"] for k in ARMS},
            "not_a_test": True,
        }
    return {
        "note": TOKEN_NOTE,
        "by_set": by_set, "pooled": pooled_ratios,
        "twelve_b_r460r_band": {
            "reps": band,
            "source": "R460R 五次複製（**換過 seed**，同一個 120 題 lcb2 題庫）"
                      "——manuscript.md 摘要引的 2.23–2.78×（每題 token）與 "
                      "1.65–2.11×（每件正確交付）就是這五次，本檔重算不抄。",
            "hmix_over_off_per_task_range": (
                [min(v["hmix_over_off_per_task"] for v in band.values()),
                 max(v["hmix_over_off_per_task"] for v in band.values())]
                if band else None),
            "hmix_over_off_tpc_range": (
                [min(v["hmix_over_off_tpc"] for v in band.values()),
                 max(v["hmix_over_off_tpc"] for v in band.values())]
                if band else None),
            "not_a_test": True,
            "caveat": "R460R 換過 seed ⇒ 與 R532 的 lcb2 **不是同一批配對**，"
                      "只是同一個題庫的 12B 成本帶。跨模型比值一律不是檢定。",
        },
    }


# ── 事前預測逐條（§四-1 P-1～P-11）────────────────────────────────────
#: 錨＝§四-0 的 **1004-only（非 thinking）** 欄。R532 跑非 thinking，
#: 可比的就是那一半；混合欄另列在 `anchor_mixed`。
ANCHOR_1004 = {
    "lcb2": {"OFF": 58.33, "CONFORM": 70.83, "HMIX": 84.17,
             "delta_c": 13.33, "delta_o": 25.83, "n": 120,
             "note": "S0 的 1004 欄＝R460 主 run（該輪 lcb2 全跑在 1004）"},
    "lcb3_medium": {"OFF": 76.7, "CONFORM": 85.0, "HMIX": 86.7,
                    "delta_c": 1.7, "delta_o": 10.0, "n": 60},
    "lcb3_hard": {"OFF": 65.0, "CONFORM": 75.0, "HMIX": 75.0,
                  "delta_c": 0.0, "delta_o": 10.0, "n": 20},
    "humanevalplus": {"OFF": 75.0, "CONFORM": 94.6, "HMIX": 96.4,
                      "delta_c": 1.8, "delta_o": 21.4, "n": 56},
    "evalplus": {"OFF": 73.6, "CONFORM": 79.3, "HMIX": 80.0,
                 "delta_c": 0.7, "delta_o": 6.4, "n": 140},
}
ANCHOR_NOTE = (
    "§四-0 的錨用 **1004-only（非 thinking）** 那一半：R529 稽核 §十一 已證實 "
    "S1–S4 的絕對值是 1003（thinking）與 1004（非 thinking）的混合物，"
    "而 R532 跑非 thinking。⚠ 1004-only 的 n 很小（20–140），"
    "那幾個數字是**描述性 b−c**，不是檢定。")


def predictions(per_set: dict, prim: dict, pooled: dict, ratios: dict,
                gates: dict, included: list[str]) -> dict:
    """§四-1 的 P-1～P-11 逐條裁決。**照實記 HIT／MISS，不挑好看的講。**"""
    out: dict[str, dict] = {}

    off = {s: per_set[s]["per_arm"]["OFF"]["deliv_pp"] for s in SETS}
    up = {s: off[s] - ANCHOR_1004[s]["OFF"] for s in SETS}
    out["P-1"] = {
        "text": "五個題組的 OFF 交付率全部上升，且至少 4/5 上升 ≥ +5 pp",
        "field": "per_set.<s>.per_arm.OFF.correct_delivery_rate",
        "values_pp": off, "diff_vs_anchor_pp": up,
        "all_up": all(v > 0 for v in up.values()),
        "n_ge_5pp": sum(1 for v in up.values() if v >= 5.0),
        "hit": all(v > 0 for v in up.values())
               and sum(1 for v in up.values() if v >= 5.0) >= 4,
        "anchor_note": ANCHOR_NOTE,
    }

    do = {s: per_set[s]["paired"]["HMIX_vs_OFF"]["delta_pp"] for s in SETS}
    shrunk_o = {s: do[s] < ANCHOR_1004[s]["delta_o"] for s in SETS}
    out["P-2"] = {
        "text": "五個題組的 Δ_O（HMIX−OFF）全部縮小（小於 §四-0 的 1004-only 值），"
                "但仍全部 > 0",
        "field": "per_set.<s>.paired.HMIX_vs_OFF.delta_pp",
        "values_pp": do, "anchor_pp": {s: ANCHOR_1004[s]["delta_o"] for s in SETS},
        "smaller_than_anchor": shrunk_o, "all_positive": all(v > 0 for v in do.values()),
        "hit": all(shrunk_o.values()) and all(v > 0 for v in do.values()),
    }

    dc = {s: per_set[s]["paired"]["HMIX_vs_CONFORM"]["delta_pp"] for s in SETS}
    out["P-3"] = {
        "text": "五個題組的 Δ_C 全部 ≤ +3.0 pp（點估計）",
        "field": "per_set.<s>.paired.HMIX_vs_CONFORM.delta_pp",
        "values_pp": dc, "hit": all(v <= 3.0 for v in dc.values()),
    }

    ci_hi = prim["HMIX_vs_CONFORM"]["ci95_hi_pp"]
    out["P-4"] = {
        "text": "合併 Δ_C 的 95% 區間上界 < +5.0 pp",
        "field": "primary.HMIX_vs_CONFORM.ci95_hi_pp",
        "value_pp": ci_hi, "hit": ci_hi < 5.0,
    }
    out["P-5"] = {
        "text": "合併 Δ_C 的 Holm p_adj 不顯著（≥ 0.05）",
        "field": "primary.HMIX_vs_CONFORM.p_adj",
        "value": prim["HMIX_vs_CONFORM"]["p_adj"],
        "hit": prim["HMIX_vs_CONFORM"]["p_adj"] >= ALPHA,
        "power_caveat": POWER_NOTE,
    }
    out["P-6"] = {
        "text": "合併 Δ_O 的 Holm p_adj 仍顯著（< 0.05）",
        "field": "primary.HMIX_vs_OFF.p_adj",
        "value": prim["HMIX_vs_OFF"]["p_adj"],
        "hit": bool(prim["HMIX_vs_OFF"]["significant"]),
    }

    dg = {s: per_set[s]["paired"]["CONFORM_vs_OFF"]["delta_pp"] for s in SETS}
    anchor_g = {s: ANCHOR_1004[s]["CONFORM"] - ANCHOR_1004[s]["OFF"] for s in SETS}
    smaller_g = {s: dg[s] < anchor_g[s] for s in SETS}
    out["P-7"] = {
        "text": "CONFORM−OFF 五集全部 > 0，且至少 3/5 小於對照值",
        "field": "per_set.<s>.paired.CONFORM_vs_OFF.delta_pp",
        "values_pp": dg, "anchor_pp": anchor_g, "smaller_than_anchor": smaller_g,
        "n_smaller": sum(1 for v in smaller_g.values() if v),
        "hit": all(v > 0 for v in dg.values())
               and sum(1 for v in smaller_g.values() if v) >= 3,
        "outside_family_note": OUTSIDE_FAMILY_NOTE,
    }

    fd = {s: {a: per_set[s]["per_arm"][a]["false_delivery_pp"] for a in ARMS}
          for s in SETS}
    out["P-8"] = {
        "text": "假交付（accepted 但隱藏測資不過）五集全部下降",
        "field": "per_set.<s>.per_arm.<arm>.false_delivery_pp",
        "values_pp": fd,
        "hit": None,
        "note": "需要 12B 的逐集假交付率當對照 ⇒ 見 vs_12b；此處只落盤本 run 的值，"
                "不自行宣稱 HIT／MISS（§四-1 沒有寫死對照的數字）。",
    }

    tpc = {s: {a: per_set[s]["tokens"][a]["tpc_incl_void"] for a in ARMS}
           for s in SETS}
    out["P-9"] = {
        "text": "token_per_correct 五集全部下降（分母變大）",
        "field": "per_set.<s>.tokens.<arm>.tpc_incl_void",
        "values": tpc, "hit": None,
        "note": "對照＝12B 那輪的逐集 tpc（見 vs_12b.by_set.<s>.arms_12b）；"
                "跨 run 比值**不是檢定**。",
    }

    e13 = gates["E13a_context_pressure"]
    out["P-10"] = {
        "text": "context／預算相關的拒交上升：至少一個題組的 HMIX budget_tokens "
                "＋ context 錯誤合計 ≥ 5 件（12B 那輪每臂 ≤2 件）",
        "field": "per_set.<s>.per_arm.<arm>.reject_reasons",
        "by_arm_total": e13["budget_or_context_rejects_by_arm"],
        "calls_not_ok": e13["calls_not_ok"],
        "calls_finish_reason_length": e13["calls_finish_reason_length"],
        "hit": any(per_set[s]["per_arm"]["HMIX"]["reject_reasons"]
                   ["budget_or_context_n"] >= 5 for s in SETS),
    }

    voids = {s: sum(b.get("infra_void_total") or 0 for b in per_set[s]["blocks"])
             for s in SETS}
    worst = max((b.get("void_rate_max") or 0.0)
                for s in SETS for b in per_set[s]["blocks"])
    out["P-11"] = {
        "text": "逐塊 infra_void ≤ 5%",
        "field": "arms.<arm>.infra_void",
        "infra_void_total_by_set": voids, "worst_block_void_rate": worst,
        "hit": worst <= 0.05,
    }

    hits = [k for k, v in out.items() if v.get("hit") is True]
    misses = [k for k, v in out.items() if v.get("hit") is False]
    undecided = [k for k, v in out.items() if v.get("hit") is None]
    out["_tally"] = {"hit": hits, "miss": misses, "not_adjudicated": undecided,
                     "note": "照實記。MISS 不是壞消息，預註冊的用處就在這裡。"}
    return out


def aggregate(per_set: dict, prim: dict, included: list[str]) -> dict:
    dc = [per_set[s]["paired"]["HMIX_vs_CONFORM"]["delta_pp"] for s in included]
    do = [per_set[s]["paired"]["HMIX_vs_OFF"]["delta_pp"] for s in included]
    dg = [per_set[s]["paired"]["CONFORM_vs_OFF"]["delta_pp"] for s in included]
    c_sig = prim["HMIX_vs_CONFORM"].get("significant")
    o_sig = prim["HMIX_vs_OFF"].get("significant")
    if c_sig and o_sig:
        stmt = ("§四-6 第一句：主指標 Holm 後成立 ⇒ 可以寫「在 836 題五個題組上，"
                "迴圈對同預算重抽的差值為 +X pp」，同一段必須寫出逐集五個數字、"
                "§四-1 的 S1／S3 天花板限制、§八 的全部誠實邊界，"
                "以及「這是一次 run，不是複製」。")
    else:
        stmt = ("§四-6 第二句：主指標未成立 ⇒ **逐集照實列**。"
                "不准寫「多數支持」「方向一致」「趨勢明顯」，"
                "也不准寫「複製失敗」「效果消失」「等價」「打平」「迴圈沒用」。")
    return {
        "n_sets_counted": len(included),
        "delta_c_pp_by_set": {s: per_set[s]["paired"]["HMIX_vs_CONFORM"]["delta_pp"]
                              for s in included},
        "delta_o_pp_by_set": {s: per_set[s]["paired"]["HMIX_vs_OFF"]["delta_pp"]
                              for s in included},
        "delta_g_pp_by_set": {s: per_set[s]["paired"]["CONFORM_vs_OFF"]["delta_pp"]
                              for s in included},
        "direction_positive_c": sum(1 for x in dc if x > 0),
        "direction_positive_o": sum(1 for x in do if x > 0),
        "direction_positive_g": sum(1 for x in dg if x > 0),
        "statement": stmt,
        "四之四_不縮小判準": {
            "text": "§四-4：S0／S2／S4 三集裡至少兩集的 Δ_C ≥ +3.0 pp，"
                    "且合併 Δ_C 的 95% 區間下界 > 0",
            "sets_ge_3pp": [s for s in ("lcb2", "lcb3_hard", "evalplus")
                            if per_set[s]["paired"]["HMIX_vs_CONFORM"]["delta_pp"] >= 3.0],
            "pooled_ci_lo_pp": prim["HMIX_vs_CONFORM"]["ci95_lo_pp"],
            "met": (len([s for s in ("lcb2", "lcb3_hard", "evalplus")
                         if per_set[s]["paired"]["HMIX_vs_CONFORM"]["delta_pp"] >= 3.0]) >= 2
                    and prim["HMIX_vs_CONFORM"]["ci95_lo_pp"] > 0),
        },
        "四之五_縮小到零判準": {
            "text": "§四-5：五集的 Δ_C 全部 ≤ +1.0 pp，或合併 Δ_C 的 95% 區間上界 "
                    "< +2.0 pp（＝RULED_OUT）",
            "all_le_1pp": all(x <= 1.0 for x in dc),
            "pooled_ci_hi_pp": prim["HMIX_vs_CONFORM"]["ci95_hi_pp"],
            "met": (all(x <= 1.0 for x in dc)
                    or prim["HMIX_vs_CONFORM"]["ci95_hi_pp"] < RULED_OUT_PP),
        },
        "no_meta_analysis_note": (
            "沒有隨機效應模型、沒有 meta-analysis、沒有合併效果量；"
            "五集的點估計**不准平均**（難度組成、來源、n、量具強度都不同）。"),
        "winners_curse": WINNERS_CURSE,
        "ceiling_note": CEILING_NOTE,
        "r440p": R440P_NOTE,
    }


# ── 主流程 ────────────────────────────────────────────────────────────
def analyze(root: pathlib.Path = ROOT,
            vgt_dir: pathlib.Path | None = None,
            *, with_12b: bool = True) -> dict:
    per_set: dict[str, dict] = {}
    loaded_sets: dict[str, dict] = {}
    all_calls: list[dict] = []
    for name in SETS:
        loaded_sets[name] = load_set(name, root)
        per_set[name] = per_set_stats(name, loaded_sets[name])
        all_calls += loaded_sets[name]["calls"]
    included = included_sets(per_set)
    gates = gates_post(all_calls, per_set, vgt_dir)
    out: dict = {
        "run": "R532",
        "decision": "DECISION_20260917_R532_STRONGER_MODEL_PREREG.md",
        "analyzer": "ops/gain/r532/analyze_r532.py",
        "worker_model": "qwen/qwen3.8-27b (Q4_K_M, non-thinking)",
        "arms": list(ARMS),
        "sets_expected": list(SETS),
        "sets_included_in_primary": included,
        "delivery_definition": "deliv = accepted ∧ meets_demand（隱藏測資判定，"
                               "**不是** visible_ok、**不是**只看 accepted）",
        "gates": gates,
        "per_set": per_set,
    }
    if not included:
        out["primary"] = {"family_size": FAMILY_SIZE,
                          "error": "沒有任何一集是 valid 的——量不到不是通過。"}
        out["decision_state"] = {"state": "INVALID",
                                 "note": "五集全部 INVALID（見 per_set.*.broken_reasons）。"}
        return out
    pooled_tokens: dict[str, dict] = {}
    for a in ARMS:
        tok = sum(per_set[s]["tokens"][a]["tokens_total"] for s in included)
        dn = sum(per_set[s]["per_arm"][a]["deliv_n"] for s in included)
        n = sum(per_set[s]["per_arm"][a]["n_measured"] for s in included)
        pooled_tokens[a] = {
            "tokens_total": tok, "deliv_n": dn, "n_measured": n,
            "deliv_pp": _pct(dn, n),
            "tpc_incl_void": (tok / dn) if dn else None,
            "tokens_per_task": (tok / n) if n else None,
        }
    out["tokens_pooled"] = pooled_tokens
    out["primary"] = primary(per_set, included)
    out["secondary_outside_family"] = secondary_outside_family(per_set, included)
    out["power"] = power_tables(per_set, included, root)
    out["token_ratios"] = token_ratios(per_set, pooled_tokens, root)
    out["decision_state"] = decide(out["primary"], pooled_tokens, gates)
    out["predictions"] = predictions(per_set, out["primary"], pooled_tokens,
                                     out["token_ratios"], gates, included)
    out["aggregate"] = aggregate(per_set, out["primary"], included)
    if with_12b:
        out["vs_12b"] = vs_12b(per_set, root)
    out["per_backend"] = {name: per_backend_stats(loaded_sets[name])
                          for name in SETS}
    out["per_backend_note"] = PER_BACKEND_NOTE
    out["honesty_bounds"] = {
        "八之一_兩台版本不同": PER_BACKEND_NOTE,
        "八之三_污染": CONTAMINATION_NOTE,
        "八之四_更強只在這五集這顆量化這個harness": (
            "「更強」只在本專題的五個題組上、這一顆量化（Q4_K_M）、這一個 harness、"
            "這一組預算、非 thinking 條件下成立。公開評測（Qwen 官方自報 "
            "LiveCodeBench v6 = 90.3）是 thinking＋agentic harness＋avg@3＋256K "
            "context 量的，不是同一件事，不得引用來預測本 run 的 OFF 交付率。"),
        "八之五_非thinking是選擇": (
            "非 thinking 是一個選擇不是這顆模型的自然狀態（對照組實測 "
            "reasoning_tokens=32 ⇒ 它預設會 thinking）。⇒ **我們量的不是這顆模型"
            "最強的樣子**。"),
        "八之六_分母": "HumanEval+ 156/164（8 題沙箱信封排除）、"
                       "MBPP+ 371/378（7 題資源信封排除），與 12B 那輪逐字相同。",
        "八之七_量具單邊": "量具是單邊保證；`lcb3_hard` 只有 3 題被參考解直接驗過"
                           "（gauge_in_filter_n=3）。擋得住已知壞解 ≠ 涵蓋真需求。",
        "八之八_VGT只掃H臂": "V/GT 工具設計上只掃 H 臂，其餘三臂要靠獨立掃描補；"
                             "被跳過的瑣碎 needle **不算檢查過**。",
        "八之九_一次run不是複製": WINNERS_CURSE,
        "四之三_不得併n": NOT_A_TEST_NOTE,
        "r440p": R440P_NOTE,
        "wording": "禁語（§四-6）：不准寫「複製失敗」「效果消失」「等價」「打平」"
                   "「迴圈沒用」「多數支持」「趨勢明顯」；差值就寫差值，"
                   "不要寫成 improvement／提升。",
    }
    return out


# ── 列印 ──────────────────────────────────────────────────────────────
def _num(v, nd: int = 0) -> str:
    return "—" if v is None else f"{v:,.{nd}f}"


def render(a: dict) -> str:
    L = [f"═══ R532 收官分析（{a['decision']}）═══",
         f"worker：{a['worker_model']}　臂：{'/'.join(a['arms'])}　"
         f"題目集：{len(a['sets_expected'])}",
         f"分子：{a['delivery_definition']}",
         f"進入主指標的集：{a['sets_included_in_primary']}", ""]

    L.append("── 逐題組三臂交付率（分母＝該集題數）")
    L.append(f"{'題目集':<16}{'n':>5}{'OFF':>14}{'CONFORM':>14}{'HMIX':>14}"
             f"{'Δ_C':>9}{'Δ_G':>9}{'Δ_O':>9}")
    for s in a["sets_expected"]:
        ps = a["per_set"][s]
        if not ps["valid"]:
            L.append(f"  {s}: INVALID {ps['broken_reasons'][:2]}")
            continue
        pa = ps["per_arm"]
        pc = ps["paired"]["HMIX_vs_CONFORM"]
        pg = ps["paired"]["CONFORM_vs_OFF"]
        po = ps["paired"]["HMIX_vs_OFF"]
        L.append(
            f"{ps['label']:<16}{ps['n_tasks']:>5}"
            + "".join(f"{pa[x]['deliv_n']:>4}/{pa[x]['n_measured']:<3}"
                      f"{_num(pa[x]['deliv_pp'], 1):>7}" for x in ARMS)
            + f"{pc['delta_pp']:>+9.2f}{pg['delta_pp']:>+9.2f}"
              f"{po['delta_pp']:>+9.2f}")
    L.append("")

    L.append("── 逐題組配對（精確 McNemar，未校正；區間＝Clopper-Pearson 條件區間）")
    for s in a["sets_expected"]:
        ps = a["per_set"][s]
        if not ps["valid"]:
            continue
        for key, tag in (("HMIX_vs_CONFORM", "Δ_C"), ("CONFORM_vs_OFF", "Δ_G"),
                         ("HMIX_vs_OFF", "Δ_O")):
            pr = ps["paired"][key]
            extra = "（家族外，p 未校正）" if pr.get("outside_preregistered_family") else ""
            L.append(f"  {ps['label']:<16}{tag} {pr['delta_pp']:>+7.2f}pp "
                     f"[{pr['ci95_lo_pp']:+6.2f},{pr['ci95_hi_pp']:+6.2f}] "
                     f"b/c={pr['b']}/{pr['c']} n_disc={pr['n_discordant']} "
                     f"p={pr['p_mcnemar_exact']:.4g}{extra}")
    L.append(f"  ⚠ {CI_DISCLAIMER}")
    L.append("")

    L.append("── 主指標（分層配對精確 McNemar，家族 2，Holm，α=0.05）")
    for a_, b_ in PAIRS:
        k = f"{a_}_vs_{b_}"
        p = a["primary"].get(k)
        if not p:
            continue
        L.append(f"  {k}: Δ={p['delta_pp']:+.2f}pp "
                 f"[{p['ci95_lo_pp']:+.2f},{p['ci95_hi_pp']:+.2f}] "
                 f"b={p['b']} c={p['c']} N_disc={p['n_discordant']} "
                 f"p={p['p']:.4g} p_adj={p['p_adj']:.4g} "
                 f"{'顯著' if p['significant'] else '不顯著'}")
        L.append("    逐集 " + "　".join(
            f"{d['set']}={d['b']}/{d['c']}" for d in p["per_stratum"]))
        het = p["heterogeneity"]
        L.append(f"    異質性（描述）chi2={het['chi2']:.3f} df={het['df']} "
                 f"p={het['p']:.3g} min_expected={het['min_expected']:.2f}")
    sof = a.get("secondary_outside_family") or {}
    for k, p in sof.items():
        L.append(f"  [家族外] {k}: Δ={p['delta_pp']:+.2f}pp "
                 f"[{p['ci95_lo_pp']:+.2f},{p['ci95_hi_pp']:+.2f}] "
                 f"b={p['b']} c={p['c']} p(未校正)={p['p_unadjusted']:.4g}")
    L.append(f"  ⚠ {POOLING_IDENTITY_NOTE}")
    L.append(f"  ⚠ {OUTSIDE_FAMILY_NOTE}")
    L.append("")

    L.append("── 檢定力（事前 vs 實測）")
    L.append(f"{'題目集':<18}{'n':>5}{'p_disc事前':>11}{'力@+2pp':>9}{'力@+5pp':>9}"
             f"{'p_disc實測':>11}{'力@+2pp':>9}{'力@+5pp':>9}{'MDE80(pp)':>11}")
    pre = {r["set"]: r for r in ((a["power"].get("prereg") or {}).get("rows") or [])}
    for row in a["power"]["observed"]:
        pr = pre.get(row["set"], {})
        L.append(
            f"{row['set']:<18}{row['n']:>5}{_num(pr.get('p_disc'), 4):>11}"
            f"{_num(pr.get('power_2pp'), 3):>9}{_num(pr.get('power_5pp'), 3):>9}"
            f"{_num(row['p_disc_observed'], 4):>11}"
            f"{_num(row.get('power_2pp'), 3):>9}{_num(row.get('power_5pp'), 3):>9}"
            f"{_num(row.get('mde_at_n_pp_power80'), 2):>11}")
    L.append(f"  ⚠ {POWER_NOTE}")
    L.append(f"  ⚠ {CEILING_NOTE}")
    L.append("")

    L.append("── token 成本（每題／每件正確交付；含 wire_probe）")
    L.append(f"{'題目集':<18}{'tok/題 OFF':>12}{'CONFORM':>10}{'HMIX':>10}"
             f"{'tpc OFF':>10}{'CONFORM':>10}{'HMIX':>10}{'H/O題':>8}{'H/O件':>8}")
    for s in a["sets_expected"]:
        r = a["token_ratios"]["by_set"][s]
        L.append(f"{r['label']:<18}"
                 + "".join(f"{_num(r['tokens_per_task'][x]):>12}" if x == "OFF"
                           else f"{_num(r['tokens_per_task'][x]):>10}" for x in ARMS)
                 + "".join(f"{_num(r['tpc_incl_void'][x]):>10}" for x in ARMS)
                 + f"{_num(r['hmix_over_off_per_task'], 2):>8}"
                   f"{_num(r['hmix_over_off_tpc'], 2):>8}")
    tp = a["tokens_pooled"]
    pr = a["token_ratios"]["pooled"]
    L.append(f"{'合併':<18}"
             + "".join(f"{_num(tp[x]['tokens_per_task']):>12}" if x == "OFF"
                       else f"{_num(tp[x]['tokens_per_task']):>10}" for x in ARMS)
             + "".join(f"{_num(tp[x]['tpc_incl_void']):>10}" for x in ARMS)
             + f"{_num(pr['hmix_over_off_per_task'], 2):>8}"
               f"{_num(pr['hmix_over_off_tpc'], 2):>8}")
    band = a["token_ratios"]["twelve_b_r460r_band"]
    if band.get("hmix_over_off_per_task_range"):
        lo, hi = band["hmix_over_off_per_task_range"]
        lo2, hi2 = band["hmix_over_off_tpc_range"]
        L.append(f"  12B R460R 五次帶（**換過 seed，不是檢定**）："
                 f"每題 {lo:.2f}–{hi:.2f}×、每件 {lo2:.2f}–{hi2:.2f}×")
    L.append(f"  ⚠ {TOKEN_NOTE}")
    L.append("")

    if "vs_12b" in a:
        L.append("── 27B vs 12B 逐題組並列（**每一列都不是檢定**）")
        L.append(f"{'題目集':<18}{'模型':>6}{'OFF':>9}{'CONFORM':>9}{'HMIX':>9}"
                 f"{'Δ_C':>8}{'Δ_G':>8}{'Δ_O':>8}{'tok/題H':>10}{'tpc H':>10}")
        for s in a["sets_expected"]:
            v = a["vs_12b"]["by_set"][s]
            if not v.get("available"):
                L.append(f"  {s}: 12B 對照不在本機")
                continue
            for tag, arms_k, pk in (("27B", "arms_27b", "r532_27b"),
                                    ("12B", "arms_12b", "r_12b")):
                ar = v[arms_k]
                L.append(
                    f"{(v['label'] if tag == '27B' else ''):<18}{tag:>6}"
                    + "".join(f"{_num(ar[x]['deliv_pp'], 2):>9}" for x in ARMS)
                    + f"{v['delta_c_pp'][pk]:>+8.2f}{v['delta_g_pp'][pk]:>+8.2f}"
                      f"{v['delta_o_pp'][pk]:>+8.2f}"
                    + f"{_num(ar['HMIX']['tokens_per_task']):>10}"
                      f"{_num(ar['HMIX']['tpc_incl_void']):>10}")
        L.append(f"  ⚠ {NOT_A_TEST_NOTE}")
        L.append(f"  ⚠ {CONTAMINATION_NOTE}")
        L.append("")

    g = a["gates"]
    L.append("── 擋門事後查核")
    e11 = g["E11_inference_mode"]
    L.append(f"  E-11 推論模式：{e11['inference_mode']}　"
             f"帶 reasoning 的呼叫 {_num(e11['reasoning_call_pp'], 2)}%　"
             f"reasoning token 合計 {e11['reasoning_tokens_total']:,}　"
             f"{'**紅**' if e11['red'] else '綠'}")
    e13 = g["E13a_context_pressure"]
    L.append(f"  E-13a context／預算拒交：{e13['budget_or_context_rejects_by_arm']}　"
             f"失敗呼叫 {e13['calls_not_ok']}　finish=length {e13['calls_finish_reason_length']}　"
             f"prompt_tokens 最大 {e13['prompt_tokens_max']:,}／{e13['context_per_slot']:,}")
    v = g["vgt"]
    L.append("  V/GT：" + ("**沒量**（沒給 --vgt-dir）——這不是 CLEAN"
                          if not v["applied"] else
                          f"{v['clean_n']}/{v['blocks_expected']} CLEAN　"
                          f"{'通過' if v['clean'] else '**不通過** ' + str(v['not_clean'][:5])}"))
    L.append("")

    d = a["decision_state"]
    L.append(f"── R532 四狀態：**{d['state']}**")
    L.append(f"   (i) 兩個主指標 Holm 都成立＝{d['cond_i_both_primary_holm']}　"
             f"(ii) 合併 tpc HMIX ≤ CONFORM＝{d['cond_ii_tpc_hmix_le_conform']}"
             f"（{_num(d['tpc_incl_void']['HMIX'], 1)} vs "
             f"{_num(d['tpc_incl_void']['CONFORM'], 1)}）")
    L.append(f"   RULED_OUT 條件（ci95_hi < +{d['ruled_out_line_pp']}pp）＝"
             f"{d['ruled_out_condition_ci_hi_lt_2pp']}"
             f"（實測上界 {_num(d['ci95_hi_pp_HMIX_vs_CONFORM'], 2)}pp）")
    L.append(f"   {d['states_verbatim'][d['state']]}")
    L.append(f"  ⚠ {d['note']}")
    L.append("")

    L.append("── 事前預測逐條（§四-1）")
    for k in sorted((x for x in a["predictions"] if not x.startswith("_")),
                    key=lambda x: int(x.split("-")[1])):
        p = a["predictions"][k]
        mark = {True: "HIT", False: "MISS", None: "未裁決"}[p.get("hit")]
        L.append(f"  {k} [{mark}] {p['text']}")
    t = a["predictions"]["_tally"]
    L.append(f"  合計：HIT {len(t['hit'])}／MISS {len(t['miss'])}／"
             f"未裁決 {len(t['not_adjudicated'])}")
    L.append("")

    ag = a["aggregate"]
    L.append("── §四-4／§四-5 的事前判準")
    L.append(f"  §四-4「增益不縮小」＝{ag['四之四_不縮小判準']['met']}"
             f"（S0/S2/S4 中 Δ_C≥+3pp 的：{ag['四之四_不縮小判準']['sets_ge_3pp']}；"
             f"合併區間下界 {ag['四之四_不縮小判準']['pooled_ci_lo_pp']:+.2f}pp）")
    L.append(f"  §四-5「縮小到 0」＝{ag['四之五_縮小到零判準']['met']}"
             f"（五集 Δ_C 全 ≤+1pp＝{ag['四之五_縮小到零判準']['all_le_1pp']}；"
             f"合併區間上界 {ag['四之五_縮小到零判準']['pooled_ci_hi_pp']:+.2f}pp）")
    L.append(f"  宣稱句規則：{ag['statement']}")
    L.append(f"  ⚠ {ag['winners_curse']}")
    L.append(f"  ⚠ {ag['r440p']}")

    pb = a.get("per_backend") or {}
    if pb:
        L += ["", "── 逐後端（§八-1；**描述性，不進任何仲裁**；b−c 不是檢定）",
              f"{'題目集':<16}{'後端':>8}{'LMS':>10}{'塊':>4}"
              f"{'OFF':>10}{'CONFORM':>10}{'HMIX':>10}{'H−C':>6}{'H−O':>6}"
              f"{'reason均':>9}{'模式':>13}"]
        for s in a["sets_expected"]:
            for host, h in sorted((pb.get(s) or {}).items()):
                pa = h["per_arm"]
                L.append(
                    f"{s:<16}{host:>8}{(h.get('lmstudio_version') or '?'):>10}"
                    f"{h['blocks_n']:>4}"
                    + "".join(f"{pa[x]['deliv_fraction']:>10}" for x in ARMS)
                    + f"{h['paired']['HMIX_vs_CONFORM']['b_minus_c_descriptive']:>+6}"
                      f"{h['paired']['HMIX_vs_OFF']['b_minus_c_descriptive']:>+6}"
                    + f"{_num(h['reasoning']['reasoning_tokens_mean'], 1):>9}"
                      f"{h['reasoning']['inference_mode']:>13}")
        L.append(f"  ⚠ {PER_BACKEND_NOTE}")
    return "\n".join(L)


# ── selftest ──────────────────────────────────────────────────────────
def _row(arm, tid, ok, acc=True, calls=1):
    return {"arm": arm, "task_id": tid, "meets_demand": ok, "accepted": acc,
            "calls_used": calls, "err": ""}


def selftest() -> int:
    """手算對照。每一條都是「不用這支程式也能在紙上算出來」的數。"""
    fails: list[str] = []

    def chk(name, got, want, eps=1e-9):
        ok = (abs(got - want) <= eps) if isinstance(want, float) else (got == want)
        if not ok:
            fails.append(f"{name}: got={got!r} want={want!r}")

    # (1) paired 的 b/c/delta：A 對 B 錯 3 題、B 對 A 錯 1 題、共 10 題
    A = [_row("HMIX", f"t{i}", i < 6) for i in range(10)]
    B = [_row("CONFORM", f"t{i}", i in (0, 1, 2, 6)) for i in range(10)]
    p = paired(A, B)
    chk("paired.b", p["b"], 3)            # t3,t4,t5
    chk("paired.c", p["c"], 1)            # t6
    chk("paired.n_common", p["n_common"], 10)
    chk("paired.delta_pp", p["delta_pp"], 20.0, 1e-9)
    chk("paired.p_disc", p["p_disc"], 0.4, 1e-12)
    # 精確 McNemar：b=3,c=1 ⇒ 雙尾 p = 2*P(X<=1|n=4,0.5) = 2*(5/16) = 0.625
    chk("paired.p", p["p_mcnemar_exact"], 0.625, 1e-12)

    # (2) complete case：B 少一題 ⇒ 分母是交集
    p2 = paired(A, B[:9])
    chk("paired.n_common_cc", p2["n_common"], 9)

    # (3) deliv 口徑：accepted=False 但 meets_demand=True 不算交付
    chk("deliv.gate", _deliv({"accepted": False, "meets_demand": True}), False)
    chk("deliv.both", _deliv({"accepted": True, "meets_demand": True}), True)

    # (4) mcnemar_exact 與 diff_ci 的一致性（區間排除 0 ⟺ p<0.05）
    for (b, c, n) in ((10, 1, 100), (3, 1, 10), (20, 5, 200), (6, 6, 50)):
        d = diff_ci(b, c, n)
        pv = mcnemar_exact(b, c)
        excl = (d["lo"] > 0) or (d["hi"] < 0)
        if excl != (pv < 0.05):
            fails.append(f"ci/p 一致性 b={b} c={c}: lo={d['lo']} hi={d['hi']} p={pv}")

    # (5) Holm：兩個 p ⇒ 小的 ×2、大的不動，並取累積最大
    adj = holm_bonferroni([0.01, 0.40])
    chk("holm[0]", adj[0], 0.02, 1e-12)
    chk("holm[1]", adj[1], 0.40, 1e-12)

    # (6) 分層合併與「直接相加做一次 McNemar」數值相同
    st = stratified_mcnemar_exact([(3, 1), (5, 2), (0, 0)])
    chk("strat.b", st["b"], 8)
    chk("strat.c", st["c"], 3)
    chk("strat.p_identity", st["p"], mcnemar_exact(8, 3), 1e-12)

    # (7) token 帳：wire_probe 進 HMIX、preflight 不進任何一臂
    calls = [
        {"ok": True, "role": "gen", "usage": {"total_tokens": 100},
         "meta": {"arm": "OFF", "task_id": "t1"}},
        {"ok": True, "role": "gen", "usage": {"total_tokens": 200},
         "meta": {"arm": "HMIX", "task_id": "t1"}},
        {"ok": True, "role": "wire_probe", "usage": {"total_tokens": 50},
         "meta": {"arm": "HMIX", "task_id": "t1"}},
        {"ok": True, "role": "preflight", "usage": {"total_tokens": 999},
         "meta": {}},
        {"ok": False, "role": "gen", "usage": {"total_tokens": 7},
         "meta": {"arm": "OFF", "task_id": "t2"}},
    ]
    tk = tokens_by_arm(calls)
    chk("tokens.OFF", tk["OFF"]["tokens"], 100)          # 失敗那通不算 token
    chk("tokens.OFF.wire", tk["OFF"]["calls_wire_total"], 2)
    chk("tokens.OFF.ok", tk["OFF"]["calls_wire_ok"], 1)
    chk("tokens.HMIX", tk["HMIX"]["tokens"], 250)
    chk("tokens.HMIX.probe", tk["HMIX"]["probe_tokens"], 50)
    chk("tokens.preflight_excluded", "preflight" in tk, False)

    # (8) 推論模式：一通帶 reasoning ⇒ 不是 non_thinking
    rs = reasoning_stats([
        {"ok": True, "usage": {"total_tokens": 10, "completion_tokens": 5,
                               "prompt_tokens": 5,
                               "completion_tokens_details": {"reasoning_tokens": 0}}},
        {"ok": True, "usage": {"total_tokens": 10, "completion_tokens": 5,
                               "prompt_tokens": 5,
                               "completion_tokens_details": {"reasoning_tokens": 3}}},
    ])
    chk("reasoning.pp", rs["reasoning_call_pp"], 50.0, 1e-9)
    chk("reasoning.mode", rs["inference_mode"], "thinking")
    chk("reasoning.unknown", reasoning_stats([])["inference_mode"], "unknown")

    # (9) mcnemar_power 的自我對帳：ψ=0.5 ⇒ 檢定力 ≤ α
    if mcnemar_power(120, 0.19, 0.5, alpha=0.05) > 0.05 + 1e-12:
        fails.append("mcnemar_power(ψ=0.5) 應 ≤ α")

    # (10) 四狀態：RULED_OUT 的線是 +2.0 pp，不是 +5
    fake_prim = {"HMIX_vs_CONFORM": {"significant": False, "ci95_hi_pp": 1.5,
                                     "b": 3, "c": 2},
                 "HMIX_vs_OFF": {"significant": True}}
    st1 = decide(fake_prim, {"HMIX": {"tpc_incl_void": 9.0},
                             "CONFORM": {"tpc_incl_void": 8.0}}, {})
    chk("decide.ruled_out", st1["state"], "RULED_OUT")
    fake_prim2 = {"HMIX_vs_CONFORM": {"significant": True, "ci95_hi_pp": 9.0,
                                      "b": 30, "c": 2},
                  "HMIX_vs_OFF": {"significant": True}}
    st2 = decide(fake_prim2, {"HMIX": {"tpc_incl_void": 8.0},
                              "CONFORM": {"tpc_incl_void": 9.0}}, {})
    chk("decide.effective", st2["state"], "EFFECTIVE")
    st3 = decide(fake_prim2, {"HMIX": {"tpc_incl_void": 19.0},
                              "CONFORM": {"tpc_incl_void": 9.0}}, {})
    chk("decide.costly_falls_to_inconclusive", st3["state"], "INCONCLUSIVE")
    chk("decide.costly_shape_flag", st3["costly_but_real_shape"], True)
    st4 = decide(fake_prim2, {"HMIX": {"tpc_incl_void": 8.0},
                              "CONFORM": {"tpc_incl_void": 9.0}},
                 {"vgt": {"red": True}})
    chk("decide.invalid_by_gate", st4["state"], "INVALID")

    # (11) Wilcoxon 只吃 token 差、不吃交付率
    tw = token_wilcoxon({"HMIX": {"by_task": {"a": 10, "b": 20}},
                         "CONFORM": {"by_task": {"a": 5, "b": 5}}})
    chk("wilcoxon.n", tw["HMIX_vs_CONFORM"]["n"], 2)
    chk("wilcoxon.mean", tw["HMIX_vs_CONFORM"]["mean_diff_tokens"], 10.0, 1e-9)

    # (12) 家族大小凍結在 2
    chk("family_size", FAMILY_SIZE, 2)
    chk("pairs_in_family", len(PAIRS), 2)
    chk("ruled_out_line", RULED_OUT_PP, 2.0, 1e-12)

    for f in fails:
        print("FAIL", f)
    print(f"selftest: {'PASS' if not fails else 'FAIL'}"
          f"（{12 - len(set(x.split(':')[0].split('.')[0] for x in fails))}/12 組）")
    return 0 if not fails else 1


#: 每一種突變都必須讓**至少一個仲裁欄位**變掉。變不掉＝那個欄位沒有人在看。
MUTANTS = ("M1_deliv_ignores_accepted", "M2_union_denominator",
           "M4_ruled_out_line_moved", "M5_drop_a_set_silently",
           "M7_vgt_not_checked", "M8_per_backend_merges_hosts",
           "M9_reasoning_ignored", "M10_deliv_uses_visible_ok", "M11_no_holm")


def _arbiter_view(a: dict) -> dict:
    """仲裁欄位的投影（突變只要動到這裡任一格就算被咬到）。"""
    return {
        "state": a["decision_state"]["state"],
        "cond_i": a["decision_state"]["cond_i_both_primary_holm"],
        "cond_ii": a["decision_state"]["cond_ii_tpc_hmix_le_conform"],
        "ruled_out": a["decision_state"]["ruled_out_condition_ci_hi_lt_2pp"],
        "primary": {k: {kk: a["primary"][k][kk]
                        for kk in ("b", "c", "p", "p_adj", "delta_pp",
                                   "ci95_lo_pp", "ci95_hi_pp", "sets_included")}
                    for k in ("HMIX_vs_CONFORM", "HMIX_vs_OFF")},
        "per_set_deliv": {s: {x: a["per_set"][s]["per_arm"][x]["deliv_n"]
                              for x in ARMS} for s in SETS},
        "gates": {"e11": a["gates"]["E11_inference_mode"]["inference_mode"],
                  "vgt_clean": a["gates"]["vgt"]["clean"]},
        "per_backend_hosts": sorted(a["per_backend"]["lcb2"].keys()),
        "predictions": {k: v.get("hit") for k, v in a["predictions"].items()
                        if not k.startswith("_")},
    }


def mutation_check(root: pathlib.Path, vgt_dir: pathlib.Path | None) -> int:
    """每一種突變都要讓仲裁投影變掉。變不掉 ⇒ 那個欄位沒有人在看。"""
    os.environ.pop("R532_MUTANT", None)
    base = _arbiter_view(analyze(root, vgt_dir, with_12b=False))
    bad: list[str] = []
    for m in MUTANTS:
        os.environ["R532_MUTANT"] = m
        try:
            got = _arbiter_view(analyze(root, vgt_dir, with_12b=False))
        except Exception as exc:                            # noqa: BLE001
            got = {"crash": repr(exc)}
        os.environ.pop("R532_MUTANT", None)
        changed = got != base
        print(f"  {m:<34}{'變紅 ✓' if changed else '**沒被咬到** ✗'}")
        if not changed:
            bad.append(m)
    print(f"mutation-check: {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return 0 if not bad else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="R532 收官分析（零模型呼叫）")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", default=None, help="把完整結果寫到這個路徑")
    ap.add_argument("--vgt-dir", default=None,
                    help="harness_vgt_audit.py --scope v2 的產物目錄")
    ap.add_argument("--no-12b", action="store_true", help="跳過跨模型並列")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mutation-check", action="store_true")
    ns = ap.parse_args(argv)
    root = pathlib.Path(ns.root)
    vgt = pathlib.Path(ns.vgt_dir) if ns.vgt_dir else None
    if ns.selftest:
        return selftest()
    if ns.mutation_check:
        return mutation_check(root, vgt)
    a = analyze(root, vgt, with_12b=not ns.no_12b)
    print(render(a))
    if ns.json:
        p = pathlib.Path(ns.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(a, ensure_ascii=False, indent=1, sort_keys=False),
                     encoding="utf-8")
        print(f"\n[json] {p}")
    return 0


if __name__ == "__main__":       # pragma: no cover
    raise SystemExit(main())
