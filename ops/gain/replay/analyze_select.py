"""執行落地選擇（execution-grounded selection）的離線重放分析。

輸入＝exec_select.py 產出的 V 側事實（每個候選在 base inputs 上逐筆通過與否、
行為簽名、程式長度）＋ hidden 計分欄位。

V/GT 分離的操作化：所有 policy 函式只讀 visible_pass / visible_total / sig /
code_len / idx。`hidden_ok` 只在 `score()` 之後被讀。任何 policy 都拿不到它。

等預算：policy 都在 OFF5 那 5 次 gen 呼叫的同一批候選上選；沙箱執行是本機
免費的，不計入呼叫預算 ⇒ 5 呼叫／題，與 OFF5、ON 相同。
adaptive 那條是**更省**（平均 <5 呼叫），另外標出。
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from vacant.research import mcnemar_exact  # noqa: E402

CACHE = pathlib.Path(__file__).resolve().parent / "cache"


def load(run, arm="OFF5"):
    facts = collections.defaultdict(dict)
    for ln in (CACHE / f"{run}.jsonl").open(encoding="utf-8"):
        r = json.loads(ln)
        if r["arm"] != arm:
            continue
        facts[r["task_id"]][r["idx"]] = r
    # 重跑補正：只把「長 timeout 下其實會過」的假陰性翻回 True（見 verify_hidden.py）
    retry = CACHE / "hidden_retry.jsonl"
    n_flip = 0
    if retry.exists():
        for ln in retry.open(encoding="utf-8"):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("run") != run or r.get("arm") != arm or not r.get("hidden_ok2"):
                continue
            d = facts.get(r["task_id"], {})
            if r["idx"] in d and d[r["idx"]].get("hidden_ok") is False:
                d[r["idx"]]["hidden_ok"] = True
                d[r["idx"]]["timeout_recovered"] = True
                n_flip += 1
    if n_flip:
        print(f"[{run}] hidden retry recovered {n_flip} timeout false-negatives")
    fz = CACHE / "fuzz_sig.jsonl"
    n_fz = 0
    if fz.exists():
        for ln in fz.open(encoding="utf-8"):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("run") != run or r.get("arm") != arm or "fuzz_sig" not in r:
                continue
            d = facts.get(r["task_id"], {})
            if r["idx"] in d:
                d[r["idx"]]["fsig"] = r["fuzz_sig"]
                d[r["idx"]]["n_fuzz"] = r.get("n_fuzz", 0)
                n_fz += 1
    if n_fz:
        print(f"[{run}] fuzz signatures merged for {n_fz} candidates")
    out = {t: [d[i] for i in sorted(d)] for t, d in facts.items()}
    rows = {}
    for ln in (REPO / "runs" / run / "rows.jsonl").open(encoding="utf-8"):
        r = json.loads(ln)
        rows[(r["arm"], r["task_id"])] = r
    return out, rows


def _group(cs):
    g = collections.defaultdict(list)
    for c in cs:
        g[c["sig"]].append(c)
    return g


def _bk(cs):
    return collections.Counter(c["sig"] for c in cs)


def _rich(c):
    """base 行為簽名 ＋ 契約合法變異輸入上的行為（沒有期望輸出，只看彼此同意）。"""
    return c["sig"] + "||" + c.get("fsig", "")


def _bkr(cs):
    return collections.Counter(_rich(c) for c in cs)


def p_fuzz_vote(cs):
    b = _bkr(cs)
    return min(cs, key=lambda c: (-b[_rich(c)], c["code_len"], c["idx"]))


def p_visfilter_fuzz_vote(cs):
    pool = [c for c in cs if c["visible_ok"]] or cs
    b = collections.Counter(_rich(c) for c in pool)
    return min(pool, key=lambda c: (-b[_rich(c)], c["code_len"], c["idx"]))


def p_vote(cs):
    b = _bk(cs)
    m = max(b.values())
    return next(c for c in cs if b[c["sig"]] == m)


def p_maxvis_vote(cs):
    b = _bk(cs)
    return min(cs, key=lambda c: (-c["visible_pass"], -b[c["sig"]], c["idx"]))


def p_maxvis_short(cs):
    return min(cs, key=lambda c: (-c["visible_pass"], c["code_len"], c["idx"]))


def p_maxvis_vote_short(cs):
    b = _bk(cs)
    return min(cs, key=lambda c: (-c["visible_pass"], -b[c["sig"]], c["code_len"],
                                  c["idx"]))


def p_visfilter_vote(cs):
    ok = [c for c in cs if c["visible_ok"]] or cs
    return p_vote(ok)


def p_visfilter_vote_short(cs):
    pool = [c for c in cs if c["visible_ok"]] or cs
    b = _bk(pool)
    return min(pool, key=lambda c: (-b[c["sig"]], c["code_len"], c["idx"]))


def p_visfilter_vote_long(cs):
    """平手時取**最長**：r441 的 15 個「可見全過但隱藏分歧」題目上，最長者
    對 11/15、最短者只對 5/15（事後觀察、n 小，標為探索性）。"""
    pool = [c for c in cs if c["visible_ok"]] or cs
    b = _bk(pool)
    return min(pool, key=lambda c: (-b[c["sig"]], -c["code_len"], c["idx"]))


def p_visfilter_long(cs):
    pool = [c for c in cs if c["visible_ok"]] or cs
    return min(pool, key=lambda c: (-c["code_len"], c["idx"]))


def p_first_pass(cs):
    for c in cs:
        if c["visible_ok"]:
            return c
    return p_vote(cs)


def p_adaptive3(cs):
    """先花 3 呼叫；前 3 個有人通過可見測試就結案，否則再花 2 個。"""
    head = cs[:3]
    if any(c["visible_ok"] for c in head):
        return p_visfilter_vote_short(head)
    return p_visfilter_vote_short(cs)


def cost_5(cs, picked):
    return 5


def cost_first(cs, picked):
    return picked["idx"] + 1 if picked["visible_ok"] else 5


def cost_adaptive3(cs, picked):
    return 3 if any(c["visible_ok"] for c in cs[:3]) else 5


POLICIES = [
    ("vote (replay of current OFF5)", p_vote, cost_5),
    ("max-visible / vote", p_maxvis_vote, cost_5),
    ("max-visible / shortest", p_maxvis_short, cost_5),
    ("max-visible / vote / shortest", p_maxvis_vote_short, cost_5),
    ("visible-filter + vote", p_visfilter_vote, cost_5),
    ("visible-filter + vote / shortest", p_visfilter_vote_short, cost_5),
    ("first-visible-pass (early stop)", p_first_pass, cost_first),
    ("adaptive 3->5 (visible-filter)", p_adaptive3, cost_adaptive3),
    ("visible-filter + vote / longest", p_visfilter_vote_long, cost_5),
    ("visible-filter + longest", p_visfilter_long, cost_5),
    ("fuzz-consensus vote", p_fuzz_vote, cost_5),
    ("visible-filter + fuzz-consensus", p_visfilter_fuzz_vote, cost_5),
]


# ── 期望值版本：把「平手時抽籤」算成期望值，去掉抽籤運氣 ──────────────
def _exp_over(pool):
    """在 pool 上做行為多數決＋平手抽籤的期望通過率（gain_run 的抽法）。"""
    b = collections.defaultdict(list)
    for c in pool:
        b[c["sig"]].append(c)
    m = max(len(v) for v in b.values())
    tied = [v for v in b.values() if len(v) == m]
    return sum(sum(bool(c["hidden_ok"]) for c in v) / len(v) for v in tied) / len(tied)


def exp_current(cs):
    """現行 OFF5：全部 5 個候選做行為多數決，平手抽籤。"""
    return _exp_over(cs)


def exp_visfilter(cs):
    """先用可見測試過濾，再在存活者上做同一個多數決＋抽籤。"""
    pool = [c for c in cs if c["visible_ok"]] or cs
    return _exp_over(pool)


def exp_fuzz(cs):
    b = collections.defaultdict(list)
    for c in cs:
        b[_rich(c)].append(c)
    m = max(len(v) for v in b.values())
    tied = [v for v in b.values() if len(v) == m]
    return sum(sum(bool(c["hidden_ok"]) for c in v) / len(v) for v in tied) / len(tied)


def exp_visfilter_fuzz(cs):
    pool = [c for c in cs if c["visible_ok"]] or cs
    b = collections.defaultdict(list)
    for c in pool:
        b[_rich(c)].append(c)
    m = max(len(v) for v in b.values())
    tied = [v for v in b.values() if len(v) == m]
    return sum(sum(bool(c["hidden_ok"]) for c in v) / len(v) for v in tied) / len(tied)


def exp_maxvis(cs):
    top = max(c["visible_pass"] for c in cs)
    pool = [c for c in cs if c["visible_pass"] == top]
    return _exp_over(pool)


def exp_uniform(cs):
    return sum(bool(c["hidden_ok"]) for c in cs) / len(cs)


def boot_diff(d, n_boot=5000, seed=0):
    import random
    rng = random.Random(seed)
    n = len(d)
    out = []
    for _ in range(n_boot):
        out.append(sum(d[rng.randrange(n)] for _ in range(n)) / n)
    out.sort()
    return out[int(0.025 * n_boot)], out[int(0.975 * n_boot)]


def expectations(run, tasks, facts, rows):
    n = len(tasks)
    cur = [exp_current(facts[t]) for t in tasks]
    vf = [exp_visfilter(facts[t]) for t in tasks]
    mv = [exp_maxvis(facts[t]) for t in tasks]
    uni = [exp_uniform(facts[t]) for t in tasks]
    act = sum(bool(rows[("OFF5", t)]["meets_demand"]) for t in tasks) / n
    print(f"\n  --- expected pass rate (tie-break lottery integrated out), n={n} ---")
    print(f"  E[uniform random of 5 (no vote)]        {100*sum(uni)/n:6.2f}%")
    import math
    sd = math.sqrt(sum(p * (1 - p) for p in cur)) / n
    print(f"  E[current OFF5 behaviour-vote]          {100*sum(cur)/n:6.2f}%"
          f"   (this run actually shipped {100*act:.2f}%; "
          f"lottery SD {100*sd:.2f}pp, gap {(act-sum(cur)/n)/max(sd,1e-9):.1f}σ)")
    extra = []
    if all("fsig" in c for t in tasks for c in facts[t]):
        extra = [("E[fuzz-consensus vote]", [exp_fuzz(facts[t]) for t in tasks]),
                 ("E[visible-filter + fuzz-consensus]",
                  [exp_visfilter_fuzz(facts[t]) for t in tasks])]
        nb = sum(1 for t in tasks if len(_bk(facts[t])) == 1 and len(_bkr(facts[t])) > 1)
        print(f"  fuzz split {nb} of the {sum(1 for t in tasks if len(_bk(facts[t]))==1)}"
              f" base-unanimous tasks into >1 behaviour class")
    for nm, arr in ([("E[visible-filter + vote]", vf), ("E[max-visible + vote]", mv)]
                    + extra):
        d = [a - b for a, b in zip(arr, cur)]
        lo, hi = boot_diff(d)
        print(f"  {nm:38s}{100*sum(arr)/n:6.2f}%   Δ vs current "
              f"{100*sum(d)/n:+6.2f}pp  95%% CI [{100*lo:+.2f}, {100*hi:+.2f}]")


def mcn(a, b):
    bb = sum(1 for x, y in zip(a, b) if (not x) and y)
    cc = sum(1 for x, y in zip(a, b) if x and (not y))
    return len(a), bb, cc, mcnemar_exact(bb, cc)


def usable_tasks(facts, rows, k=5):
    out, skipped = [], collections.Counter()
    for t, cs in sorted(facts.items()):
        if len(cs) != k:
            skipped["wrong_candidate_count"] += 1
            continue
        if any("hidden_ok" not in c or "sig" not in c for c in cs):
            skipped["void_or_missing"] += 1
            continue
        if ("OFF5", t) not in rows:
            skipped["no_row"] += 1
            continue
        out.append(t)
    return out, skipped


def report(run):
    facts, rows = load(run)
    tasks, skipped = usable_tasks(facts, rows)
    n = len(tasks)
    actual = [bool(rows[("OFF5", t)]["meets_demand"]) for t in tasks]
    print(f"\n{'='*78}\n{run} · arm=OFF5 · n={n} tasks  (skipped {dict(skipped)})")
    print(f"{'='*78}")
    print(f"OFF5 actual shipped                    {sum(actual):3d}/{n} = "
          f"{100*sum(actual)/n:6.2f}%   [baseline]")

    # ── 天花板 ──
    orc = sum(1 for t in tasks if any(c["hidden_ok"] for c in facts[t]))
    reach = sum(1 for t in tasks
                if any(c["visible_ok"] and c["hidden_ok"] for c in facts[t]))
    novis = sum(1 for t in tasks if not any(c["visible_ok"] for c in facts[t]))
    novis_but_hidden = sum(
        1 for t in tasks
        if not any(c["visible_ok"] for c in facts[t]) and any(c["hidden_ok"] for c in facts[t]))
    free = sum(1 for t in tasks
               if any(c["visible_ok"] for c in facts[t])
               and all(c["hidden_ok"] for c in facts[t] if c["visible_ok"]))
    trap = sum(1 for t in tasks
               if any(c["visible_ok"] for c in facts[t])
               and not any(c["visible_ok"] and c["hidden_ok"] for c in facts[t]))
    print(f"  oracle ceiling  ∃cand hidden-pass     {orc:3d}/{n} = {100*orc/n:6.2f}%")
    print(f"  V-reachable     ∃cand vis✓ & hid✓     {reach:3d}/{n} = {100*reach/n:6.2f}%")
    print(f"  no candidate passes visible           {novis:3d}/{n} = {100*novis/n:6.2f}%"
          f"   (of these {novis_but_hidden} still had a hidden-passing candidate)")
    print(f"  all vis-passers also hidden-pass      {free:3d}   (selection choice is free)")
    print(f"  vis-pass exists but ALL fail hidden   {trap:3d}   (visible suite fooled)")

    # ── 同一個行為桶內部仍然不同命 ──
    uni = [t for t in tasks if len(_bk(facts[t])) == 1]
    uni_mixed = [t for t in uni if len({bool(c["hidden_ok"]) for c in facts[t]}) > 1]
    nonuni = [t for t in tasks if len(_bk(facts[t])) > 1]
    mixed_any = [t for t in tasks
                 if any(len({bool(c["hidden_ok"]) for c in v}) > 1
                        for v in _group(facts[t]).values())]
    print(f"  unanimous on base inputs (1 bucket)   {len(uni):3d}/{n}"
          f"  of which hidden outcome is MIXED: {len(uni_mixed)}")
    print(f"  any behaviour bucket with mixed hidden {len(mixed_any):3d}"
          f"   (base-input agreement does not pin down hidden correctness)")
    print(f"  non-unanimous tasks                    {len(nonuni):3d}")

    # ── policy ──
    print(f"\n  {'policy':36s} {'pass':>12s}  {'Δ vs OFF5':>9s}  "
          f"{'b':>3s} {'c':>3s} {'McNemar p':>9s}  calls/task")
    results = {}
    for name, fn, cost in POLICIES:
        picked = [fn(facts[t]) for t in tasks]
        got = [bool(p["hidden_ok"]) for p in picked]
        _, bb, cc, p = mcn(actual, got)
        calls = sum(cost(facts[t], picked[i]) for i, t in enumerate(tasks)) / n
        results[name] = got
        print(f"  {name:36s} {sum(got):3d}/{n} ={100*sum(got)/n:6.2f}%  "
              f"{100*(sum(got)-sum(actual))/n:+8.2f}pp  {bb:3d} {cc:3d} {p:9.4f}  "
              f"{calls:5.2f}")

    # ── 棄權（拒絕出貨）變體 ──
    abstain = [t for t in tasks if not any(c["visible_ok"] for c in facts[t])]
    ship = [t for t in tasks if t not in set(abstain)]
    if ship:
        got = [bool(p_visfilter_vote_short(facts[t])["hidden_ok"]) for t in ship]
        base_ship = [bool(rows[("OFF5", t)]["meets_demand"]) for t in ship]
        would_fail = sum(1 for t in abstain if not rows[("OFF5", t)]["meets_demand"])
        print(f"\n  refuse-to-ship variant (gate = no candidate passes visible):")
        print(f"    abstained {len(abstain)}/{n} tasks; of those, OFF5 actually "
              f"failed {would_fail}/{len(abstain)} = "
              f"{100*would_fail/max(1,len(abstain)):.1f}% (abstention precision)")
        print(f"    conditional pass rate on shipped {sum(got)}/{len(ship)} = "
              f"{100*sum(got)/len(ship):.2f}%  (OFF5 on same subset "
              f"{100*sum(base_ship)/len(ship):.2f}%)")

    # ── 失敗解剖 ──
    fails = [t for t in tasks if not rows[("OFF5", t)]["meets_demand"]]
    f_visfalse = [t for t in fails if not rows[("OFF5", t)].get("visible_ok")]
    rescuable = [t for t in f_visfalse
                 if any(c["visible_ok"] and c["hidden_ok"] for c in facts[t])]
    print(f"\n  OFF5 failures {len(fails)}; shipped-with-visible_ok=false "
          f"{len(f_visfalse)}; of those, a vis✓&hid✓ candidate existed: {len(rescuable)}")
    return tasks, facts, rows, results, actual


def coverage_risk(run, tasks, facts, rows):
    """執行落地的「有多少把握」：以通過可見測試的候選數當信心分數。

    ON 已經有一道拒絕出貨的閘（accepted = visible_ok），所以公平的比較不是
    只看 pass rate，而是**同覆蓋率下的條件正確率**。"""
    n = len(tasks)
    pick = {t: p_visfilter_vote_short(facts[t]) for t in tasks}
    nv = {t: sum(1 for c in facts[t] if c["visible_ok"]) for t in tasks}
    print(f"\n  --- coverage / conditional accuracy (execution-grounded gate), n={n} ---")
    print(f"  {'ship iff #vis-pass >= t':28s} {'coverage':>10s} {'cond. pass':>12s}")
    for t_ in range(1, 6):
        ship = [t for t in tasks if nv[t] >= t_]
        if not ship:
            continue
        ok = sum(1 for t in ship if pick[t]["hidden_ok"])
        print(f"  t={t_}                          "
              f"{len(ship):3d}/{n} = {100*len(ship)/n:5.1f}%  "
              f"{ok:3d}/{len(ship)} = {100*ok/len(ship):5.2f}%")
    # 跟 ON 同一道閘（出貨的那份自己要過可見測試），套在 OFF5 的現行選法上
    cur_ok = [t for t in tasks if rows[("OFF5", t)].get("visible_ok")]
    okc = sum(1 for t in cur_ok if rows[("OFF5", t)]["meets_demand"])
    print(f"  OFF5 current pick + ON-style gate "
          f"{len(cur_ok):3d}/{n} = {100*len(cur_ok)/n:5.1f}%  "
          f"{okc:3d}/{len(cur_ok)} = {100*okc/len(cur_ok):5.2f}%")
    on = [t for t in tasks if ("ON", t) in rows]
    if on:
        acc = [t for t in on if rows[("ON", t)].get("accepted") is not False]
        okp = sum(1 for t in acc if rows[("ON", t)]["meets_demand"])
        print(f"  ON (5 calls, its own accept gate) "
              f"{len(acc):3d}/{len(on)} = {100*len(acc)/len(on):5.1f}%  "
              f"{okp:3d}/{len(acc)} = {100*okp/len(acc):5.2f}%")


def cross_arm(run, tasks, facts, rows):
    pairs = [t for t in tasks
             if ("ON", t) in rows and rows[("ON", t)].get("meets_demand") is not None]
    if not pairs:
        return
    on = [bool(rows[("ON", t)]["meets_demand"]) for t in pairs]
    off = [bool(rows[("OFF", t)]["meets_demand"]) for t in pairs
           if ("OFF", t) in rows]
    print(f"\n  --- vs ON (both 5 calls), paired n={len(pairs)} ---")
    print(f"  ON actual                              {sum(on):3d}/{len(pairs)} = "
          f"{100*sum(on)/len(pairs):6.2f}%")
    if len(off) == len(pairs):
        print(f"  OFF actual (1 call)                    {sum(off):3d}/{len(pairs)} = "
              f"{100*sum(off)/len(pairs):6.2f}%")
    for name, fn, _c in POLICIES:
        got = [bool(fn(facts[t])["hidden_ok"]) for t in pairs]
        _, bb, cc, p = mcn(on, got)
        print(f"  {name:36s} {sum(got):3d}/{len(pairs)} ={100*sum(got)/len(pairs):6.2f}%"
              f"  Δ vs ON {100*(sum(got)-sum(on))/len(pairs):+6.2f}pp  "
              f"b={bb:3d} c={cc:3d} p={p:.4f}")


def k_curve(run):
    """把 5 個候選當「依序生成」，看前 k 個上的選法（k 呼叫預算）。"""
    facts, rows = load(run)
    tasks, _ = usable_tasks(facts, rows)
    n = len(tasks)
    actual = sum(bool(rows[("OFF5", t)]["meets_demand"]) for t in tasks)
    off = [t for t in tasks if ("OFF", t) in rows]
    print(f"\n  --- budget curve (first k of the same 5 candidates), n={n} ---")
    if len(off) == n:
        print(f"  OFF actual (1 call)                     "
              f"{sum(bool(rows[('OFF', t)]['meets_demand']) for t in off):3d}/{n} = "
              f"{100*sum(bool(rows[('OFF', t)]['meets_demand']) for t in off)/n:6.2f}%")
    base1 = [bool(facts[t][0]["hidden_ok"]) for t in tasks]
    fp = [bool(p_first_pass(facts[t])["hidden_ok"]) for t in tasks]
    calls = sum(cost_first(facts[t], p_first_pass(facts[t])) for t in tasks) / n
    _, bb, cc, pv = mcn(base1, fp)
    print(f"  first-visible-pass ({calls:.2f} calls/task) vs single sample "
          f"(1 call), same replay labels: {100*sum(fp)/n:.2f}% vs "
          f"{100*sum(base1)/n:.2f}% = {100*(sum(fp)-sum(base1))/n:+.2f}pp  "
          f"b={bb} c={cc} p={pv:.4f}")
    print(f"  {'k':>2s}  {'vote-only':>16s}  {'visible-filter+vote/short':>26s}")
    for k in range(1, 6):
        v = sum(bool(p_vote(facts[t][:k])["hidden_ok"]) for t in tasks)
        e = sum(bool(p_visfilter_vote_short(facts[t][:k])["hidden_ok"]) for t in tasks)
        print(f"  {k:2d}  {v:3d}/{n} = {100*v/n:6.2f}%  {e:3d}/{n} = {100*e/n:6.2f}%"
              f"   (OFF5 actual@5 = {100*actual/n:.2f}%)")


def pooled(runs):
    all_actual, all_pol, ns = [], collections.defaultdict(list), 0
    e_cur, e_vf, base1, fp, fp_cost, orc = [], [], [], [], [], []
    for run in runs:
        facts, rows = load(run)
        tasks, _ = usable_tasks(facts, rows)
        ns += len(tasks)
        all_actual += [bool(rows[("OFF5", t)]["meets_demand"]) for t in tasks]
        e_cur += [exp_current(facts[t]) for t in tasks]
        e_vf += [exp_visfilter(facts[t]) for t in tasks]
        base1 += [bool(facts[t][0]["hidden_ok"]) for t in tasks]
        fp += [bool(p_first_pass(facts[t])["hidden_ok"]) for t in tasks]
        fp_cost += [cost_first(facts[t], p_first_pass(facts[t])) for t in tasks]
        orc += [any(c["hidden_ok"] for c in facts[t]) for t in tasks]
        for name, fn, _c in POLICIES:
            all_pol[name] += [bool(fn(facts[t])["hidden_ok"]) for t in tasks]
    print(f"\n{'='*78}\nPOOLED across {len(runs)} runs · n={ns}\n{'='*78}")
    print(f"  OFF5 actual                            {sum(all_actual):3d}/{ns} = "
          f"{100*sum(all_actual)/ns:6.2f}%")
    for name, got in all_pol.items():
        _, bb, cc, p = mcn(all_actual, got)
        print(f"  {name:36s} {sum(got):3d}/{ns} ={100*sum(got)/ns:6.2f}%  "
              f"{100*(sum(got)-sum(all_actual))/ns:+8.2f}pp  b={bb:3d} c={cc:3d} "
              f"p={p:.4f}")
    d = [a - b for a, b in zip(e_vf, e_cur)]
    lo, hi = boot_diff(d)
    print(f"\n  oracle ceiling over the same 5 candidates "
          f"{sum(orc):3d}/{ns} = {100*sum(orc)/ns:6.2f}%  "
          f"(actual {100*sum(all_actual)/ns:.2f}% ⇒ max recoverable "
          f"{100*(sum(orc)-sum(all_actual))/ns:+.2f}pp)")
    print(f"  E[current OFF5 vote]                   {100*sum(e_cur)/ns:6.2f}%")
    print(f"  E[visible-filter + vote]               {100*sum(e_vf)/ns:6.2f}%  "
          f"Δ {100*sum(d)/ns:+.2f}pp  95% CI [{100*lo:+.2f}, {100*hi:+.2f}]")
    _, bb, cc, p = mcn(base1, fp)
    print(f"  first-visible-pass ({sum(fp_cost)/ns:.2f} calls/task) "
          f"{100*sum(fp)/ns:.2f}% vs single sample (1 call) {100*sum(base1)/ns:.2f}% "
          f"= {100*(sum(fp)-sum(base1))/ns:+.2f}pp  b={bb} c={cc} p={p:.4f}")


def validate(run):
    facts, rows = load(run)
    ok = bad = miss = 0
    for t, cs in facts.items():
        r = rows.get(("OFF5", t))
        if not r or len(cs) != 5 or r.get("vote_agreement") is None:
            miss += 1
            continue
        b = _bk(cs)
        if max(b.values()) == r["vote_agreement"] and len(b) == r["n_buckets"]:
            ok += 1
        else:
            bad += 1
    print(f"[validate {run}] replayed behaviour buckets vs rows.jsonl "
          f"(vote_agreement,n_buckets): {ok} match, {bad} mismatch, {miss} skipped")
    # visible_ok 對帳：至少該有「shipped 的那個候選 visible_ok」一致的可能
    v_ok = v_bad = 0
    for t, cs in facts.items():
        r = rows.get(("OFF5", t))
        if not r or len(cs) != 5:
            continue
        if any(c["visible_ok"] == bool(r["visible_ok"]) for c in cs):
            v_ok += 1
        else:
            v_bad += 1
    print(f"[validate {run}] some replayed candidate matches row visible_ok: "
          f"{v_ok} ok, {v_bad} impossible")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    a = ap.parse_args()
    runs = a.runs.split(",")
    for run in runs:
        validate(run)
        tasks, facts, rows, _res, _act = report(run)
        expectations(run, tasks, facts, rows)
        coverage_risk(run, tasks, facts, rows)
        cross_arm(run, tasks, facts, rows)
        k_curve(run)
    if len(runs) > 1:
        pooled(runs)
