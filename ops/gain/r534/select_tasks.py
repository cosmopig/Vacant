#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R534 選題：從 LCB v2（120 題）裡挑出這一輪 pi agent 要跑的 20 題。

這支在架構裡承重什麼
--------------------
R534 要量的是**可究責層的三件事**（可執行驗收當出貨閘門／沒過就重抽／仍沒過就
拒交）在一個**外部 agent harness**（pi）上還成不成立。要量它就得先決定量在哪些
題上，而「挑哪些題」本身就是一個會決定結論的旋鈕——挑「閘門救得回來」的題，
差值一定變大；挑整個題庫，差值會被大量「兩邊都過」「兩邊都不過」的題稀釋。

所以這支把選題拆成**兩層，事前寫死、分開報**，不合併成一個數字：

* **A 層（高分歧，10 題）**：用已歸檔的 run 算每題的「閘門相關分歧度」`D_net`，
  取前 10。**這一層是條件在過去結果上挑出來的 ⇒ 它的差值結構性地上偏**，
  只能拿來看機制在「閘門有機會發揮的題」上長什麼樣，不能當成題庫層級的估計。
* **B 層（隨機，10 題）**：從扣掉 A 層之後的剩餘題裡，用寫死的種子字串抽 10 題。
  這一層沒有條件在結果上；它是題庫層級的樣子。注意它抽的是 *剩餘* 而不是全部
  118 題 ⇒ 高分歧題已被 A 層抽走一部分，**B 層若有差值，是偏保守的那一側**。

選取規則是一個**對已歸檔資料的確定性函式**：同樣的 rows.jsonl 跑幾次都同一份
20 題，`--check` 可以驗 manifest 沒有漂。規則逐字寫在 `RULE_TEXT`，並原樣抄進
`bank_manifest.json`——挑題規則不落盤等於沒有規則。

證據來源（只讀，不重跑）
------------------------
* 12B 層：`runs/g_r460_harness_lcb2_{a1,a2,a3,b1,b2,b3}/rows.jsonl`
  （gemma-4-12b-it-qat，seed `g-r440-lcb2`，6 塊 × 20 題 ＝ 全 120 題，
   六臂 OFF/OFF5/CONFORM/HPI/HOC/HMIX 各一筆）
* 27B 層：`runs/g_r532_lcb2_a{1..6}/rows.jsonl`
  （qwen3-27b，6 塊 × 20 題 ＝ 全 120 題，三臂 OFF/CONFORM/HMIX 各一筆）

兩層的每一格都有 `meets_demand`（隱藏測資判定，真正的分子），沒有 null、
沒有 infra_void ⇒ 不需要缺值規則。**誠實邊界：每題每臂只有一個觀測**，
`D_net` 因此是一個帶抽樣雜訊的排序鍵，不是「這題閘門一定有效」的證據。

用法
----
    python3 ops/gain/r534/select_tasks.py            # 印兩層選題與逐題表
    python3 ops/gain/r534/select_tasks.py --json     # 機器讀
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

BANK_PATH = os.path.join(REPO, "ops", "gain", "data", "lcb_bank_v2.jsonl")
BANK_SHA256 = "b98f027213e2469a0a41bed813d99f029d3d6e2fac64e0fa18887c42c865b9ba"
BANK_N = 120

# ops/gain/check_bank_precision.py::KNOWN_BAD["lcb2"]，逐字。
KNOWN_BAD = ("lcb_3613", "lcb_3763")

# 證據來源：兩個模型尺度各一組已歸檔 run。
STRATA = {
    "12B": {
        "glob": "runs/g_r460_harness_lcb2_*/rows.jsonl",
        "model": "gemma-4-12b-it-qat",
        "run_family": "g_r460_harness_lcb2",
        "baseline_arm": "OFF",
        "gated_arms": ("CONFORM", "HPI", "HOC", "HMIX"),
    },
    "27B": {
        "glob": "runs/g_r532_lcb2_*/rows.jsonl",
        "model": "qwen3-27b",
        "run_family": "g_r532_lcb2",
        "baseline_arm": "OFF",
        "gated_arms": ("CONFORM", "HMIX"),
    },
}

N_LAYER_A = 10
N_LAYER_B = 10
LAYER_B_SEED = "r534-layerB-lcb2-2026-09-18"

