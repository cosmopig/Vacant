#!/usr/bin/env python3
"""ctl_select16 — 修正 3 的選題規則（原樣實作，不改）：
1. 先取校準沒過、但 hidden 通過比例 ≥30% 的題。
2. 再依序交替補上「校準沒過且比例 <30%」與「校準通過」的題；校準通過的題最多 4 題，其中至少 2 題來自 hard 集。
   同一類內以題名字典序。
3. 湊不滿 16 就有幾題用幾題（不低於 12；低於 12 要回報）。
「hard 集」＝ exercism_py_hard.json 的 chosen_tasks（19 題候選裡扣 ex_alphametics）。
解讀（修正 3 沒寫、這裡照實標明）：「至少 2 題來自 hard」只作用在「校準通過」那一類——若通過的題少於 2 題來自 hard，
能補多少補多少。「交替」＝先 fail<30%、再 pass、再 fail<30%…，一類用完就只取另一類。
Usage: ctl_select16.py <table.json> [--hard <exercism_py_hard.json>]
"""
import argparse
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def select(rows: list[dict], hard: set[str]) -> dict:
    ok = [r for r in rows if "hid" in r]
    c1 = sorted([r["task"] for r in ok if not r["hidpass"] and r["frac"] >= 0.3])
    c2 = sorted([r["task"] for r in ok if not r["hidpass"] and r["frac"] < 0.3])
    c3 = sorted([r["task"] for r in ok if r["hidpass"]])
    # pass 類：先保證 hard 的 2 題，再按字典序補到 4
    p_hard = [t for t in c3 if t in hard][:2]
    p_rest = [t for t in c3 if t not in p_hard]
    passes = p_hard + p_rest[: max(0, 4 - len(p_hard))]
    passes = sorted(passes)
    chosen = list(c1)
    i2 = ip = 0
    turn = 0
    while len(chosen) < 16 and (i2 < len(c2) or ip < len(passes)):
        if (turn % 2 == 0 and i2 < len(c2)) or ip >= len(passes):
            chosen.append(c2[i2]); i2 += 1
        else:
            chosen.append(passes[ip]); ip += 1
        turn += 1
    return {"n": len(chosen), "tasks": chosen, "class1_fail_ge30": c1, "class2_fail_lt30": c2,
            "class3_pass_available": c3, "pass_picked": [t for t in chosen if t in c3],
            "below_floor_12": len(chosen) < 12}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("table")
    ap.add_argument("--hard", default=str(HERE.parent / "banks" / "exercism_py_hard.json"))
    a = ap.parse_args()
    hard = set(json.load(open(a.hard))["chosen_tasks"]) - {"ex_alphametics"}
    print(json.dumps(select(json.load(open(a.table)), hard), ensure_ascii=False, indent=1))
