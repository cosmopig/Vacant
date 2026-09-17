#!/usr/bin/env python3
"""R532 發射前擋門 E-14：persona 不變量離線重放（DECISION_20260917_R532 §二-4／§五-5）。

這支在架構裡承重什麼
────────────────────
R532 的主張是「**只換了 worker 模型**」。要讓這句話可驗，必須證明
persona（POOL 裡那六個 system prompt 身份）的指派序列**與模型輸出無關**，
因而與 12B 那輪**逐格相同**。§二-4 主張這一點成立的機制是：

  `gain_run.py` 在建 arm 狀態時**每一臂各自**開一顆
  `random.Random(f"{seed}:{arm}")`（不是全域共用），而每一臂**每題抽幾次**
  是寫死的常數，抽樣發生在任何模型呼叫**之前**：

    OFF      1 次   `a = rng.choice(agents)`                    （arm_off 第一行）
    CONFORM  5 次   `assigned = [rng.choice(agents) ...]`        （一次抽滿，早停不減）
    HMIX     1 次   `worker = rng.choice(agents)`               （harness_arms，一題一人）
    HPI/HOC  1 次   （與 HMIX 同一支 run_harness_arm）

  ⇒ 同 seed ＋ 同 bank ＋ 同 offset ⇒ 每一格 (task, arm) 的 persona 與
  R460／R529 逐格相同，與模型是哪一顆無關，也與臂清單是三臂還是六臂無關。

本腳本把上面那條序列**離線重放**（零模型呼叫、不碰題庫、不碰端點），
與對照 run 的 `rows.jsonl` 裡的 persona 欄位逐格比對。一格不符就停
（§五-5）——那代表「只換了模型」這句話是假的，發射出去的 run 不能與
12B 那輪配對。

**哪些臂不在判定內，以及為什麼**（保守排除，不是遺漏）：
  · `OFF5`／`EQ5`：`arm_off5` 除了 k 次 `rng.choice(agents)`，在多數決階段
    還有 `rng.choice(tied)`／`rng.choice(win)`（gain_run 第 526/527、851/852 行），
    抽取次數在 `InfraVoid` 下不固定 ⇒ 序列不是資料無關的，不可純離線重放。
  · `ON`／`ONR`：`_route_agent`／評審池 shuffle 依賴聲譽狀態，同樣資料相依。
  這幾條臂都不在 R532 的 `--arms OFF,CONFORM,HMIX` 裡，排除不影響本擋門的效力。

**單邊保證**：本擋門證明的是「persona 指派序列可離線重算且與落盤逐格相符」。
它不證明題目內容相同（那是 §五-7 的 sha 釘死與 §二-1 的釘值在管），
也不證明後端條件相同（§五-1 E-12）。

零模型呼叫、唯讀；不修改任何既有程式碼。
用法：
    python3 ops/gain/r532/check_persona_invariant.py [--run runs/xxx ...] [--all-authorized]
退出碼：0 = E14 PASS，1 = E14 FAIL。
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import random
import socket
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops.gain.brain_cline import POOL  # noqa: E402  單一真相：agent 池與順序

# §二-4 那張表。值＝每題固定抽幾次；抽樣在模型呼叫之前，InfraVoid 不影響次數。
DRAWS_PER_TASK = {"OFF": 1, "CONFORM": 5, "HPI": 1, "HOC": 1, "HMIX": 1}
# 資料相依、不可純離線重放（理由見模組 docstring）。
UNREPLAYABLE = {"OFF5", "EQ5", "ON", "ONR"}

# §二-3 的四顆 seed；--all-authorized 會掃這四顆底下所有 run。
AUTHORIZED_SEEDS = ["g-r440-lcb2", "g-r529-lcb3", "g-r529-he", "g-r529-mbpp"]
# 預設對照 run：四顆 seed 各一個（§五-5）。
DEFAULT_RUNS = [
    "runs/g_r460_harness_lcb2_a1",
    "runs/g_r529_lcb3m_a1",
    "runs/g_r529_hep_a1",
    "runs/g_r529_mbpp_a1",
]


def replay(seed: str, arm: str, n_tasks: int, agent_ids: list[str]) -> list[list[str]]:
    """重放某一臂的抽樣序列，回傳每題的 persona 清單（長度＝該臂每題抽幾次）。"""
    rng = random.Random(f"{seed}:{arm}")
    k = DRAWS_PER_TASK[arm]
    return [[rng.choice(agent_ids) for _ in range(k)] for _ in range(n_tasks)]


def observed_personas(row: dict) -> list[str]:
    """從一列 rows.jsonl 取出**可觀測**的 persona 序列。

    CONFORM 早停 ⇒ 落盤的 `involved` 只是 5 次抽樣的**前綴**
    （`arm_conform` return: `[a.agent_id for a in assigned[:len(attempts)]]`），
    所以只比得到前綴——抽樣次數仍然是 5，重放不能少抽。
    """
    arm = row["arm"]
    if arm == "CONFORM":
        inv = list(row.get("involved") or [])
        return inv
    return [row["worker"]]


def check_run(run_dir: pathlib.Path, agent_ids: list[str]) -> tuple[int, int, list[str], list[str]]:
    """回傳 (比對格數, 比對 persona 數, 不符清單, 備註清單)。"""
    notes: list[str] = []
    mism: list[str] = []
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    rows_path = run_dir / "rows.jsonl"
    if not rows_path.exists():
        notes.append(f"{run_dir.name}: 沒有 rows.jsonl，跳過")
        return 0, 0, mism, notes
    seed = summary.get("seed")
    if not seed:
        notes.append(f"{run_dir.name}: summary.json 沒有 seed，跳過")
        return 0, 0, mism, notes

    by_arm: dict[str, dict[int, dict]] = {}
    seq_counter: dict[str, int] = {}
    for line in rows_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        arm = r.get("arm")
        if arm is None:
            continue
        seq_counter[arm] = seq_counter.get(arm, 0) + 1
        # `i` 是 gain_run 主迴圈的 enumerate(tasks, 1)，即塊內題序；
        # 沒有 `i` 的舊 run 退回「該臂的出現順序」（infra_void 會讓它偏移，
        # 所以只在沒有 `i` 時使用，並在備註裡標明）。
        idx = r.get("i")
        if idx is None:
            idx = seq_counter[arm]
            notes.append(f"{run_dir.name}/{arm}: rows 沒有 `i` 欄位，改用出現順序")
        by_arm.setdefault(arm, {})[int(idx)] = r

    cells = 0
    personas = 0
    for arm in sorted(by_arm):
        if arm in UNREPLAYABLE:
            notes.append(f"{run_dir.name}/{arm}: 資料相依抽樣，不進判定（見 docstring）")
            continue
        if arm not in DRAWS_PER_TASK:
            notes.append(f"{run_dir.name}/{arm}: §二-4 未定義抽取次數，不進判定")
            continue
        idxs = by_arm[arm]
        n_tasks = max(idxs)
        exp = replay(seed, arm, n_tasks, agent_ids)
        gap = n_tasks - len(idxs)
        if gap:
            notes.append(f"{run_dir.name}/{arm}: 題序 1..{n_tasks} 少了 {gap} 格"
                         f"（infra_void／中斷）——rng 仍照抽，只比對有落盤的格")
        for i in sorted(idxs):
            row = idxs[i]
            obs = observed_personas(row)
            want = exp[i - 1][:len(obs)] if obs else []
            cells += 1
            personas += len(obs)
            if obs != want:
                mism.append(
                    f"{run_dir.name} seed={seed} arm={arm} i={i} "
                    f"task={row.get('task_id')} 落盤={obs} 重放={exp[i - 1]}")
            if arm == "CONFORM" and obs and row.get("worker") != obs[-1]:
                mism.append(
                    f"{run_dir.name} seed={seed} arm=CONFORM i={i} "
                    f"worker={row.get('worker')} 與 involved 尾端 {obs[-1]} 不一致")
    return cells, personas, mism, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", default=None,
                    help="對照 run 目錄（可重複）；預設＝四顆 seed 各一個")
    ap.add_argument("--all-authorized", action="store_true",
                    help="改掃 §二-3 四顆 seed 底下**所有** run")
    ap.add_argument("--repo", default=None)
    args = ap.parse_args()

    repo = pathlib.Path(args.repo).resolve() if args.repo else REPO
    agent_ids = [aid for aid, _ in POOL]

    print("── E-14 persona 不變量離線重放（DECISION §二-4／§五-5）")
    print(f"   主機　{socket.gethostname()}")
    print(f"   repo　{repo}")
    print(f"   agent 池（brain_cline.POOL，順序即 rng.choice 的定義域）："
          f"{agent_ids}")

    if args.all_authorized:
        targets = []
        for p in sorted(glob.glob(str(repo / "runs" / "*" / "summary.json"))):
            try:
                if json.loads(pathlib.Path(p).read_text(encoding="utf-8")
                              ).get("seed") in AUTHORIZED_SEEDS:
                    targets.append(pathlib.Path(p).parent)
            except Exception:
                continue
    else:
        targets = [repo / r for r in (args.run or DEFAULT_RUNS)]

    total_cells = total_personas = 0
    all_mism: list[str] = []
    all_notes: list[str] = []
    for d in targets:
        if not (d / "summary.json").exists():
            all_notes.append(f"{d}: 找不到 summary.json，跳過")
            continue
        c, p, m, n = check_run(d, agent_ids)
        seed = json.loads((d / "summary.json").read_text(encoding="utf-8")).get("seed")
        status = "OK" if not m else f"不符 {len(m)}"
        print(f"   · {d.name}　seed={seed}　{c} 格／{p} 個 persona　{status}")
        total_cells += c
        total_personas += p
        all_mism += m
        all_notes += n

    for n in all_notes:
        print(f"   ⓘ {n}")

    if all_mism:
        print(f"E14 FAIL（不符 {len(all_mism)} 格／共比對 {total_cells} 格）")
        for line in all_mism[:10]:
            print(f"   ✗ {line}")
        if len(all_mism) > 10:
            print(f"   …另有 {len(all_mism) - 10} 格未列出")
        return 1
    if total_cells == 0:
        print("E14 FAIL（一格都沒比到——量不到不是通過，是沒接上）")
        return 1
    print(f"E14 PASS (比對 {total_cells} 格，{total_personas} 個 persona)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
