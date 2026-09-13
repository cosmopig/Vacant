"""離線重放：REP5 —— 等預算下，把 5 通呼叫**一人一通發給信譽最高的 5 個 worker**。

這支**不打任何模型端點**。候選全部來自 runs/<run>/calls.jsonl 已落盤的 response；
標記沿用 exec_select.visible_grade（只讀 visible_check）與 gain_run.meets_demand
（只寫 hidden_ok）。

反其道而行在哪：其他角度都在改「拿到 5 份答案之後怎麼挑／怎麼審」。REP5 改的是
**這 5 通呼叫該打給誰**，一份答案都還沒生出來就決定了。

  gain_run.py:288   assigned = [rng.choice(agents) for _ in range(k)]
                    ——均勻、有放回。r441 的 179 題裡有 162 題撞名，
                      只有 17 題真的用到 5 個不同 persona。
  gain_run.py:496   arm_on 其實已經有信譽路由（_route_agent, UCB），但
                    (a) 只路由第 1 通，(b) 信譽只由 20% hidden audit 更新
                    ——也就是需要 GT 回饋才學得動。

REP5 的信譽只用**免費的 visible_check 通過率**（零模型呼叫、零 ground truth），
所以可部署；hidden_ok 只出現在 score()。policy 函式吃的是 VFacts（只有 V 側欄位），
回傳候選索引上的機率分布——V/GT 分離是型別層級的，不是紀律層級的。

預算：恰好 5 次 gen 呼叫／題，與 OFF5、ON 相同。沙箱執行本機免費
（arm_off5 現行的 behavior_signature 已經把每個候選跑過同一批 base inputs）。
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from roster_budget import (  # noqa: E402
    ROSTER, boot_ci, load_pool, load_rows, mcnemar_exact, policy_fixed, score, vfilter,
)

K = 5


# ── 信譽：Beta(1,1) 後驗均值，只吃 visible_ok（免費、無 GT） ────────
def rep_from(tasks, ids, key="visible"):
    ok, n = collections.Counter(), collections.Counter()
    for t in ids:
        for c in tasks[t]:
            n[c.v.persona] += 1
            ok[c.v.persona] += (c.v.visible_ok if key == "visible" else c.hidden_ok)
    return {p: (ok[p] + 1) / (n[p] + 2) for p in ROSTER}


def ranked(rep, reverse=False):
    return sorted(ROSTER, key=lambda p: (rep[p], p), reverse=not reverse)


# ── 分配：一人一通，照排序拿；不夠 5 個 persona 就往回加第 2 份 ────
def slots_for(cands, ranking, k=K):
    """回傳 persona -> 該拿幾個槽。只看 persona 與可用性，不看任何結果欄位。"""
    avail = collections.Counter(c.v.persona for c in cands)
    slots = collections.Counter()
    for rnd in range(k):
        for p in ranking:
            if sum(slots.values()) >= k:
                break
            if avail[p] > slots[p]:
                slots[p] += 1
        if sum(slots.values()) >= k:
            break
    return slots


def enumerate_allocs(cands, ranking, k=K, cap=400):
    """把「同一 persona 內抽哪一份」窮舉掉，期望值因此是精確值、與 seed 無關。"""
    bypersona = collections.defaultdict(list)
    for c in cands:
        bypersona[c.v.persona].append(c.v.idx)
    slots = slots_for(cands, ranking, k)
    choices = [list(itertools.combinations(sorted(bypersona[p]), s))
               for p, s in slots.items() if s]
    out = []
    for combo in itertools.product(*choices):
        flat = tuple(sorted(i for grp in combo for i in grp))
        if len(flat) == k:
            out.append(flat)
        if len(out) >= cap:
            break
    if not out:                                    # 池不足 5（極少）：全拿
        out = [tuple(sorted(c.v.idx for c in cands))[:k]]
    return out


def exp_over(allocs, facts, use_vfilter=True):
    acc = collections.defaultdict(float)
    for s in allocs:
        for i, p in policy_fixed(s, facts, use_vfilter).items():
            acc[i] += p / len(allocs)
    return dict(acc)


def fold_of(tid):
    return int(hashlib.sha256(tid.encode()).hexdigest(), 16) % 2


def main(runs, pool_size, seed, boot, stability):
    summary = {}
    for run in runs:
        pool, rows = load_pool(run), load_rows(run)
        tasks = {t: c for t, c in pool.items()
                 if len(c) == pool_size and ("OFF5", t) in rows
                 and sum(1 for x in c if x.arm == "OFF5") == K}
        ids = sorted(tasks)
        N = len(ids)
        if not N:
            print(f"{run}: no complete pools"); continue
        folds = {0: [t for t in ids if fold_of(t) == 0],
                 1: [t for t in ids if fold_of(t) == 1]}
        print(f"\n{'='*80}\n{run}: n={N} tasks with a complete {pool_size}-candidate pool"
              f"  (cross-fit folds {len(folds[0])}/{len(folds[1])})\n{'='*80}")

        names = ["OFF5_actual", "OFF5+vfilter", "REP5", "REP5_online",
                 "DIVERSE5", "ANTI-REP5", "ALLOC-ORACLE", "ALLOC-WORST"]
        exp = {k: [] for k in names}
        order = {t: i for i, t in enumerate(ids)}
        repbank = {}
        for f in (0, 1):
            repbank[f] = rep_from(tasks, folds[1 - f], "visible")
        print("  cross-fit visible reputation (Beta posterior mean, free signal):")
        for f in (0, 1):
            print(f"    eval fold {f}: " + " > ".join(
                f"{p}:{repbank[f][p]:.3f}" for p in ranked(repbank[f])))

        for t in ids:
            cands = tasks[t]
            facts = [c.v for c in cands]
            n = len(cands)
            off5 = tuple(sorted(c.v.idx for c in cands if c.arm == "OFF5"))
            rep = repbank[fold_of(t)]
            rk = ranked(rep)

            # 線上版：只用「這題之前已經跑過的題目」累積的信譽（真正可部署的形式）
            prev = [x for x in ids if order[x] < order[t]]
            rep_on = rep_from(tasks, prev, "visible") if prev else {p: 0.5 for p in ROSTER}

            exp["OFF5_actual"].append(1.0 if rows[("OFF5", t)]["meets_demand"] else 0.0)
            exp["OFF5+vfilter"].append(score(policy_fixed(off5, facts, True), cands))
            exp["REP5"].append(score(exp_over(enumerate_allocs(cands, rk), facts), cands))
            exp["REP5_online"].append(
                score(exp_over(enumerate_allocs(cands, ranked(rep_on)), facts), cands))
            exp["ANTI-REP5"].append(
                score(exp_over(enumerate_allocs(cands, list(reversed(rk))), facts), cands))
            subs = list(itertools.combinations(range(n), K))
            div = {s: len({facts[i].persona for i in s}) for s in subs}
            mx = max(div.values())
            exp["DIVERSE5"].append(
                score(exp_over([s for s in subs if div[s] == mx], facts), cands))
            sc = [(score(policy_fixed(s, facts, True), cands), s) for s in subs]
            exp["ALLOC-ORACLE"].append(max(sc)[0])
            exp["ALLOC-WORST"].append(min(sc)[0])

        print(f"\n--- 期望通過率（所有抽籤積分掉 ⇒ 與 seed 無關；全部 5 次 gen 呼叫／題）---")
        for k in names:
            print(f"  {k:14s} {sum(exp[k])/N*100:6.2f}%   calls/task = 5.00")

        print(f"\n--- 期望值配對差（bootstrap {boot}，任務層重抽）---")
        for a, b in [("REP5", "OFF5_actual"), ("REP5", "OFF5+vfilter"),
                     ("REP5", "DIVERSE5"), ("REP5", "ANTI-REP5"),
                     ("REP5_online", "OFF5_actual"),
                     ("OFF5+vfilter", "OFF5_actual"),
                     ("ALLOC-ORACLE", "OFF5_actual")]:
            o, lo, hi = boot_ci(list(zip(exp[a], exp[b])), B=boot, seed=seed)
            star = "*" if lo > 0 or hi < 0 else " "
            print(f" {star}{a:13s} - {b:13s} = {o*100:+6.2f}pp  "
                  f"95% CI [{lo*100:+6.2f},{hi*100:+6.2f}]")

        # 實現抽樣 → McNemar（每個 policy 用自己的 RNG，彼此不干擾）
        print(f"\n--- 配對 McNemar vs OFF5 實際出貨（seed={seed}）---")
        mc = {}
        for k in names[1:]:
            rng = random.Random(seed)
            realk, base = [], []
            for t in ids:
                cands = tasks[t]
                base.append(bool(rows[("OFF5", t)]["meets_demand"]))
                p1 = exp[k][ids.index(t)] if False else None
                realk.append(rng.random() < exp[k][order[t]])
            b = sum(1 for i in range(N) if realk[i] and not base[i])
            c = sum(1 for i in range(N) if not realk[i] and base[i])
            mc[k] = (b, c, N, mcnemar_exact(b, c))
            print(f"  {k:14s} {sum(realk)}/{N} = {sum(realk)/N*100:5.2f}%  "
                  f"b={b} c={c} n={N} p={mc[k][3]:.4f}")

        if stability:
            print(f"\n--- seed 穩定性（{stability} 個 seed；REP5 vs OFF5 實際）---")
            bs, cs, ps = [], [], []
            for s in range(stability):
                rng = random.Random(20260903 + s)
                r = [rng.random() < exp["REP5"][order[t]] for t in ids]
                base = [bool(rows[("OFF5", t)]["meets_demand"]) for t in ids]
                b = sum(1 for i in range(N) if r[i] and not base[i])
                c = sum(1 for i in range(N) if not r[i] and base[i])
                bs.append(b); cs.append(c); ps.append(mcnemar_exact(b, c))
            bs.sort(); cs.sort(); ps.sort()
            m = len(bs) // 2
            print(f"  b median={bs[m]} [{bs[0]},{bs[-1]}]   c median={cs[m]} [{cs[0]},{cs[-1]}]"
                  f"   p median={ps[m]:.4f}   p<0.05 in {sum(1 for x in ps if x<0.05)}/{len(ps)}")
        summary[run] = {"n": N, "exp": {k: sum(v)/N for k, v in exp.items()},
                        "mcnemar": mc, "series": exp}
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--pool", type=int, default=7)
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--stability", type=int, default=0)
    a = ap.parse_args()
    main(a.runs.split(","), a.pool, a.seed, a.boot, a.stability)
