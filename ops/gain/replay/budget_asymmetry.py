"""離線重放：為什麼「換人／多抽」買不到東西——相關性與預算重分配的天花板。

這支**不打任何模型端點**。候選來自已落盤的 calls.jsonl，標記沿用
exec_select.visible_grade / gain_run.meets_demand。

三件事：
  A. 錯誤相關性：同 persona vs 不同 persona 的「一起錯」條件機率。
     這是 REP5／DIVERSE5 買不到東西的機制解釋。
  B. ∃正確候選 vs 抽樣數 k 的精確曲線（k=1..7，超幾何，無 Monte Carlo）。
     這是**任何**選擇／彙總機制的天花板來源。
  C. 依難度非對稱分配預算：先抽一份、免費跑 visible_check、只在沒共識時才續抽。
     報平均呼叫數與通過率——這條是「等預算」以外唯一能贏的方向（更省）。
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import math
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from roster_budget import (  # noqa: E402
    boot_ci, load_pool, load_rows, mcnemar_exact, vfilter, vote_dist,
)


def exists_curve(m, h, k):
    """精確：m 個候選裡 h 個正確，無放回抽 k 個，至少抽到 1 個正確的機率。"""
    if h == 0:
        return 0.0
    if k > m:
        k = m
    return 1.0 - math.comb(m - h, k) / math.comb(m, k) if m - h >= k else 1.0


def adaptive(cands, perms, rng, cap):
    """依難度分配：抽一份→免費 visible_check→有 2 份可見通過且行為一致就停。

    只用 V 側訊號決定停不停。回傳 (期望通過率, 期望呼叫數)。
    """
    n = len(cands)
    tot_ok = tot_calls = 0.0
    idxs = list(range(n))
    for _ in range(perms):
        rng.shuffle(idxs)
        drawn = []
        shipped = None
        for step, i in enumerate(idxs[:cap], 1):
            drawn.append(cands[i].v)
            S = [f for f in drawn if f.visible_ok]
            if S:
                b = collections.Counter(f.sig for f in S)
                if max(b.values()) >= 2:
                    top = [f for f in S if b[f.sig] == max(b.values())]
                    shipped = (step, rng.choice(top).idx)
                    break
        if shipped is None:
            step = min(cap, n)
            d = vote_dist(vfilter(drawn))
            keys = list(d)
            r, acc = rng.random(), 0.0
            pick = keys[-1]
            for kk in keys:
                acc += d[kk]
                if r <= acc:
                    pick = kk
                    break
            shipped = (step, pick)
        tot_calls += shipped[0]
        tot_ok += 1.0 if cands[shipped[1]].hidden_ok else 0.0
    return tot_ok / perms, tot_calls / perms


def main(runs, pool_size, perms, seed, boot):
    for run in runs:
        pool, rows = load_pool(run), load_rows(run)
        tasks = {t: c for t, c in pool.items()
                 if len(c) == pool_size and ("OFF5", t) in rows
                 and sum(1 for x in c if x.arm == "OFF5") == 5}
        ids = sorted(tasks)
        N = len(ids)
        if not N:
            print(f"{run}: none"); continue
        print(f"\n{'='*80}\n{run}: n={N} tasks, {pool_size}-candidate pools\n{'='*80}")

        # ── A. 錯誤相關性 ────────────────────────────────────────────
        same = [0, 0]   # [both wrong, i wrong]
        diff = [0, 0]
        for t in ids:
            cs = tasks[t]
            for a, b in itertools.permutations(cs, 2):
                if a.hidden_ok:
                    continue
                bucket = same if a.v.persona == b.v.persona else diff
                bucket[1] += 1
                bucket[0] += (not b.hidden_ok)
        print("\n--- A. 錯誤相關性：P(第二份也錯 | 第一份錯)，同題配對 ---")
        print(f"  同一個 persona     {same[0]}/{same[1]} = {same[0]/max(same[1],1)*100:.2f}%")
        print(f"  不同 persona       {diff[0]}/{diff[1]} = {diff[0]/max(diff[1],1)*100:.2f}%")
        base = sum(1 for t in ids for c in tasks[t] if not c.hidden_ok)
        tot = sum(len(tasks[t]) for t in ids)
        print(f"  無條件錯誤率       {base}/{tot} = {base/tot*100:.2f}%"
              f"   ⇒ 換人把「一起錯」從 {same[0]/max(same[1],1)*100:.1f}% "
              f"降到 {diff[0]/max(diff[1],1)*100:.1f}%（無關則應降到 {base/tot*100:.1f}%）")

        # ── B. ∃正確 vs k（精確） ────────────────────────────────────
        print("\n--- B. ∃至少一份正確候選 vs 抽樣數 k（精確超幾何，池=7）---")
        prev = None
        for k in range(1, pool_size + 1):
            v = sum(exists_curve(pool_size, sum(1 for c in tasks[t] if c.hidden_ok), k)
                    for t in ids) / N
            delta = "" if prev is None else f"  (+{(v-prev)*100:.2f}pp)"
            print(f"  k={k}: {v*100:6.2f}%{delta}")
            prev = v
        nohit = sum(1 for t in ids if not any(c.hidden_ok for c in tasks[t]))
        print(f"  7 份全錯的題目: {nohit}/{N} = {nohit/N*100:.1f}%  "
              f"⇒ 任何選擇／分配機制的絕對上限 = {(1-nohit/N)*100:.2f}%")
        # 5 份 OFF5 全錯、但池裡另外 2 份有正確的題目 = 加碼預算的實際收穫
        rescue = sum(1 for t in ids
                     if not any(c.hidden_ok for c in tasks[t] if c.arm == "OFF5")
                     and any(c.hidden_ok for c in tasks[t] if c.arm != "OFF5"))
        off5_none = sum(1 for t in ids
                        if not any(c.hidden_ok for c in tasks[t] if c.arm == "OFF5"))
        print(f"  OFF5 那 5 份全錯的題目: {off5_none}/{N};  其中另外 2 份（OFF/ON）"
              f"救回來的: {rescue}  ⇒ 第 6、7 通呼叫的實際收穫 = {rescue/N*100:.2f}pp")

        # ── C. 依難度非對稱分配 ─────────────────────────────────────
        print(f"\n--- C. 依難度非對稱分配預算（{perms} 個隨機抽樣順序／題）---")
        rows_out = []
        for cap in (2, 3, 5, 7):
            rng = random.Random(seed)
            oks, calls = [], []
            for t in ids:
                o, c = adaptive(tasks[t], perms, rng, cap)
                oks.append(o); calls.append(c)
            rows_out.append((cap, sum(oks)/N, sum(calls)/N, oks))
            print(f"  cap={cap}: 通過率 {sum(oks)/N*100:6.2f}%   "
                  f"平均呼叫 {sum(calls)/N:.2f}/題")
        off5 = [1.0 if rows[("OFF5", t)]["meets_demand"] else 0.0 for t in ids]
        print(f"  OFF5 實際:  通過率 {sum(off5)/N*100:6.2f}%   平均呼叫 5.00/題")
        for cap, rate, c, oks in rows_out:
            o, lo, hi = boot_ci(list(zip(oks, off5)), B=boot, seed=seed)
            rng = random.Random(seed)
            r = [rng.random() < x for x in oks]
            b = sum(1 for i in range(N) if r[i] and not (off5[i] > 0.5))
            cc = sum(1 for i in range(N) if not r[i] and (off5[i] > 0.5))
            print(f"    cap={cap} vs OFF5: {o*100:+6.2f}pp CI [{lo*100:+6.2f},{hi*100:+6.2f}]"
                  f"   McNemar b={b} c={cc} n={N} p={mcnemar_exact(b, cc):.4f}"
                  f"   ({c:.2f} vs 5.00 calls)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--pool", type=int, default=7)
    ap.add_argument("--perms", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--boot", type=int, default=10000)
    a = ap.parse_args()
    main(a.runs.split(","), a.pool, a.perms, a.seed, a.boot)
