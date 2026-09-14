#!/usr/bin/env python3
"""R530 的效力前提擋門：**E-9（沙箱）與 E-10（noop 格）**。

Fable 2026-09-14 裁決第 3 點。兩條都是「這份資料算不算數」的擋門，
**不是預測**——任一條紅，先修或先揭露，不准先判（§五-5 的同一條紀律）。

## E-9　沙箱的隔離強度是**發射前提**不是事後註解

`backend_meta.repo_hidden_from_sandbox` 必須為 `true` 才准發射。

為什麼是硬的：V/GT 紅線（§五-3 第 1 條）要的是「隱藏驗收在 worker 構得到的
地方**不存在**」。`repo_hidden_from_sandbox=false` 的時候，`ops/gain/r530/hidden/`
是**讀得到**的，擋著的只有 `DENY` 的指令文字比對——而擋門建立在
「模型不會換個寫法」上。那不是結構性保證，是紀律。

`write_confined=false` 不是發射擋門，但要記，而且**每格結束後要比對
「工作區外沒有新檔」**（`outside_new_files`）。理由：沒有檔案隔離的時候，
「這一格有沒有寫到工作區外面」是一個只能事後觀察的事實，
而事實沒有被觀察就等於沒有發生過——那正是 R530 不准接受的那種空白。

## E-10　什麼都沒發生的格子

`noop_cell` ＝ `ws_start == ws_end` **且** 零工具呼叫。

為什麼要單獨數它：2026-09-13 的第一次真後端冒煙，6 格裡 4 格是這個狀態，
而**在 `rows.jsonl` 上它長得跟「模型很笨」一模一樣**（低分、低通過率）。
分得出來只因為工作區樹雜湊是一個**獨立於模型輸出**的訊號。
那一次的真因是工具協定不通（模型不寫 ```bash 圍欄）——
**量具故障，不是結果**。

⇒ 同一臂的 noop 比例 **> 20%** ⇒ 整個 run `INVALID`。
低於門檻的 noop 格**照 `accepted` 語意計**，不特別處理：
  · `A-SOLO`：交付一份空的（`accepted=True`、`deliv=False`）——
    它沒有拒交語意，這是定義不是量測。
  · `A-GATE`／`A-CONF`：`accepted=False`。

⚠ 20% 這個門檻是 Fable 訂的，**不是從任何實測推出來的**。
  它與 P-W9 的 `infra_void ≤ 10%` 是同一種東西（量具故障率的上界），
  引用時要跟著講它是約定不是量測。
"""
from __future__ import annotations

import pathlib

#: E-10 的門檻：同一臂的 noop 比例超過它 ⇒ 整個 run INVALID。
NOOP_RATE_ABORT = 0.20


def e9_sandbox_gate(backend_meta: dict) -> dict:
    """E-9：沙箱夠不夠格發射。回 `{"ok", "reason", …}`。

    `ok` 為 False ⇒ **不准發射**。這支不自己停，停是呼叫端的事
    （`run_r530` 在任何一通模型呼叫之前讀它）。
    """
    meta = backend_meta or {}
    hidden = meta.get("repo_hidden_from_sandbox")
    rec = {
        "gate": "E-9",
        "sandbox": meta.get("sandbox") or meta.get("backend"),
        "sandbox_uid": meta.get("sandbox_uid"),
        "network_isolated": meta.get("network_isolated"),
        "write_confined": meta.get("write_confined"),
        "repo_hidden_from_sandbox": hidden,
        "ok": hidden is True,
    }
    if hidden is not True:
        rec["reason"] = (
            "abort_repo_visible_from_sandbox：沙箱裡看得到 repo（裡面有 "
            "ops/gain/r530/hidden/）⇒ 隱藏驗收的隔離靠的是 DENY 擋門而不是"
            "結構。E-9 要求 repo_hidden_from_sandbox 為 true 才准發射。")
    elif meta.get("write_confined") is not True:
        # 不擋發射，但要記，而且每格結束後要比對工作區外有沒有新檔。
        rec["warning"] = (
            "write_confined=false：沒有檔案隔離，只有 unix 權限。"
            "每格結束後必須比對 outside_new_files（本擋門不代勞）。")
    return rec


