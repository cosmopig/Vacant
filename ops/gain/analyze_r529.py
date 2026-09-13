#!/usr/bin/env python3
"""R529（跨題庫、三臂 OFF／CONFORM／HMIX）的收官分析尺。

這支在架構裡承重什麼
────────────────────
`DECISION_20260911_R529_CROSS_BANK_PREREG.md` 的每一條判準都指名「它讀 analyzer
輸出的哪一個 key」。判準指名了一個不存在的 key，收官時 `.get()` 會安靜地回 `None`，
然後被讀成「量到 0」——記憶鐵律：**判準要指名欄位，不准靠「工具印了什麼字串」**。

⚠ **本檔與那份 DECISION 的關係，誠實版**：預註冊是 2026-09-11 11:04:01Z 發射**之前**
凍結的；本檔是**發射之後**才寫的（Fable 的裁決：從「發射阻斷」降為
「第一個 block 收官之前必須 commit」）。之所以可以這樣，是因為
**仲裁欄位、門檻、家族大小、四狀態的定義全部逐字寫死在 DECISION 裡**，
本檔只是把它們編譯成程式；「看過數字再寫 analyzer」能動的空間只剩實作 bug，
而那由 `--selftest`（手算對照）與 `--mutation-check`（三種突變都要變紅）擋。
**這一段不准被刪**——它是這份分析可信度的邊界，不是免責聲明。

估計量宣稱（收官不准換詞彙）
──────────────────────────
R529 答的是：**在 4 個互斥題目集（3 個來源：LCB v3 的 medium/hard 兩層、
HumanEval+、MBPP+）上、同一顆 12B worker、同樣的呼叫預算，把預算花在
「跑客戶的驗收測資、把失敗原文貼回去、讓同一個人改」（H-MIX）
比花在「換人重抽」（CONFORM）或「隨機路由交回來就收」（OFF）多交付多少。**
配對單位是 `task_id`，成功＝`deliv = accepted ∧ meets_demand`（R667 凍結口徑）。

三層結構（§六）
──────────────
  §六-1 **主指標**：跨題庫**分層**的配對精確檢定，家族 **2**（HMIX−CONFORM、
        HMIX−OFF），Holm，α=0.05。H0＝「每一集都沒有效果」；以各集的不一致對數
        為條件，`b_k ~ Bin(n_k, 1/2)` 且各集獨立 ⇒ `B = Σb_k ~ Bin(N, 1/2)`。
        ⚠ 這個統計量與「把四集的不一致對直接加起來做一次 McNemar」**數值相同**。
        分層買到的是**解釋**（H0 的意思、逐集必須照實列、異質性另外量），
        **不是更嚴的檢定**。`primary.<pair>.pooling_identity_note` 逐字印這句。
  §六-2 **次指標**（描述性，**不下裁決**）：逐題庫的 Δ、b/c、未調整 95% 區間、
        方向一致計數、2×4 的 b/c 異質性卡方、逐集 token/calls。
  §六-3 **四狀態**（本研究自訂、在資料前凍結，**與 R460 的同名狀態不是同一個東西**）。

「安靜量不到」兩型都要擋（判準不是 rc≠0）
  型一 缺欄位：任一列缺 REQUIRED 任一欄 ⇒ BROKEN，**不准**當 False 算過去。
  型二 帳對不上：某臂 rows 行數 + infra_void ≠ processed ⇒ BROKEN。
  另外：block 未 terminal ⇒ 該 block BROKEN（期中資料不是收官資料）；
  某一集少一塊 ⇒ 那一集 INVALID 且**從主指標的 N 裡拿掉**（§一〇-2），
  但 **Holm 家族仍然是 2**。

零 API、零 ssh、零沙箱。只讀 `rows.jsonl`／`summary.json`／`calls.jsonl`。

用法：
    python3 ops/gain/analyze_r529.py --json ops/gain/replay/r529/analysis.json
    python3 ops/gain/analyze_r529.py --selftest
    python3 ops/gain/analyze_r529.py --mutation-check
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.gain.replay.paired_ci import diff_ci, verdict as raw_verdict  # noqa: E402
from vacant.research import (  # noqa: E402
    bc_heterogeneity_chisq, holm_bonferroni, mcnemar_exact,
    stratified_mcnemar_exact,
)

#: 突變開關（只給 `--mutation-check` 用；正式跑一定是 None）。
MUTANT = os.environ.get("R529_MUTANT") or None

ARMS = ("OFF", "CONFORM", "HMIX")
#: §六-1：家族固定 2。**不准**因為某一集 void 太多就抽掉它再重算。
PAIRS = (("HMIX", "CONFORM"), ("HMIX", "OFF"))
FAMILY_SIZE = 2
ALPHA = 0.05

#: 四個題目集 → 它的塊（順序＝ offset 遞增；佇列的**發射**順序是交錯的，
#: 但合併時照 offset 排，與 R445／R460 §六-(0) 的先例相同）。
SETS: dict[str, tuple[str, ...]] = {
    "lcb3_medium": tuple(f"g_r529_lcb3m_a{i}" for i in range(1, 8)),
    "lcb3_hard": tuple(f"g_r529_lcb3h_a{i}" for i in range(1, 4)),
    "humanevalplus": tuple(f"g_r529_hep_a{i}" for i in range(1, 9)),
    "evalplus": tuple(f"g_r529_mbpp_a{i}" for i in range(1, 20)),
}
#: 每一集的**預期題數**（§一 的表）。對不上就是取樣錯了，不是「少跑幾題」。
SET_N = {"lcb3_medium": 135, "lcb3_hard": 54, "humanevalplus": 156, "evalplus": 371}
#: 每一集的 `task_id` 前綴（§三 的不變量 3／4）。
SET_PREFIX = {"lcb3_medium": "lcb_", "lcb3_hard": "lcb_",
              "humanevalplus": "humanevalplus_", "evalplus": "mbppplus_"}
SET_FAMILY = {"lcb3_medium": "lcb_leetcode_medium", "lcb3_hard": "lcb_leetcode_hard"}

REQUIRED = ("arm", "task_id", "meets_demand", "accepted", "calls_used")

#: 任一臂的 void 率超過這條線 ⇒ 那一塊不進分析（§一〇-1，沿用 R460 §十）。
VOID_RATE_ABORT = 0.20

CALLS_SOURCE_NOTE = (
    "`calls_wire_total`＝`calls.jsonl` 的列數（含 `wire_probe`、含失敗後的每一次"
    "重試）；`calls_logical_total`＝`rows.calls_used` 的和（臂在預算帳上花掉的"
    "呼叫數）＝`calls_per_task` × `n_measured`。兩個都對、**意思不同**，"
    "引用時要指名是哪一個；round529-2 之前兩者共用 `calls_total` 一個名字。")

#: 後端身分 → LM Studio 版本的**兜底**對照表（`DECISION_20260912_R529_FABLE_
#: AUDIT_CROSS_BANK.md` §十一 逐字）。優先讀 `runs/<block>.backend_meta.json`
#: 的 `declared.lmstudio_version`；那裡沒有才用這張表。
#: ⚠ 兩者都是**人回報的宣稱**（`lms version`），runner 查證不到
#: （/v1/models 與 HTTP header 都不帶版本，2026-09-11 實測）。
LMSTUDIO_VERSION_FALLBACK = {"1003": "0.4.24", "1004": "0.4.17"}
#: `<block>.endpoint` 的 IP → 主機名（`backend_meta.json` 不在時的兜底）。
ENDPOINT_HOST_FALLBACK = {"100.119.113.56": "1003", "100.86.226.21": "1004"}

PER_BACKEND_NOTE = (
    "**描述性，不進任何仲裁**：本區塊的每一個數字都不改 primary／decision_state／"
    "refutation／aggregate 的任何一格。它存在的理由是 DECISION_20260912 §十一——"
    "1003（LM Studio 0.4.24）把 gemma-4 跑成 thinking 模式、1004（0.4.17）沒有，"
    "**同一顆模型檔、兩種推論條件**。⇒ §二 的逐集絕對值與 §四 的 token／tpc 是"
    "兩種條件的混合物，不可再單獨引用；要引用就引用這裡的逐後端數字。"
    "⚠ 配對主指標不受影響：每一塊的三臂跑在**同一台**上，b/c 是塊內配對。")
INFERENCE_MODE_NOTE = (
    "`inference_mode` 是從 `usage.completion_tokens_details.reasoning_tokens` "
    "**推斷**的，不是後端自己報的設定：>0 的呼叫占比 ≥50% ⇒ thinking、"
    "==0% ⇒ non_thinking、其間 ⇒ mixed；一通成功呼叫都沒有 ⇒ unknown"
    "（**不是** non_thinking——量不到不是通過）。")

CI_DISCLAIMER = "區間未做多重比較調整；仲裁以 analyzer 為準"
POOLING_IDENTITY_NOTE = (
    "分層統計量與「把四集的不一致對直接加起來做一次 McNemar」**數值相同**；"
    "分層買到的是解釋（H0＝每一集都沒有效果、逐集必須照實列、異質性另外量），"
    "不是更嚴的檢定。不准寫成「我們做了分層校正所以比較穩」。")
HETEROGENEITY_NOTE = (
    "描述性：2×K 的 b/c 卡方沒有精確版本，期望次數小的時候近似本來就不準"
    "（min_expected 一起印，<5 要在報告裡講）。不進 Holm 家族、不改任何一格裁決。")
WINNERS_CURSE = (
    "winner's curse：R460 的 +13.33pp 是**能被判顯著**的點估計 ⇒ 上偏。"
    "本 run 的點估計預期比它小，那是預期之內的事，不是「效果消失」。")
STATE_NOTE = (
    "R529 四狀態是**本研究自訂並在資料前凍結**的口徑（DECISION §六-3），"
    "與 R460 §六-(4) 的同名狀態**不是同一個東西**（本 run 沒有 OFF5 臂），不可互引。")


# ── 基本量 ────────────────────────────────────────────────────────────
def _deliv(r: dict) -> bool:
    """R667 凍結口徑：交付成功 ＝ 交出去了(accepted) 且 真的對(meets_demand)。"""
    if MUTANT == "M1_deliv_ignores_accepted":
        return bool(r.get("meets_demand"))
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


def paired(a_rows: list[dict], b_rows: list[dict]) -> dict:
    """A 相對 B 的配對計數。`b`＝只有 A 交付對、`c`＝只有 B 交付對。

    分母 `n_common` ＝ **complete case**：兩臂都寫了 rows 的題。
    `gain_run` 只在非 void 的格子寫 rows（void 走 `continue`），所以交集
    就是「兩臂都量到」（§六-0）。
    """
    A = {r["task_id"]: _deliv(r) for r in a_rows}
    B = {r["task_id"]: _deliv(r) for r in b_rows}
    common = sorted(set(A) & set(B))
    if MUTANT == "M2_union_denominator":
        common = sorted(set(A) | set(B))
    b = sum(1 for t in common if A.get(t) and not B.get(t))
    c = sum(1 for t in common if B.get(t) and not A.get(t))
    d = (diff_ci(b, c, len(common)) if common
         else {"delta": 0.0, "lo": 0.0, "hi": 0.0})
    return {
        "b": b, "c": c, "n_discordant": b + c, "n_common": len(common),
        "delta_pp": 100.0 * d["delta"],
        "ci95_lo_pp": 100.0 * d["lo"], "ci95_hi_pp": 100.0 * d["hi"],
        "p_mcnemar_exact": mcnemar_exact(b, c),
        "verdict_paired_ci": raw_verdict(100.0 * d["lo"], 100.0 * d["hi"]),
        "ci_note": CI_DISCLAIMER,
        "b_only_task_ids": [t for t in common if A.get(t) and not B.get(t)][:40],
        "c_only_task_ids": [t for t in common if B.get(t) and not A.get(t)][:40],
    }


def block_backend(blk: str, root: pathlib.Path) -> dict:
    """一塊跑在哪一台、那台是什麼版本。**只讀落盤 sidecar，零網路**。

    順序：`<blk>.backend_meta.json` 的 `slot_host` ／ `declared.lmstudio_version`
    → `<blk>.endpoint` 的 IP 查 `ENDPOINT_HOST_FALLBACK` → 版本查
    `LMSTUDIO_VERSION_FALLBACK`。三層都查不到就回 `unknown`——
    **不是**把它歸到某一台（量不到不是通過）。
    """
    meta = _read_json(root / "runs" / f"{blk}.backend_meta.json") or {}
    host = (meta.get("slot_host") or "").strip()
    endpoint = (meta.get("endpoint") or "").strip()
    if not endpoint:
        ep = root / "runs" / f"{blk}.endpoint"
        endpoint = ep.read_text(encoding="utf-8").strip() if ep.exists() else ""
    if not host and endpoint:
        for ip, h in ENDPOINT_HOST_FALLBACK.items():
            if ip in endpoint:
                host = h
                break
    declared = (meta.get("declared") or {})
    version = (declared.get("lmstudio_version") or "").strip()
    version_source = "backend_meta.declared" if version else None
    if not version and host in LMSTUDIO_VERSION_FALLBACK:
        version = LMSTUDIO_VERSION_FALLBACK[host]
        version_source = "fallback_table(DECISION_20260912 §十一)"
    return {
        "host": host or "unknown",
        "endpoint": endpoint or None,
        "lmstudio_version": version or None,
        "lmstudio_version_source": version_source,
        "probe_reasoning_tokens": meta.get("probe_reasoning_tokens"),
        "reasoning_effort_requested": meta.get("reasoning_effort"),
        "honesty": "lmstudio_version 是人回報的宣稱，analyzer 查證不到",
    }


def reasoning_stats(calls: list[dict]) -> dict:
    """一堆呼叫的 reasoning token 帳。只看**成功**的呼叫（失敗的沒有 usage）。

    ⚠ 這是 DECISION_20260912 §十一 的量具：R529 在 1003 的呼叫 100% 帶
      `usage.completion_tokens_details.reasoning_tokens`（平均數千）、
      1004 是 0%。沒有這一格，「兩台是同一個推論條件」這個假設就沒有人在查。
    """
    ok = [c for c in calls if c.get("ok")]
    n = len(ok)
    with_r = 0
    r_sum = c_sum = t_sum = 0
    for c in ok:
        u = c.get("usage") or {}
        det = u.get("completion_tokens_details") or {}
        rt = int(det.get("reasoning_tokens") or 0)
        if MUTANT == "M9_reasoning_ignored":
            rt = 0
        if rt > 0:
            with_r += 1
        r_sum += rt
        c_sum += int(u.get("completion_tokens") or 0)
        t_sum += int(u.get("total_tokens") or 0)
    pp = _pct(with_r, n)
    mode = ("unknown" if pp is None else
            "non_thinking" if pp == 0.0 else
            "thinking" if pp >= 50.0 else "mixed")
    return {
        "calls_ok": n,
        "calls_with_reasoning": with_r,
        "reasoning_call_pp": pp,
        "reasoning_tokens_mean": (r_sum / n) if n else None,
        "completion_tokens_mean": (c_sum / n) if n else None,
        "total_tokens_mean": (t_sum / n) if n else None,
        "inference_mode": mode,
        "note": INFERENCE_MODE_NOTE,
    }


def tokens_by_arm(calls: list[dict], measured_ids: dict[str, set[str]]) -> dict:
    """逐臂的呼叫數與 token 總量，**含 void 與排除 void 兩個版本都算**。

    void 格的呼叫已經燒掉 token 但那一格不進分母 ⇒ 只報「排除 void」會**低估**
    H 臂的成本。§六-3 的 (ii) 用**含 void** 的那個（`tpc_incl_void`）。

    ⚠ 這裡數出來的是 **wire 層**的呼叫數（`calls_wire_total`）：`calls.jsonl`
    有幾列就是幾通，含 `wire_probe`、含失敗後重試的每一次。它**不等於**臂在
    預算帳上花掉的呼叫數（那是 `rows.calls_used` 的和＝`calls_logical_total`）。
    兩個數字都對、意思不同；round529-2 之前它們共用 `calls_total` 這一個名字，
    於是「每題幾通」與「總共幾通」除出來對不上——那不是 bug 在數字上，
    是 bug 在**名字**上，而名字錯掉的帳會被讀成量到了不存在的東西。
    """
    out: dict[str, dict] = {}
    for rec in calls:
        arm = (rec.get("meta") or {}).get("arm")
        if arm is None:
            continue
        d = out.setdefault(arm, {"calls_wire_total": 0, "calls_wire_ok": 0,
                                 "tokens_incl_void": 0, "tokens_excl_void": 0})
        d["calls_wire_total"] += 1
        if not rec.get("ok"):
            continue
        d["calls_wire_ok"] += 1
        tok = int((rec.get("usage") or {}).get("total_tokens") or 0)
        d["tokens_incl_void"] += tok
        if (rec.get("meta") or {}).get("task_id") in measured_ids.get(arm, set()):
            d["tokens_excl_void"] += tok
    if MUTANT == "M3_tpc_ignores_void_calls":
        for d in out.values():
            d["tokens_incl_void"] = d["tokens_excl_void"]
    return out


# ── 載入與 BROKEN 判定 ────────────────────────────────────────────────
def load_set(name: str, root: pathlib.Path) -> dict:
    """把一個題目集的塊合併起來（依 offset 排序、按 task_id 合併）。

    回傳 `{rows, calls, blocks, broken_reasons, n_tasks, blocks_present}`。
    **不吞任何錯**：每一種「安靜量不到」都寫進 `broken_reasons`。
    """
    rows: list[dict] = []
    calls: list[dict] = []
    blocks: list[dict] = []
    broken: list[str] = []
    seen_ids: set[str] = set()
    # 逐塊留一份（`per_backend` 要用）。**不進輸出 JSON**——它只是中繼資料，
    # 而 `per_set_stats` 的回傳是逐鍵明列的，不會把它漏出去。
    rows_by_block: dict[str, list[dict]] = {}
    calls_by_block: dict[str, list[dict]] = {}
    for blk in SETS[name]:
        d = root / "runs" / blk
        summary = _read_json(d / "summary.json")
        info = {"block": blk, "present": d.exists(), "terminal": None,
                "void_rate_max": None, "n_rows": 0}
        if not summary:
            info["missing_summary"] = True
            blocks.append(info)
            broken.append(f"{blk}:no_summary")
            continue
        info["terminal"] = bool(summary.get("run_terminal"))
        if not info["terminal"]:
            broken.append(f"{blk}:not_terminal")
        arms_s = summary.get("arms") or {}
        worst = 0.0
        for arm, v in arms_s.items():
            processed = float(v.get("processed") or 0)
            if processed > 0:
                worst = max(worst, float(v.get("infra_void") or 0) / processed)
        info["void_rate_max"] = round(worst, 4)
        if worst > VOID_RATE_ABORT:
            broken.append(f"{blk}:void_rate_{worst:.3f}")
        brows = _read_jsonl(d / "rows.jsonl")
        for r in brows:
            miss = [k for k in REQUIRED if k not in r]
            if miss:
                broken.append(f"{blk}:row_missing_fields:{miss}")
                break
        # 帳要對得上：每臂 rows 行數 ＋ infra_void ＝ processed
        by_arm: dict[str, int] = {}
        for r in brows:
            by_arm[r.get("arm")] = by_arm.get(r.get("arm"), 0) + 1
        for arm, v in arms_s.items():
            want = int(v.get("processed") or 0) - int(v.get("infra_void") or 0)
            got = by_arm.get(arm, 0)
            if want != got:
                broken.append(f"{blk}:{arm}:rows_{got}_vs_processed_minus_void_{want}")
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
        blocks.append(info)
    present = [b for b in blocks if b["present"]]
    if len(present) != len(SETS[name]):
        broken.append(f"block_count_mismatch:{len(present)}/{len(SETS[name])}")
    ids = sorted({r["task_id"] for r in rows})
    bad_prefix = [t for t in ids if not t.startswith(SET_PREFIX[name])]
    if bad_prefix:
        broken.append(f"wrong_task_prefix:{bad_prefix[:3]}")
    if name in SET_FAMILY:
        bad_fam = sorted({r.get("family") for r in rows
                          if r.get("family") != SET_FAMILY[name]})
        if bad_fam:
            broken.append(f"wrong_family:{bad_fam[:3]}")
    return {"rows": rows, "calls": calls, "blocks": blocks,
            "broken_reasons": broken, "n_tasks": len(ids),
            "blocks_present": len(present), "blocks_expected": len(SETS[name]),
            "n_tasks_expected": SET_N[name],
            "rows_by_block": rows_by_block, "calls_by_block": calls_by_block}


def included_sets(per_set: dict) -> list[str]:
    """哪幾集進主指標的 N。**只有 `valid` 的才進**（§一〇-2）。

    ⚠ 這一步單獨抽成函式，是為了讓 `--mutation-check` 咬得到它：
      「安靜地少算一集」會讓主指標的 N 變小而 log 上完全看不出來。
    """
    out = [s for s in SETS if per_set[s]["valid"]]
    if MUTANT == "M5_drop_a_set_silently":
        out = [x for x in out if x != "lcb3_hard"]
    return out


# ── §六-2 次指標：逐題庫 ──────────────────────────────────────────────
def per_set_stats(name: str, loaded: dict) -> dict:
    rows = loaded["rows"]
    by_arm: dict[str, list[dict]] = {}
    for r in rows:
        by_arm.setdefault(r.get("arm"), []).append(r)
    measured = {a: {r["task_id"] for r in rs} for a, rs in by_arm.items()}
    per_arm: dict[str, dict] = {}
    for a in ARMS:
        rs = by_arm.get(a, [])
        n = len(rs)
        dn = sum(1 for r in rs if _deliv(r))
        acc = sum(1 for r in rs if r.get("accepted"))
        false_n = sum(1 for r in rs
                      if r.get("accepted") and not r.get("meets_demand"))
        logical = sum(int(r.get("calls_used") or 0) for r in rs)
        if MUTANT == "M6_calls_per_task_from_wire":
            logical = -1        # 讓 calls_per_task 與 calls_logical_total 脫鉤
        per_arm[a] = {
            "n_measured": n, "deliv_n": dn, "deliv_pp": _pct(dn, n),
            "accepted_n": acc,
            "false_delivery_n": false_n, "false_delivery_pp": _pct(false_n, n),
            # **邏輯**呼叫數（預算帳）：rows.calls_used 的和。`calls_per_task`
            # 一定是它除以 n——兩者同源是可檢查的，見 selftest (12)。
            "calls_logical_total": logical,
            "calls_per_task": (logical / n) if n else None,
        }
    tok = tokens_by_arm(loaded["calls"], measured)
    tokens: dict[str, dict] = {}
    for a in ARMS:
        t = tok.get(a, {})
        dn = per_arm[a]["deliv_n"]
        n = per_arm[a]["n_measured"]
        tokens[a] = {
            "tokens_incl_void": t.get("tokens_incl_void", 0),
            "tokens_excl_void": t.get("tokens_excl_void", 0),
            # wire 層（calls.jsonl 的列數，含 wire_probe／失敗重試）
            "calls_wire_total": t.get("calls_wire_total", 0),
            "calls_wire_ok": t.get("calls_wire_ok", 0),
            # 邏輯層（預算帳，rows.calls_used 的和）＝ calls_per_task × n
            "calls_logical_total": per_arm[a]["calls_logical_total"],
            "calls_source_note": CALLS_SOURCE_NOTE,
            "tokens_per_task": (t.get("tokens_incl_void", 0) / n) if n else None,
            "tpc_incl_void": (t.get("tokens_incl_void", 0) / dn) if dn else None,
        }
    pairs: dict[str, dict] = {}
    for a, b in PAIRS:
        pairs[f"{a}_vs_{b}"] = paired(by_arm.get(a, []), by_arm.get(b, []))
    return {
        "n_tasks": loaded["n_tasks"], "n_tasks_expected": loaded["n_tasks_expected"],
        "blocks_present": loaded["blocks_present"],
        "blocks_expected": loaded["blocks_expected"],
        "broken_reasons": loaded["broken_reasons"],
        "valid": not loaded["broken_reasons"],
        "per_arm": per_arm, "tokens": tokens, "paired": pairs,
        "blocks": loaded["blocks"],
        "arbiter_note": "逐題庫**不下裁決**，只給數字（DECISION §六-2 逐字）。",
    }


# ── 逐後端（DECISION_20260912 §十一；描述性，不進仲裁）──────────────────
def per_backend_stats(loaded: dict, root: pathlib.Path = ROOT) -> dict:
    """把一集的塊照**後端主機**分堆，逐堆算三臂 deliv／b-c／token／reasoning。

    為什麼可以在後端內部做配對：一塊的三臂跑在**同一台**上（發射器逐塊 export
    一個 `VACANT_GAIN_API`），而不同塊的題目集互斥 ⇒ 「同一台上的 b/c」是
    完整的塊內配對，只是把塊分成兩群各自加起來。
    ⚠ 它**不是**另一個檢定：不算 p、不進 Holm、不改四狀態。要比較兩台的差別
      需要另一個預註冊（推論模式當因子），本檔不做。
    """
    by_host: dict[str, dict] = {}
    for blk, brows in loaded.get("rows_by_block", {}).items():
        be = block_backend(blk, root)
        if MUTANT == "M8_per_backend_merges_hosts":
            be = dict(be, host="1004")
        d = by_host.setdefault(be["host"], {
            "backend": be, "blocks": [], "rows": [], "calls": []})
        d["blocks"].append(blk)
        d["rows"] += brows
        d["calls"] += loaded.get("calls_by_block", {}).get(blk, [])
    out: dict[str, dict] = {}
    for host in sorted(by_host):
        d = by_host[host]
        by_arm: dict[str, list[dict]] = {}
        for r in d["rows"]:
            by_arm.setdefault(r.get("arm"), []).append(r)
        measured = {a: {r["task_id"] for r in rs} for a, rs in by_arm.items()}
        tok = tokens_by_arm(d["calls"], measured)
        per_arm: dict[str, dict] = {}
        for a in ARMS:
            rs = by_arm.get(a, [])
            n = len(rs)
            dn = sum(1 for r in rs if _deliv(r))
            t = tok.get(a, {})
            ti = t.get("tokens_incl_void", 0)
            per_arm[a] = {
                "n_measured": n, "deliv_n": dn, "deliv_pp": _pct(dn, n),
                "deliv_fraction": f"{dn}/{n}",
                "tokens_incl_void": ti,
                "tokens_per_task": (ti / n) if n else None,
                "tpc_incl_void": (ti / dn) if dn else None,
                "calls_logical_total": sum(int(r.get("calls_used") or 0) for r in rs),
            }
        pairs: dict[str, dict] = {}
        for a, b in PAIRS:
            pr = paired(by_arm.get(a, []), by_arm.get(b, []))
            pairs[f"{a}_vs_{b}"] = {
                "b": pr["b"], "c": pr["c"], "n_common": pr["n_common"],
                "delta_pp": pr["delta_pp"],
            }
        out[host] = {
            "backend": d["backend"],
            "blocks": sorted(d["blocks"]),
            "blocks_n": len(d["blocks"]),
            "per_arm": per_arm,
            "paired": pairs,
            "reasoning": reasoning_stats(d["calls"]),
            "note": PER_BACKEND_NOTE,
        }
    return out


# ── §六-1 主指標 ──────────────────────────────────────────────────────
def primary(per_set: dict, included: list[str]) -> dict:
    """跨題庫分層的配對精確檢定，家族 2，Holm。"""
    out: dict[str, dict] = {}
    raw_p: list[float] = []
    keys: list[str] = []
    for a, b in PAIRS:
        key = f"{a}_vs_{b}"
        strata = []
        per_stratum_named = []
        for s in included:
            pr = per_set[s]["paired"][key]
            strata.append((pr["b"], pr["c"]))
            per_stratum_named.append({"set": s, "b": pr["b"], "c": pr["c"],
                                      "n_common": pr["n_common"],
                                      "p_unadjusted": pr["p_mcnemar_exact"]})
        st = stratified_mcnemar_exact(strata)
        het = bc_heterogeneity_chisq(strata)
        out[key] = {
            "b": st["b"], "c": st["c"], "n_discordant": st["n_discordant"],
            "p": st["p"], "k_strata": st["k_strata"],
            "sets_included": list(included),
            "per_stratum": per_stratum_named,
            "pooling_identity_check": mcnemar_exact(st["b"], st["c"]),
            "pooling_identity_note": POOLING_IDENTITY_NOTE,
            "heterogeneity": dict(het, note=HETEROGENEITY_NOTE),
        }
        raw_p.append(st["p"])
        keys.append(key)
    adj = holm_bonferroni(raw_p)
    for k, p in zip(keys, adj):
        out[k]["p_adj"] = p
        out[k]["significant"] = p < ALPHA
    out["family_size"] = FAMILY_SIZE
    out["alpha"] = ALPHA
    out["family_note"] = (
        "家族固定 2（HMIX−CONFORM、HMIX−OFF）。某一集 INVALID 只把它從 N 裡拿掉"
        "（DECISION §一〇-2），**不改家族大小**。")
    if len(included) != len(SETS):
        out["excluded_sets"] = [s for s in SETS if s not in included]
        out["exclusion_note"] = (
            f"主指標的 N 少了 {len(SETS) - len(included)} 集："
            f"{out['excluded_sets']}——這幾集 INVALID（見 per_set.<set>.broken_reasons）。")
    return out


# ── §六-3 四狀態 ──────────────────────────────────────────────────────
def decide(prim: dict, pooled_tokens: dict) -> dict:
    """R529 四狀態。**與 R460 的同名狀態不是同一個東西**（STATE_NOTE）。"""
    c_ok = prim["HMIX_vs_CONFORM"].get("significant")
    o_ok = prim["HMIX_vs_OFF"].get("significant")
    cond_i = bool(c_ok and o_ok)
    tpc_h = pooled_tokens.get("HMIX", {}).get("tpc_incl_void")
    tpc_c = pooled_tokens.get("CONFORM", {}).get("tpc_incl_void")
    cond_ii = (tpc_h is not None and tpc_c is not None and tpc_h <= tpc_c)
    b = prim["HMIX_vs_CONFORM"]["b"]
    c = prim["HMIX_vs_CONFORM"]["c"]
    ruled_out = (b < c) and bool(c_ok)
    if ruled_out:
        state = "RULED_OUT"
    elif cond_i and cond_ii:
        state = "EFFECTIVE"
    elif cond_i:
        state = "COSTLY_BUT_REAL"
    else:
        state = "INCONCLUSIVE"
    if MUTANT == "M4_tpc_threshold_flipped":
        state = "EFFECTIVE" if cond_i else state
    return {
        "state": state,
        "cond_i_both_primary_holm": cond_i,
        "cond_ii_tpc_hmix_le_conform": cond_ii,
        "tpc_incl_void": {"HMIX": tpc_h, "CONFORM": tpc_c},
        "note": STATE_NOTE,
        "pooled_tpc_note": (
            "這是本檔**唯一**一處把四集加起來算比值的地方，而且只用來判一個布林值；"
            "不准被引用成「H-MIX 的成本是 CONFORM 的 x 倍」——那個比值逐集差很多。"),
    }


# ── V/GT 閘門（round529-2；DECISION_20260912 §六-3 的處置）───────────
VGT_NOTE = (
    "analyzer 只讀 `rows/calls/summary`，**結構上看不到隱藏測資有沒有洩漏**"
    "⇒ 在這一版之前它永遠判不出 INVALID（`DECISION_20260912_R529_FABLE_AUDIT_"
    "CROSS_BANK.md` §六-3）。`--vgt-dir` 把 `harness_vgt_audit.py --scope v2` "
    "的產物讀進來，任何一塊 `verdict != CLEAN` ⇒ `decision_state.state=INVALID`。"
    "⚠ **檔案不在也算不通過**（`missing`）：沒掃過不等於掃過是乾淨的"
    "（鐵律 3 的同一條紀律）。⚠ 這道閘門是**單邊**的：V/GT 全 CLEAN 只代表"
    "那一套 needle 沒命中，不代表沒有洩漏——不准讀成「已證明零洩漏」。")


def vgt_gate(vgt_dir: pathlib.Path | None) -> dict:
    """讀 `vgt_v2_<block>.json`，任一塊 verdict≠CLEAN ⇒ 不通過。

    ⚠ 沒給 `--vgt-dir` 時回 `applied=False`——那是「這一格沒量」，
    **不是** CLEAN。收官引用時要看得到這個布林值。
    """
    out: dict = {"applied": vgt_dir is not None,
                 "dir": str(vgt_dir) if vgt_dir else None,
                 "blocks_expected": sum(len(v) for v in SETS.values()),
                 "clean_n": 0, "by_block": {}, "not_clean": [],
                 "clean": None, "note": VGT_NOTE}
    if vgt_dir is None:
        return out
    for name, blks in SETS.items():
        for blk in blks:
            f = vgt_dir / f"vgt_v2_{blk}.json"
            if not f.exists():
                out["by_block"][blk] = {"set": name, "verdict": "MISSING",
                                        "path": str(f)}
                out["not_clean"].append(f"{blk}:MISSING")
                continue
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception as exc:                       # noqa: BLE001
                out["by_block"][blk] = {"set": name, "verdict": "UNREADABLE",
                                        "error": repr(exc)}
                out["not_clean"].append(f"{blk}:UNREADABLE")
                continue
            v = d.get("verdict")
            rec = {"set": name, "verdict": v,
                   "violations_n": len(d.get("violations") or []),
                   "excused_n": d.get("excused_n"),
                   "needles_checked": d.get("needles_checked"),
                   "scope": d.get("scope")}
            out["by_block"][blk] = rec
            if v == "CLEAN" and MUTANT != "M7_vgt_not_checked":
                out["clean_n"] += 1
            else:
                out["not_clean"].append(f"{blk}:{v}")
    if MUTANT == "M7_vgt_not_checked":
        out["not_clean"] = []
    out["clean"] = not out["not_clean"]
    return out


# ── §六-4 推翻鍵 ／ §六-5 宣稱規則 ────────────────────────────────────
def refutation(per_set: dict) -> dict:
    """R460 §九 第一條的推翻鍵：LCB v3 任一層 c ≥ b ⇒ 觸發。"""
    out: dict = {"triggered": False, "keys": {}}
    for s in ("lcb3_hard", "lcb3_medium"):
        pr = (per_set.get(s) or {}).get("paired", {}).get("HMIX_vs_CONFORM")
        if not pr:
            continue
        hit = pr["c"] >= pr["b"]
        out["keys"][s] = {"b": pr["b"], "c": pr["c"], "c_ge_b": hit}
        out["triggered"] = out["triggered"] or hit
    for s in ("humanevalplus", "evalplus"):
        pr = (per_set.get(s) or {}).get("paired", {}).get("HMIX_vs_CONFORM")
        if pr:
            out[f"{s}_c_ge_b"] = pr["c"] >= pr["b"]
    out["note"] = (
        "觸發 ⇒ R460 的 EFFECTIVE 降為「一次顯著」，且 examples/verdicts.py 與"
        "官網資料源要同步改口徑（DECISION §六-4）。MBPP+／HumanEval+ 不是觸發鍵，"
        "但出現 c ≥ b 一樣要逐字報出來。")
    return out


def aggregate(per_set: dict, prim: dict, included: list[str]) -> dict:
    dc = [per_set[s]["paired"]["HMIX_vs_CONFORM"]["delta_pp"] for s in included]
    do = [per_set[s]["paired"]["HMIX_vs_OFF"]["delta_pp"] for s in included]
    agree_c = sum(1 for x in dc if x > 0)
    agree_o = sum(1 for x in do if x > 0)
    c_sig = prim["HMIX_vs_CONFORM"].get("significant")
    o_sig = prim["HMIX_vs_OFF"].get("significant")
    if c_sig and o_sig and agree_c == len(SETS):
        stmt = ("這個效果在三個來源、四個互斥題目集上方向一致，"
                "合併後在配對精確檢定下顯著。")
    elif c_sig and o_sig:
        rev = [s for s in included
               if per_set[s]["paired"]["HMIX_vs_CONFORM"]["delta_pp"] <= 0]
        stmt = f"主指標成立，但方向不是 4/4——反向／打平的是 {rev}，必須逐集列出。"
    else:
        stmt = "主指標未成立 ⇒ 逐集照實列，不准寫「多數支持」。"
    return {
        "direction_agree_c": agree_c, "direction_agree_o": agree_o,
        "n_sets_counted": len(included),
        "delta_c_pp_by_set": {s: per_set[s]["paired"]["HMIX_vs_CONFORM"]["delta_pp"]
                              for s in included},
        "delta_o_pp_by_set": {s: per_set[s]["paired"]["HMIX_vs_OFF"]["delta_pp"]
                              for s in included},
        "statement": stmt,
        "statement_rule": (
            "主指標兩格都 p_adj<0.05 且 direction_agree_c==4 ⇒ 可以寫「三個來源、"
            "四集方向一致且合併顯著」；主指標成立但方向不是 4/4 ⇒ 必須指名哪一集反向；"
            "主指標任一格不成立 ⇒ 逐集照實列（DECISION §六-5 逐字）。"),
        "no_meta_analysis_note": (
            "沒有隨機效應模型、沒有 meta-analysis、沒有合併效果量；"
            "四集的點估計**不准平均**（難度組成、來源、n、量具強度都不同）。"),
        "winners_curse": WINNERS_CURSE,
    }


# ── 主流程 ────────────────────────────────────────────────────────────
def analyze(root: pathlib.Path = ROOT,
            vgt_dir: pathlib.Path | None = None) -> dict:
    per_set: dict[str, dict] = {}
    loaded_sets: dict[str, dict] = {}
    for name in SETS:
        loaded_sets[name] = load_set(name, root)
        per_set[name] = per_set_stats(name, loaded_sets[name])
    included = included_sets(per_set)
    vgt = vgt_gate(vgt_dir)
    out: dict = {
        "run": "R529",
        "decision": "DECISION_20260911_R529_CROSS_BANK_PREREG.md",
        "arms": list(ARMS),
        "sets_expected": list(SETS),
        "sets_included_in_primary": included,
        "vgt": vgt,
        "per_set": per_set,
    }
    # ⚠ `per_backend` 一律**最後**才塞進 out：它是描述性的，放在所有仲裁鍵
    #   之後 ⇒ 既有 JSON 的鍵順序與值逐位元不變，diff 只會多出這一個鍵。
    def _with_per_backend(o: dict) -> dict:
        o["per_backend"] = {name: per_backend_stats(loaded_sets[name], root)
                            for name in SETS}
        o["per_backend_note"] = PER_BACKEND_NOTE
        return o

    if not included:
        out["primary"] = {"family_size": FAMILY_SIZE,
                          "error": "沒有任何一集是 valid 的——量不到不是通過。"}
        out["decision_state"] = {"state": "INVALID",
                                 "note": "四集全部 INVALID（見 per_set.*.broken_reasons）。"}
        return _with_per_backend(out)
    pooled_tokens: dict[str, dict] = {}
    for a in ARMS:
        tok = sum(per_set[s]["tokens"][a]["tokens_incl_void"] for s in included)
        dn = sum(per_set[s]["per_arm"][a]["deliv_n"] for s in included)
        n = sum(per_set[s]["per_arm"][a]["n_measured"] for s in included)
        pooled_tokens[a] = {
            "tokens_incl_void": tok, "deliv_n": dn, "n_measured": n,
            "tpc_incl_void": (tok / dn) if dn else None,
            "tokens_per_task": (tok / n) if n else None,
        }
    out["tokens_pooled"] = pooled_tokens
    out["primary"] = primary(per_set, included)
    out["refutation"] = refutation(per_set)          # 先於四狀態印（§六-4）
    out["decision_state"] = decide(out["primary"], pooled_tokens)
    if vgt["applied"] and not vgt["clean"]:
        # V/GT 不乾淨 ⇒ 整個 run 的資料不可用，四狀態一律 INVALID。
        # **保留**原本算出來的那一格，好讓人看得到「是被這道閘門翻掉的」。
        out["decision_state"] = {
            "state": "INVALID",
            "state_before_vgt": out["decision_state"]["state"],
            "invalidated_by": "vgt_not_clean",
            "not_clean": vgt["not_clean"],
            "note": VGT_NOTE,
        }
    out["aggregate"] = aggregate(per_set, out["primary"], included)
    return _with_per_backend(out)


def render(a: dict) -> str:
    L = [f"═══ R529 收官分析（{a['decision']}）═══",
         f"臂：{'/'.join(a['arms'])}　題目集：{len(a['sets_expected'])}",
         f"進入主指標的集：{a['sets_included_in_primary']}"]
    if "refutation" in a:
        r = a["refutation"]
        L.append(f"【推翻鍵】R460 §九 第一條 triggered={r['triggered']}　"
                 + "　".join(f"{k}: b={v['b']} c={v['c']} c≥b={v['c_ge_b']}"
                             for k, v in r["keys"].items()))
    L.append("")
    L.append("── 主指標（分層配對精確檢定，家族 2，Holm）")
    for a_, b_ in PAIRS:
        k = f"{a_}_vs_{b_}"
        p = a["primary"].get(k)
        if not p:
            continue
        L.append(f"  {k}: b={p['b']} c={p['c']} N_disc={p['n_discordant']} "
                 f"p={p['p']:.3g} p_adj={p.get('p_adj', float('nan')):.3g} "
                 f"{'顯著' if p.get('significant') else '不顯著'}")
        L.append("    逐集 " + "　".join(
            f"{d['set']}={d['b']}/{d['c']}" for d in p["per_stratum"]))
        het = p["heterogeneity"]
        L.append(f"    異質性（描述）chi2={het['chi2']:.3f} df={het['df']} "
                 f"p={het['p']:.3g} min_expected={het['min_expected']:.2f}")
    L.append(f"  ⚠ {POOLING_IDENTITY_NOTE}")
    L.append("")
    L.append("── 次指標（描述性，不下裁決）")
    for s in a["sets_expected"]:
        ps = a["per_set"][s]
        if not ps["valid"]:
            L.append(f"  {s}: INVALID {ps['broken_reasons'][:2]}")
            continue
        pc = ps["paired"]["HMIX_vs_CONFORM"]
        po = ps["paired"]["HMIX_vs_OFF"]
        L.append(f"  {s}: n={ps['n_tasks']}/{ps['n_tasks_expected']}　"
                 f"ΔC={pc['delta_pp']:+.2f}pp [{pc['ci95_lo_pp']:+.1f},"
                 f"{pc['ci95_hi_pp']:+.1f}] b/c={pc['b']}/{pc['c']}　"
                 f"ΔO={po['delta_pp']:+.2f}pp b/c={po['b']}/{po['c']}")
    L.append(f"  ⚠ {CI_DISCLAIMER}")
    g = a.get("vgt") or {}
    if g:
        L.append("")
        if not g.get("applied"):
            L.append("── V/GT 閘門：**沒量**（沒給 --vgt-dir）——"
                     "這不是 CLEAN，收官引用時要講清楚")
        else:
            L.append(f"── V/GT 閘門：{g['clean_n']}/{g['blocks_expected']} CLEAN　"
                     f"{'通過' if g['clean'] else '**不通過** ' + str(g['not_clean'][:5])}")
        L.append(f"  ⚠ {g.get('note')}")
    if "decision_state" in a:
        d = a["decision_state"]
        L.append("")
        L.append(f"── R529 四狀態：**{d['state']}**"
                 f"（(i)={d.get('cond_i_both_primary_holm')} "
                 f"(ii)={d.get('cond_ii_tpc_hmix_le_conform')}）")
        if d.get("invalidated_by"):
            L.append(f"  ⚠ 被 {d['invalidated_by']} 翻成 INVALID；"
                     f"翻之前是 {d.get('state_before_vgt')}")
        L.append(f"  ⚠ {d['note']}")
    if "aggregate" in a:
        g = a["aggregate"]
        L.append(f"  方向一致 ΔC {g['direction_agree_c']}/{g['n_sets_counted']}、"
                 f"ΔO {g['direction_agree_o']}/{g['n_sets_counted']}")
        L.append(f"  宣稱：{g['statement']}")
    pb = a.get("per_backend") or {}
    if pb:
        L += ["",
              "── 逐後端（DECISION_20260912 §十一；**描述性，不進任何仲裁**）",
              f"{'題目集':<14}{'後端':>6}{'LMS':>11}{'塊':>4}"
              f"{'OFF':>10}{'CONFORM':>10}{'HMIX':>10}"
              f"{'H−C':>6}{'H−O':>6}{'tok/題':>9}{'tpc':>9}"
              f"{'reason均':>9}{'帶reason%':>10}{'模式':>13}"]
        for s in a["sets_expected"]:
            for host, h in sorted((pb.get(s) or {}).items()):
                pa = h["per_arm"]
                pc = h["paired"]["HMIX_vs_CONFORM"]
                po = h["paired"]["HMIX_vs_OFF"]
                rs = h["reasoning"]
                hm = pa["HMIX"]
                L.append(
                    f"{s:<14}{host:>6}"
                    f"{(h['backend'].get('lmstudio_version') or '?'):>11}"
                    f"{h['blocks_n']:>4}"
                    f"{pa['OFF']['deliv_fraction']:>10}"
                    f"{pa['CONFORM']['deliv_fraction']:>10}"
                    f"{pa['HMIX']['deliv_fraction']:>10}"
                    f"{pc['b'] - pc['c']:>+6}{po['b'] - po['c']:>+6}"
                    f"{_num(hm['tokens_per_task']):>9}"
                    f"{_num(hm['tpc_incl_void']):>9}"
                    f"{_num(rs['reasoning_tokens_mean']):>9}"
                    f"{_num(rs['reasoning_call_pp'], 1):>10}"
                    f"{rs['inference_mode']:>13}")
        L.append(f"  ⚠ {PER_BACKEND_NOTE}")
        L.append(f"  ⚠ {INFERENCE_MODE_NOTE}")
    return "\n".join(L)


def _num(v, nd: int = 0) -> str:
    """描述性表格用的格式化。`None` 印 `-`——**不是 0**。"""
    return "-" if v is None else f"{v:.{nd}f}"


# ── --selftest：手算對照 ──────────────────────────────────────────────
def _fake_rows(arm: str, deliv: list[bool], prefix: str) -> list[dict]:
    return [{"arm": arm, "task_id": f"{prefix}{i}", "meets_demand": d,
             "accepted": True, "calls_used": 1, "family": "x"}
            for i, d in enumerate(deliv)]


def selftest() -> int:
    """手算對照。對照值寫在註解裡，不是「跑一次看它印什麼」。"""
    bad: list[str] = []

    # (1) paired：A 對 4 題、B 對 2 題，其中兩題只有 A 對、零題只有 B 對。
    A = _fake_rows("HMIX", [True, True, True, True, False], "t")
    B = _fake_rows("CONFORM", [True, True, False, False, False], "t")
    pr = paired(A, B)
    if (pr["b"], pr["c"], pr["n_common"]) != (2, 0, 5):
        bad.append(f"paired b/c/n = {pr['b']}/{pr['c']}/{pr['n_common']}，應為 2/0/5")
    # McNemar exact(2,0) = 2 * (1/2)^2 = 0.5
    if abs(pr["p_mcnemar_exact"] - 0.5) > 1e-12:
        bad.append(f"mcnemar_exact(2,0)={pr['p_mcnemar_exact']}，應為 0.5")

    # (2) 分層：b=(3,2) c=(1,0) ⇒ B=5, N=6
    #     p = 2·(C(6,0)+C(6,1))/2^6 = 2·7/64 = 0.21875
    st = stratified_mcnemar_exact([(3, 1), (2, 0)])
    if abs(st["p"] - 0.21875) > 1e-12:
        bad.append(f"stratified p={st['p']}，應為 0.21875")
    # 與「直接合併」數值相同（POOLING_IDENTITY_NOTE 的那句話）
    if st["p"] != mcnemar_exact(5, 1):
        bad.append("分層統計量與合併 McNemar 不相同——POOLING_IDENTITY_NOTE 失效")

    # (3) 異質性：兩層 (10,0) 與 (0,10) ⇒ p̂=0.5、每層期望 (5,5)、chi2 = 4·25/5 = 20
    het = bc_heterogeneity_chisq([(10, 0), (0, 10)])
    if abs(het["chi2"] - 20.0) > 1e-9 or het["df"] != 1:
        bad.append(f"heterogeneity chi2/df = {het['chi2']}/{het['df']}，應為 20.0/1")

    # (4) Holm 家族 2：最小的 p 乘 2（上限 1）
    adj = holm_bonferroni([0.01, 0.30])
    if abs(adj[0] - 0.02) > 1e-12 or abs(adj[1] - 0.30) > 1e-12:
        bad.append(f"holm([0.01,0.30])={adj}，應為 [0.02, 0.30]")

    # (5) 四狀態：兩格顯著 ＋ tpc 較低 ⇒ EFFECTIVE；tpc 較高 ⇒ COSTLY_BUT_REAL
    prim = {"HMIX_vs_CONFORM": {"significant": True, "b": 20, "c": 3},
            "HMIX_vs_OFF": {"significant": True, "b": 40, "c": 2}}
    if decide(prim, {"HMIX": {"tpc_incl_void": 100.0},
                     "CONFORM": {"tpc_incl_void": 120.0}})["state"] != "EFFECTIVE":
        bad.append("四狀態：(i)+(ii) 應為 EFFECTIVE")
    if decide(prim, {"HMIX": {"tpc_incl_void": 200.0},
                     "CONFORM": {"tpc_incl_void": 120.0}})["state"] != "COSTLY_BUT_REAL":
        bad.append("四狀態：(i) 成立、(ii) 不成立應為 COSTLY_BUT_REAL")
    prim_rev = {"HMIX_vs_CONFORM": {"significant": True, "b": 3, "c": 20},
                "HMIX_vs_OFF": {"significant": False, "b": 5, "c": 6}}
    if decide(prim_rev, {"HMIX": {"tpc_incl_void": 1.0},
                         "CONFORM": {"tpc_incl_void": 9.0}})["state"] != "RULED_OUT":
        bad.append("四狀態：方向反了且顯著應為 RULED_OUT")
    prim_ns = {"HMIX_vs_CONFORM": {"significant": False, "b": 9, "c": 8},
               "HMIX_vs_OFF": {"significant": True, "b": 30, "c": 2}}
    if decide(prim_ns, {"HMIX": {"tpc_incl_void": 1.0},
                        "CONFORM": {"tpc_incl_void": 9.0}})["state"] != "INCONCLUSIVE":
        bad.append("四狀態：只有一格顯著應為 INCONCLUSIVE")

    # (6) 家族大小永遠是 2，而且少一集也不變
    ps = {s: {"paired": {"HMIX_vs_CONFORM": {"b": 5, "c": 1, "n_common": 20,
                                             "p_mcnemar_exact": 0.2},
                         "HMIX_vs_OFF": {"b": 9, "c": 1, "n_common": 20,
                                         "p_mcnemar_exact": 0.02}}}
          for s in SETS}
    p2 = primary(ps, ["lcb3_medium", "evalplus"])
    if p2["family_size"] != FAMILY_SIZE:
        bad.append("少一集時 family_size 變了——§六-2 的禁令失效")
    if p2["HMIX_vs_CONFORM"]["b"] != 10 or p2["HMIX_vs_CONFORM"]["c"] != 2:
        bad.append("分層合併的 b/c 算錯")
    if "excluded_sets" not in p2:
        bad.append("少集時沒有印 excluded_sets——「N 少了多少」必須說出來")

    # (7) 推翻鍵：lcb3 任一層 c ≥ b ⇒ triggered
    r = refutation({"lcb3_hard": {"paired": {"HMIX_vs_CONFORM": {"b": 2, "c": 3}}},
                    "lcb3_medium": {"paired": {"HMIX_vs_CONFORM": {"b": 9, "c": 1}}}})
    if not r["triggered"] or not r["keys"]["lcb3_hard"]["c_ge_b"]:
        bad.append("推翻鍵：c ≥ b 沒有觸發")

    # (8) M1：`deliv` 必須同時要 accepted 與 meets_demand。
    #     交出去了但不對、以及對了卻沒交出去，兩種都**不算**交付成功。
    if _deliv({"accepted": True, "meets_demand": False}):
        bad.append("deliv：accepted 但 meets_demand=False 不該算成功")
    if _deliv({"accepted": False, "meets_demand": True}):
        bad.append("deliv：meets_demand 但沒 accepted 不該算成功（R667 凍結口徑）")
    if not _deliv({"accepted": True, "meets_demand": True}):
        bad.append("deliv：兩個都真卻不算成功")

    # (9) M2：分母是 complete case（交集），不是聯集。
    #     A 有 t0..t3、B 只有 t0..t1 ⇒ n_common 必須是 2，不是 4。
    A2 = _fake_rows("HMIX", [True, False, True, True], "t")
    B2 = _fake_rows("CONFORM", [False, False], "t")
    pr2 = paired(A2, B2)
    if pr2["n_common"] != 2:
        bad.append(f"paired n_common={pr2['n_common']}，應為 2（complete case 不是聯集）")
    if (pr2["b"], pr2["c"]) != (1, 0):
        bad.append(f"paired b/c={pr2['b']}/{pr2['c']}，應為 1/0")

    # (10) M3：tpc 用**含 void**的 token。void 格燒掉的 token 不進分母卻要進分子，
    #      只報「排除 void」會低估 H 臂的成本。
    calls = [
        {"ok": True, "usage": {"total_tokens": 100},
         "meta": {"arm": "HMIX", "task_id": "t0"}},          # 量到的格
        {"ok": True, "usage": {"total_tokens": 900},
         "meta": {"arm": "HMIX", "task_id": "t_void"}},      # void 格：燒了 900
        {"ok": False, "usage": {"total_tokens": 7},
         "meta": {"arm": "HMIX", "task_id": "t0"}},          # 失敗的呼叫不計 token
    ]
    tb = tokens_by_arm(calls, {"HMIX": {"t0"}})["HMIX"]
    if tb["tokens_incl_void"] != 1000:
        bad.append(f"tokens_incl_void={tb['tokens_incl_void']}，應為 1000（含 void 格）")
    if tb["tokens_excl_void"] != 100:
        bad.append(f"tokens_excl_void={tb['tokens_excl_void']}，應為 100")
    if tb["calls_wire_total"] != 3 or tb["calls_wire_ok"] != 2:
        bad.append(f"calls_wire_total/ok={tb['calls_wire_total']}/"
                   f"{tb['calls_wire_ok']}，應為 3/2（wire 層：含失敗那一通）")

    # (11) M5：`included_sets` 只准把 INVALID 的拿掉，不准安靜地少算一集。
    all_valid = {s: {"valid": True} for s in SETS}
    if included_sets(all_valid) != list(SETS):
        bad.append(f"included_sets 少算了：{included_sets(all_valid)}，應為 {list(SETS)}")
    one_bad = dict(all_valid, evalplus={"valid": False})
    if included_sets(one_bad) != [s for s in SETS if s != "evalplus"]:
        bad.append("included_sets 沒有正確拿掉 INVALID 的那一集")

    # (12) M6：`calls_per_task` 與 `calls_logical_total` **必須同源**
    #      （round529-2：DECISION_20260912 §六-2 的第一條不一致）。
    #      wire 層（calls.jsonl 的列數，含 wire_probe／重試）與邏輯層
    #      （rows.calls_used 的和）不是同一個數，共用一個名字會被除成鬼數字。
    loaded = {"rows": (_fake_rows("HMIX", [True, True], "t")
                       + _fake_rows("CONFORM", [True, False], "t")
                       + _fake_rows("OFF", [False, False], "t")),
              # wire 層刻意比邏輯層多：3 通（1 通是 wire_probe／重試）
              "calls": [{"ok": True, "usage": {"total_tokens": 10},
                         "meta": {"arm": "HMIX", "task_id": "t0"}},
                        {"ok": True, "usage": {"total_tokens": 10},
                         "meta": {"arm": "HMIX", "task_id": "t1"}},
                        {"ok": False, "usage": {"total_tokens": 0},
                         "meta": {"arm": "HMIX", "task_id": "t1"}}],
              "n_tasks": 2, "n_tasks_expected": 2, "blocks_present": 1,
              "blocks_expected": 1, "broken_reasons": [], "blocks": []}
    ps = per_set_stats("lcb3_medium", loaded)
    pa, tk = ps["per_arm"]["HMIX"], ps["tokens"]["HMIX"]
    if pa["calls_logical_total"] != 2:
        bad.append(f"calls_logical_total={pa['calls_logical_total']}，應為 2"
                   "（rows.calls_used 的和）")
    if tk["calls_wire_total"] != 3:
        bad.append(f"calls_wire_total={tk['calls_wire_total']}，應為 3"
                   "（calls.jsonl 的列數，含失敗那一通）")
    if pa["calls_per_task"] is None or abs(
            pa["calls_per_task"] * pa["n_measured"]
            - pa["calls_logical_total"]) > 1e-9:
        bad.append(f"calls_per_task({pa['calls_per_task']}) × n"
                   f"({pa['n_measured']}) ≠ calls_logical_total"
                   f"({pa['calls_logical_total']})——兩欄不同源")
    if tk["calls_logical_total"] != pa["calls_logical_total"]:
        bad.append("tokens.calls_logical_total 與 per_arm 的不一致")

    # (13) M7：V/GT 閘門。任一塊不是 CLEAN ⇒ 不准通過；沒給目錄＝沒量，不是 CLEAN。
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        vd = pathlib.Path(td)
        for blks in SETS.values():
            for blk in blks:
                (vd / f"vgt_v2_{blk}.json").write_text(
                    json.dumps({"verdict": "CLEAN", "violations": [],
                                "scope": "v2"}), encoding="utf-8")
        g = vgt_gate(vd)
        if not g["clean"] or g["clean_n"] != g["blocks_expected"]:
            bad.append(f"vgt_gate 全 CLEAN 卻不通過：{g['not_clean'][:3]}")
        dirty = SETS["lcb3_hard"][0]
        (vd / f"vgt_v2_{dirty}.json").write_text(
            json.dumps({"verdict": "VIOLATION",
                        "violations": [{"task_id": "x"}]}), encoding="utf-8")
        g2 = vgt_gate(vd)
        if g2["clean"] or f"{dirty}:VIOLATION" not in g2["not_clean"]:
            bad.append(f"vgt_gate 沒抓到髒的那一塊：{g2['not_clean'][:3]}")
        (vd / f"vgt_v2_{dirty}.json").unlink()
        g3 = vgt_gate(vd)
        if g3["clean"] or f"{dirty}:MISSING" not in g3["not_clean"]:
            bad.append("vgt_gate 把「檔案不在」當成通過了——沒掃過≠掃過是乾淨的")
    g4 = vgt_gate(None)
    if g4["applied"] or g4["clean"] is not None:
        bad.append("沒給 --vgt-dir 時應該是 applied=False／clean=None（沒量≠CLEAN）")

    # (14) M9：reasoning token 的帳。三通成功（兩通帶 reasoning）＋一通失敗
    #      ⇒ 分母是**成功的 3 通**，占比 2/3＝66.7%、均值 (100+200+0)/3＝100。
    #      66.7 ≥ 50 ⇒ thinking。一通成功都沒有 ⇒ unknown（**不是** non_thinking）。
    rcalls = [
        {"ok": True, "usage": {"completion_tokens": 300, "total_tokens": 400,
                               "completion_tokens_details": {"reasoning_tokens": 100}}},
        {"ok": True, "usage": {"completion_tokens": 400, "total_tokens": 500,
                               "completion_tokens_details": {"reasoning_tokens": 200}}},
        {"ok": True, "usage": {"completion_tokens": 10, "total_tokens": 20}},
        {"ok": False, "error": "HTTPError"},
    ]
    rs = reasoning_stats(rcalls)
    if rs["calls_ok"] != 3 or rs["calls_with_reasoning"] != 2:
        bad.append(f"reasoning calls_ok/with={rs['calls_ok']}/"
                   f"{rs['calls_with_reasoning']}，應為 3/2（失敗的呼叫不計）")
    if abs((rs["reasoning_call_pp"] or 0) - 200.0 / 3) > 1e-9:
        bad.append(f"reasoning_call_pp={rs['reasoning_call_pp']}，應為 66.67")
    if abs((rs["reasoning_tokens_mean"] or 0) - 100.0) > 1e-9:
        bad.append(f"reasoning_tokens_mean={rs['reasoning_tokens_mean']}，應為 100")
    if rs["inference_mode"] != "thinking":
        bad.append(f"inference_mode={rs['inference_mode']}，應為 thinking")
    if reasoning_stats([{"ok": True, "usage": {"completion_tokens": 2}}]
                       )["inference_mode"] != "non_thinking":
        bad.append("零 reasoning 的呼叫應判 non_thinking")
    if reasoning_stats([])["inference_mode"] != "unknown":
        bad.append("一通成功呼叫都沒有應判 unknown（量不到不是 non_thinking）")

    # (15) M8：`per_backend` 必須真的**分兩台**，而且只靠落盤 sidecar 分。
    #      兩塊：一塊在 1003、一塊在 1004；三臂都在自己那一塊裡配對。
    with tempfile.TemporaryDirectory() as td:
        troot = pathlib.Path(td)
        (troot / "runs").mkdir()
        blk_a, blk_b = SETS["lcb3_hard"][0], SETS["lcb3_hard"][1]
        (troot / "runs" / f"{blk_a}.backend_meta.json").write_text(
            json.dumps({"slot_host": "1003", "endpoint": "http://x/v1",
                        "declared": {"lmstudio_version": "0.4.24.0"}}),
            encoding="utf-8")
        # b 塊只有 .endpoint（沒有 backend_meta）⇒ 走 IP 兜底 + 版本對照表。
        (troot / "runs" / f"{blk_b}.endpoint").write_text(
            "http://100.86.226.21:1234/v1/chat/completions", encoding="utf-8")
        loaded = {
            "rows_by_block": {
                # 1003 那一塊：HMIX 兩題都對、CONFORM 一題對 ⇒ b/c = 1/0
                blk_a: (_fake_rows("HMIX", [True, True], "p")
                        + _fake_rows("CONFORM", [True, False], "p")
                        + _fake_rows("OFF", [False, False], "p")),
                # 1004 那一塊：HMIX 一題對、CONFORM 兩題都對 ⇒ b/c = 0/1
                blk_b: (_fake_rows("HMIX", [True, False], "q")
                        + _fake_rows("CONFORM", [True, True], "q")
                        + _fake_rows("OFF", [False, False], "q")),
            },
            "calls_by_block": {
                blk_a: [{"ok": True, "usage": {
                    "total_tokens": 1000, "completion_tokens": 900,
                    "completion_tokens_details": {"reasoning_tokens": 800}},
                    "meta": {"arm": "HMIX", "task_id": "p0"}}],
                blk_b: [{"ok": True, "usage": {
                    "total_tokens": 100, "completion_tokens": 90},
                    "meta": {"arm": "HMIX", "task_id": "q0"}}],
            },
        }
        pb = per_backend_stats(loaded, troot)
        if sorted(pb) != ["1003", "1004"]:
            bad.append(f"per_backend 沒有分成兩台：{sorted(pb)}")
        else:
            if pb["1003"]["backend"]["lmstudio_version"] != "0.4.24.0":
                bad.append("per_backend 沒讀到 backend_meta 的宣稱版本")
            if pb["1004"]["backend"]["lmstudio_version"] != "0.4.17":
                bad.append("per_backend 的 endpoint→host→版本兜底沒生效")
            if pb["1004"]["backend"]["lmstudio_version_source"] == "backend_meta.declared":
                bad.append("兜底來的版本卻標成 backend_meta——來源要說實話")
            pc3 = pb["1003"]["paired"]["HMIX_vs_CONFORM"]
            pc4 = pb["1004"]["paired"]["HMIX_vs_CONFORM"]
            if (pc3["b"], pc3["c"]) != (1, 0) or (pc4["b"], pc4["c"]) != (0, 1):
                bad.append(f"逐後端 b/c 算錯：1003={pc3['b']}/{pc3['c']} "
                           f"1004={pc4['b']}/{pc4['c']}，應為 1/0 與 0/1")
            if pb["1003"]["reasoning"]["inference_mode"] != "thinking":
                bad.append("1003 那一塊應判 thinking")
            if pb["1004"]["reasoning"]["inference_mode"] != "non_thinking":
                bad.append("1004 那一塊應判 non_thinking")
            if pb["1003"]["per_arm"]["HMIX"]["deliv_fraction"] != "2/2":
                bad.append("逐後端 deliv 分子分母算錯")

    for line in bad:
        print("FAIL " + line)
    print(f"selftest: {'OK（15 組手算對照全過）' if not bad else f'{len(bad)} 條不符'}")
    return 1 if bad else 0


# ── --mutation-check：每一種突變都要讓 selftest 變紅 ──────────────────
MUTATIONS = ("M1_deliv_ignores_accepted", "M2_union_denominator",
             "M3_tpc_ignores_void_calls", "M4_tpc_threshold_flipped",
             "M5_drop_a_set_silently",
             # round529-2：兩個新的紅線也要有牙齒。
             "M6_calls_per_task_from_wire",     # calls_per_task 與邏輯總數脫鉤
             "M7_vgt_not_checked",              # V/GT 髒了卻放行
             # 2026-09-13（DECISION_20260912 §十一）：逐後端那一格也要有牙齒。
             # 它不進仲裁，但它是「兩台是不是同一個推論條件」的**唯一**量具；
             # 安靜地把兩台併成一台、或安靜地把 reasoning 讀成 0，
             # 都會讓那個問題看起來已經被回答了。
             "M8_per_backend_merges_hosts",     # 兩台併成一台
             "M9_reasoning_ignored")            # reasoning token 一律讀成 0


def mutation_check() -> int:
    """把 analyzer 逐個弄壞，看 selftest／不變量抓不抓得到。

    抓不到的突變＝那條紅線其實不存在，而它會安靜地改掉裁決。
    """
    import subprocess
    caught, missed = [], []
    for m in MUTATIONS:
        env = dict(os.environ, R529_MUTANT=m)
        r = subprocess.run([sys.executable, str(pathlib.Path(__file__)), "--selftest"],
                           capture_output=True, text=True, env=env)
        (caught if r.returncode != 0 else missed).append(m)
        print(f"  {m}: {'抓到' if r.returncode != 0 else '**沒抓到**'}")
    print(f"mutation-check: 抓到 {len(caught)}/{len(MUTATIONS)}")
    if missed:
        print("沒抓到：" + ", ".join(missed) + " ——那幾條紅線其實不存在。")
    return 1 if missed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="R529 跨題庫收官分析尺")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--vgt-dir", default=None,
                    help="`harness_vgt_audit.py --scope v2` 的產物目錄"
                         "（找 vgt_v2_<block>.json）；任一塊 verdict≠CLEAN "
                         "⇒ decision_state=INVALID。不給＝這一格沒量（不是 CLEAN）")
    ap.add_argument("--json", default=None, help="把完整結果寫成 JSON")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mutation-check", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.mutation_check:
        return mutation_check()
    a = analyze(pathlib.Path(args.root),
                vgt_dir=pathlib.Path(args.vgt_dir) if args.vgt_dir else None)
    print(render(a))
    if args.json:
        p = pathlib.Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(a, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
        print(f"\n完整結果 → {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
