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
