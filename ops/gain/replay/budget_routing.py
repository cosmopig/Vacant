"""離線重放：REP5 —— 等預算下改「這 5 通呼叫打給誰」，不改選法、不加審查。

這支**不打任何模型端點**。候選全部來自已落盤的 calls.jsonl，標記沿用
exec_select.visible_grade / gain_run.meets_demand（見 roster_budget.py 的說明）。

背景：`gain_run.arm_off5` 的 worker 指派是
    assigned = [rng.choice(agents) for _ in range(k)]      # gain_run.py:288
——**均勻、有放回**。`arm_on` 反而已經有信譽路由（`_route_agent`，UCB），
但只路由第 1 通呼叫，而且信譽只由 20% 的 hidden audit 更新
（`apply_audit_reputation`）。也就是說：G 實驗從來沒有測過「把整個 5 通預算
按信譽分配」。這支就測那件事。

三種信譽來源，對應三種可部署性：
  REP5/V    —— 只用**免費的 visible_check** 線上學（零 ground truth，可部署）
  REP5/GT   —— 用 hidden 結果學，但**跨折**（held-out）；代表「有交付回饋
                管道時，信譽層的上限」。不可在無回饋的場景部署。
  CUT/GT    —— 只做一件事：把最差的 worker 從名單移掉。
另外算 ALLOC-ORACLE：在同一個 7 候選池裡，所有 C(7,5)=21 個子集合的最大期望
通過率 —— 這是**任何**「怎麼分配 5 通呼叫」的機制的天花板。

預算：每個 policy 都恰好 5 次 gen 呼叫／題。沙箱執行本機免費（arm_off5 現行的
behavior_signature 本來就跑過同一批 base inputs）。
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
    ROSTER, boot_ci, load_pool, load_rows, mcnemar_exact, policy_fixed, score,
    vote_dist, vfilter,
)


def fold_of(task_id: str) -> int:
    return int(hashlib.sha256(task_id.encode()).hexdigest(), 16) % 2


# ── 信譽：只從「已看過的任務」學，評估任務永遠是 held-out ──────────
def persona_rates(tasks, ids, key):
    """key='visible' 用免費閘門；key='hidden' 用交付回饋（跨折才合法）。"""
    ok = collections.Counter()
    n = collections.Counter()
    for t in ids:
        for c in tasks[t]:
            n[c.v.persona] += 1
            ok[c.v.persona] += (c.v.visible_ok if key == "visible" else c.hidden_ok)
    # Beta(1,1) 後驗均值，沒看過的 persona 回中性 0.5
    return {p: (ok[p] + 1) / (n[p] + 2) for p in ROSTER}, dict(n)


def allocate(cands, ranking, k, rng):
    """按 ranking 依序要 persona；同一 persona 有多份就隨機取。不夠 5 個就往下輪。

    回傳 (選中的 idx tuple, 依 ranking 拿到的槽數)。選擇只看 persona 與可用性，
    完全不看 visible/hidden 結果。
    """
    bypersona = collections.defaultdict(list)
    for c in cands:
        bypersona[c.v.persona].append(c.v.idx)
    for v in bypersona.values():
        rng.shuffle(v)
    picked, intended = [], 0
    for rnd in range(6):                       # 第 0 輪：每個 persona 各一份
        for p in ranking:
            if len(picked) >= k:
                break
            lst = bypersona.get(p) or []
            if len(lst) > rnd:
                picked.append(lst[rnd])
                if rnd == 0:
                    intended += 1
        if len(picked) >= k:
            break
    if len(picked) < k:                        # 池不夠深（極少）：補剩下的
        rest = [c.v.idx for c in cands if c.v.idx not in picked]
        rng.shuffle(rest)
        picked += rest[:k - len(picked)]
    return tuple(sorted(picked[:k])), intended


def repvote_dist(sel, rep):
    """信譽加權的行為多數決：bucket 權重＝成員 persona 信譽和（V 側學來的）。

    arm_off5 是一人一票；Vacant 的信譽層本來就該讓「誰說的」有分量。
    這裡只用 REP5/V 的 visible 信譽，不碰 hidden。
    """
    buckets = {}
    for f in sel:
        buckets.setdefault(f.sig, []).append(f)
    w = {k: sum(rep.get(f.persona, 0.5) for f in v) for k, v in buckets.items()}
    mx = max(w.values())
    tied = [k for k in buckets if abs(w[k] - mx) < 1e-12]
    dist = collections.defaultdict(float)
    for k in tied:
        for f in buckets[k]:
            dist[f.idx] += 1.0 / (len(tied) * len(buckets[k]))
    return dict(dist)


def run(runs, pool_size, seed, boot):
    allres = {}
    for run in runs:
        pool = load_pool(run)
        rows = load_rows(run)
        tasks = {t: c for t, c in pool.items()
                 if len(c) == pool_size and ("OFF5", t) in rows
                 and sum(1 for x in c if x.arm == "OFF5") == 5}
        if not tasks:
            print(f"{run}: no complete pools"); continue
        ids = sorted(tasks)
        f0 = [t for t in ids if fold_of(t) == 0]
        f1 = [t for t in ids if fold_of(t) == 1]
        N = len(ids)
        print(f"\n{'='*78}\n{run}: n={N} tasks, {pool_size}-candidate pools "
              f"(cross-fit folds {len(f0)}/{len(f1)})\n{'='*78}")

        rng = random.Random(seed)
        names = ["off5_actual", "off5_vfilter", "REP5/V", "REP5/V+repvote",
                 "REP5/GT-xfit", "CUT/GT-xfit", "ALLOC-ORACLE", "ALLOC-WORST"]
        exp = {k: [] for k in names}
        real = {k: [] for k in names}
        intended_slots = collections.Counter()
        cut_choice = collections.Counter()
        rank_report = {}

        for train, test in ((f0, f1), (f1, f0)):
            vis_rate, vn = persona_rates(tasks, train, "visible")
            hid_rate, hn = persona_rates(tasks, train, "hidden")
            rank_v = sorted(ROSTER, key=lambda p: -vis_rate[p])
            rank_g = sorted(ROSTER, key=lambda p: -hid_rate[p])
            worst = rank_g[-1]
            cut_choice[worst] += 1
            rank_report[len(rank_report)] = (
                [f"{p}:{vis_rate[p]:.3f}" for p in rank_v],
                [f"{p}:{hid_rate[p]:.3f}" for p in rank_g])
            for t in test:
                cands = tasks[t]
                facts = [c.v for c in cands]
                off5 = tuple(sorted(c.v.idx for c in cands if c.arm == "OFF5"))
                subs = list(itertools.combinations(range(len(cands)), 5))

                d = {}
                d["off5_vfilter"] = policy_fixed(off5, facts, True)
                s_v, iv = allocate(cands, rank_v, 5, rng)
                d["REP5/V"] = policy_fixed(s_v, facts, True)
                intended_slots["REP5/V"] += iv
                d["REP5/V+repvote"] = repvote_dist(
                    vfilter([facts[i] for i in s_v]), vis_rate)
                s_g, ig = allocate(cands, rank_g, 5, rng)
                d["REP5/GT-xfit"] = policy_fixed(s_g, facts, True)
                intended_slots["REP5/GT-xfit"] += ig
                keep = [c for c in cands if c.v.persona != worst]
                s_c, _ = allocate(keep if len(keep) >= 5 else cands,
                                  [p for p in rank_v if p != worst] + [worst], 5, rng)
                d["CUT/GT-xfit"] = policy_fixed(s_c, facts, True)

                scored = [(score(policy_fixed(s, facts, True), cands), s) for s in subs]
                d["ALLOC-ORACLE"] = policy_fixed(max(scored)[1], facts, True)
                d["ALLOC-WORST"] = policy_fixed(min(scored)[1], facts, True)

                for k, v in d.items():
                    exp[k].append(score(v, cands))
                exp["off5_actual"].append(1.0 if rows[("OFF5", t)]["meets_demand"] else 0.0)

                def draw(dist):
                    r, acc = rng.random(), 0.0
                    for i, p in sorted(dist.items()):
                        acc += p
                        if r <= acc:
                            return cands[i].hidden_ok
                    return cands[max(dist, key=dist.get)].hidden_ok
                real["off5_actual"].append(bool(rows[("OFF5", t)]["meets_demand"]))
                for k, v in d.items():
                    real[k].append(bool(draw(v)))

        print("\n--- 跨折學到的排序（fold A / fold B）---")
        for i, (rv, rg) in rank_report.items():
            print(f"  fold{i} visible: {' > '.join(rv)}")
            print(f"  fold{i} hidden : {' > '.join(rg)}")
        print(f"  CUT 每折選到要移除的 worker: {dict(cut_choice)}")
        print(f"  分配保真度（第一輪就拿到指定 persona 的槽數／{5*N}）: "
              + ", ".join(f"{k}={v}/{5*N}={v/(5*N)*100:.1f}%"
                          for k, v in intended_slots.items()))

        print("\n--- 期望通過率（抽籤積分掉；全部 5 次 gen 呼叫／題）---")
        for k in names:
            print(f"  {k:16s} {sum(exp[k])/N*100:6.2f}%   calls/task = 5.00")

        print(f"\n--- 期望值配對差（bootstrap {boot}，任務層重抽）---")
        for a, b in [("REP5/V", "off5_actual"), ("REP5/V+repvote", "off5_actual"),
                     ("REP5/V+repvote", "off5_vfilter"), ("REP5/GT-xfit", "off5_actual"),
                     ("CUT/GT-xfit", "off5_actual"), ("REP5/GT-xfit", "off5_vfilter"),
                     ("ALLOC-ORACLE", "off5_actual"), ("ALLOC-ORACLE", "ALLOC-WORST")]:
            o, lo, hi = boot_ci(list(zip(exp[a], exp[b])), B=boot, seed=seed)
            print(f"  {a:14s} - {b:14s} = {o*100:+6.2f}pp  95% CI [{lo*100:+6.2f},{hi*100:+6.2f}]")

        print(f"\n--- 配對 McNemar（實現抽樣 seed={seed}；vs OFF5 實際出貨）---")
        mc = {}
        for k in names[1:]:
            b = sum(1 for i in range(N) if real[k][i] and not real["off5_actual"][i])
            c = sum(1 for i in range(N) if not real[k][i] and real["off5_actual"][i])
            p = mcnemar_exact(b, c)
            mc[k] = (b, c, N, p)
            print(f"  {k:16s} {sum(real[k])}/{N} = {sum(real[k])/N*100:5.2f}%  "
                  f"b={b} c={c} n={N} p={p:.4f}")
        allres[run] = {"n": N, "exp": {k: sum(v)/N for k, v in exp.items()},
                       "mcnemar": mc, "exp_series": exp, "real": real}
    return allres


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--pool", type=int, default=7)
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--boot", type=int, default=10000)
    a = ap.parse_args()
    run(a.runs.split(","), a.pool, a.seed, a.boot)
