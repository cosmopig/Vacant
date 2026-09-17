#!/usr/bin/env python3
"""R532 塊→後端分配（預註冊 §二-5）。

這支在架構裡承重什麼：把 43 塊依佇列順序**交替**分給兩台後端，產出兩個純文字
plan 檔給 `run_r532_queue.sh` 逐行讀。交替（而不是按題庫切）是為了讓任何一台的
故障都不會整包吃掉某一個題庫——R530 AMEND2-G 就是被「s1 的塊全在同一台」咬到。

冒煙塊 `g_r532_hep_a1` 一定排在 1003 的第一個；`--smoke-only` 時兩個 plan 只有它。
"""
import argparse, json, pathlib, sys

SMOKE = "g_r532_hep_a1"
HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(REPO / "ops/gain/queues/r532.json"))
    ap.add_argument("--smoke-only", action="store_true")
    ap.add_argument("--skip-smoke", action="store_true",
                    help="冒煙已過、要放其餘 42 塊時用")
    a = ap.parse_args()

    q = json.load(open(a.queue))
    blocks = q["blocks"] if isinstance(q, dict) else q
    names = [b["name"] for b in blocks]
    if len(set(names)) != len(names):
        sys.exit("佇列有重複塊名")
    if SMOKE not in names:
        sys.exit(f"佇列裡沒有冒煙塊 {SMOKE}")

    if a.smoke_only:
        plans = {"1003": [SMOKE], "1004": []}
    else:
        rest = [n for n in names if n != SMOKE] if a.skip_smoke else names
        plans = {"1003": rest[0::2], "1004": rest[1::2]}

    for host, lst in plans.items():
        p = HERE / f"plan_{host}.txt"
        p.write_text("".join(n + "\n" for n in lst))
        print(f"{p.name}: {len(lst)} 塊  {lst[:2]}{' …' if len(lst) > 2 else ''}")
    total = sum(len(v) for v in plans.values())
    print(f"合計 {total} 塊 / 佇列 {len(names)} 塊")

if __name__ == "__main__":
    main()