def snapshot_outside(work_root: str | pathlib.Path) -> set[str]:
    """工作區**根目錄**底下的直屬項目快照。

    `write_confined=false` 時，每格前後各取一次，差集就是
    「這一格寫到工作區外面的東西」。只看直屬層：更深的比對要掃整棵樹，
    而那在每格都做會比跑實驗還慢，且抓到的東西幾乎都是我們自己寫的
    （`_verify`／`ws`）。**這是一個有意的淺檢查，不准被引用成「沒有外洩」。**
    """
    root = pathlib.Path(work_root)
    if not root.is_dir():
        return set()
    return {p.name for p in root.iterdir()}


def e10_noop_gate(rows: list[dict], *,
                  rate_abort: float = NOOP_RATE_ABORT) -> dict:
    """E-10：逐臂的 noop 比例。回可落盤的判定。

    ⚠ `offending_cells` **逐格記名**（`arm`／`task_id`／`seed`）——
      「有幾格壞掉」不准只報一個數字（§五-5 的同一條）。
    """
    per_arm: dict[str, dict] = {}
    offending: list[dict] = []
    for r in rows or []:
        arm = r.get("arm")
        d = per_arm.setdefault(arm, {"n": 0, "noop": 0})
        d["n"] += 1
        if r.get("noop_cell"):
            d["noop"] += 1
            offending.append({"arm": arm, "task_id": r.get("task_id"),
                              "seed": r.get("seed"),
                              "stop_reason": r.get("stop_reason")})
    over = []
    for arm, d in sorted(per_arm.items()):
        d["rate"] = (d["noop"] / d["n"]) if d["n"] else 0.0
        if d["rate"] > rate_abort:
            over.append(arm)
    return {
        "gate": "E-10",
        "rate_abort": rate_abort,
        "per_arm": per_arm,
        "arms_over_threshold": over,
        "offending_cells": offending,
        "ok": not over,
        "reason": (None if not over else
                   f"noop 比例超過 {rate_abort:.0%} 的臂：{over}"
                   "——工作區逐位元沒動且零工具呼叫代表量具故障，不是結果。"
                   "整個 run INVALID。"),
        "honest_bound": (
            f"{rate_abort:.0%} 是 Fable 2026-09-14 訂的約定，"
            "不是從任何實測推出來的門檻；引用時要跟著講。"),
    }


# ══ E-11　推論模式必須一致（Fable 2026-09-14 第六輪裁決）══════════════
#
# R529 §十一 的教訓：**同一份 gguf 可以在兩台上跑成兩種實驗條件**
# （thinking／非 thinking），而那件事只有落盤看得出來——沒有錯誤訊息、
# 沒有異常，只有一批不能併的資料。R530 的兩台後端有同樣的曝險，而且更隱蔽：
# `reasoning_effort=none` 在**不帶 tools** 的請求上生效，不代表它在**帶 tools**
# 的請求上生效，而 R530 只走後者。
#
# 兩段：
#   · 發射前（`e11_preflight_gate`）：兩台的探針都必須 `reasoning_tokens == 0`。
#     欄位不存在（`FIELD_MISSING`）**也算紅**——量不到不是通過。
#   · 收官時（`e11_closeout_gate`）：該塊實際呼叫的 reasoning 占比 > 0
#     ⇒ 該塊 `broken`（`inference_mode_inconsistent`），資料不進分析。
#
# ⚠ 這一條擋的是**條件不一致**，不是「thinking 比較差」。
#   兩台都 thinking 也可以是一個合法的 run——只要**一致**而且落盤。
#   會殺掉資料的是「一台是、一台不是」而沒有人發現。
E11_BROKEN = "inference_mode_inconsistent"


