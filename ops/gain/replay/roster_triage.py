"""ROSTER-TRIAGE：等預算下，改「這 5 通呼叫打給誰、還要不要打」，不改選法、不加審查。

離線重放，**不打任何模型端點**。候選全部來自 runs/<run>/calls.jsonl 已落盤的
response 文字；標記沿用 exec_select.visible_grade（只讀 visible_check）與
gain_run.meets_demand（只寫 hidden_ok 計分欄位）。

機制（一次講完）
────────────────
每個 worker 帶一個 Beta 信譽，只由**免費的 visible_check 通過率**更新
（零模型呼叫、零 ground truth ⇒ 可部署）。對每一題：

  1. 依信譽排序點名，**同一題不重複點同一個 worker**（roster 輪替）。
  2. 每拿到一份答案，就在本機跑一次需求自帶的公開測資（免費）。
  3. 只要有兩份「公開測資全過且行為一致」的答案 ⇒ 出貨，**不再打電話**。
  4. 打滿 CAP 通仍無共識 ⇒ 先濾掉公開測資沒過的，再行為多數決（＝ OFF5 的規則）。

對照的 OFF5 是 `gain_run.py:288  assigned = [rng.choice(agents) for _ in range(k)]`
——均勻、**有放回**、固定打滿 5 通、事後才多數決。

為什麼這是「反其道」：其他角度都在改「拿到 5 份答案之後怎麼挑／怎麼審」。
這裡一份答案都還沒生出來就已經做完決策了。

V/GT 分離：停不停、選哪份，全部只讀 visible_ok 與行為簽名；`hidden_ok` 只在
最後一行計分時被讀到。預算：CAP=5 ⇒ 每題最多 5 通 gen 呼叫，與 OFF5／ON 相同；
本機沙箱執行免費（arm_off5 現行的 behavior_signature 本來就跑過同一批 base inputs）。
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from roster_budget import (  # noqa: E402
    ROSTER, boot_ci, load_pool, load_rows, mcnemar_exact, policy_fixed, score,
    vfilter, vote_dist,
)


def fold_of(tid: str) -> int:
    return int(hashlib.sha256(tid.encode()).hexdigest(), 16) % 2


def visible_reputation(tasks, ids):
    """Beta(1,1) 後驗均值，只吃 visible_ok。這是唯一的信譽來源。"""
    ok, n = collections.Counter(), collections.Counter()
    for t in ids:
        for c in tasks[t]:
            n[c.v.persona] += 1
            ok[c.v.persona] += c.v.visible_ok
    return {p: (ok[p] + 1) / (n[p] + 2) for p in ROSTER}


def draw_order(cands, ranking, rng):
    """點名順序：信譽高的先，同一題不重複點人；同 persona 有多份時隨機取。"""
    by = collections.defaultdict(list)
    for c in cands:
        by[c.v.persona].append(c.v.idx)
    for v in by.values():
        rng.shuffle(v)
    order, rnd = [], 0
    while len(order) < len(cands):
        added = False
        for p in ranking:
            lst = by.get(p) or []
            if len(lst) > rnd:
                order.append(lst[rnd]); added = True
        if not added:
            break
        rnd += 1
    return order


def triage(cands, order, cap, rng, early_stop=True):
    """回傳 (出貨候選 idx, 用掉的呼叫數)。只讀 V 側欄位。"""
    drawn = []
    for step, i in enumerate(order[:cap], 1):
        drawn.append(cands[i].v)
        if not early_stop:
            continue
        S = [f for f in drawn if f.visible_ok]
        if S:
            b = collections.Counter(f.sig for f in S)
            mx = max(b.values())
            if mx >= 2:
                return rng.choice([f for f in S if b[f.sig] == mx]).idx, step
    d = vote_dist(vfilter(drawn))
    r, acc = rng.random(), 0.0
    for k in sorted(d):
        acc += d[k]
        if r <= acc:
            return k, len(drawn)
    return max(d, key=d.get), len(drawn)


def main(runs, pool_size, cap, reps, seed, boot, stability):
    for run in runs:
        pool, rows = load_pool(run), load_rows(run)
        tasks = {t: c for t, c in pool.items()
                 if len(c) == pool_size and ("OFF5", t) in rows
                 and sum(1 for x in c if x.arm == "OFF5") == 5}
        ids = sorted(tasks)
        N = len(ids)
        if not N:
            print(f"{run}: no complete pools"); continue
        print(f"\n{'='*80}\n{run}: n={N} tasks, complete {pool_size}-candidate pools, "
              f"CAP={cap}, {reps} replicates/task\n{'='*80}")
        repbank = {f: visible_reputation(tasks, [t for t in ids if fold_of(t) != f])
                   for f in (0, 1)}
        for f in (0, 1):
            print(f"  cross-fit visible reputation (eval fold {f}): " + " > ".join(
                f"{p}:{repbank[f][p]:.3f}"
                for p in sorted(ROSTER, key=lambda x: -repbank[f][x])))

        variants = {
            "ROSTER-TRIAGE": dict(rank="rep", stop=True),
            "  ablate: random order": dict(rank="rand", stop=True),
            "  ablate: anti-reputation": dict(rank="anti", stop=True),
            "  ablate: no early stop": dict(rank="rep", stop=False),
        }
        res = {k: ([], []) for k in variants}
        for t in ids:
            cands = tasks[t]
            rep = repbank[fold_of(t)]
            rk = sorted(ROSTER, key=lambda p: (-rep[p], p))
            for name, cfg in variants.items():
                rng = random.Random(seed ^ hash(name) & 0xffffffff)
                oks, calls = 0.0, 0.0
                for _ in range(reps):
                    if cfg["rank"] == "rand":
                        o = [c.v.idx for c in cands]; rng.shuffle(o)
                    else:
                        r2 = rk if cfg["rank"] == "rep" else list(reversed(rk))
                        o = draw_order(cands, r2, rng)
                    i, used = triage(cands, o, cap, rng, cfg["stop"])
                    oks += cands[i].hidden_ok
                    calls += used
                res[name][0].append(oks / reps)
                res[name][1].append(calls / reps)

        off5 = [1.0 if rows[("OFF5", t)]["meets_demand"] else 0.0 for t in ids]
        # like-for-like：同一把尺（replay 標記）下的 OFF5——逐字重現 arm_off5
        # 的行為多數決＋雙層抽籤，抽籤積分掉。這條才是「兩邊同尺」的對照。
        off5_replay = []
        for t in ids:
            cs = tasks[t]
            facts = [c.v for c in cs]
            sel = tuple(sorted(c.v.idx for c in cs if c.arm == "OFF5"))
            off5_replay.append(score(policy_fixed(sel, facts, False), cs))
        print(f"\n--- 量具校準：OFF5 兩種計分 ---")
        print(f"  OFF5 as shipped (rows.jsonl 的 meets_demand)      {sum(off5)/N*100:6.2f}%")
        print(f"  OFF5 replayed   (同一把尺，arm_off5 規則逐字重現)  "
              f"{sum(off5_replay)/N*100:6.2f}%")
        print(f"\n--- 通過率與預算（等預算：CAP={cap} 通 gen 呼叫上限）---")
        print(f"  {'OFF5 (as shipped)':28s} {sum(off5)/N*100:6.2f}%   5.00 calls/task")
        for name, (oks, calls) in res.items():
            print(f"  {name:28s} {sum(oks)/N*100:6.2f}%   {sum(calls)/N:.2f} calls/task")

        for label, basel in (("vs OFF5 AS SHIPPED (rows.jsonl)", off5),
                             ("vs OFF5 REPLAYED (same instrument)", off5_replay)):
            print(f"\n--- {label}  (bootstrap {boot}; McNemar seed={seed}) ---")
            for name, (oks, _c) in res.items():
                o, lo, hi = boot_ci(list(zip(oks, basel)), B=boot, seed=seed)
                rng = random.Random(seed)
                r = [rng.random() < x for x in oks]
                r2 = [rng.random() < x for x in basel]
                b = sum(1 for i in range(N) if r[i] and not r2[i])
                c = sum(1 for i in range(N) if not r[i] and r2[i])
                print(f"  {name:28s} {o*100:+6.2f}pp CI [{lo*100:+6.2f},{hi*100:+6.2f}]   "
                      f"b={b} c={c} n={N} p={mcnemar_exact(b, c):.4f}")

        if stability:
            oks = res["ROSTER-TRIAGE"][0]
            bs, cs, ps = [], [], []
            for s in range(stability):
                rng = random.Random(20260903 + s)
                r = [rng.random() < x for x in oks]
                b = sum(1 for i in range(N) if r[i] and off5[i] < 0.5)
                c = sum(1 for i in range(N) if not r[i] and off5[i] > 0.5)
                bs.append(b); cs.append(c); ps.append(mcnemar_exact(b, c))
            bs.sort(); cs.sort(); ps.sort(); m = stability // 2
            print(f"\n--- seed 穩定性（{stability} seeds, ROSTER-TRIAGE vs OFF5）---")
            print(f"  b median={bs[m]} [{bs[0]},{bs[-1]}]  c median={cs[m]} [{cs[0]},{cs[-1]}]"
                  f"  p median={ps[m]:.4f}  p<0.05 in {sum(1 for x in ps if x<0.05)}/{stability}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--pool", type=int, default=7)
    ap.add_argument("--cap", type=int, default=5)
    ap.add_argument("--reps", type=int, default=400)
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--stability", type=int, default=500)
    a = ap.parse_args()
    main(a.runs.split(","), a.pool, a.cap, a.reps, a.seed, a.boot, a.stability)
