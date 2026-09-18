#!/usr/bin/env python3
"""這支在架構裡承重什麼：R535 的**收官判定器**——把預註冊 §六 的狀態表變成程式。

零模型呼叫、離線、確定性（bootstrap 的 seed 寫死）。

## 為什麼要有這支

預註冊（`decisions/DECISION_20260919_R535_RETRY_CHANNEL_PREREG.md`，分支
`prereg/r535`）§六 定了一整張狀態表，**但沒有任何程式在算它**：
`ops/gain/r535/run_r535.py` 只管跑，`ops/gain/r535/score_r535.py` 只吐逐臂計數。
狀態寫在文件裡而判定靠人眼，等於沒有判定——**R532 的 AMEND1 就是這個形狀**
（analyzer 把一個負向顯著的結果貼成 `EFFECTIVE`，因為那張表沒有寫死方向）。
所以本檔的每一個判準都帶方向，而且每一條都有一個**可關掉的開關**
（`disabled=`）讓負向控制可以機械化執行：`--mutation-check` 會把每一條判定式
逐一拿掉，證明對應的樣本真的翻紅。**沒有負控的「全綠」跟把判定關掉在輸出上同形。**

## 結果變數（2026-09-19 更正，凍結）

    M1     ≡ accepted ∧ hidden 全過        ← **主要，H1 只用這個**
             拒交（`vacant run` exit 20 ／ `accepted` 非 true）強制記 0
    M1_vis ≡ accepted（最終可見通過）       ← **配對描述**：印 b、c、exact p、
                                             95% 區間，**不進 Holm 家族、
                                             不進狀態表**

**為什麼主指標不是 accepted-only（逐字，這是本檔的立論）**：

> accepted-only 當主指標會把管道效果**灌水一個可預期的方向**：
> `revise` 拿著失敗原文改碼，比 `resample` **更容易針對可見 case 打補丁**
> （過閘門、隱藏不過）。那正是 `suitegauge` 的單邊保證殘餘（M6）。
> H1 若只看 accepted，這個殘餘會被算成「管道買到的交付」。
> 用 `accepted ∧ hidden` 才是「客戶最後拿到了什麼」。

`hidden` 是 `visible` 的超集 ⇒ hidden 全過蘊含 accepted ⇒ M1 在數值上就是
「最後交付物的 hidden 通過」，拒交強制 0。⇒ 逐格 **M1 ≤ M1_vis**，
所以「M1 贏而 M1_vis 不贏」在資料上不可能；真的出現就是資料有問題
（最可能是 L-4 的假逾時：可見逾時而隱藏過），該格標 `inconsistent`、
交回 ops 重算，**不准靜默計入**。

⚠ **`NOT_TRIGGERED` 與 `CEILING_TOO_LOW` 的判準仍然吃「第 1 次可見」**
（預註冊 §六-2 第 2、3 列逐字）：那兩條問的是「閘門有沒有被打開」，
不是「客戶拿到了什麼」，所以它們該讀可見。**不要一起改。**

## 為什麼不借用 `vacant/research.py::discordance`（三個理由，都要留著）

1. **它只讀 `.passed_gt`（＝hidden）**——欄位語意寫死在 comprehension 裡，
   與本輪要防的那種漂移正好同形：哪天有人改了它讀哪一欄，本輪的主指標會
   跟著無聲改變。b/c 是狀態表的方向來源，不能掛在別人的預設值上。
2. **它忽略 `asserted`／`refused`**——一格拒交、但凍結快照碰巧過了 hidden，
   `discordance` 會把它算成 1。本輪的 M1 要求 `accepted ∧ hidden`，
   拒交強制 0；那件事 `discordance` 表達不出來。
3. **`arm_a`／`arm_b` 的 b/c 方向與預註冊散文相反**（見下面的凍結行）。

⇒ b/c 在本檔**自己算**（`bc_counts`）。

## b/c 的方向（凍結，逐字）

    b ≡ RF 的 M1 = 0 ∧ RP 的 M1 = 1      （＝RP 贏）
    c ≡ RF 的 M1 = 1 ∧ RP 的 M1 = 0      （＝RF 贏）
    H2 同形：b2 ≡ RS 的 M1 = 0 ∧ RF 的 M1 = 1   （＝RF 贏）

這與 `discordance(results, arm_a="RF", arm_b="RP")[0]` 的 `b`（「a 錯 b 對」）
同構。⚠ **預註冊 §六-2 第 4／5 列的字母與本約定相反**（它把 `CONFIRMED_POSITIVE`
寫成 `c > b`）。兩邊講同一件事，字母鏡像；本檔以上面三行為準，對照預註冊時互換。
`tests/test_r535_state.py` 把這一條釘死，並直接拿 `research.discordance`
對算——它哪天改方向，測試會先紅。

## 事前寫死的分歧句

`M1_vis` 顯示 RP > RF（方向對且單獨 exact p < 0.05）而 `M1` 的 Holm 調整後
不顯著 ⇒ 輸出
**「管道買到的是過閘門，不是通過隱藏測資（M6 = <x>）」**。
**M6（可見過而隱藏沒過的比例）任何情況下都要印。**

## 它讀什麼

* `score_r535.py` 產的 `scores_*.json`（`cells[]`：逐格 `visible_accepted`／
  `hidden_pass`／`visible_pass_hidden_fail`／`by_attempt[]`／`m7_file`／
  `m7_ws`／`f6`／`attempts_used`）；
* `run_r535.py --reconcile` 產的 `reconcile.json`（`verdict` ∈ {OK, INVALID}）。

兩份都不重算、不修改。本檔**不碰** `bank/`、不呼叫驗收 runner、不開網路。
**資料不必重跑**：M1 只是改讀哪一欄。

## 求值順序（照預註冊 §六-1，不准改、不准跳號、不准回頭）

    INVALID → NOT_TRIGGERED → CEILING_TOO_LOW → CONFIRMED_POSITIVE →
    CONFIRMED_NEGATIVE → RULED_OUT → INCONCLUSIVE

`MECHANISM_BREACH`／`STALE_WORKSPACE_EFFECT(±)`／`M7_WS_INVALID` 在
**RF／RS 控制鏈**上：獨立、互斥、**不在上面那條鏈上**，可以與鏈上任何一個
同時成立。護欄表 2026-09-19 最後一輪**整張換掉**，逐字抄在 `control_state`
的 docstring 裡。三件事要一起記著：

1. NOTHINK 冒煙實測 pi **會去看工作區** ⇒「RF 與 RS 可交換」的預測撤回；
2. `RF < RS` 也不再是異常——模型看到自己上一份錯碼會**錨定在上面**，
   `resample` 重置工作區反而拿到乾淨的重抽 ⇒ **兩個符號都可能**，所以
   `STALE_WORKSPACE_EFFECT` **帶符號**（＝`RF − RS` 的符號）且方向不進判準；
3. ⚠ **H1 完全不受影響**：RP 與 RF **都是 `revise`**（都保留工作區）⇒
   那個效果在配對裡對消，H1 剩下的唯一差異仍是「回饋在不在模型輸入裡」。

## 誠實邊界（改碼請保留）

1. **`INCONCLUSIVE` 是事前預期的落點不是失敗**：預註冊 §七 事前算好，
   +10 pp 的真效果在 n=50 的檢定力只有 0.086。「沒顯著」與「效果是 0」和
   「效果是 +10 pp」**都相容**，本輪區分不了。
2. **S1／S2 分開報，任何情況下不合併**：兩對題跨層共用參考解
   （`s1_32_pct`／`s2_06_pct`、`s1_35_rle`／`s2_29_rle`），合併會把它們當成
   四個獨立觀測。
3. **`M7_file` 是單邊的**：命中 0 只說明那三個字串沒出現在請求 body 裡，
   不說明 agent 沒有以任何方式受到那個檔的影響。
4. **`null` 不是 `false`**（鐵律 3 的 `infra_void` 同一條）：`m7_file`／`m7_ws`／
   `f6` 的 `null` 一律不進分母，並且逐項印出「有第 ≥2 次嘗試卻量不到」的格數。
5. **本檔不重算汙染**：L-4 的假逾時重算是 ops 的事。這裡只把 `suspect_timeout`
   與 `inconsistent` 的格數印出來，並在還沒處理時出聲。
6. **hidden 全過 ≠ 做對了**：`vacant/suitegauge.py` 的單邊保證對隱藏套件一樣成立
   （擋得住已知壞解 ≠ 涵蓋真需求）。M1 量的是「兩套驗收都過了」。
7. **口徑**：本輪講的是**可究責性**（讓依賴有根據），不是那兩個字。
8. 本輪不得與 R530／R532／R534 併表或併 n。

## 口徑紀律（可執行）

`check_diction()` 掃過整份輸出，命中 `BANNED` 任何一條就把 `diction_ok` 判 false
並回非零 exit。**「等價」兩個字任何輸出都不准出現**；TOST 只能寫
「成立／不成立」或「±15 pp 內未區分開」。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from vacant.research import (                                   # noqa: E402
    boot_ci, holm_bonferroni, mcnemar_exact, tost_equiv_boot,
    wilcoxon_signed_rank_exact,
)

# ── 凍結常數（全部來自預註冊，不准在這裡「調一下」）───────────────────────
STRATA: tuple[str, ...] = ("S1", "S2")
#: ⚠ **PC 不在這裡。** 它的工作區是 `TASK_explicit.md`，是另一個 TASK。
TRIGGER_ARMS: tuple[str, ...] = ("RS", "RF", "RP")
#: L-4：`infra_void` 剔除是**三臂一起**（配對比較的那三個）。PC 單獨 void，不連坐。
PAIRED_ARMS: tuple[str, ...] = ("RS", "RF", "RP")
N_TASKS_PLANNED = {"S1": 50, "S2": 40}
#: §六-2 第 2 列：S1 < 0.6、S2 < 0.3（三臂合併的第 1 次**可見**失敗率）
TRIGGER_FAIL_THRESHOLD = {"S1": 0.60, "S2": 0.30}
#: §六-2 第 2 列的分母：S1 共 150 個第 1 次嘗試、S2 共 120 個
TRIGGER_N_EXPECTED = {"S1": 150, "S2": 120}
CEILING_PASS_THRESHOLD = 0.50      # §六-2 第 3 列：PC 第 1 次**可見**通過 < 0.5
VOID_RATE_MAX = 0.10               # §六-2 第 1 列：剔除 > 10% ⇒ INVALID
M7_FILE_BREACH = 0.10              # §五-2：M7_file > 10%（任一層）⇒ BREACH
ALPHA = 0.05                       # H1 的 Holm 調整後門檻、H2 的單獨門檻
TOST_DELTA = 0.15                  # δ = 15 pp（**只印不裁**）
RULED_OUT_UPPER = 0.15             # RULED_OUT：95% 區間上緣 < +15 pp（單邊）
BOOT_N = 2000
BOOT_SEED = 0
#: Holm 家族固定大小 2：{H1-S1, H1-S2}。順序寫死，不依資料重排。
FAMILY: tuple[str, ...] = ("H1-S1", "H1-S2")

CHAIN_ORDER: tuple[str, ...] = (
    "INVALID", "NOT_TRIGGERED", "CEILING_TOO_LOW", "CONFIRMED_POSITIVE",
    "CONFIRMED_NEGATIVE", "RULED_OUT", "INCONCLUSIVE",
)

#: 口徑禁語。**輸出裡出現任何一條就判紅**（預註冊 §五-3 的禁語，逐字）。
BANNED: tuple[str, ...] = (
    "等價", "等效", "equivalent", "equivalence",
    "無差異", "沒有差異", "效果為 0", "效果是 0", "兩臂相同",
    "信任",
)

M1_DEFINITION = (
    "M1 ≡ accepted ∧ hidden 全過（拒交強制 0）。"
    "M1_vis ≡ accepted，**降為配對描述**，不進 Holm 家族、不進狀態表。"
)
M1_WHY = (
    "accepted-only 當主指標會把管道效果灌水一個可預期的方向：revise 拿著失敗"
    "原文改碼，比 resample 更容易針對可見 case 打補丁（過閘門、隱藏不過）。"
    "那正是 suitegauge 的單邊保證殘餘（M6）。H1 若只看 accepted，這個殘餘會被"
    "算成「管道買到的交付」。用 accepted ∧ hidden 才是「客戶最後拿到了什麼」。"
)
BC_CONVENTION = (
    "b ≡ RF 的 M1 = 0 ∧ RP 的 M1 = 1（＝RP 贏）；"
    "c ≡ RF 的 M1 = 1 ∧ RP 的 M1 = 0（＝RF 贏）。"
    "H2 同形：b2 ≡ RS 的 M1 = 0 ∧ RF 的 M1 = 1（＝RF 贏）。"
    "與 discordance(results, arm_a=\"RF\", arm_b=\"RP\")[0] 同構。"
    "⚠ 預註冊 §六-2 第 4／5 列的字母與本約定**相反**（鏡像），對照時互換。"
)
WHY_NOT_DISCORDANCE = (
    "不借用 vacant/research.py::discordance，三個理由："
    "(1) 它只讀 `.passed_gt`（＝hidden），欄位語意寫死在 comprehension 裡，"
    "與本輪要防的漂移正好同形；"
    "(2) **它忽略 asserted／refused**——一格拒交但凍結快照碰巧過了 hidden，"
    "會被它算成 1，而本輪的 M1 要求拒交強制 0；"
    "(3) arm_a／arm_b 的 b/c 方向與預註冊散文相反。"
)
DIVERGENCE_LINE = ("管道買到的是過閘門，不是通過隱藏測資（M6 = {m6}）")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _rate(num: int, den: int) -> float | None:
    """分母 0 ⇒ `None`，**不是 0.0**。沒量到不是量到 0。"""
    return (num / den) if den else None


def check_diction(payload) -> dict:
    """把整份輸出攤平成字串掃禁語。**命中就紅，不給例外。**"""
    text = json.dumps(payload, ensure_ascii=False)
    hits = sorted({w for w in BANNED if w in text})
    return {"ok": not hits, "hits": hits,
            "rule": ("「等價」兩個字任何輸出都不准出現；TOST 只能寫"
                     "「成立／不成立」或「±15 pp 內未區分開」。"
                     "口徑用「可究責性」。")}


# ── 讀資料 ────────────────────────────────────────────────────────────────

def normalise_cell(row: dict) -> dict:
    """把 `score_r535.py` 的一列縮成判定要用的形狀。

    `status != "scored"`／`infra_void` 非空／`visible_accepted is None`
    三者任一 ⇒ 該格 `void`。**void 不是 0 分，是沒量到。**
    """
    by = row.get("by_attempt") or []
    a1 = next((a for a in by if a.get("attempt") == 1), None)
    void_reason = None
    if row.get("status") != "scored":
        void_reason = f"status={row.get('status')}"
    elif row.get("infra_void"):
        void_reason = f"infra_void={row.get('infra_void')}"
    elif row.get("visible_accepted") is None:
        void_reason = "visible_accepted=null"
    return {
        "cell": row.get("cell"),
        "task_id": row.get("task_id"),
        "arm": row.get("arm"),
        "stratum": row.get("stratum"),
        "void": void_reason is not None,
        "void_reason": void_reason,
        # 原始兩欄：accepted 與 hidden 全過。M1 在 `apply_m1` 才合成。
        "accepted": row.get("visible_accepted"),
        "hidden": row.get("hidden_pass"),
        "stop_reason": row.get("stop_reason"),
        "attempt1_visible": (a1 or {}).get("visible_accepted"),
        "attempt1_hidden": (a1 or {}).get("hidden_pass"),
        "attempts_used": row.get("attempts_used"),
        "m7_file": row.get("m7_file"),
        "m7_ws": row.get("m7_ws"),
        "m7_ws_ratio": row.get("m7_ws_ratio"),
        # 驅動那邊正在加：RF 第 ≥2 次嘗試裡「讀自己上一份 solution.py」。
        # 還沒落盤時是 None ⇒ **不可當 false**（同 m7_file 的 null 規則）。
        "m7_ws_solution": row.get("m7_ws_solution"),
        "f6": row.get("f6"),
        "suspect_timeout": bool(row.get("suspect_timeout")),
        "requests_seen": row.get("requests_seen"),
    }


def apply_m1(cells: list[dict], *,
             disabled: frozenset[str] = frozenset()) -> list[dict]:
    """合成 `m1`／`m1_vis`／`m6`／`inconsistent`。**在這裡，不在別處。**

    * `m1` ＝ `accepted ∧ hidden`。拒交（`accepted` 非 true）強制 0，
      即使凍結快照碰巧過了 hidden。
    * `m1_vis` ＝ `accepted`。
    * `m6`（本格）＝ `accepted ∧ ¬hidden`：可見過而隱藏沒過
      ＝ `suitegauge` 單邊保證的殘餘現場。
    * `inconsistent` ＝ `hidden ∧ ¬accepted`：hidden ⊇ visible 之下不該出現
      （最可能是 L-4 的假逾時）。**M1 照樣記 0，但要標出來交回重算。**

    `M1_REQUIRES_ACCEPTED` 只給 `--mutation-check` 用：拿掉之後 `m1` 只看
    hidden，那個拒交格會被算成 1——那正是要防的事。
    """
    require_accepted = "M1_REQUIRES_ACCEPTED" not in disabled
    for c in cells:
        acc, hid = c.get("accepted"), c.get("hidden")
        if acc is None or hid is None:
            c["m1"] = None
        elif require_accepted:
            c["m1"] = bool(acc) and bool(hid)
        else:
            c["m1"] = bool(hid)
        c["m1_vis"] = None if acc is None else bool(acc)
        c["m6"] = (bool(acc) and hid is False) if (acc is not None
                                                  and hid is not None) else None
        c["inconsistent"] = bool(hid is True and acc is False)
    return cells


def load_scores(path: pathlib.Path) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return [normalise_cell(r) for r in doc.get("cells") or []]


def newest_scores(out: pathlib.Path) -> pathlib.Path:
    cands = sorted(out.glob("scores_*.json"))
    if not cands:
        raise SystemExit(
            f"{out} 底下沒有 scores_*.json。先跑 ops/gain/r535/score_r535.py。")
    return cands[-1]


# ── 量（每一個都自己算，分母寫死）──────────────────────────────────────────

def bc_counts(cells: list[dict], *, arm_a: str, arm_b: str,
              field: str, only_tasks: set[str] | None = None) -> dict:
    """配對計數。**方向凍結**：

        b ≡ arm_a 的 <field> = 0 ∧ arm_b 的 <field> = 1
        c ≡ arm_a 的 <field> = 1 ∧ arm_b 的 <field> = 0

    ⇒ `bc_counts(..., arm_a="RF", arm_b="RP", field="m1")` 的 `b` 就是 RP 贏。
    只收**兩臂都非 void、且該欄都非 null** 的題；`diffs` 是逐題配對差
    ∈ {−1, 0, +1}，符號與 b/c 一致（+1 ＝ arm_b 贏 ＝ 計進 b）。

    ⚠ `only_tasks` 是 **L-4 的三臂一起剔除**（`void_stats` 算好的那一份）：
    RS 壞掉的題，RF vs RP 也不准用。少了這個過濾，同一層的 H1 與 H2 會用到
    不同的題集，而那件事在輸出上看不出來。

    為什麼不呼叫 `research.discordance` 見模組 docstring 的三個理由。
    """
    by_task: dict[str, dict[str, dict]] = {}
    for c in cells:
        by_task.setdefault(c["task_id"], {})[c["arm"]] = c
    b = c_ = both_pass = both_fail = 0
    diffs: list[float] = []
    used: list[str] = []
    for tid in sorted(by_task):
        if only_tasks is not None and tid not in only_tasks:
            continue
        pair = by_task[tid]
        ca, cb = pair.get(arm_a), pair.get(arm_b)
        if not ca or not cb or ca["void"] or cb["void"]:
            continue
        va, vb = ca.get(field), cb.get(field)
        if va is None or vb is None:
            continue
        used.append(tid)
        diffs.append(float(bool(vb)) - float(bool(va)))
        if not va and vb:
            b += 1
        elif va and not vb:
            c_ += 1
        elif va and vb:
            both_pass += 1
        else:
            both_fail += 1
    direction = "tie" if b == c_ else (f"{arm_b}>{arm_a}" if b > c_
                                       else f"{arm_a}>{arm_b}")
    return {"arm_a": arm_a, "arm_b": arm_b, "field": field,
            "b": b, "c": c_, "both_pass": both_pass, "both_fail": both_fail,
            "n_pairs": len(used), "direction": direction,
            "three_arm_filter": only_tasks is not None,
            "convention": BC_CONVENTION, "task_ids": used, "diffs": diffs}


def ci_of(diffs: list[float]) -> dict:
    """95% bootstrap 百分位區間（`research.boot_ci` 2.5/97.5，seed 寫死）。"""
    if not diffs:
        return {"mean_diff": None, "ci_lo": None, "ci_hi": None,
                "method": "無配對可算"}
    lo, hi = boot_ci(diffs, lambda s: _mean(s), n_boot=BOOT_N,
                     seed=BOOT_SEED, lo=2.5, hi=97.5)
    return {"mean_diff": _mean(diffs), "ci_lo": lo, "ci_hi": hi,
            "method": f"boot_ci 2.5/97.5（95%），seed={BOOT_SEED}，"
                      f"n_boot={BOOT_N}",
            "sign": "+ ＝ RP 贏（與 b 同號）"}


def trigger_rate(cells: list[dict], stratum: str, *,
                 include_pc: bool = False) -> dict:
    """`NOT_TRIGGERED` 的判準來源：**RS／RF／RP 合併**的第 1 次可見失敗率。

    ⚠ 這一條**吃可見**，不吃 M1（預註冊 §六-2 第 2 列逐字）：它問的是
    「閘門有沒有被打開」，不是「客戶拿到了什麼」。

    ⚠ **PC 的 attempt-1 不准混進這個分母。** PC 的工作區是
    `TASK_explicit.md`（改名成 `TASK.md`），那是**另一個 TASK**——
    把它併進來就是把天花板當成基線，會把失敗率往下拉、讓 `NOT_TRIGGERED`
    假觸發。`include_pc` 只給 `--mutation-check` 的負向控制用，正路不准開。
    """
    arms = TRIGGER_ARMS + (("PC",) if include_pc else ())
    sel = [c for c in cells
           if c["stratum"] == stratum and c["arm"] in arms and not c["void"]
           and c["attempt1_visible"] is not None]
    n = len(sel)
    fails = sum(1 for c in sel if not c["attempt1_visible"])
    return {"arms": list(arms), "pc_excluded": not include_pc,
            "n": n, "n_expected": TRIGGER_N_EXPECTED[stratum],
            "attempt1_fail": fails,
            "attempt1_fail_rate": _rate(fails, n),
            "threshold": TRIGGER_FAIL_THRESHOLD[stratum],
            "basis": "第 1 次**可見**失敗（不是 M1）",
            "note": ("分母＝RS／RF／RP 三臂的第 1 次嘗試；"
                     "PC 的 attempt-1 是另一個 TASK，不進這個分母。")}


def ceiling_rate(cells: list[dict], stratum: str) -> dict:
    """`CEILING_TOO_LOW` 的判準來源：PC 的第 1 次**可見**通過率（不是 M1）。"""
    sel = [c for c in cells
           if c["stratum"] == stratum and c["arm"] == "PC" and not c["void"]
           and c["attempt1_visible"] is not None]
    n = len(sel)
    passed = sum(1 for c in sel if c["attempt1_visible"])
    return {"arm": "PC", "n": n, "attempt1_pass": passed,
            "attempt1_pass_rate": _rate(passed, n),
            "threshold": CEILING_PASS_THRESHOLD,
            "basis": "第 1 次**可見**通過（預註冊 §六-2 第 3 列逐字）",
            "note": ("PC 量的是「把話講清楚」的上界，不是「正確答案」的上界。"
                     "PC 低可能是題目太難，也可能是 explicit 版寫得不夠明白——"
                     "本輪分不開這兩者。")}


def m6_stats(cells: list[dict], stratum: str) -> dict:
    """`M6`：可見過而隱藏沒過的格數比例——`suitegauge` 單邊保證的殘餘。

    **任何情況下都要印。** 它是「管道買到的是過閘門還是交付」那個分歧句的證據。
    """
    out: dict = {"by_arm": {}, "definition": "accepted ∧ ¬hidden",
                 "why": ("可見套件擋得住已知壞解 ≠ 涵蓋真需求；"
                         "針對可見 case 打補丁會落在這一格。")}
    for arm in ("RS", "RF", "RP", "PC"):
        sel = [c for c in cells if c["stratum"] == stratum and c["arm"] == arm
               and not c["void"] and c["m6"] is not None]
        hit = sum(1 for c in sel if c["m6"])
        out["by_arm"][arm] = {"n": len(sel), "hit": hit,
                              "rate": _rate(hit, len(sel)),
                              "cells": sorted(c["cell"] for c in sel
                                              if c["m6"])[:32]}
    return out


def inconsistent_stats(cells: list[dict], stratum: str) -> dict:
    """`hidden ∧ ¬accepted`：hidden ⊇ visible 之下不該出現的格。

    **M1 照樣記 0**（拒交就是拒交），但要點名交回 ops 重算（L-4）。
    """
    bad = sorted(c["cell"] for c in cells
                 if c["stratum"] == stratum and c["inconsistent"])
    return {"n": len(bad), "cells": bad[:32],
            "rule": ("hidden 是 visible 的超集 ⇒ 這個組合不該出現。"
                     "最可能是 L-4 的假逾時（可見逾時而隱藏過）。"
                     "M1 記 0，該格交回 ops 重算，**不准靜默計入**。")}


def invariants(cells: list[dict], stratum: str) -> dict:
    """預註冊 §二-5 的可驗不變量裡，**本檔讀得到的那兩條**。

    * **I-4**：RS／PC 的 `attempts_used == 1`。它們是 `--retry none`；
      看到 3 就代表那一格不是用該臂的旗標跑的——RS 不再是單發基線，
      H2（RF vs RS）就變成「3 次 vs 3 次」，而那件事在分數上看不出來。
    * **I-5**：每格 `requests_seen > 0`。`== 0` ＝ agent 根本沒被中介到
      （§二-3 那個埠差一號的坑），那不是「模型不想講話」。

    ⚠ **這裡只出聲，不改狀態。** `INVALID` 的權威是 `run_r535.py --reconcile`
    （它比對 `arm_flags` 與 `bank_manifest_sha256`），本檔不越權替它判。
    I-1／I-2／I-3／I-6 需要 `run_*.json` 與收據鏈，不在 `scores_*.json` 裡，
    由 `--reconcile` 與 `ops/gain/replay/verify_run_receipts.py` 各自負責。
    """
    sel = [c for c in cells if c["stratum"] == stratum and not c["void"]]
    i4 = sorted(c["cell"] for c in sel
                if c["arm"] in ("RS", "PC") and c["attempts_used"] not in (None, 1))
    i5 = sorted(c["cell"] for c in sel if not c["requests_seen"])
    return {"i4_single_shot_arms_retried": {"n": len(i4), "cells": i4[:32]},
            "i5_not_mediated": {"n": len(i5), "cells": i5[:32]},
            "ok": not i4 and not i5,
            "changes_state": False,
            "elsewhere": ("I-1／I-2／I-3／I-6 不在 scores_*.json 裡，"
                          "由 run_r535.py --reconcile 與 "
                          "ops/gain/replay/verify_run_receipts.py 負責。")}


def m7_file_stats(cells: list[dict], stratum: str, *,
                  null_as_false: bool = False) -> dict:
    """`M7_file`：回饋文字出現在第 ≥2 次嘗試 wire 的**格數比例**（RF 臂）。

    ⚠ **分母只收真的量到的格**（`m7_file is not None`）。
    `null` 有三種：沒有第 2 次嘗試／這一臂不產生回饋／wire 對不起來或
    特徵字串不具鑑別力。把它們當成 `false` 算進分母，就是把「沒量到」
    偽裝成「沒發生」——鐵律 3 的 `infra_void` 同一條。
    有第 ≥2 次嘗試卻 `null` 的格數另外印（`n_retried_unmeasured`），
    這是本量測的已知缺口，不是 0。

    `null_as_false` 只給 `--mutation-check` 的負向控制用。
    """
    sel = [c for c in cells
           if c["stratum"] == stratum and c["arm"] == "RF" and not c["void"]]
    true_ = sum(1 for c in sel if c["m7_file"] is True)
    false_ = sum(1 for c in sel if c["m7_file"] is False)
    null_ = sum(1 for c in sel if c["m7_file"] is None)
    unmeasured_retried = sum(
        1 for c in sel
        if c["m7_file"] is None and (c["attempts_used"] or 0) >= 2)
    den = (true_ + false_ + null_) if null_as_false else (true_ + false_)
    return {"arm": "RF", "n_cells": len(sel),
            "hit": true_, "miss": false_, "null": null_,
            "n_measured": true_ + false_,
            "n_retried_unmeasured": unmeasured_retried,
            "denominator": den, "null_counted_as_false": null_as_false,
            "rate": _rate(true_, den),
            "breach_threshold": M7_FILE_BREACH,
            "one_sided": ("單邊：命中 0 只說明那三個字串沒出現在請求 body 裡，"
                          "不說明 agent 沒有以任何方式受到那個檔的影響。")}


def m7_ws_stats(cells: list[dict], stratum: str) -> dict:
    """`M7_ws`：RF 第 ≥2 次嘗試裡出現「讀 TASK／寫 solution 以外」工具呼叫的格數。

    分母同樣只收量到的格（`m7_ws is not None`）。
    `m7_ws > 0` 讀成「保留的髒工作區**被摸過**」，它是 `STALE_WORKSPACE_EFFECT`
    與 `MECHANISM_BREACH` 的分水嶺——**分類器是我們猜的，原始呼叫清單在
    `cell.json` 的 `m7_ws_calls`，要換分類規則離線重算即可。**
    """
    sel = [c for c in cells
           if c["stratum"] == stratum and c["arm"] == "RF" and not c["void"]]
    true_ = sum(1 for c in sel if c["m7_ws"] is True)
    false_ = sum(1 for c in sel if c["m7_ws"] is False)
    null_ = sum(1 for c in sel if c["m7_ws"] is None)
    ratios = [c["m7_ws_ratio"] for c in sel if c["m7_ws_ratio"] is not None]
    return {"arm": "RF", "n_cells": len(sel), "cells_with_other_calls": true_,
            "cells_without": false_, "null": null_,
            "n_measured": true_ + false_,
            "rate": _rate(true_, true_ + false_),
            "other_call_ratio_mean": (_mean(ratios) if ratios else None),
            "source": "last_request_per_attempt（框架若做脈絡壓縮，這是上界）"}


def m7_ws_solution_stats(cells: list[dict], stratum: str) -> dict:
    """`M7_ws_solution`：RF 第 ≥2 次嘗試裡「**讀自己上一份 `solution.py`**」的比例。

    判準是驅動那邊算的（`read solution.py`，或 `bash` 內含
    `cat`／`sed`／`head`／`tail`／`less` 指向它），逐格 `true/false/null`。
    `null` ＝ 沒有第 2 次嘗試，**不可當 false** ⇒ 不進分母。

    ⚠ **不進任何判準。** 但 `STALE_WORKSPACE_EFFECT` 的收官句**必須引它**：
    `M7_ws > 0` 只說明工作區被摸過（可能只是 `ls`），
    `M7_ws_solution > 0` 才說明**上一份錯碼真的被讀進去**。
    兩者都 0 而 RF ≠ RS 顯著 ⇒ 差異來源未定。
    """
    sel = [c for c in cells
           if c["stratum"] == stratum and c["arm"] == "RF" and not c["void"]]
    true_ = sum(1 for c in sel if c["m7_ws_solution"] is True)
    false_ = sum(1 for c in sel if c["m7_ws_solution"] is False)
    null_ = sum(1 for c in sel if c["m7_ws_solution"] is None)
    unmeasured_retried = sum(
        1 for c in sel
        if c["m7_ws_solution"] is None and (c["attempts_used"] or 0) >= 2)
    return {"arm": "RF", "n_cells": len(sel), "hit": true_, "miss": false_,
            "null": null_, "n_measured": true_ + false_,
            "n_retried_unmeasured": unmeasured_retried,
            "rate": _rate(true_, true_ + false_),
            "in_decision": False,
            "note": ("不進判準，但 STALE_WORKSPACE_EFFECT 的收官句必須引它。"
                     "null 不進分母（沒有第 2 次嘗試 ≠ 沒讀）。")}


def f6_stats(cells: list[dict], stratum: str) -> dict:
    """`F6`：RP 的每個第 ≥2 次嘗試 `feedback_in_prompt_bytes > 0`。

    `f6 is None` 而 `attempts_used >= 2` ⇒ **量不到，保守記成沒成立**
    （會擋住 `CONFIRMED_POSITIVE`）。`attempts_used < 2` 的 `null` 是 N/A。
    """
    sel = [c for c in cells
           if c["stratum"] == stratum and c["arm"] == "RP" and not c["void"]]
    true_ = sum(1 for c in sel if c["f6"] is True)
    false_ = sum(1 for c in sel if c["f6"] is False)
    null_retried = sum(1 for c in sel
                       if c["f6"] is None and (c["attempts_used"] or 0) >= 2)
    na = sum(1 for c in sel
             if c["f6"] is None and (c["attempts_used"] or 0) < 2)
    return {"arm": "RP", "n_cells": len(sel), "true": true_, "false": false_,
            "null_with_retry": null_retried, "not_applicable": na,
            "all_ok": bool(false_ == 0 and null_retried == 0),
            "note": ("F6 是 RP 的機制門：回饋真的進了 argv。"
                     "有第 ≥2 次嘗試卻量不到 ⇒ 保守記成沒成立。")}


def void_stats(cells: list[dict], stratum: str) -> dict:
    """L-4：`infra_void` 的剔除是 **RS／RF／RP 三臂一起**（配對比較的那三個）。

    PC 是天花板量測、不進任何配對檢定 ⇒ PC 該格單獨 void，
    **不連坐、也不進 10% 的分子**（預註冊 L-4 明寫，裁決原文沒有指定 PC）。
    """
    tasks: dict[str, dict[str, dict]] = {}
    for c in cells:
        if c["stratum"] == stratum:
            tasks.setdefault(c["task_id"], {})[c["arm"]] = c
    excluded: list[dict] = []
    kept: list[str] = []
    pc_void: list[str] = []
    for tid in sorted(tasks):
        arms = tasks[tid]
        bad = [a for a in PAIRED_ARMS if a not in arms or arms[a]["void"]]
        if bad:
            excluded.append({"task_id": tid, "arms": bad})
        else:
            kept.append(tid)
        pc = arms.get("PC")
        if pc is None or pc["void"]:
            pc_void.append(tid)
    n_planned = N_TASKS_PLANNED[stratum]
    n_seen = len(tasks)
    return {"n_tasks_planned": n_planned, "n_tasks_seen": n_seen,
            "n_excluded": len(excluded), "n_kept": len(kept),
            "kept_task_ids": kept, "excluded": excluded[:64],
            "pc_void_tasks": pc_void[:64],
            "n_pc_void": len(pc_void),
            # 分母用**計畫的題數**：只跑了 5 格就說「剔除率 0%」
            # 是把沒跑當成跑過了。
            "void_rate": _rate(len(excluded) + max(0, n_planned - n_seen),
                               n_planned),
            "threshold": VOID_RATE_MAX,
            "note": ("剔除率的分母是**計畫的題數**，不是看到幾題："
                     "沒跑到的題也算沒量到。PC 的 void 不連坐、不進分子。")}


def rate_table(cells: list[dict], stratum: str, field: str) -> dict:
    out: dict = {}
    for arm in ("RS", "RF", "RP", "PC"):
        sel = [c for c in cells if c["stratum"] == stratum and c["arm"] == arm
               and not c["void"] and c.get(field) is not None]
        n = len(sel)
        p = sum(1 for c in sel if c[field])
        out[arm] = {"n": n, "pass": p, "rate": _rate(p, n)}
    return out


# ── 判定 ──────────────────────────────────────────────────────────────────

def evidence_for(cells: list[dict], stratum: str, *,
                 disabled: frozenset[str] = frozenset()) -> dict:
    """把一層的所有量算出來（**不下狀態**）。狀態在 `decide_stratum`。"""
    ev: dict = {"stratum": stratum, "m1_definition": M1_DEFINITION,
                "m1_why": M1_WHY}
    ev["void"] = void_stats(cells, stratum)
    ev["trigger"] = trigger_rate(
        cells, stratum, include_pc=("TRIGGER_EXCLUDES_PC" in disabled))
    ev["ceiling"] = ceiling_rate(cells, stratum)
    ev["m1"] = rate_table(cells, stratum, "m1")
    ev["m1_vis"] = {**rate_table(cells, stratum, "m1_vis"),
                    "not_a_test": True,
                    "why": "accepted-only，降為描述（見 m1_why）。"}
    ev["hidden_only"] = {**rate_table(cells, stratum, "hidden"),
                         "not_a_test": True,
                         "why": "凍結快照的 hidden 全過率，描述用。"}
    ev["m6"] = m6_stats(cells, stratum)
    ev["inconsistent"] = inconsistent_stats(cells, stratum)
    sel = [c for c in cells if c["stratum"] == stratum]
    #: L-4：三臂一起剔除。**四個配對量共用這一份題集**，否則 H1 與 H2 會
    #: 落在不同的題上，而那件事在輸出上看不出來。
    keep = set(ev["void"]["kept_task_ids"])

    # H1：**用 M1**（accepted ∧ hidden）
    h1_field = "m1_vis" if "H1_USES_M1" in disabled else "m1"
    h1 = bc_counts(sel, arm_a="RF", arm_b="RP", field=h1_field,
                   only_tasks=keep)
    h1["p_exact"] = mcnemar_exact(h1["b"], h1["c"])
    h1["basis"] = f"M1（{h1_field}）：{M1_DEFINITION}"
    ev["ci"] = ci_of(h1["diffs"])
    diffs = list(h1["diffs"])
    h1.pop("diffs", None)
    ev["h1"] = h1

    # M1_vis：**配對描述**（b、c、exact p、95% 區間），不進家族不進狀態表
    hv = bc_counts(sel, arm_a="RF", arm_b="RP", field="m1_vis",
                   only_tasks=keep)
    hv_ci = ci_of(hv["diffs"])
    hv.pop("diffs", None)
    ev["m1_vis_paired"] = {
        **hv, "p_exact": mcnemar_exact(hv["b"], hv["c"]), "ci": hv_ci,
        "in_family": False, "in_state_table": False,
        "why": ("accepted-only 會把「針對可見 case 打補丁」算成交付"
                "（＝M6），所以它只當描述。")}

    # H2：控制檢查（RF vs RS），**不進家族**，單獨 α = 0.05
    h2 = bc_counts(sel, arm_a="RS", arm_b="RF", field=h1_field,
                   only_tasks=keep)
    #: 護欄表第 4 列要求「不顯著也要印 95% 區間」⇒ H2 的區間一律算。
    #: 符號＝**RF − RS**（+1 ＝ RF 贏），與 STALE 的符號同一個約定。
    ev["h2_ci"] = ci_of(h2["diffs"])
    ev["h2_ci"]["sign"] = "+ ＝ RF 贏（＝RF − RS）"
    h2.pop("diffs", None)
    h2["p_exact"] = mcnemar_exact(h2["b"], h2["c"])
    h2.update({"in_family": False, "alpha": ALPHA,
               "reading": ("b2 ＝ RS 的 M1 = 0 ∧ RF 的 M1 = 1 ＝ RF 贏。"
                           "RF > RS 顯著多半是**多抽了兩次**，不是管道有效——"
                           "要先看 M7_file 與 M7_ws。")})
    ev["h2_control"] = h2

    # H3：RP vs RS，**降為描述**，不進家族不進狀態表
    h3 = bc_counts(sel, arm_a="RS", arm_b="RP", field=h1_field,
                   only_tasks=keep)
    h3.pop("diffs", None)
    h3["p_exact"] = mcnemar_exact(h3["b"], h3["c"])
    ev["h3_descriptive"] = {
        **h3, "in_family": False, "in_state_table": False,
        "why": ("RP 與 RS 同時差了兩件事（多抽兩次 ＋ 回饋進輸入），分不開。"
                "只印。")}

    ev["f6"] = f6_stats(cells, stratum)
    ev["m7_ws_solution"] = m7_ws_solution_stats(cells, stratum)
    ev["m7_file"] = m7_file_stats(
        cells, stratum, null_as_false=("M7_NULL_NOT_FALSE" in disabled))
    ev["m7_ws"] = m7_ws_stats(cells, stratum)
    ev["suspect_timeout_cells"] = sorted(
        c["cell"] for c in sel if c["suspect_timeout"])
    ev["invariants"] = invariants(cells, stratum)

    # TOST：**只印不裁**
    if diffs:
        t = tost_equiv_boot(diffs, TOST_DELTA, n_boot=BOOT_N, seed=BOOT_SEED)
        holds = bool(t["equivalent"])
        ev["tost"] = {
            "delta_pp": TOST_DELTA * 100, "mean": t["mean"],
            "ci_lo": t["ci_lo"], "ci_hi": t["ci_hi"],
            "alpha": 0.05, "ci_level": "90%（TOST 預設 α=0.05 ⇒ 1−2α）",
            "tost_holds": holds,
            "verdict": f"TOST（δ=15 pp）{'成立' if holds else '不成立'}",
            "reading": ("±15 pp 內未區分開" if holds else
                        "本輪的 n 不足以在 ±15 pp 內宣告未區分開"),
            "decides_nothing": True,
            "why": ("**只印不裁**：預註冊 §七-3 事前算過，即使真差是 0，"
                    "n=50 也只有 24/300 會讓它成立。不成立是「量不到」，"
                    "與 H1 顯著是兩件獨立的事。")}
        ev["wilcoxon"] = (
            {**wilcoxon_signed_rank_exact(diffs),
             "note": "與 McNemar 並列印出，不取代它。"}
            if any(d != 0 for d in diffs)
            else {"note": "全部配對差為 0，無秩可排。"})
    else:
        ev["tost"] = {"delta_pp": TOST_DELTA * 100, "tost_holds": None,
                      "verdict": "TOST（δ=15 pp）不成立",
                      "reading": "無配對可算", "decides_nothing": True}
        ev["wilcoxon"] = {"note": "無配對可算"}
    return ev


def divergence_note(ev: dict, p_holm: float, *,
                    disabled: frozenset[str] = frozenset()) -> dict:
    """事前寫死的分歧句：`M1_vis` 贏而 `M1` 不顯著 ⇒ 管道買到的是過閘門。

    反向（`M1` 贏而 `M1_vis` 不贏）在 hidden ⊇ visible 之下**不可能**；
    真的出現就是資料有問題，走 `inconsistent` 那條，不在這裡靜默吸收。
    """
    hv = ev["m1_vis_paired"]
    vis_rp_wins = hv["b"] > hv["c"] and hv["p_exact"] < ALPHA
    m1_ns = p_holm >= ALPHA
    m6 = ev["m6"]["by_arm"]["RP"]["rate"]
    fire = vis_rp_wins and m1_ns and "DIVERGENCE_NOTE" not in disabled
    h1 = ev["h1"]
    reverse = (h1["b"] > h1["c"]) and not (hv["b"] > hv["c"])
    return {
        "m1_vis_shows_rp_gt_rf": bool(vis_rp_wins),
        "m1_not_significant": bool(m1_ns),
        "fired": bool(fire),
        "m6_rp_rate": m6,
        "line": (DIVERGENCE_LINE.format(
            m6=("—" if m6 is None else f"{m6:.3f}")) if fire else None),
        "reverse_impossible_seen": bool(reverse),
        "reverse_rule": ("M1 贏而 M1_vis 不贏在 hidden ⊇ visible 下不可能；"
                         "出現 ⇒ 該格標 inconsistent、重算，不准靜默計入。"),
    }


def read_m7ws_selftest(path: pathlib.Path | None) -> dict:
    """讀 `m7_ws` 解析器的 `--selftest` 結果。**拿不到不可以當成綠。**

    接受兩種形狀（驅動那邊還在定，所以兩種都吃）：
    JSON（`{"ok": true}`／`{"all_ok": true}`／`{"verdict": "OK"}`／
    `{"selftest": "green"}`），或純文字檔內容為 `green`／`red`／`OK`／`FAIL`。
    看不懂 ⇒ `unavailable`，**不是 green**。
    """
    if path is None:
        return {"result": "unavailable", "reason": "沒有給 --m7ws-selftest",
                "path": None}
    if not path.exists():
        return {"result": "unavailable", "reason": f"檔案不存在：{path}",
                "path": str(path)}
    raw = path.read_text(encoding="utf-8").strip()
    try:
        doc = json.loads(raw)
    except Exception:                                        # noqa: BLE001
        low = raw.lower()
        if low in ("green", "ok", "pass", "passed", "true"):
            return {"result": "green", "reason": raw[:80], "path": str(path)}
        if low in ("red", "fail", "failed", "false"):
            return {"result": "red", "reason": raw[:80], "path": str(path)}
        return {"result": "unavailable", "reason": f"看不懂的內容：{raw[:80]}",
                "path": str(path)}
    if isinstance(doc, dict):
        for k in ("ok", "all_ok", "passed", "green"):
            if isinstance(doc.get(k), bool):
                return {"result": "green" if doc[k] else "red",
                        "reason": f"{k}={doc[k]}", "path": str(path)}
        for k in ("verdict", "selftest", "status"):
            v = doc.get(k)
            if isinstance(v, str):
                low = v.lower()
                if low in ("ok", "green", "pass", "passed"):
                    return {"result": "green", "reason": f"{k}={v}",
                            "path": str(path)}
                if low in ("fail", "red", "failed", "invalid"):
                    return {"result": "red", "reason": f"{k}={v}",
                            "path": str(path)}
    return {"result": "unavailable", "reason": "JSON 裡找不到判定欄位",
            "path": str(path)}


def control_state(ev: dict, *, m7ws_selftest: str = "unavailable",
                  disabled: frozenset[str] = frozenset()) -> dict:
    """RF／RS 控制鏈。**獨立、互斥、不在主鏈上**（可與主鏈任一狀態同時成立）。

    護欄表（2026-09-19 最後一輪裁決**整張換掉**，逐字）：

    | 觀測                                             | 狀態                       |
    |--------------------------------------------------|----------------------------|
    | RF ≠ RS 顯著（**任一方向**）∧ M7_file=0 ∧ M7_ws>0 | `STALE_WORKSPACE_EFFECT(±)` |
    | RF ≠ RS 顯著 ∧ M7_ws = 0                          | 先跑 m7_ws 解析器 `--selftest`：紅 ⇒ **M7_ws 這個指標判 `INVALID`**（量具壞了，不是 breach）；綠 ⇒ `MECHANISM_BREACH` |
    | M7_file > 10%（任一層）                           | `MECHANISM_BREACH`（預測被證偽） |
    | 不顯著                                            | 無狀態；印 (b,c)、p、95% 區間、TOST、M7_file、M7_ws、**M7_ws_solution** |

    **舊表那兩列（`RF < RS ⇒ BREACH`、`RF > RS ∧ m7_ws=0 ⇒ BREACH`）合併成
    第二列，方向不再進判準。** 起因是 NOTHINK 冒煙實測：pi 在不思考模式下
    **會去看工作區**（`m7_ws` 從 false 變 true）⇒「RF 與 RS 可交換」的預測撤回；
    而且 `RF < RS` 也不再是異常——`v1_real_pi` 三次嘗試寫出**同一份**
    `add_numbers`，模型看到自己上一份錯碼會**錨定在上面**，`resample` 重置
    工作區反而拿到乾淨的重抽。**「保留工作區」的效果兩個符號都可能。**

    ⚠ **H1 完全不受這一段影響**：RP 與 RF **都是 `revise`**（都保留工作區）
    ⇒ 那個效果在配對裡對消，H1 剩下的唯一差異仍是「回饋在不在模型輸入裡」。

    ⚠ 求值順序是本檔訂的（護欄表沒給）：M7_file>10% 先判，因為它不依賴
    `m7_ws` 這把量具；再判 STALE；再判 M7_ws=0 那一列。
    ⚠ 仍有一個**沒有覆蓋的區間**：顯著 ∧ `0 < M7_file ≤ 10%` ∧ `M7_ws > 0`
    （第 1 列要求 M7_file=0、第 3 列要求 >10%）。本檔不發明狀態，標 `gap`。
    """
    h2, m7f, m7w = ev["h2_control"], ev["m7_file"], ev["m7_ws"]
    sig = h2["p_exact"] < ALPHA and h2["b"] != h2["c"]
    rf_gt_rs = sig and h2["b"] > h2["c"]     # b2 ＝ RS 的 M1=0 ∧ RF 的 M1=1
    rf_lt_rs = sig and h2["c"] > h2["b"]
    sign = "+" if rf_gt_rs else ("−" if rf_lt_rs else None)
    m7f_rate = m7f["rate"]
    m7f_zero = (m7f_rate == 0.0)
    m7w_zero = (m7w["cells_with_other_calls"] == 0)
    # 「拿不到 ⇒ 不可以當成綠」。`M7WS_SELFTEST_GATE` 只給負向控制用。
    gate_green = (m7ws_selftest == "green") or \
        ("M7WS_SELFTEST_GATE" in disabled)
    reasons: list[str] = []
    state, gap = None, False
    if "BREACH_M7FILE" not in disabled and m7f_rate is not None \
            and m7f_rate > M7_FILE_BREACH:
        state = "MECHANISM_BREACH"
        reasons.append(f"M7_file={m7f_rate:.3f} > {M7_FILE_BREACH}"
                       f"（{m7f['hit']}/{m7f['denominator']}）："
                       "回饋文字出現在第 ≥2 次嘗試的請求裡，事前預測被證偽")
    elif sig and m7f_zero and not m7w_zero and "STALE_WS" not in disabled:
        state = f"STALE_WORKSPACE_EFFECT({sign})"
        reasons.append(
            f"RF {'>' if rf_gt_rs else '<'} RS 顯著（b2={h2['b']}, "
            f"c2={h2['c']}, p={h2['p_exact']:.4g}）而 M7_file=0、M7_ws>0"
            f"（{m7w['cells_with_other_calls']}/{m7w['n_measured']} 格）："
            "保留的工作區被摸過。**描述性、帶符號、不凍結任何句子**；"
            "符號＝RF − RS 的符號，兩個方向都可能（模型會錨定在自己上一份錯碼）。")
    elif sig and m7w_zero and "BREACH_WS_ZERO" not in disabled:
        if gate_green:
            state = "MECHANISM_BREACH"
            reasons.append(
                f"RF ≠ RS 顯著（b2={h2['b']}, c2={h2['c']}, "
                f"p={h2['p_exact']:.4g}）而 M7_ws=0，且 m7_ws 解析器的 "
                "--selftest 是綠的 ⇒ 量具沒壞，是機制模型解釋不了這個差")
        else:
            state = "M7_WS_INVALID"
            reasons.append(
                f"RF ≠ RS 顯著而 M7_ws=0，但 m7_ws 解析器的 --selftest "
                f"＝`{m7ws_selftest}`（不是綠）⇒ **判 `M7_ws` 這個指標 "
                "`INVALID`：量具壞了，不是機制壞了。** "
                "拿不到 selftest 結果一律不當成綠。"
                "⚠ 這只作廢 M7_ws，不作廢 H1、不作廢該層。")
    elif sig and m7f_rate is not None and 0.0 < m7f_rate <= M7_FILE_BREACH \
            and not m7w_zero:
        gap = True
        reasons.append(f"RF ≠ RS 顯著、M7_ws>0，而 M7_file={m7f_rate:.3f} 落在 "
                       f"(0, {M7_FILE_BREACH}]：**護欄表沒有覆蓋這一格**"
                       "（第 1 列要求 =0、第 3 列要求 >10%）。"
                       "本檔不發明狀態，提請人類補判準。")
    if state is None and not reasons:
        reasons.append("H2 不顯著（或 M7_file 未超標）⇒ 控制鏈無狀態。"
                       "照護欄表第 4 列，(b,c)、p、95% 區間、TOST、M7_file、"
                       "M7_ws、M7_ws_solution 照樣印。")
    return {"state": state, "sign": sign,
            "gap_uncovered_by_guardrail": gap, "reasons": reasons,
            "h2_significant": sig, "rf_gt_rs": rf_gt_rs, "rf_lt_rs": rf_lt_rs,
            "m7_file_rate": m7f_rate,
            "m7_ws_cells": m7w["cells_with_other_calls"],
            "m7_ws_selftest": m7ws_selftest,
            "independent_of_main_chain": True,
            "h1_unaffected": ("RP 與 RF 都是 revise（都保留工作區）⇒ 這個效果"
                              "在 H1 的配對裡對消。H1 的唯一差異仍是"
                              "「回饋在不在模型輸入裡」。"),
            "on_breach": ("該層所有引用 RF／RS 的句子凍結，不得當成果；"
                          "H1 仍可收官，但收官句必須帶「負控制異常，機制待查」。")}


def decide_stratum(ev: dict, p_holm: float, *,
                   reconcile_invalid: bool = False,
                   disabled: frozenset[str] = frozenset()) -> dict:
    """求值順序寫死（預註冊 §六-1）：**由上往下，第一個成立的就是狀態。**

        INVALID → NOT_TRIGGERED → CEILING_TOO_LOW → CONFIRMED_POSITIVE →
        CONFIRMED_NEGATIVE → RULED_OUT → INCONCLUSIVE

    不准跳號、不准回頭。`disabled` 只給 `--mutation-check` 用：拿掉一條判定式
    之後對應的樣本必須翻紅，否則那條判定式等於沒在跑。
    """
    trail: list[dict] = []
    h1, void, trig, ceil = ev["h1"], ev["void"], ev["trigger"], ev["ceiling"]
    b, c = h1["b"], h1["c"]
    sig = p_holm < ALPHA
    ci_hi = ev["ci"].get("ci_hi")

    def step(name: str, hit: bool, why: str) -> bool:
        trail.append({"state": name, "hit": bool(hit), "why": why,
                      "disabled": name in disabled})
        return hit and name not in disabled

    # 1. INVALID
    vr = void["void_rate"]
    rate_bad = vr is not None and vr > VOID_RATE_MAX
    inv = reconcile_invalid or rate_bad
    parts = []
    if reconcile_invalid:
        parts.append("reconcile 判 INVALID")
    parts.append(f"剔除率 {vr if vr is None else round(vr, 3)}"
                 f" {'>' if rate_bad else '≤'} {VOID_RATE_MAX}")
    if step("INVALID", inv, "；".join(parts)):
        return _verdict("INVALID", trail,
                        "該層**所有**數字不得引用，連描述性的都不行。")
    # 2. NOT_TRIGGERED（吃**可見** attempt-1 失敗率，PC 不在分母）
    fr = trig["attempt1_fail_rate"]
    nt = fr is not None and fr < trig["threshold"]
    if step("NOT_TRIGGERED", nt,
            f"三臂合併 attempt-1 可見失敗率 "
            f"{'—' if fr is None else round(fr, 3)}"
            f"（n={trig['n']}／預期 {trig['n_expected']}）"
            f" vs 門檻 < {trig['threshold']}；PC 不在分母"):
        return _verdict("NOT_TRIGGERED", trail,
                        "題庫沒有製造出窗口——管道問題根本沒被提出來。")
    # 3. CEILING_TOO_LOW（吃 PC 的**可見** attempt-1 通過率）
    cr = ceil["attempt1_pass_rate"]
    ct = cr is not None and cr < CEILING_PASS_THRESHOLD
    if step("CEILING_TOO_LOW", ct,
            f"PC attempt-1 可見通過率 {'—' if cr is None else round(cr, 3)}"
            f" vs 門檻 < {CEILING_PASS_THRESHOLD}"):
        return _verdict("CEILING_TOO_LOW", trail,
                        "題目對這顆模型太難，管道問題根本沒被提出來。")
    # 4. CONFIRMED_POSITIVE —— 方向寫死：**只有 RP > RF 才算**
    dir_ok = (b > c) or ("POS_DIRECTION" in disabled)
    f6_ok = ev["f6"]["all_ok"] or ("F6_GUARD" in disabled)
    if step("CONFIRMED_POSITIVE", sig and dir_ok and f6_ok,
            f"Holm 調整後 p={p_holm:.4g} < {ALPHA}? {sig}；"
            f"方向 b={b} > c={c}? {b > c}；F6 全格成立? {ev['f6']['all_ok']}"):
        return _verdict("CONFIRMED_POSITIVE", trail, None)
    # 5. CONFIRMED_NEGATIVE —— 方向寫死：**只有 RF > RP 才算**
    negdir = (c > b) or ("NEG_DIRECTION" in disabled)
    if step("CONFIRMED_NEGATIVE", sig and negdir,
            f"Holm 調整後 p={p_holm:.4g} < {ALPHA}? {sig}；"
            f"方向 c={c} > b={b}? {c > b}"):
        return _verdict("CONFIRMED_NEGATIVE", trail,
                        "把回饋塞進 argv 反而更差——這是一個真的結論，不是失敗。")
    # 6. RULED_OUT —— 95% 區間**上緣** < +15 pp（單邊）
    if step("RULED_OUT", (ci_hi is not None) and (ci_hi < RULED_OUT_UPPER),
            f"95% 區間上緣 {'—' if ci_hi is None else round(ci_hi, 4)}"
            f" < +{RULED_OUT_UPPER}?"):
        return _verdict("RULED_OUT", trail,
                        "本輪排除掉的是「RP 比 RF 高 15 pp 以上」這個大小的"
                        "效果，排除不掉更小的。")
    # 7. INCONCLUSIVE
    step("INCONCLUSIVE", True, "以上皆不成立（預設落點）")
    return _verdict("INCONCLUSIVE", trail,
                    "⚠ 這是**事前就預期的最可能落點**，不是失敗："
                    "預註冊 §七 事前算好 +10 pp 的真效果在 n=50 的檢定力只有 "
                    "0.086。「沒顯著」不可以讀成「沒有效果」。")


def _verdict(state: str, trail: list[dict], note: str | None) -> dict:
    return {"state": state, "chain": list(CHAIN_ORDER), "trail": trail,
            "note": note}


def closing_line(stratum: str, ev: dict, state: str, p_holm: float,
                 control: dict, diverge: dict) -> str:
    """收官句模板（預註冊 §六-3，逐字）＋ 分歧句。"""
    h1 = ev["h1"]
    n, b, c = h1["n_pairs"], h1["b"], h1["c"]
    mean = ev["ci"].get("mean_diff")
    tail = ("**這是對 `gemma-4-12b-it-qat` ＋ pi 0.85.1 ＋ 本題庫的結論，"
            "不可外推。**")
    if state == "CONFIRMED_POSITIVE":
        d = "—" if mean is None else f"{mean * 100:.1f}"
        s = (f"在 {stratum}（n={n}）上，把回饋接進 argv 相對於寫檔進工作區，"
             f"最終交付（accepted ∧ hidden）高 {d} pp"
             f"（b={b}, c={c}, Holm 調整後 p={p_holm:.4g}）。{tail}")
    elif state == "CONFIRMED_NEGATIVE":
        d = "—" if mean is None else f"{abs(mean) * 100:.1f}"
        s = (f"在 {stratum}（n={n}）上，把回饋接進 argv 相對於寫檔進工作區，"
             f"最終交付（accepted ∧ hidden）**低** {d} pp"
             f"（b={b}, c={c}, Holm 調整後 p={p_holm:.4g}）。{tail}")
    elif state == "INVALID":
        s = (f"{stratum} 判 `INVALID`：該層**所有**數字不得引用，"
             "連描述性的都不行。")
    elif state == "NOT_TRIGGERED":
        fr = ev["trigger"]["attempt1_fail_rate"]
        s = (f"{stratum} 判 `NOT_TRIGGERED`：三臂合併的 attempt-1 可見失敗率"
             f" {'—' if fr is None else round(fr, 3)} 低於門檻 "
             f"{ev['trigger']['threshold']}，題庫沒有製造出窗口。"
             "本層不得引用任何關於管道的結論。")
    elif state == "CEILING_TOO_LOW":
        cr = ev["ceiling"]["attempt1_pass_rate"]
        s = (f"{stratum} 判 `CEILING_TOO_LOW`：PC attempt-1 可見通過率 "
             f"{'—' if cr is None else round(cr, 3)} < "
             f"{CEILING_PASS_THRESHOLD}，題目對這顆模型太難。")
    elif state == "RULED_OUT":
        hi = ev["ci"].get("ci_hi")
        s = (f"在 {stratum}（n={n}）上，本輪把「RP 比 RF 高 "
             f"{RULED_OUT_UPPER * 100:.0f} pp 以上」排除掉了"
             f"（95% 區間上緣 {hi:.3f}）。**比這更小的效果沒有被排除。**")
    else:
        s = (f"在 {stratum}（n={n}）上，本輪**沒有區分開**兩條管道"
             f"（Holm 調整後 p={p_holm:.4g}）。"
             "依預註冊 §七 的事前檢定力表，本輪對 +10 pp 的真效果檢定力只有 "
             "0.086（n=50）／0.068（n=40），**「沒顯著」不可以讀成"
             "「沒有效果」。**")
    if diverge.get("fired"):
        s += diverge["line"] + "。"
    if control.get("state") == "MECHANISM_BREACH":
        m7f = control.get("m7_file_rate")
        d = "RF<RS" if control.get("rf_lt_rs") else (
            "RF>RS" if control.get("rf_gt_rs") else "—")
        s += (f"**負控制異常，機制待查**（H2 {d}，"
              f"M7_file={'—' if m7f is None else round(m7f, 3)}）。"
              "本層引用 RF／RS 的句子已凍結。")
    # ⚠ `STALE_WORKSPACE_EFFECT(±)` **不接在這一句後面**（裁決）：
    #   它與本輪主問題無關，接上去會讓人讀成 H1 的一部分。
    #   它自己一段，見 `stale_closing_line`。
    return s


def stale_closing_line(stratum: str, ev: dict, control: dict,
                       evidence_path: str) -> str | None:
    """`STALE_WORKSPACE_EFFECT(±)` 的收官句（逐字，**另起一段**）。

    ⚠ `M7_ws_solution == 0` 而 RF ≠ RS 顯著 ⇒ 改寫成
    「保留工作區被 `ls` 到但沒被讀、差異來源未定」。
    """
    st = control.get("state") or ""
    if not st.startswith("STALE_WORKSPACE_EFFECT"):
        return None
    h2, ci = ev["h2_control"], ev["h2_ci"]
    mw, ms = ev["m7_ws"], ev["m7_ws_solution"]
    mean = ci.get("mean_diff")
    more = "多" if (mean or 0) > 0 else "少"
    d = "—" if mean is None else f"{abs(mean) * 100:.1f}"
    lo = "—" if ci.get("ci_lo") is None else f"{ci['ci_lo'] * 100:.1f}"
    hi = "—" if ci.get("ci_hi") is None else f"{ci['ci_hi'] * 100:.1f}"
    y = (f"{mw['cells_with_other_calls']}/{mw['n_measured']}"
         f"＝{'—' if mw['rate'] is None else round(mw['rate'], 3)}")
    z = (f"{ms['hit']}/{ms['n_measured']}"
         f"＝{'—' if ms['rate'] is None else round(ms['rate'], 3)}")
    line = (f"在 {stratum}（n={h2['n_pairs']}）上，保留工作區的臂（RF）"
            f"比重置的臂（RS）{more}交付並通過隱藏測資 {d} pp"
            f"（95% 區間 {lo}–{hi} pp；b={h2['b']}, c={h2['c']}, "
            f"exact p={h2['p_exact']:.4g}，**未經家族校正**）；"
            f"M7_file=0、M7_ws={y}、M7_ws_solution={z}。"
            "**這是描述性觀測，與本輪主問題（回饋走哪條管道）無關；"
            "不得讀成 revise 與 resample 的優劣結論。**"
            f" 逐題工具序列見 {evidence_path}。")
    if ms["hit"] == 0:
        line += ("⚠ `M7_ws_solution = 0` 而 RF ≠ RS 顯著 ⇒ "
                 "**保留工作區被 `ls` 到但沒被讀、差異來源未定。**")
    return line


HONESTY: tuple[str, ...] = (
    "n 小、單一模型（gemma-4-12b-it-qat）、單一 agent（pi 0.85.1）、"
    "單一自造題庫 ⇒ 不可外推；換掉其中任何一個都要重跑。",
    "「檔案投遞失效」只是對**這條 argv、這個 agent**的結論，"
    "不是對 file 模式的普遍結論。會 ls 工作區的 agent 情況不同。",
    "M7_file 是單邊的：命中 0 只說明那三個字串沒出現在請求 body 裡。",
    "RF 與 RS 的差別不只有管道，還有「多抽兩次」——本設計沒有無回饋重抽臂，"
    "兩者在 RF 這一臂上分不開。H3（RP vs RS）降為描述，同一個理由。",
    "PC 不是「正確答案」的上界，是「把話講清楚」的上界；"
    "PC 低分不開「題目太難」與「我們的 explicit 版寫得不夠明白」。",
    "hidden 全過 ≠ 做對了：suitegauge 的單邊保證對隱藏套件一樣成立。"
    "M1 量的是「兩套驗收都過了」，M6 量的是「只過了看得到的那一套」。",
    "S1 與 S2 不是完全獨立的 90 題：s1_32_pct／s2_06_pct 與 s1_35_rle／"
    "s2_29_rle 跨層共用參考解 ⇒ 分開報不是慣例而是必要條件。",
    "一次 run 不是複製；每一個點估計都要當單次值讀（R460 的 +13.33 → "
    "五次複製 +0.83～+5.83 已經演過一次單次點估計是上偏的）。",
    "本輪講的是**可究責性**（讓依賴有根據）：`vacant run` 能強制的只有"
    "「沒過就不出貨」；「回饋一定出現在模型的輸入裡」不等於「不可忽略」。",
    "本輪不得與 R530／R532／R534／docs/VACANT_RUN.md §7.8 併表或併 n。",
)

DEVIATIONS: tuple[str, ...] = (
    "M1 的定義：預註冊 §三寫「最終**可見**通過率」；本檔照 2026-09-19 的更正"
    "用 `accepted ∧ hidden`（拒交強制 0），accepted-only 降為配對描述"
    "（M1_vis）。理由見 m1_why。資料不必重跑，只改讀哪一欄——但這一條要進"
    "預註冊附錄，引用時要說是哪一個 M1。",
    "b/c 字母：預註冊 §六-2 第 4／5 列與本檔的約定**相反**（鏡像）。",
    "RULED_OUT：預註冊 §六-2 第 6 列寫的是「H1 不顯著且 TOST 成立」；"
    "本檔照 2026-09-19 的指示改成「95% 區間上緣 < +15 pp（單邊，boot_ci "
    "2.5/97.5）」，TOST **只印不裁**。兩者不是同一個判準。",
    "M7_file 的分母：預註冊 §三寫「RF 有第 ≥2 次嘗試的格數」；本檔只收"
    "**真的量到**的格（m7_file 非 null），並另印「有重試卻量不到」的格數。"
    "照字面做會把「量不到」變成「沒發生」，違反鐵律 3。",
    "護欄表在「顯著 ∧ 0 < M7_file ≤ 10% ∧ M7_ws > 0」沒有覆蓋（第 1 列要求 "
    "M7_file=0、第 3 列要求 >10%）；本檔標 gap，不發明狀態。",
    "護欄表沒有給列與列之間的求值順序；本檔訂為 M7_file>10% → STALE → "
    "M7_ws=0 那一列，理由是第一條不依賴 m7_ws 那把量具。",
    "M7_file > 10%「任一層」：本檔**逐層**判定，另出 run 層級的 "
    "mechanism_breach_any_stratum 讓保守讀法也看得到。",
)


#: `STALE_WORKSPACE_EFFECT` 收官句裡「逐題工具序列見 <路徑>」的預設寫法。
#: 原始清單落在每一格的 `cell.json`（`run_r535.py::measure_m7_ws` 寫的）。
EVIDENCE_PATH_TMPL = "<run>/cells/<task_id>__RF/cell.json 的 m7_ws_calls"


def analyse(cells: list[dict], *, reconcile_invalid: bool = False,
            m7ws_selftest: str = "unavailable",
            evidence_path: str = EVIDENCE_PATH_TMPL,
            disabled: frozenset[str] = frozenset()) -> dict:
    """整份判定。**Holm 家族固定大小 2（{H1-S1, H1-S2}），不依資料伸縮。**"""
    apply_m1(cells, disabled=disabled)
    ev = {s: evidence_for(cells, s, disabled=disabled) for s in STRATA}
    # 一層算不出 p（沒有配對）時仍佔家族一格，用 p=1.0 補位：
    # 家族大小是預註冊凍結的 2，不准因為資料少了就變 1。
    raw = [1.0 if ev[s]["h1"]["p_exact"] is None else ev[s]["h1"]["p_exact"]
           for s in STRATA]
    holm = holm_bonferroni(raw)
    out: dict = {"family": {"members": list(FAMILY), "size": len(FAMILY),
                            "raw_p": raw, "holm_p": holm,
                            "method": "vacant/research.py::holm_bonferroni",
                            "note": ("家族大小固定 2：一層算不出 p 時用 1.0 "
                                     "補位，不縮家族。")},
                 "per_stratum": {}, "state": {}, "control": {},
                 "divergence": {}, "closing": {}, "closing_control": {},
                 "m7_ws_selftest": m7ws_selftest}
    for i, s in enumerate(STRATA):
        ctrl = control_state(ev[s], m7ws_selftest=m7ws_selftest,
                             disabled=disabled)
        div = divergence_note(ev[s], holm[i], disabled=disabled)
        v = decide_stratum(ev[s], holm[i],
                           reconcile_invalid=reconcile_invalid,
                           disabled=disabled)
        out["per_stratum"][s] = {**ev[s], "p_holm": holm[i], "decision": v}
        out["state"][s] = v["state"]
        out["control"][s] = ctrl
        out["divergence"][s] = div
        out["closing"][s] = closing_line(s, ev[s], v["state"], holm[i],
                                         ctrl, div)
        out["closing_control"][s] = stale_closing_line(s, ev[s], ctrl,
                                                       evidence_path)
    out["mechanism_breach_any_stratum"] = any(
        out["control"][s]["state"] == "MECHANISM_BREACH" for s in STRATA)
    out["report_rule"] = ("S1／S2 **分開報，不合併**：兩對題跨層共用參考解，"
                          "合併會把它們當成四個獨立觀測。")
    out["conventions"] = {"m1": M1_DEFINITION, "m1_why": M1_WHY,
                          "bc": BC_CONVENTION,
                          "why_not_discordance": WHY_NOT_DISCORDANCE}
    out["honesty_bounds"] = list(HONESTY)
    out["deviations_from_prereg"] = list(DEVIATIONS)
    return out


# ── 負向控制：把判定式拿掉，看樣本會不會翻紅 ───────────────────────────────

def _cell(task, arm, stratum, *, accepted, hidden=None, a1=None,
          m7_file=None, m7_ws=None, m7_ws_solution=None, f6=None,
          attempts=1, void=False, stop_reason=None):
    """手工格。`hidden` 預設跟著 `accepted`（＝沒有 M6 殘餘的乾淨格）。"""
    return {"cell": f"{task}__{arm}", "task_id": task, "arm": arm,
            "stratum": stratum, "void": void,
            "void_reason": "fixture" if void else None,
            "accepted": accepted,
            "hidden": accepted if hidden is None else hidden,
            "stop_reason": stop_reason or ("visible_pass" if accepted
                                           else "attempts_exhausted"),
            "attempt1_visible": accepted if a1 is None else a1,
            "attempt1_hidden": accepted if a1 is None else a1,
            "attempts_used": attempts, "m7_file": m7_file, "m7_ws": m7_ws,
            "m7_ws_ratio": None, "m7_ws_solution": m7_ws_solution,
            "f6": f6, "suspect_timeout": False, "requests_seen": 4}


def fixture(kind: str) -> list[dict]:
    """手工樣本。**每一個都是為了打一條判定式而造的，不是「示範資料」。**"""
    cells: list[dict] = []

    def quad(t, *, rs, rf, rp, pc=True, rs_h=None, rf_h=None, rp_h=None,
             pc_h=None, a1=False, m7f=False, m7w=False, m7sol=None):
        cells.extend([
            _cell(t, "RS", "S1", accepted=rs, hidden=rs_h, a1=a1),
            _cell(t, "RF", "S1", accepted=rf, hidden=rf_h, a1=a1,
                  m7_file=m7f, m7_ws=m7w, m7_ws_solution=m7sol, attempts=3),
            _cell(t, "RP", "S1", accepted=rp, hidden=rp_h, a1=a1, f6=True,
                  attempts=3),
            _cell(t, "PC", "S1", accepted=pc, hidden=pc_h, a1=True)])

    if kind == "rf_wins":
        # 14 題 RF 贏（c）、1 題 RP 贏（b）⇒ 精確雙尾 p ≈ 0.001
        for i in range(50):
            quad(f"s1_{i:02d}", rs=False, rf=(i >= 1), rp=(i >= 15))
    elif kind == "rp_wins":
        for i in range(50):
            quad(f"s1_{i:02d}", rs=False, rf=(i >= 15), rp=(i >= 1))
    elif kind in ("rf_gt_rs_stale", "rf_gt_rs_nostale"):
        # RF > RS 顯著（RF 多贏 15 題）。`_stale` 版 m7_ws=true 且讀過自己的解。
        stale = kind.endswith("_stale")
        for i in range(50):
            quad(f"s1_{i:02d}", rs=False, rf=(i >= 15), rp=(i >= 15),
                 m7w=stale, m7sol=(True if stale else False))
    elif kind in ("rs_gt_rf_stale", "rs_gt_rf_stale_unread"):
        # **RF < RS 顯著**（RS 多贏 15 題）且 m7_ws>0 ⇒ 要出 STALE(−)。
        # `_unread` 版 m7_ws_solution 全 false ⇒ 收官句要改寫成「差異來源未定」。
        read_own = not kind.endswith("_unread")
        for i in range(50):
            quad(f"s1_{i:02d}", rs=True, rf=(i >= 15), rp=(i >= 15),
                 m7w=True, m7sol=read_own)
    elif kind == "pc_pollutes_trigger":
        # RS/RF/RP 的 attempt-1 失敗率 ＝ 0.62（≥ 0.6 ⇒ 不該 NOT_TRIGGERED）；
        # 把 PC（attempt-1 全過）混進分母 ⇒ 0.465 < 0.6 ⇒ 假觸發
        for i in range(50):
            a1 = i >= 31                       # 31/50 失敗 ＝ 0.62
            quad(f"s1_{i:02d}", rs=a1, rf=a1, rp=(i >= 1), a1=a1)
    elif kind == "m7_null_not_false":
        # 20 格 RF：2 格量到且命中、18 格 null（沒有第 2 次嘗試）
        # 正確：2/2 = 1.0 > 0.10 ⇒ MECHANISM_BREACH
        # 把 null 當 false：2/20 = 0.10，**不** > 0.10 ⇒ 漏掉
        for i in range(20):
            t = f"s1_{i:02d}"
            measured = i < 2
            cells.extend([
                _cell(t, "RS", "S1", accepted=False, a1=False),
                _cell(t, "RF", "S1", accepted=False, a1=False,
                      m7_file=(True if measured else None), m7_ws=False,
                      attempts=(3 if measured else 1)),
                _cell(t, "RP", "S1", accepted=True, a1=False, f6=True,
                      attempts=3),
                _cell(t, "PC", "S1", accepted=True, a1=True)])
    elif kind == "order_not_triggered_beats_positive":
        # attempt-1 失敗率 0（⇒ NOT_TRIGGERED）但 b≫c 且顯著（⇒ 會是 POSITIVE）
        for i in range(50):
            quad(f"s1_{i:02d}", rs=True, rf=(i >= 15), rp=True, a1=True)
    elif kind == "vis_vs_m1_opposite":
        # M1_vis：RP 贏 15（b=15, c=0）——只過閘門，hidden 沒過
        # M1    ：RF 贏 10（b=0, c=10）——方向相反
        for i in range(50):
            t = f"s1_{i:02d}"
            if i < 15:
                quad(t, rs=False, rf=False, rp=True, rp_h=False)
            elif i < 25:
                quad(t, rs=False, rf=True, rp=True, rp_h=False)
            else:
                quad(t, rs=False, rf=True, rp=True)
    elif kind == "refused_but_hidden_passes":
        # 15 格 RP 拒交（accepted=False）但凍結快照 hidden 全過
        #   正確：M1=0 ⇒ RF 贏 15 ⇒ CONFIRMED_NEGATIVE
        #   拿掉「M1 要求 accepted」：那 15 格被算成 1 ⇒ 打平 ⇒ INCONCLUSIVE
        for i in range(50):
            t = f"s1_{i:02d}"
            if i < 15:
                quad(t, rs=False, rf=True, rp=False, rp_h=True)
            else:
                quad(t, rs=False, rf=True, rp=True)
    elif kind == "divergence_m6":
        # M1_vis：RP 贏 15 且顯著；M1：兩邊都 0 ⇒ b=c=0 ⇒ 不顯著
        for i in range(50):
            t = f"s1_{i:02d}"
            if i < 15:
                quad(t, rs=False, rf=False, rp=True, rp_h=False)
            else:
                quad(t, rs=False, rf=True, rp=True)
    else:
        raise ValueError(f"未知樣本：{kind}")
    return cells


#: 主鏈負向控制：(樣本, 拿掉哪條判定式, 正路答案, 拿掉之後必須變成什麼)
#: **「必須變成什麼」不准與正路答案相同**——結果一樣＝那條判定式沒在跑。
MUTATIONS: tuple[tuple[str, str, str, str], ...] = (
    # 拿掉方向護欄之後掉到哪一格是**求值順序**決定的，不是我們選的：
    # RF 贏 ⇒ 均差為負 ⇒ 95% 上緣 < +15 pp ⇒ 落 RULED_OUT；
    # RP 贏 ⇒ 均差為正且上緣 > +15 pp ⇒ 落 INCONCLUSIVE。
    ("rf_wins", "CONFIRMED_NEGATIVE", "CONFIRMED_NEGATIVE", "RULED_OUT"),
    ("rp_wins", "CONFIRMED_POSITIVE", "CONFIRMED_POSITIVE", "INCONCLUSIVE"),
    ("pc_pollutes_trigger", "TRIGGER_EXCLUDES_PC", "CONFIRMED_POSITIVE",
     "NOT_TRIGGERED"),
    ("order_not_triggered_beats_positive", "NOT_TRIGGERED", "NOT_TRIGGERED",
     "CONFIRMED_POSITIVE"),
    ("vis_vs_m1_opposite", "H1_USES_M1", "CONFIRMED_NEGATIVE",
     "CONFIRMED_POSITIVE"),
    # 拿掉「M1 要求 accepted」⇒ 那 15 格拒交被算成交付 ⇒ 全數打平
    # ⇒ 逐題配對差全是 0 ⇒ 95% 上緣 0 < +15 pp ⇒ 落 RULED_OUT。
    ("refused_but_hidden_passes", "M1_REQUIRES_ACCEPTED", "CONFIRMED_NEGATIVE",
     "RULED_OUT"),
)

#: 控制鏈與分歧句的負向控制
#: (樣本, 拿掉哪條, m7_ws selftest, 正路答案, 拿掉之後)
MUTATIONS_CONTROL: tuple[tuple[str, str, str, str | None, str | None], ...] = (
    ("rf_gt_rs_nostale", "BREACH_WS_ZERO", "green", "MECHANISM_BREACH", None),
    ("rf_gt_rs_stale", "STALE_WS", "green", "STALE_WORKSPACE_EFFECT(+)", None),
    ("rs_gt_rf_stale", "STALE_WS", "green", "STALE_WORKSPACE_EFFECT(−)", None),
    ("m7_null_not_false", "M7_NULL_NOT_FALSE", "green", "MECHANISM_BREACH",
     None),
    # 「拿不到 selftest ⇒ 不可以當成綠」：拿掉那道閘 ⇒ 變成 BREACH（假警報）
    ("rf_gt_rs_nostale", "M7WS_SELFTEST_GATE", "unavailable", "M7_WS_INVALID",
     "MECHANISM_BREACH"),
)


def mutation_check() -> dict:
    """把每一條判定式逐一拿掉，證明對應的樣本真的翻紅。"""
    rows: list[dict] = []
    for kind, key, want, want_off in MUTATIONS:
        on = analyse(fixture(kind))["state"]["S1"]
        off = analyse(fixture(kind), disabled=frozenset({key}))["state"]["S1"]
        rows.append({"fixture": kind, "removed": key, "layer": "state",
                     "on": on, "off": off, "want_on": want,
                     "want_off": want_off,
                     "ok": (on == want and off == want_off), "flipped": on != off})
    for kind, key, gate, want, want_off in MUTATIONS_CONTROL:
        on = analyse(fixture(kind),
                     m7ws_selftest=gate)["control"]["S1"]["state"]
        off = analyse(fixture(kind), m7ws_selftest=gate,
                      disabled=frozenset({key}))["control"]["S1"]["state"]
        rows.append({"fixture": kind, "removed": key, "layer": "control",
                     "gate": gate, "on": on, "off": off, "want_on": want,
                     "want_off": want_off,
                     "ok": (on == want and off == want_off), "flipped": on != off})
    # 分歧句（M6）的負向控制
    on = analyse(fixture("divergence_m6"))["divergence"]["S1"]["fired"]
    off = analyse(fixture("divergence_m6"),
                  disabled=frozenset({"DIVERGENCE_NOTE"}))["divergence"]["S1"]["fired"]
    rows.append({"fixture": "divergence_m6", "removed": "DIVERGENCE_NOTE",
                 "layer": "divergence", "on": on, "off": off,
                 "want_on": True, "want_off": False,
                 "ok": (on is True and off is False), "flipped": on != off})
    return {"rows": rows, "all_ok": all(r["ok"] for r in rows),
            "rule": ("每一條判定式拿掉之後，對應樣本的結論**必須**改變。"
                     "沒改變 ⇒ 那條判定式等於沒在跑，"
                     "跟把它註解掉在輸出上同形。")}


def selftest() -> dict:
    """離線自檢：方向、分母、順序、M1 vs M1_vis、拒交強制 0，各一條。"""
    checks: list[dict] = []

    def ck(name: str, ok: bool, detail: str):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    rp = analyse(fixture("rp_wins"))
    h1 = rp["per_stratum"]["S1"]["h1"]
    ck("bc_direction_rp_wins_b_gt_c", h1["b"] > h1["c"],
       f"b={h1['b']}（RF 的 M1=0 ∧ RP 的 M1=1）> c={h1['c']}")
    ck("rp_wins_is_positive", rp["state"]["S1"] == "CONFIRMED_POSITIVE",
       rp["state"]["S1"])
    rf = analyse(fixture("rf_wins"))
    ck("rf_wins_is_negative_not_positive",
       rf["state"]["S1"] == "CONFIRMED_NEGATIVE", rf["state"]["S1"])
    sp = analyse(fixture("rf_gt_rs_stale"), m7ws_selftest="green")
    ck("stale_ws_plus_not_breach",
       sp["control"]["S1"]["state"] == "STALE_WORKSPACE_EFFECT(+)",
       str(sp["control"]["S1"]["state"]))
    sm = analyse(fixture("rs_gt_rf_stale"), m7ws_selftest="green")
    ck("stale_ws_minus_not_breach",
       sm["control"]["S1"]["state"] == "STALE_WORKSPACE_EFFECT(−)",
       str(sm["control"]["S1"]["state"]))
    ck("stale_closing_is_its_own_paragraph",
       sm["closing_control"]["S1"] is not None
       and sm["closing_control"]["S1"] not in sm["closing"]["S1"]
       and "M7_ws_solution=" in sm["closing_control"]["S1"],
       (sm["closing_control"]["S1"] or "")[:100])
    un = analyse(fixture("rs_gt_rf_stale_unread"), m7ws_selftest="green")
    ck("unread_workspace_line_is_rewritten",
       "差異來源未定" in (un["closing_control"]["S1"] or ""),
       (un["closing_control"]["S1"] or "")[-60:])
    br = analyse(fixture("rf_gt_rs_nostale"),
                 m7ws_selftest="green")["control"]["S1"]["state"]
    ck("ws_zero_with_green_selftest_is_breach", br == "MECHANISM_BREACH",
       str(br))
    iv = analyse(fixture("rf_gt_rs_nostale"),
                 m7ws_selftest="unavailable")["control"]["S1"]["state"]
    ck("ws_zero_without_selftest_is_m7ws_invalid", iv == "M7_WS_INVALID",
       str(iv))
    pc = analyse(fixture("pc_pollutes_trigger"))
    ck("pc_not_in_trigger_denominator",
       pc["state"]["S1"] != "NOT_TRIGGERED"
       and pc["per_stratum"]["S1"]["trigger"]["n"] == 150,
       f"state={pc['state']['S1']}, n={pc['per_stratum']['S1']['trigger']['n']}")
    nn = analyse(fixture("m7_null_not_false"))
    ck("m7_null_not_counted_as_false",
       nn["control"]["S1"]["state"] == "MECHANISM_BREACH"
       and nn["per_stratum"]["S1"]["m7_file"]["denominator"] == 2,
       f"denominator={nn['per_stratum']['S1']['m7_file']['denominator']}")
    od = analyse(fixture("order_not_triggered_beats_positive"))
    ck("order_not_triggered_before_positive",
       od["state"]["S1"] == "NOT_TRIGGERED", od["state"]["S1"])
    vo = analyse(fixture("vis_vs_m1_opposite"))["per_stratum"]["S1"]
    ck("h1_uses_m1_not_accepted_only",
       vo["h1"]["c"] == 10 and vo["h1"]["b"] == 0
       and vo["m1_vis_paired"]["b"] == 15,
       f"M1 b/c={vo['h1']['b']}/{vo['h1']['c']}；"
       f"M1_vis b/c={vo['m1_vis_paired']['b']}/{vo['m1_vis_paired']['c']}")
    rb = analyse(fixture("refused_but_hidden_passes"))
    bad = [c for c in fixture("refused_but_hidden_passes")
           if c["cell"] == "s1_00__RP"]
    apply_m1(bad)
    ck("refused_forces_m1_zero",
       bad[0]["m1"] is False and bad[0]["inconsistent"] is True
       and rb["state"]["S1"] == "CONFIRMED_NEGATIVE",
       f"m1={bad[0]['m1']} inconsistent={bad[0]['inconsistent']} "
       f"state={rb['state']['S1']}")
    dv = analyse(fixture("divergence_m6"))["divergence"]["S1"]
    ck("divergence_line_fires_with_m6", dv["fired"] and dv["m6_rp_rate"] == 0.3,
       f"line={dv['line']}")
    d = check_diction(rp)
    ck("diction_clean", d["ok"], str(d["hits"]))
    return {"checks": checks, "all_ok": all(c["ok"] for c in checks)}


# ── 報表 ──────────────────────────────────────────────────────────────────

def render(doc: dict) -> str:
    L: list[str] = []
    L.append(f"R535 收官判定　{doc['generated_at']}")
    L.append(f"  scores    : {doc['inputs']['scores']}")
    L.append(f"  reconcile : {doc['inputs']['reconcile']}"
             f"  verdict={doc['inputs']['reconcile_verdict']}")
    L.append(f"  M1        : {M1_DEFINITION}")
    L.append(f"  Holm 家族 : {doc['family']['members']}（大小 "
             f"{doc['family']['size']}）"
             f"  raw={[round(p, 5) for p in doc['family']['raw_p']]}"
             f"  holm={[round(p, 5) for p in doc['family']['holm_p']]}")
    L.append("")
    for s in STRATA:
        ps, c, dv = doc["per_stratum"][s], doc["control"][s], doc["divergence"][s]
        L.append(f"── {s} ──────────────────────────────────────────")
        L.append(f"  狀態        : {doc['state'][s]}")
        L.append(f"  控制鏈      : {c['state'] or '（無異常）'}"
                 + ("  ⚠ 護欄未覆蓋" if c["gap_uncovered_by_guardrail"] else ""))
        v = ps["void"]
        L.append(f"  剔除        : {v['n_excluded']} 題（RS/RF/RP 一起）"
                 f"／計畫 {v['n_tasks_planned']} 題，看到 {v['n_tasks_seen']} 題"
                 f"　剔除率 {v['void_rate']}")
        t = ps["trigger"]
        L.append(f"  觸發率      : attempt-1 可見失敗 {t['attempt1_fail']}/"
                 f"{t['n']}（預期 n={t['n_expected']}）＝{t['attempt1_fail_rate']}"
                 f"　門檻 <{t['threshold']}　PC 不在分母＝{t['pc_excluded']}")
        ce = ps["ceiling"]
        L.append(f"  天花板(PC)  : attempt-1 可見通過 {ce['attempt1_pass']}/"
                 f"{ce['n']}＝{ce['attempt1_pass_rate']}　門檻 <{ce['threshold']}")
        L.append("  M1 逐臂     : " + "  ".join(
            f"{a}={ps['m1'][a]['pass']}/{ps['m1'][a]['n']}"
            for a in ("RS", "RF", "RP", "PC")))
        L.append("  M1_vis 逐臂 : " + "  ".join(
            f"{a}={ps['m1_vis'][a]['pass']}/{ps['m1_vis'][a]['n']}"
            for a in ("RS", "RF", "RP", "PC")) + "　**描述**")
        L.append("  M6（可見過而隱藏沒過）: " + "  ".join(
            f"{a}={ps['m6']['by_arm'][a]['hit']}/{ps['m6']['by_arm'][a]['n']}"
            for a in ("RS", "RF", "RP", "PC")))
        h1 = ps["h1"]
        L.append(f"  H1(M1)      : b={h1['b']}（RP 贏）c={h1['c']}（RF 贏）"
                 f"  n_pairs={h1['n_pairs']}  p={h1['p_exact']:.5g}"
                 f"  Holm p={ps['p_holm']:.5g}")
        hv = ps["m1_vis_paired"]
        L.append(f"  M1_vis 配對 : b={hv['b']} c={hv['c']} "
                 f"p={hv['p_exact']:.5g}"
                 + (f"  95% [{hv['ci']['ci_lo']:.4f}, {hv['ci']['ci_hi']:.4f}]"
                    if hv["ci"].get("ci_hi") is not None else "")
                 + "　**不進家族不進狀態表**")
        h2, h2ci = ps["h2_control"], ps["h2_ci"]
        L.append(f"  H2(RF vs RS): b2={h2['b']}（RF 贏）c2={h2['c']}"
                 f"  p={h2['p_exact']:.5g}（不進家族）"
                 + (f"  95% [{h2ci['ci_lo']:.4f}, {h2ci['ci_hi']:.4f}]"
                    "（+ ＝ RF 贏）" if h2ci.get("ci_hi") is not None else ""))
        h3 = ps["h3_descriptive"]
        L.append(f"  H3(RP vs RS): b={h3['b']} c={h3['c']} "
                 f"p={h3['p_exact']:.5g}　**只印**")
        mf, mw = ps["m7_file"], ps["m7_ws"]
        L.append(f"  M7_file     : {mf['hit']}/{mf['denominator']}"
                 f"＝{mf['rate']}　null={mf['null']}"
                 f"（其中有重試卻量不到 {mf['n_retried_unmeasured']}）")
        L.append(f"  M7_ws       : {mw['cells_with_other_calls']}/"
                 f"{mw['n_measured']}＝{mw['rate']}"
                 f"　解析器 --selftest={doc['m7_ws_selftest']}")
        ms = ps["m7_ws_solution"]
        L.append(f"  M7_ws_solution: {ms['hit']}/{ms['n_measured']}"
                 f"＝{ms['rate']}　null={ms['null']}　**不進判準**")
        f6 = ps["f6"]
        L.append(f"  F6          : true={f6['true']} false={f6['false']} "
                 f"null_with_retry={f6['null_with_retry']} "
                 f"all_ok={f6['all_ok']}")
        ci = ps["ci"]
        if ci.get("ci_hi") is not None:
            L.append(f"  區間(M1)    : 均差 {ci['mean_diff']:.4f}"
                     f"  95% [{ci['ci_lo']:.4f}, {ci['ci_hi']:.4f}]"
                     "（+ ＝ RP 贏）")
        else:
            L.append("  區間(M1)    : 無配對可算")
        to = ps["tost"]
        L.append(f"  TOST        : {to['verdict']}　{to['reading']}"
                 "　（只印不裁）")
        ic = ps["inconsistent"]
        if ic["n"]:
            L.append(f"  ⚠ inconsistent {ic['n']} 格（hidden 過而拒交）"
                     f"：{ic['cells'][:6]}　M1 記 0，交回 ops 重算")
        if ps["suspect_timeout_cells"]:
            L.append(f"  ⚠ suspect_timeout {len(ps['suspect_timeout_cells'])} 格"
                     "：L-4 的重算是 ops 的事，本檔沒有替它做")
        iv = ps["invariants"]
        if iv["i4_single_shot_arms_retried"]["n"]:
            L.append(f"  ⚠ I-4 破：{iv['i4_single_shot_arms_retried']['n']} 格 "
                     "RS／PC 的 attempts_used ≠ 1"
                     f"（{iv['i4_single_shot_arms_retried']['cells'][:4]}）"
                     "——那一格不是用該臂的旗標跑的。本檔只出聲不改狀態")
        if iv["i5_not_mediated"]["n"]:
            L.append(f"  ⚠ I-5 破：{iv['i5_not_mediated']['n']} 格 "
                     "requests_seen = 0（agent 根本沒被中介到）")
        if dv["fired"]:
            L.append(f"  ⚠ 分歧句：{dv['line']}")
        L.append("  求值軌跡：")
        for stp in ps["decision"]["trail"]:
            L.append(f"    {'✔' if stp['hit'] else '·'} {stp['state']:<20} "
                     f"{stp['why']}")
        L.append(f"  收官句：{doc['closing'][s]}")
        if doc["closing_control"][s]:
            # **另起一段**：它與本輪主問題無關，接在 H1 句後會被讀成 H1 的一部分。
            L.append("")
            L.append(f"  〔控制鏈另記，與主問題無關〕{doc['closing_control'][s]}")
        for r in c["reasons"]:
            L.append(f"  控制鏈說明：{r}")
        L.append("")
    L.append("口徑檢查："
             + ("綠" if doc["diction"]["ok"] else "紅 " + str(doc["diction"]["hits"])))
    L.append(doc["report_rule"])
    return "\n".join(L)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="state_r535.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "R535 收官判定器：把預註冊 §六 的狀態表變成程式。"
            "零模型呼叫、離線、確定性。\n"
            "結果變數：M1 ≡ accepted ∧ hidden 全過（拒交強制 0）＝**主要**；"
            "M1_vis ≡ accepted ＝配對描述，不進家族不進狀態表。\n"
            "求值順序（寫死）：INVALID → NOT_TRIGGERED → CEILING_TOO_LOW → "
            "CONFIRMED_POSITIVE → CONFIRMED_NEGATIVE → RULED_OUT → "
            "INCONCLUSIVE。\n"
            'MECHANISM_BREACH／STALE_WORKSPACE_EFFECT(±)／M7_WS_INVALID 在 '
            'RF／RS 控制鏈上，獨立、互斥、不在主鏈上。護欄表 2026-09-19 換版：'
            '方向不再進判準（STALE 帶符號），M7_ws=0 那一列要先看 m7_ws '
            '解析器的 --selftest——拿不到不當成綠。'),
        epilog=(
            "方向凍結：b ≡ RF 的 M1 = 0 ∧ RP 的 M1 = 1（＝RP 贏）；"
            "H2 同形 b2 ≡ RS 的 M1 = 0 ∧ RF 的 M1 = 1。\n"
            "⚠ 預註冊 §六-2 第 4／5 列的字母與這個約定相反（鏡像）。\n"
            "不借用 research.discordance：它只讀 .passed_gt、忽略拒交、"
            "方向與預註冊散文相反。\n"
            "S1／S2 分開報，任何情況下不合併。"))
    ap.add_argument("--out", default=None,
                    help="run 目錄（自動找最新的 scores_*.json 與 reconcile.json）")
    ap.add_argument("--scores", default=None,
                    help="score_r535.py 產的 scores_*.json（覆寫 --out 的自動尋找）")
    ap.add_argument("--reconcile", default=None,
                    help="run_r535.py --reconcile 產的 reconcile.json")
    ap.add_argument("--no-reconcile", action="store_true",
                    help="不讀 reconcile.json。⚠ 那代表 INVALID 的第一個條件"
                         "（對帳）沒有被檢查過，輸出會標明")
    ap.add_argument("--m7ws-selftest", default=None,
                    help="`m7_ws` 解析器 --selftest 的結果檔（JSON 或 "
                         "green/red 一行）。**進判準**：護欄表第 2 列在 "
                         "M7_ws=0 時要靠它分辨「量具壞了」與「機制壞了」。"
                         "⚠ 沒給＝拿不到＝**不當成綠**")
    ap.add_argument("--json", default=None, help="判定落點（預設只印到 stdout）")
    ap.add_argument("--selftest", action="store_true",
                    help="跑離線自檢（手工樣本，零 I/O）")
    ap.add_argument("--mutation-check", action="store_true",
                    help="負向控制：逐條拿掉判定式，證明對應樣本會翻紅")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest or args.mutation_check:
        rc = 0
        if args.selftest:
            st = selftest()
            for c in st["checks"]:
                print(f"  [{'綠' if c['ok'] else '紅'}] {c['check']:<38} "
                      f"{c['detail'][:110]}")
            print(f"selftest: {'全綠' if st['all_ok'] else '有紅'}")
            rc |= 0 if st["all_ok"] else 1
        if args.mutation_check:
            mc = mutation_check()
            for r in mc["rows"]:
                print(f"  [{'綠' if r['ok'] else '紅'}] {r['fixture']:<34}"
                      f" −{r['removed']:<24} {r['on']} → {r['off']}"
                      f"（要 {r['want_on']} → {r['want_off']}）")
            print(f"mutation-check: {'全綠' if mc['all_ok'] else '有紅'}")
            print(f"  {mc['rule']}")
            rc |= 0 if mc["all_ok"] else 1
        return rc

    if not args.scores and not args.out:
        raise SystemExit("要 --out <run 目錄> 或 --scores <scores_*.json>")
    out = pathlib.Path(args.out).resolve() if args.out else None
    scores = pathlib.Path(args.scores).resolve() if args.scores \
        else newest_scores(out)
    rec_path = None
    if not args.no_reconcile:
        if args.reconcile:
            rec_path = pathlib.Path(args.reconcile).resolve()
        elif out is not None and (out / "reconcile.json").exists():
            rec_path = out / "reconcile.json"
    if rec_path is not None and rec_path.exists():
        rec_verdict = json.loads(
            rec_path.read_text(encoding="utf-8")).get("verdict")
    elif args.no_reconcile:
        rec_verdict = "NOT_CHECKED（--no-reconcile）"
    else:
        rec_verdict = "MISSING"

    gate = read_m7ws_selftest(
        pathlib.Path(args.m7ws_selftest).resolve()
        if args.m7ws_selftest else None)
    cells = load_scores(scores)
    ev_path = (f"{out}/cells/<task_id>__RF/cell.json 的 m7_ws_calls"
               if out else EVIDENCE_PATH_TMPL)
    doc = analyse(cells, reconcile_invalid=(rec_verdict != "OK"),
                  m7ws_selftest=gate["result"], evidence_path=ev_path)
    doc = {
        "run": "R535", "tool": "ops/gain/r535/state_r535.py",
        "generated_at": now_iso(),
        "inputs": {
            "scores": str(scores), "scores_sha256": sha256_file(scores),
            "reconcile": str(rec_path) if rec_path else None,
            "reconcile_sha256": (sha256_file(rec_path) if rec_path
                                 and rec_path.exists() else None),
            "reconcile_verdict": rec_verdict,
            "n_cells_read": len(cells),
            "m7ws_selftest": gate,
            "reconcile_rule": ("verdict != \"OK\"（含缺檔、未檢查）⇒ "
                               "兩層都判 INVALID。對帳沒過就沒有資料可以講。")},
        **doc,
    }
    doc["diction"] = check_diction(
        {k: v for k, v in doc.items() if k != "diction"})
    print(render(doc))
    if args.json:
        p = pathlib.Path(args.json)
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        print(f"\n→ {p}  sha256={sha256_file(p)}", file=sys.stderr)
    return 0 if doc["diction"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
