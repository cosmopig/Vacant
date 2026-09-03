"""離線重放：ROSTER-5 —— 等預算下把 5 次呼叫**分給不同的產生者**，而不是換選法。

這支**不打任何模型端點**。候選全部來自 runs/<run>/calls.jsonl 已落盤的 response，
標記沿用 exec_select.visible_grade（只讀 visible_check）與 gain_run.meets_demand
（只寫 hidden_ok 計分欄位）。

為什麼是「反其道」：其他角度都在改「拿到 5 份答案之後怎麼挑／怎麼審」。
本角度改的是**這 5 通呼叫該打給誰**。arm_off5 的 `assigned = [rng.choice(agents)
for _ in range(k)]` 是**有放回抽樣**——179 題裡有 162 題的 5 通呼叫撞名，
只有 17 題真的用到 5 個不同 persona。ROSTER-5 把它換成無放回（roster 輪替），
呼叫數一模一樣，下游彙總規則一模一樣。

V/GT 分離的結構性保證：所有 policy 函式吃的是 `VFacts`（只有 V 側欄位），
回傳的是**候選索引上的機率分布**；`hidden_ok` 只在 `score()` 裡被讀到，
policy 拿不到它。這不是紀律問題，是型別問題。

呼叫預算：每個 policy 都恰好用 5 次 gen 呼叫／題（與 OFF5、ON 相同）。
本機沙箱執行免費、不計入預算——arm_off5 現行的 behavior_signature 本來就已經
把每個候選跑過 base inputs（gain_run.py:306），visible_check 是同一批 base
inputs 加上公開的期望值，零額外模型呼叫。
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
from typing import NamedTuple

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]

ROSTER = ("careful-1", "careful-2", "hasty-1", "hasty-2", "plain-1", "plain-2")


# ── 候選事實：policy 只看得到這些欄位（V 側） ──────────────────────
class VFacts(NamedTuple):
    idx: int            # 池內位置（穩定排序後）
    persona: str        # agent_id / system prompt 身分
    sig: str            # behaviour signature（base inputs 上的行為）
    visible_ok: bool    # 3 條 base assert 全過？
    visible_pass: int
    visible_total: int


class Cand(NamedTuple):
    v: VFacts
    hidden_ok: bool     # 只給 score() 用
    arm: str


# ── 池載入 ──────────────────────────────────────────────────────────
def load_pool(run: str) -> dict[str, list[Cand]]:
    """(task_id) -> [Cand, ...]，合併 exec_select cache 與 cache_roster。"""
    seen: dict[tuple, dict] = {}
    for d in (HERE / "cache", HERE / "cache_roster"):
        p = d / f"{run}.jsonl"
        if not p.exists():
            continue
        for ln in p.open(encoding="utf-8"):
            r = json.loads(ln)
            if r.get("role") != "gen" or "hidden_ok" not in r or r.get("err"):
                continue
            seen[(r["arm"], r["task_id"], r["idx"])] = r
    pool: dict[str, list[Cand]] = collections.defaultdict(list)
    for (arm, tid, idx), r in sorted(seen.items()):
        pool[tid].append((arm, idx, r))
    out: dict[str, list[Cand]] = {}
    for tid, lst in pool.items():
        cands = []
        for i, (arm, _idx, r) in enumerate(lst):
            cands.append(Cand(
                v=VFacts(i, r["agent_id"], r["sig"], bool(r["visible_ok"]),
                         int(r.get("visible_pass", 0)), int(r.get("visible_total", 0))),
                hidden_ok=bool(r["hidden_ok"]), arm=arm))
        out[tid] = cands
    return out


def load_rows(run: str) -> dict:
    out = {}
    for ln in (REPO / "runs" / run / "rows.jsonl").open(encoding="utf-8"):
        r = json.loads(ln)
        out[(r["arm"], r["task_id"])] = r
    return out


# ── 彙總規則：逐字重現 gain_run.arm_off5（多數決＋雙層抽籤） ───────
def vote_dist(sel: list[VFacts]) -> dict[int, float]:
    """回傳 idx -> 機率。抽籤積分掉：先在並列 bucket 間均分，再在 bucket 內均分。"""
    buckets: dict[str, list[int]] = {}
    for f in sel:
        buckets.setdefault(f.sig, []).append(f.idx)
    mx = max(len(v) for v in buckets.values())
    tied = [v for v in buckets.values() if len(v) == mx]
    dist: dict[int, float] = collections.defaultdict(float)
    for b in tied:
        for i in b:
            dist[i] += 1.0 / (len(tied) * len(b))
    return dict(dist)


def vfilter(sel: list[VFacts]) -> list[VFacts]:
    """免費的可見測資閘：只留全過的；一個都沒有就退回原集合（不棄權）。"""
    keep = [f for f in sel if f.visible_ok]
    return keep or sel


# ── policies：吃 VFacts 池，回傳 (子集合機率, 子集合內 idx 分布) ─────
def _subsets(n: int, k: int):
    return list(itertools.combinations(range(n), k))


def policy_fixed(sel_idx: tuple[int, ...], facts: list[VFacts], use_vfilter: bool):
    sel = [facts[i] for i in sel_idx]
    return vote_dist(vfilter(sel) if use_vfilter else sel)


def policy_over_subsets(subs, facts: list[VFacts], use_vfilter: bool) -> dict[int, float]:
    """在一組等機率子集合上求期望分布。"""
    acc: dict[int, float] = collections.defaultdict(float)
    for s in subs:
        for i, p in policy_fixed(s, facts, use_vfilter).items():
            acc[i] += p / len(subs)
    return dict(acc)


def n_personas(sub, facts) -> int:
    return len({facts[i].persona for i in sub})


def score(dist: dict[int, float], cands: list[Cand]) -> float:
    """把 policy 的分布跟 hidden_ok 內積——hidden 只在這裡出現。"""
    return sum(p * (1.0 if cands[i].hidden_ok else 0.0) for i, p in dist.items())


# ── 統計 ────────────────────────────────────────────────────────────
def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, lo + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def boot_ci(pairs, B=10000, seed=20260903):
    rng = random.Random(seed)
    n = len(pairs)
    d = [x - y for x, y in pairs]
    obs = sum(d) / n
    reps = []
    for _ in range(B):
        s = 0.0
        for _ in range(n):
            s += d[rng.randrange(n)]
        reps.append(s / n)
    reps.sort()
    return obs, reps[int(0.025 * B)], reps[int(0.975 * B)]


# ── 主流程 ──────────────────────────────────────────────────────────
def analyse(run: str, pool_size: int, seed: int, boot: int, verbose: bool):
    pool = load_pool(run)
    rows = load_rows(run)
    tasks = []
    for tid, cands in sorted(pool.items()):
        if len(cands) != pool_size:
            continue
        if ("OFF5", tid) not in rows:
            continue
        off5 = [c for c in cands if c.arm == "OFF5"]
        if len(off5) != 5:
            continue
        tasks.append((tid, cands, off5))
    print(f"\n{'='*78}\n{run}: {len(tasks)} tasks with a complete {pool_size}-candidate pool "
          f"(+5 OFF5 rows)\n{'='*78}")
    if not tasks:
        return None

    rng = random.Random(seed)
    names = ["off5_actual(shipped)", "off5_vote(replay)", "off5_vote+vfilter",
             "pool_rand5", "pool_rand5+vfilter", "ROSTER5+vfilter", "clone5+vfilter"]
    exp = {n: [] for n in names}
    real = {n: [] for n in names}
    diversity = collections.Counter()
    exists = collections.Counter()          # ∃correct 的機率，分 policy
    ex_acc = collections.defaultdict(float)
    calls = collections.Counter()
    per_task = []

    for tid, cands, off5 in tasks:
        facts = [c.v for c in cands]
        n = len(cands)
        off5_idx = tuple(sorted(c.v.idx for c in off5))
        subs = _subsets(n, 5)
        div = {s: n_personas(s, facts) for s in subs}
        mx, mn = max(div.values()), min(div.values())
        roster_subs = [s for s in subs if div[s] == mx]
        clone_subs = [s for s in subs if div[s] == mn]
        diversity[(n_personas(off5_idx, facts), mx, mn)] += 1

        d = {}
        d["off5_vote(replay)"] = policy_fixed(off5_idx, facts, False)
        d["off5_vote+vfilter"] = policy_fixed(off5_idx, facts, True)
        d["pool_rand5"] = policy_over_subsets(subs, facts, False)
        d["pool_rand5+vfilter"] = policy_over_subsets(subs, facts, True)
        d["ROSTER5+vfilter"] = policy_over_subsets(roster_subs, facts, True)
        d["clone5+vfilter"] = policy_over_subsets(clone_subs, facts, True)
        for k, v in d.items():
            exp[k].append(score(v, cands))
        exp["off5_actual(shipped)"].append(
            1.0 if rows[("OFF5", tid)]["meets_demand"] else 0.0)
        for k in names:
            calls[k] += 5

        # ∃correct 機率（機制的因果通道，與彙總規則無關）
        for lbl, ss in (("pool_rand5", subs), ("ROSTER5", roster_subs),
                        ("clone5", clone_subs), ("off5_actual", [off5_idx])):
            hit = sum(1 for s in ss if any(cands[i].hidden_ok for i in s))
            ex_acc[lbl] += hit / len(ss)
            exists[lbl] += 1

        # 實現抽樣（給 McNemar）
        def draw(dist):
            r, acc = rng.random(), 0.0
            for i, p in sorted(dist.items()):
                acc += p
                if r <= acc:
                    return cands[i].hidden_ok
            return cands[max(dist, key=dist.get)].hidden_ok
        rr = {}
        rr["off5_actual(shipped)"] = bool(rows[("OFF5", tid)]["meets_demand"])
        rr["off5_vote(replay)"] = draw(d["off5_vote(replay)"])
        rr["off5_vote+vfilter"] = draw(d["off5_vote+vfilter"])
        rr["pool_rand5"] = draw(policy_fixed(rng.choice(subs), facts, False))
        rr["pool_rand5+vfilter"] = draw(policy_fixed(rng.choice(subs), facts, True))
        rr["ROSTER5+vfilter"] = draw(policy_fixed(rng.choice(roster_subs), facts, True))
        rr["clone5+vfilter"] = draw(policy_fixed(rng.choice(clone_subs), facts, True))
        for k, v in rr.items():
            real[k].append(bool(v))
        per_task.append((tid, {k: exp[k][-1] for k in names}, rr))

    N = len(tasks)
    print(f"\n--- 期望通過率（抽籤積分掉；每個 policy 都是 5 次 gen 呼叫／題）---")
    for k in names:
        print(f"  {k:24s} {sum(exp[k])/N*100:6.2f}%   calls/task = {calls[k]/N:.2f}")
    print(f"\n--- ∃ 正確候選的機率（機制的因果通道，與彙總規則無關）---")
    for lbl in ("off5_actual", "pool_rand5", "ROSTER5", "clone5"):
        print(f"  {lbl:24s} {ex_acc[lbl]/N*100:6.2f}%")
    print(f"\n--- 樣本內 persona 多樣性（OFF5 實抽 / 池內 5-子集最大 / 最小）---")
    for k in sorted(diversity):
        print(f"  off5={k[0]}  max={k[1]}  min={k[2]}   n={diversity[k]}")

    print(f"\n--- 期望值配對差（bootstrap {boot} 次，任務層重抽）---")
    contrasts = [
        ("ROSTER5+vfilter", "off5_actual(shipped)"),
        ("ROSTER5+vfilter", "pool_rand5+vfilter"),
        ("ROSTER5+vfilter", "clone5+vfilter"),
        ("ROSTER5+vfilter", "off5_vote+vfilter"),
        ("off5_vote+vfilter", "off5_actual(shipped)"),
    ]
    for a, b in contrasts:
        o, lo, hi = boot_ci(list(zip(exp[a], exp[b])), B=boot, seed=seed)
        print(f"  {a:22s} - {b:22s} = {o*100:+6.2f}pp  95% CI [{lo*100:+6.2f},{hi*100:+6.2f}]")

    print(f"\n--- 配對 McNemar（實現抽樣，seed={seed}；vs OFF5 實際出貨）---")
    mc = {}
    for k in names[1:]:
        b = sum(1 for i in range(N) if real[k][i] and not real["off5_actual(shipped)"][i])
        c = sum(1 for i in range(N) if not real[k][i] and real["off5_actual(shipped)"][i])
        p = mcnemar_exact(b, c)
        mc[k] = (b, c, N, p)
        print(f"  {k:24s} {sum(real[k])}/{N} = {sum(real[k])/N*100:5.2f}%  "
              f"b={b} c={c} n={N} p={p:.4f}")
    return {"run": run, "n": N, "exp": {k: sum(v)/N for k, v in exp.items()},
            "exists": {k: ex_acc[k]/N for k in ex_acc}, "mcnemar": mc,
            "exp_series": exp, "real": real}


def seed_stability(run, pool_size, boot, trials=200):
    """同一個 policy 換 seed 重抽，看 McNemar 的 b/c/p 分布——不挑 seed。"""
    outs = []
    for s in range(trials):
        r = analyse_quiet(run, pool_size, 20260903 + s)
        if r:
            outs.append(r)
    return outs


def analyse_quiet(run, pool_size, seed):
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return analyse(run, pool_size, seed, boot=2, verbose=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--pool", type=int, default=7)
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--stability", type=int, default=0)
    a = ap.parse_args()
    res = []
    for run in a.runs.split(","):
        r = analyse(run, a.pool, a.seed, a.boot, True)
        if r:
            res.append(r)
    if a.stability:
        print(f"\n--- seed 穩定性（{a.stability} 個 seed，ROSTER5 vs OFF5 實際）---")
        for run in a.runs.split(","):
            bs, cs, ps, rates = [], [], [], []
            for s in range(a.stability):
                q = analyse_quiet(run, a.pool, 20260903 + s)
                if not q:
                    continue
                b, c, n, p = q["mcnemar"]["ROSTER5+vfilter"]
                bs.append(b); cs.append(c); ps.append(p)
                rates.append(sum(q["real"]["ROSTER5+vfilter"]) / n)
            if not bs:
                continue
            bs.sort(); cs.sort(); ps.sort(); rates.sort()
            m = len(bs) // 2
            print(f"  {run}: b median={bs[m]} [{bs[0]},{bs[-1]}]  "
                  f"c median={cs[m]} [{cs[0]},{cs[-1]}]  "
                  f"p median={ps[m]:.4f}  p<0.05 in {sum(1 for x in ps if x<0.05)}/{len(ps)}  "
                  f"rate median={rates[m]*100:.2f}%")