RULE_TEXT = """\
R534 選題規則（事前寫死；對已歸檔資料的確定性函式）

R0 母體：ops/gain/data/lcb_bank_v2.jsonl 的 120 題，sha256 釘死
   b98f027213e2469a0a41bed813d99f029d3d6e2fac64e0fa18887c42c865b9ba。

R1 排除：check_bank_precision.py::KNOWN_BAD["lcb2"] 的 lcb_3613、lcb_3763。
   合格母體 ＝ 118 題。

R2 證據：只讀已歸檔 rows.jsonl，不重跑任何模型。
   12B 層 ＝ runs/g_r460_harness_lcb2_{a1,a2,a3,b1,b2,b3}（gemma-4-12b-it-qat，
   seed g-r440-lcb2，六臂）；27B 層 ＝ runs/g_r532_lcb2_a{1..6}（qwen3-27b，三臂）。
   讀的欄位只有 task_id／arm／meets_demand（隱藏測資判定）。

R3 閘門對：12B 層取 (OFF, CONFORM)、(OFF, HPI)、(OFF, HOC)、(OFF, HMIX)；
   27B 層取 (OFF, CONFORM)、(OFF, HMIX)。共 6 對。
   OFF5 不列入——它是「五次呼叫多數決」的等預算對照，沒有驗收閘門語意，
   把它算進來會讓「分歧」混進「多花錢」。

R4 逐題分歧度：對每一對，
     d = +1  若 OFF.meets_demand=False 且 gated.meets_demand=True
     d = -1  若 OFF.meets_demand=True  且 gated.meets_demand=False
     d =  0  其餘
   D_plus ＝ (+1) 的對數，D_minus ＝ (-1) 的對數，D_net ＝ D_plus - D_minus，
   值域 [-6, +6]。

R5 A 層（高分歧，10 題）：合格母體依
     (D_net 由大到小, D_plus 由大到小, OFF 通過次數由小到大, task_id 字典序)
   排序，取前 10。⚠ 這一層條件在過去結果上 ⇒ 差值上偏，只能單獨報。

R6 B 層（隨機，10 題）：從 118 題扣掉 A 層的 10 題之後的 108 題裡，
   以 random.Random("r534-layerB-lcb2-2026-09-18").sample(sorted(剩餘), 10) 抽出。
   種子字串寫死在 select_tasks.py::LAYER_B_SEED。

R7 報告紀律：A 層與 B 層的結果**分開報**，不合併成一個數字，也不加權平均。
   B 層抽的是「扣掉 A 層之後」的剩餘 ⇒ 高分歧題已被抽走一部分，
   B 層的差值是偏保守的那一側；報告要寫出這件事。

R8 誠實邊界：每題每臂在每一層只有一個觀測，D_net 是帶抽樣雜訊的排序鍵，
   不是「這題閘門一定有效」的證據。A 層預期會有向均值回歸。
"""


def _load_rows(pattern: str) -> tuple[dict[str, dict[str, dict]], list[str]]:
    """回 (`{task_id: {arm: row}}`, 讀到的檔案清單)；缺塊／重複格一律 raise（fail-closed）。"""
    out: dict[str, dict[str, dict]] = {}
    files = sorted(glob.glob(os.path.join(REPO, pattern)))
    if not files:
        raise SystemExit(f"找不到 rows：{pattern}。停。")
    for path in files:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                tid, arm = row["task_id"], row["arm"]
                if row.get("meets_demand") is None:
                    raise SystemExit(f"{path} 的 {tid}/{arm} meets_demand 是 null。停。")
                if arm in out.setdefault(tid, {}):
                    raise SystemExit(f"{path} 的 {tid}/{arm} 重複出現。停。")
                out[tid][arm] = row
    return out, [os.path.relpath(p, REPO) for p in files]


def _bank_task_ids() -> list[str]:
    import hashlib

    raw = open(BANK_PATH, "rb").read()
    got = hashlib.sha256(raw).hexdigest()
    if got != BANK_SHA256:
        raise SystemExit(f"題庫 sha256 不符：got {got} want {BANK_SHA256}。停。")
    ids = [json.loads(l)["task_id"] for l in raw.decode("utf-8").splitlines() if l.strip()]
    if len(ids) != BANK_N or len(set(ids)) != BANK_N:
        raise SystemExit(f"題數不符或有重複：{len(ids)}。停。")
    return ids