def e11_preflight_gate(probes: dict) -> dict:
    """`probes`：`{host_or_api: probe_inference_mode(...) 的回傳}`。

    **每一台都要有探針**；缺一台算紅（沒有量過的那一台不能假設它一樣）。
    """
    rec: dict = {"gate": "E-11", "phase": "preflight", "per_endpoint": {},
                 "ok": bool(probes)}
    if not probes:
        rec["reason"] = "abort_no_inference_probe：一台都沒有量過。停。"
        return rec
    for key, pr in sorted(probes.items()):
        zero = pr.get("reasoning_tokens_all_zero")
        entry = {
            "reasoning_tokens": pr.get("reasoning_tokens"),
            "all_zero": zero,
            "reasoning_effort_sent": pr.get("reasoning_effort_sent"),
            "prefill_ms_per_1k_prompt": pr.get("prefill_ms_per_1k_prompt"),
            "long_ctx_ms_per_1k_prompt": pr.get("long_ctx_ms_per_1k_prompt"),
            "prefill_diff_unusable": pr.get("prefill_diff_unusable"),
            "error": pr.get("error"),
        }
        rec["per_endpoint"][key] = entry
        if zero is not True:
            rec["ok"] = False
    # prefill 差異不是擋門，但要**被看見**：它會讓 budget_wall 在兩台上
    # 咬到不同的地方（跨題的差別截斷）。
    # 優先讀單通上界（跨台可比、不會是負的）；差分法只在它真的可用時才用。
    pf = {k: (v.get("long_ctx_ms_per_1k_prompt")
              or v.get("prefill_ms_per_1k_prompt"))
          for k, v in rec["per_endpoint"].items()
          if (v.get("long_ctx_ms_per_1k_prompt")
              or v.get("prefill_ms_per_1k_prompt"))}
    if len(pf) >= 2:
        rec["prefill_spread"] = {
            "per_endpoint": pf,
            "max_over_min": round(max(pf.values()) / min(pf.values()), 2),
            "warning": (
                "prefill 吞吐差距**不擋發射**，但它是實驗條件：多輪迴圈每通重送"
                "整段對話 ⇒ 慢的那台隨輪數二次地慢 ⇒ `budget_wall` 在兩台上咬到"
                "不同的地方。收官報 `wall_s` 分佈時要逐台分開。"),
        }
    if not rec["ok"]:
        rec["reason"] = (
            "abort_reasoning_tokens_nonzero：**在原生 tools 請求下** "
            "`reasoning_tokens` 不是 0（或端點根本沒回報這個欄位）⇒ "
            "推論模式不是我們以為的那一種。R529 §十一 的同一條：同一份 gguf "
            "可以跑成兩種實驗條件，而那只有落盤看得出來。停。")
    return rec


def e11_closeout_gate(calls: list[dict], *, block: str | None = None) -> dict:
    """收官：這一塊實際燒掉的 reasoning 占比。> 0 ⇒ 該塊 `broken`。"""
    rt = ct = 0
    missing = seen = 0
    for r in calls or []:
        if not r.get("ok") or not (r.get("meta") or {}).get("arm"):
            continue
        seen += 1
        u = r.get("usage") or {}
        det = u.get("completion_tokens_details") or {}
        ct += int(u.get("completion_tokens") or 0)
        if "reasoning_tokens" in det:
            rt += int(det["reasoning_tokens"] or 0)
        else:
            missing += 1
    share = (rt / ct) if ct else 0.0
    ok = (seen > 0) and (rt == 0) and (missing == 0)
    rec = {
        "gate": "E-11", "phase": "closeout", "block": block,
        "calls_audited": seen,
        "reasoning_tokens_total": rt,
        "completion_tokens_total": ct,
        "reasoning_share": round(share, 6),
        "calls_without_the_field": missing,
        "ok": ok,
        "verdict": "ok" if ok else E11_BROKEN,
    }
    if seen == 0:
        rec["reason"] = "一通都沒稽核到——量具沒接上不是通過。"
    elif missing:
        rec["reason"] = (f"{missing} 通沒有回報 `reasoning_tokens` ⇒ 那幾通的"
                         "推論模式我們量不到。量不到不是通過。")
    elif rt:
        rec["reason"] = (f"reasoning 占 completion 的 {share:.2%} ⇒ 這一塊跑的"
                         "推論模式與登記的不同，資料不進分析（`broken`）。")
    return rec
