"""離線重放：Requirement-Conformance Delivery (RCD)。

這支**不打任何模型端點**。候選答案全部來自 runs/<run>/calls.jsonl 已落盤的
response 文字；沙箱執行是本機免費的，不計入呼叫預算。

機制（RCD）＝三個零呼叫步驟，沒有 reviewer、沒有 revise：
  1. normalize：候選若沒有把需求指定的 entry_point 綁到頂層，就用 arity 相容的
     頂層函式包一層 `def <entry_point>(*a, **k): return <fn>(*a, **k)`。
     （純 AST＋visible 試打；不看 hidden。）
  2. conformance gate：把 normalize 後的候選逐一跑 **visible_check**（顧客自己
     寫得出來的驗收條件），不通過的一律不出貨。
  3. tie-break / refuse：通過的候選裡取行為簽名最大群（同 arm_off5 的多數決
     定義，只是母體換成「已通過驗收」的那些）；一個都沒通過就**拒交**。

V/GT 分離（codebench.py §「GT 只進 hidden_check」）在這裡的操作化：
  - 任何 policy 函式只吃 CandidateFacts 的 V 側欄位（visible_pass / visible_total
    / sig / idx / normalized 與否）。`hidden_ok` 只寫進計分欄位，policy 讀不到。
  - normalize 選 alias 目標時只用 visible_check 的通過與否，不碰 hidden_check。
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures as cf
import hashlib
import json
import math
import os
import pathlib
import random
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ops" / "gain"))
os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", str(REPO / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"))

from ops.gain.gain_run import InfraVoid, meets_demand  # noqa: E402
from ops.gain.replay.exec_select import load_candidates, visible_grade  # noqa: E402
from vacant.codebench import EvalPlusMBPPLoader  # noqa: E402

SEED = "g-r212-route-20260828"
HERE = pathlib.Path(__file__).resolve().parent
CACHE = HERE / "cache"
OUT = HERE / "cache" / "rcd_facts.jsonl"

_TASKS: dict = {}


def _init():
    global _TASKS
    if not _TASKS:
        _TASKS.update({t["task_id"]: t
                       for t in EvalPlusMBPPLoader(expose_contract=True).iter_tasks(SEED)})


# ── 步驟 1：normalize（零呼叫，AST 側）────────────────────────────────
def _top_level(tree: ast.Module):
    funcs, bound = [], set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound.add(n.name); funcs.append(n)
        elif isinstance(n, ast.ClassDef):
            bound.add(n.name)
        elif isinstance(n, ast.Assign):
            bound |= {x.id for x in n.targets if isinstance(x, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            bound.add(n.target.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                bound.add(a.asname or a.name.split(".")[0])
    return funcs, bound


def _arity_fits(fn, nargs: int) -> bool:
    if not nargs:
        return True
    a = fn.args
    pos = len(getattr(a, "posonlyargs", [])) + len(a.args)
    mn = pos - len(a.defaults)
    mx = 10 ** 6 if a.vararg else pos
    return mn <= nargs <= mx


def _wrap(code: str, entry_point: str, target: str) -> str:
    return f"{code}\n\n\ndef {entry_point}(*__a, **__k):\n    return {target}(*__a, **__k)\n"


def alias_targets(code: str, task: dict) -> list[str]:
    """回傳「值得試」的 alias 目標名單（source order）。空 list ⇒ 不需要／不能 normalize。"""
    ep = task["entry_point"]
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    funcs, bound = _top_level(tree)
    if ep in bound or not funcs:
        return []
    nargs = len(task.get("input_parameters") or [])
    fit = [f for f in funcs if _arity_fits(f, nargs)] or funcs
    return list(dict.fromkeys(f.name for f in fit))


# ── 執行（免費本機沙箱）──────────────────────────────────────────────
def _facts(code: str, task: dict) -> dict:
    vp, vt, sig, vok = visible_grade(code, task)
    try:
        hok, _ = meets_demand(code, task["hidden_check"]["code"],
                              entry_point=task.get("entry_point"))
    except InfraVoid as e:
        return {"visible_pass": vp, "visible_total": vt, "sig": sig,
                "visible_ok": vok, "err": f"hidden_void:{e}"}
    return {"visible_pass": vp, "visible_total": vt, "sig": sig,
            "visible_ok": vok, "hidden_ok": hok}


def _work(job):
    run, tid, idx, code = job
    t = _TASKS[tid]
    rec = {"run": run, "task_id": tid, "idx": idx,
           "sha_raw": hashlib.sha256(code.encode()).hexdigest()[:16]}
    tgts = alias_targets(code, t)
    if not tgts:                                    # pragma: no cover - prep filters these
        rec.update({"normalized": False, "alias_target": None})
        return rec
    # V 側挑 alias 目標：跑 visible_check，取第一個通過的；都不過就取
    # visible_pass 最高者（同分取 source order 第一個）。不看 hidden。
    best = None
    for name in tgts:
        cand = _wrap(code, t["entry_point"], name)
        try:
            vp, vt, sig, vok = visible_grade(cand, t)
        except InfraVoid:
            continue
        score = (vok, vp)
        if best is None or score > best[0]:
            best = (score, name, cand, vp, vt, sig, vok)
        if vok:
            break
    if best is None:
        rec.update({"normalized": False, "alias_target": None, "err": "alias_void"})
        return rec
    _, name, cand, vp, vt, sig, vok = best
    rec.update({"normalized": True, "alias_target": name, "n_targets": len(tgts),
                "visible_pass": vp, "visible_total": vt, "sig": sig, "visible_ok": vok})
    try:
        hok, _ = meets_demand(cand, t["hidden_check"]["code"],
                              entry_point=t.get("entry_point"))
        rec["hidden_ok"] = hok
    except InfraVoid as e:
        rec["err"] = f"hidden_void:{e}"
    return rec


def cmd_prep(runs, workers):
    _init()
    CACHE.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        for ln in OUT.open():
            r = json.loads(ln)
            done.add((r["run"], r["task_id"], r["idx"]))
    jobs = []
    for run in runs:
        cands = load_candidates(run)
        for (arm, tid), lst in sorted(cands.items()):
            if arm != "OFF5" or tid not in _TASKS or len(lst) != 5:
                continue
            for i, c in enumerate(lst):
                if (run, tid, i) in done:
                    continue
                if not alias_targets(c["code"], _TASKS[tid]):
                    continue          # 不需要 normalize ⇒ 直接沿用 raw cache 的事實
                jobs.append((run, tid, i, c["code"]))
    print(f"prep: {len(jobs)} candidate-normalisations to run", flush=True)
    with OUT.open("a", encoding="utf-8") as fh:
        with cf.ProcessPoolExecutor(max_workers=workers, initializer=_init) as ex:
            for n, rec in enumerate(ex.map(_work, jobs, chunksize=1), 1):
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                if n % 25 == 0:
                    print(f"  {n}/{len(jobs)}", flush=True)


# ── 分析 ──────────────────────────────────────────────────────────────
def _load_rows(run):
    out = {}
    for ln in (REPO / "runs" / run / "rows.jsonl").open(encoding="utf-8"):
        r = json.loads(ln)
        out[(r["arm"], r["task_id"])] = r
    return out


def _load_raw_cache(run):
    out = {}
    p = CACHE / f"{run}.jsonl"
    if not p.exists():
        return out
    for ln in p.open(encoding="utf-8"):
        r = json.loads(ln)
        if r["arm"] == "OFF5":
            out[(r["task_id"], r["idx"])] = r
    return out


def _load_fuzz(run):
    out = {}
    p = CACHE / "fuzz_sig.jsonl"
    if not p.exists():
        return out
    for ln in p.open(encoding="utf-8"):
        r = json.loads(ln)
        if r["run"] == run and r["arm"] == "OFF5":
            out[(r["task_id"], r["idx"])] = r["fuzz_sig"]
    return out


def _extend_cache(run):
    out = {}
    p = CACHE / "rcd_extend.jsonl"
    if not p.exists():
        return out
    for ln in p.open(encoding="utf-8"):
        r = json.loads(ln)
        if r["run"] == run and r.get("hidden_ok") is not None:
            out.setdefault(r["task_id"], []).append(r)
    for v in out.values():
        v.sort(key=lambda r: r["order"])
    return out


def _norm_cache(run):
    out = {}
    for ln in OUT.open(encoding="utf-8"):
        r = json.loads(ln)
        if r["run"] == run:
            out[(r["task_id"], r["idx"])] = r
    return out


# ---- policies: 只吃 V 側欄位
def pol_off5_rule(cands, key="raw"):
    """gain_run.arm_off5 的規則，回傳 {idx: 機率}（lottery 未擲）。只看 sig。"""
    buckets = {}
    for c in cands:
        buckets.setdefault(c[key]["sig"], []).append(c["idx"])
    mx = max(len(v) for v in buckets.values())
    tied = [v for v in buckets.values() if len(v) == mx]
    p = {}
    for b in tied:
        for i in b:
            p[i] = p.get(i, 0.0) + 1.0 / (len(tied) * len(b))
    return p


def _classes(pool, key):
    out = {}
    for c in pool:
        out.setdefault(c[key]["sig"], []).append(c)
    return out


def _pick(cls_members):
    return min(cls_members, key=lambda x: x["idx"])


def pol_gate_vote(cands, key):
    """conformance gate ＋ 群內多數決；一個都不合格 ⇒ 拒交 (None)。"""
    pool = [c for c in cands if c[key]["visible_ok"]]
    if not pool:
        return None, 5
    cls = _classes(pool, key)
    best = max(cls.values(), key=lambda v: (len(v), -min(x["idx"] for x in v)))
    return _pick(best), 5


def pol_gate_vote_nofuse(cands, key):
    """同 gate_vote，但不合格時退回全體多數決（永遠出貨，對照用）。"""
    pool = [c for c in cands if c[key]["visible_ok"]] or list(cands)
    cls = _classes(pool, key)
    best = max(cls.values(), key=lambda v: (len(v), -min(x["idx"] for x in v)))
    return _pick(best), 5


def pol_no_gate_vote(cands, key):
    """normalize 後照 OFF5 原規則多數決（不設閘門）——拆解用的消融。"""
    cls = _classes(list(cands), key)
    best = max(cls.values(), key=lambda v: (len(v), -min(x["idx"] for x in v)))
    return _pick(best), 5


def pol_gate_first(cands, key):
    """順序抽樣、第一個通過驗收就出貨；都不過 ⇒ 拒交。預算隨失敗才追加。"""
    for c in cands:
        if c[key]["visible_ok"]:
            return c, c["idx"] + 1
    return None, len(cands)


def pol_gate_quorum(cands, key, q=2):
    """順序抽樣，直到有 q 個**合格**候選行為一致才出貨；否則繼續抽到 5。"""
    seen = []
    for c in cands:
        seen.append(c)
        pool = [x for x in seen if x[key]["visible_ok"]]
        cls = _classes(pool, key)
        ok = [v for v in cls.values() if len(v) >= q]
        if ok:
            best = max(ok, key=lambda v: (len(v), -min(x["idx"] for x in v)))
            return _pick(best), c["idx"] + 1
    pool = [x for x in seen if x[key]["visible_ok"]]
    if not pool:
        return None, len(cands)
    return _pick(pool), len(cands)


def pol_gate_diverse(cands, key):
    """合格候選裡，取「不同 agent 最多」的行為類（去相關的一致才算一致）。"""
    pool = [c for c in cands if c[key]["visible_ok"]]
    if not pool:
        return None, 5
    cls = _classes(pool, key)
    best = max(cls.values(), key=lambda v: (len({x["agent_id"] for x in v}), len(v),
                                            -min(x["idx"] for x in v)))
    return _pick(best), 5


def pol_single(cands, key):
    """1 次呼叫、直接出貨（OFF 的規則）——預算軸的對照底線。"""
    return cands[0], 1


def pol_selective(cands, key, q=2):
    """gate ＋ 「至少要有 q 個合格候選彼此行為一致」才出貨；否則拒交。
    這是把預算換成**覆蓋率**：不確定就不交，而不是硬交一份。"""
    pool = [c for c in cands if c[key]["visible_ok"]]
    if not pool:
        return None, 5
    cls = _classes(pool, key)
    ok = [v for v in cls.values() if len(v) >= q]
    if not ok:
        return None, 5
    best = max(ok, key=lambda v: (len(v), -min(x["idx"] for x in v)))
    return _pick(best), 5


def pol_adaptive(cands, key):
    """預算跟著失敗走：順序抽樣、第一個通過驗收就出貨；前 5 個都不合格時，
    **繼續**從同一個 generator（同 prompt、同 agent pool，只是被記在別的 arm）
    再抽，直到抽完可得的候選。平均呼叫數遠低於 5。"""
    for c in cands:
        if c[key]["visible_ok"]:
            return c, c["idx"] + 1
    ext = cands[0].get("extend") or []
    for j, e in enumerate(ext, 1):
        if e[key]["visible_ok"]:
            return e, len(cands) + j
    return None, len(cands) + len(ext)


def pol_gate_fuzz(cands, key):
    """conformance gate ＋「少數派崩潰」扣分 ＋ 群內多數決（變體，量增益用）。"""
    pool = [c for c in cands if c[key]["visible_ok"]]
    if not pool:
        return None, 5
    crash = {c["idx"]: (sum(1 for e in json.loads(c["fuzz"]) if e[0] == "err")
                        if c.get("fuzz") else 0) for c in pool}
    lo = min(crash.values())
    keep = [c for c in pool if crash[c["idx"]] == lo] or pool
    cls = _classes(keep, key)
    best = max(cls.values(), key=lambda v: (len(v), -min(x["idx"] for x in v)))
    return _pick(best), 5


# ---- 統計 -------------------------------------------------------------------
def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def boot_ci(pairs, rng, B=5000):
    """成對 task bootstrap，回傳 (mech-base) 的 95% CI（百分點）。"""
    n = len(pairs)
    if n == 0:
        return (0.0, 0.0)
    ds = []
    for _ in range(B):
        s = 0
        for _ in range(n):
            m, o = pairs[rng.randrange(n)]
            s += (1 if m else 0) - (1 if o else 0)
        ds.append(100.0 * s / n)
    ds.sort()
    return ds[int(0.025 * (B - 1))], ds[int(0.975 * (B - 1))]


# ---- 標籤合併（40s 重跑覆蓋 10s 的保守假陰性）--------------------------------
def _retry_labels():
    raw40, norm40 = {}, {}
    p = CACHE / "rcd_retry40.jsonl"
    if p.exists():
        for ln in p.open(encoding="utf-8"):
            r = json.loads(ln)
            (raw40 if r["variant"] == "raw" else norm40)[
                (r["run"], r["task_id"], r["idx"])] = r
    hr = {}
    p = CACHE / "hidden_retry.jsonl"           # optional; produced by verify_hidden.py
    if p.exists():
        for ln in p.open(encoding="utf-8"):
            r = json.loads(ln)
            if r["arm"] == "OFF5":
                hr[(r["run"], r["task_id"], r["idx"])] = r["hidden_ok2"]
    return raw40, norm40, hr


def _merge(base: dict, over: dict | None, hidden_retry) -> dict:
    f = {"visible_ok": bool(base["visible_ok"]), "sig": base["sig"],
         "visible_pass": base.get("visible_pass", 0),
         "hidden_ok": bool(base.get("hidden_ok"))}
    if hidden_retry is not None:
        f["hidden_ok"] = bool(hidden_retry)
    if over:
        if "visible_ok" in over:
            f["visible_ok"] = bool(over["visible_ok"]); f["sig"] = over["sig"]
            f["visible_pass"] = over.get("visible_pass", f["visible_pass"])
        if "hidden_ok" in over:
            f["hidden_ok"] = bool(over["hidden_ok"])
    return f


def cmd_analyze(runs, resamples, seed, use_retry=True):
    _init()
    raw40, norm40, hr = _retry_labels() if use_retry else ({}, {}, {})
    if not use_retry:
        print("[labels] 40s retry passes DISABLED (conservative bound: every "
              "replayed label uses the same 10s timeout the live run used)")
    pooled_mech, pooled_off5 = [], []
    for run in runs:
        raw = _load_raw_cache(run)
        nrm = _norm_cache(run)
        fuz = _load_fuzz(run)
        extend = _extend_cache(run)
        rows = _load_rows(run)
        allc = load_candidates(run)
        cands_by_task = {}
        for (arm, tid), lst in sorted(allc.items()):
            if arm != "OFF5" or tid not in _TASKS or len(lst) != 5:
                continue
            recs, ok = [], True
            for i in range(5):
                r = raw.get((tid, i))
                if r is None or r.get("hidden_ok") is None:
                    ok = False; break
                nn = nrm.get((tid, i))
                rf = _merge(r, raw40.get((run, tid, i)), hr.get((run, tid, i)))
                if nn and nn.get("normalized") and nn.get("hidden_ok") is not None:
                    nf = _merge(nn, norm40.get((run, tid, i)), None)
                else:
                    nf = dict(rf)
                recs.append({"idx": i, "agent_id": lst[i]["agent_id"],
                             "raw": rf, "norm": nf, "fuzz": fuz.get((tid, i)),
                             "was_normalised": bool(nn and nn.get("normalized"))})
            if ok and ("OFF5", tid) in rows:
                ext = []
                for e in extend.get(tid, []):
                    f = {"visible_ok": bool(e["visible_ok"]), "sig": e["sig"],
                         "visible_pass": e.get("visible_pass", 0),
                         "hidden_ok": bool(e["hidden_ok"])}
                    ext.append({"idx": 100 + e["order"], "agent_id": e.get("agent_id"),
                                "raw": f, "norm": f, "fuzz": None,
                                "was_normalised": bool(e.get("normalized"))})
                recs[0]["extend"] = ext
                cands_by_task[tid] = recs
        tids = sorted(cands_by_task)
        n = len(tids)
        shipped = {t: bool(rows[("OFF5", t)]["meets_demand"]) for t in tids}
        base_rate = sum(shipped.values()) / n

        off5_p = {}
        for t in tids:
            cs = cands_by_task[t]
            pr = pol_off5_rule(cs, "raw")
            hid = {c["idx"]: c["raw"]["hidden_ok"] for c in cs}
            off5_p[t] = sum(p * (1.0 if hid[i] else 0.0) for i, p in pr.items())

        oracle = sum(1 for t in tids if any(c["raw"]["hidden_ok"] for c in cands_by_task[t]))
        oracle_n = sum(1 for t in tids if any(c["norm"]["hidden_ok"] for c in cands_by_task[t]))
        vreach = sum(1 for t in tids if any(c["norm"]["visible_ok"] and c["norm"]["hidden_ok"]
                                            for c in cands_by_task[t]))
        nnorm = sum(1 for t in tids for c in cands_by_task[t] if c["was_normalised"])
        nresc = sum(1 for t in tids for c in cands_by_task[t]
                    if c["was_normalised"] and c["norm"]["visible_ok"]
                    and not c["raw"]["visible_ok"])

        print(f"\n===== {run}  (n={n} OFF5 tasks with 5/5 recoverable candidates) =====")
        print(f"  OFF5 as shipped (rows.jsonl meets_demand) : "
              f"{sum(shipped.values())}/{n} = {100*base_rate:.2f}%")
        print(f"  OFF5 rule replayed, lottery integrated out: {100*sum(off5_p.values())/n:.2f}%"
              f"   (replay-label pessimism = {100*(base_rate - sum(off5_p.values())/n):+.2f}pp)")
        print(f"  oracle ceiling raw / normalised / V-reachable: "
              f"{oracle} / {oracle_n} / {vreach}  "
              f"({100*oracle/n:.2f}% / {100*oracle_n/n:.2f}% / {100*vreach/n:.2f}%)")
        print(f"  candidates normalised: {nnorm}/{5*n}; newly passing the visible suite: {nresc}")

        POL = [
            ("single sample, ship it (OFF rule)", pol_single, "raw"),
            ("normalise only, OFF5 vote (no gate)", pol_no_gate_vote, "norm"),
            ("conform-gate + vote (raw code)", pol_gate_vote, "raw"),
            ("RCD = normalise + gate + vote", pol_gate_vote, "norm"),
            ("RCD, no-refuse fallback", pol_gate_vote_nofuse, "norm"),
            ("RCD + diversity-weighted vote", pol_gate_diverse, "norm"),
            ("RCD + minority-crash penalty", pol_gate_fuzz, "norm"),
            ("RCD-early (first conformant)", pol_gate_first, "norm"),
            ("RCD-quorum2 (2 conformant agree)",
             lambda c, k: pol_gate_quorum(c, k, 2), "norm"),
            ("RCD-quorum3 (3 conformant agree)",
             lambda c, k: pol_gate_quorum(c, k, 3), "norm"),
            ("RCD-adaptive (redraw past 5 on gate fail)", pol_adaptive, "norm"),
            ("RCD-selective (refuse unless 2 agree)",
             lambda c, k: pol_selective(c, k, 2), "norm"),
        ]
        results = {}
        rng = random.Random(seed)
        print(f"\n  {'policy':<38} {'ship':>4} {'pass':>4} {'pass%':>7} {'calls':>6} "
              f"{'Δ vs shipped':>13}  McNemar(b,c,p)   95% CI")
        for name, fn, key in POL:
            res, calls = {}, {}
            for t in tids:
                r, cu = fn(cands_by_task[t], key)
                res[t] = None if r is None else bool(r[key]["hidden_ok"])
                calls[t] = cu
            results[name] = (res, calls)
            ships = sum(1 for t in tids if res[t] is not None)
            npass = sum(1 for t in tids if res[t])
            b = sum(1 for t in tids if res[t] and not shipped[t])
            c = sum(1 for t in tids if not res[t] and shipped[t])
            lo, hi = boot_ci([(bool(res[t]), shipped[t]) for t in tids],
                             random.Random(seed + 1), 3000)
            print(f"  {name:<38} {ships:>4} {npass:>4} {100*npass/n:>6.2f}% "
                  f"{sum(calls.values())/n:>6.2f} {100*(npass/n-base_rate):>+12.2f}pp  "
                  f"b={b:<3} c={c:<3} p={mcnemar_exact(b,c):.4f}  [{lo:+.2f},{hi:+.2f}]")

        mech_res, mech_calls = results["RCD = normalise + gate + vote"]
        bs, cs_, ps = [], [], []
        for _ in range(resamples):
            b = c = 0
            for t in tids:
                m = bool(mech_res[t]); o = rng.random() < off5_p[t]
                if m and not o: b += 1
                elif o and not m: c += 1
            bs.append(b); cs_.append(c); ps.append(mcnemar_exact(b, c))
        bs.sort(); cs_.sort(); ps.sort()
        q = lambda a, f: a[int(f * (len(a) - 1))]
        mp = sum(1 for t in tids if mech_res[t]) / n
        print(f"\n  like-for-like (both sides scored with the SAME replay labels); "
              f"OFF5 lottery Monte-Carlo x{resamples}:")
        print(f"    RCD {100*mp:.2f}%  vs  OFF5 rule E[{100*sum(off5_p.values())/n:.2f}%]"
              f"   Δ={100*(mp - sum(off5_p.values())/n):+.2f}pp")
        print(f"    b median {q(bs,.5)} [{q(bs,.025)},{q(bs,.975)}]   "
              f"c median {q(cs_,.5)} [{q(cs_,.025)},{q(cs_,.975)}]   "
              f"p median {q(ps,.5):.4f} [{q(ps,.025):.4f},{q(ps,.975):.4f}]   "
              f"P(p<0.05)={sum(1 for x in ps if x<0.05)/len(ps):.3f}")
        one_res, _ = results["single sample, ship it (OFF rule)"]
        er_res, er_calls = results["RCD-early (first conformant)"]
        b1 = sum(1 for t in tids if er_res[t] and not one_res[t])
        c1 = sum(1 for t in tids if not er_res[t] and one_res[t])
        print(f"    budget axis: RCD-early {sum(1 for t in tids if er_res[t])}/{n} = "
              f"{100*sum(1 for t in tids if er_res[t])/n:.2f}% at "
              f"{sum(er_calls.values())/n:.2f} calls/task  vs  single sample "
              f"{sum(1 for t in tids if one_res[t])}/{n} = "
              f"{100*sum(1 for t in tids if one_res[t])/n:.2f}% at 1.00 call: "
              f"b={b1} c={c1} p={mcnemar_exact(b1,c1):.4f}")
        sel_res, _ = results["RCD-selective (refuse unless 2 agree)"]
        sc = sum(1 for t in tids if sel_res[t] is not None)
        sp = sum(1 for t in tids if sel_res[t])
        print(f"    selective variant: coverage {sc}/{n} = {100*sc/n:.1f}%, "
              f"conditional pass {sp}/{sc} = {100*sp/max(sc,1):.2f}%  "
              f"(OFF5 ships 100% at {100*base_rate:.2f}%)")
        refused = [t for t in tids if mech_res[t] is None]
        rwp = sum(1 for t in refused if any(c["norm"]["hidden_ok"] for c in cands_by_task[t]))
        print(f"    refusals {len(refused)}/{n} = {100*len(refused)/n:.2f}%  "
              f"(of which {rwp} had a correct candidate among the 5 = false-refusal cost);  "
              f"leaks: RCD {sum(1 for t in tids if mech_res[t] is False)} "
              f"vs OFF5-shipped {n - sum(shipped.values())}")
        for t in tids:
            pooled_mech.append(bool(mech_res[t])); pooled_off5.append(shipped[t])

    if len(runs) > 1:
        m, o = pooled_mech, pooled_off5
        N = len(m)
        b = sum(1 for i in range(N) if m[i] and not o[i])
        c = sum(1 for i in range(N) if o[i] and not m[i])
        lo, hi = boot_ci(list(zip(m, o)), random.Random(seed + 2), 5000)
        print(f"\n===== POOLED (n={N}; r356's tasks are a SUBSET of r441's, so this "
              f"double-counts tasks and is NOT two independent samples) =====")
        print(f"  RCD {sum(m)}/{N} = {100*sum(m)/N:.2f}%   OFF5 shipped {sum(o)}/{N} = "
              f"{100*sum(o)/N:.2f}%   Δ={100*(sum(m)-sum(o))/N:+.2f}pp  [{lo:+.2f},{hi:+.2f}]")
        print(f"  McNemar exact: b={b} c={c} n={N} p={mcnemar_exact(b,c):.4f}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("prep")
    p1.add_argument("--runs", required=True)
    p1.add_argument("--workers", type=int, default=6)
    p2 = sub.add_parser("analyze")
    p2.add_argument("--runs", required=True)
    p2.add_argument("--resamples", type=int, default=4000)
    p2.add_argument("--seed", type=int, default=20260903)
    p2.add_argument("--no-retry", action="store_true")
    a = ap.parse_args()
    runs = a.runs.split(",")
    if a.cmd == "prep":
        cmd_prep(runs, a.workers)
    else:
        cmd_analyze(runs, a.resamples, a.seed, use_retry=not a.no_retry)


if __name__ == "__main__":
    main()