def select() -> dict:
    """回一份完整的選題結果（含逐題證據），不寫任何檔案。"""
    bank_ids = _bank_task_ids()
    eligible = [t for t in bank_ids if t not in KNOWN_BAD]

    evidence: dict[str, dict] = {}
    sources: dict[str, list[str]] = {}
    for name, spec in STRATA.items():
        rows, files = _load_rows(spec["glob"])
        sources[name] = files
        evidence[name] = rows
        missing = [t for t in eligible if t not in rows]
        if missing:
            raise SystemExit(f"{name} 層缺題：{missing[:5]}…。停。")

    per_task: dict[str, dict] = {}
    for tid in eligible:
        pairs = []
        d_plus = d_minus = 0
        off_pass = 0
        for name, spec in STRATA.items():
            row_by_arm = evidence[name][tid]
            base = bool(row_by_arm[spec["baseline_arm"]]["meets_demand"])
            off_pass += int(base)
            for arm in spec["gated_arms"]:
                gated = bool(row_by_arm[arm]["meets_demand"])
                d = 1 if (not base and gated) else (-1 if (base and not gated) else 0)
                d_plus += int(d == 1)
                d_minus += int(d == -1)
                pairs.append({"stratum": name, "gated_arm": arm,
                              "off": base, "gated": gated, "d": d})
        per_task[tid] = {
            "task_id": tid,
            "D_plus": d_plus,
            "D_minus": d_minus,
            "D_net": d_plus - d_minus,
            "off_pass_count": off_pass,
            "pairs": pairs,
            "arms": {name: {a: bool(r["meets_demand"]) for a, r in evidence[name][tid].items()}
                     for name in STRATA},
            "accepted": {name: {a: bool(r["accepted"]) for a, r in evidence[name][tid].items()}
                         for name in STRATA},
        }

    ranked = sorted(
        eligible,
        key=lambda t: (-per_task[t]["D_net"], -per_task[t]["D_plus"],
                       per_task[t]["off_pass_count"], t),
    )
    layer_a = ranked[:N_LAYER_A]
    remainder = sorted(set(eligible) - set(layer_a))
    layer_b = sorted(random.Random(LAYER_B_SEED).sample(remainder, N_LAYER_B))

    return {
        "rule_text": RULE_TEXT,
        "bank_path": os.path.relpath(BANK_PATH, REPO),
        "bank_sha256": BANK_SHA256,
        "bank_n": BANK_N,
        "known_bad_excluded": list(KNOWN_BAD),
        "eligible_n": len(eligible),
        "evidence_sources": sources,
        "strata": {k: {kk: vv for kk, vv in v.items() if kk != "glob"}
                   for k, v in STRATA.items()},
        "layer_a_seed": None,
        "layer_b_seed": LAYER_B_SEED,
        "layer_a": layer_a,
        "layer_b": layer_b,
        "per_task": per_task,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="R534 選題（只讀已歸檔 run）")
    ap.add_argument("--json", action="store_true", help="輸出機器讀 JSON")
    args = ap.parse_args(argv)
    sel = select()
    if args.json:
        json.dump(sel, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        print()
        return 0
    print(RULE_TEXT)
    for layer in ("layer_a", "layer_b"):
        print(f"── {layer} ({len(sel[layer])} 題) ──")
        print(f"{'task_id':>10} {'D_net':>6} {'D+':>3} {'D-':>3} {'OFF通過/2':>9}  "
              f"12B OFF/CONFORM/HPI/HOC/HMIX   27B OFF/CONFORM/HMIX")
        for tid in sel[layer]:
            p = sel["per_task"][tid]
            a12 = p["arms"]["12B"]
            a27 = p["arms"]["27B"]
            f = lambda b: "1" if b else "0"
            print(f"{tid:>10} {p['D_net']:>6} {p['D_plus']:>3} {p['D_minus']:>3} "
                  f"{p['off_pass_count']:>9}  "
                  f"  {f(a12['OFF'])}/{f(a12['CONFORM'])}/{f(a12['HPI'])}/"
                  f"{f(a12['HOC'])}/{f(a12['HMIX'])}"
                  f"            {f(a27['OFF'])}/{f(a27['CONFORM'])}/{f(a27['HMIX'])}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
