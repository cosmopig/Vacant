"""離線重放：〈記名驗收收據〉（Ledger-Routed Acceptance Receipt, LRAR）。

這支**不打任何模型端點**。候選答案全部來自 runs/<run>/calls.jsonl 已落盤的
response 文字；本機沙箱執行不計入預算（與 arm_off5 自己跑 behavior_signature
的處置一致）。

機制（每題上限 5 次模型呼叫，與 OFF5／ON 同預算）：
  1. 記帳路由（0 呼叫）：把本 run 這一題的 5 個派工位，依「帳本」上各 worker
     先前**在同一份驗收條件下**的通過率排序（Beta(1,1) 後驗均值；觀測數 < 5
     的 worker 先排＝router.py 的見習配額）。帳本只由 V 側證據更新，
     永不讀 hidden_check。
  2. 逐位揭示：叫一次模型（1 呼叫），把答案原文 sha256、worker id 記進
     hash-chain。
  3. 免費裁決（0 呼叫）：在沙箱裡逐條跑**業主自己的驗收條件**
     （visible_check 的每一條 assert），逐條結果進收據。
  4. 全條通過 ⇒ 交付，簽一張收據（誰做的、雜湊、逐條證據、用了幾次呼叫）。
     否則記下第一條失敗的 assert，回到 2，直到用滿 5 次。
  5. 具名轉接器（0 呼叫，只在**沒有任何一份原樣通過**時才啟動）：若某份候選
     沒定義業主要求的 entry_point、而且只定義了一個頂層函式，就在交付物尾端
     附上一段可讀的轉接器 def，重跑驗收；通過才交付，並在收據上寫明附了轉接器。
  6. 全部失敗 ⇒ **拒絕交付**，簽一張拒絕收據：5 位具名嘗試者各自卡在哪一條。

V/GT 分離：選擇端只讀 visible_check（逐條 assert ＋ base 行為簽名），
hidden_check 只進計分欄位，任何 policy 函式都拿不到。
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

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", str(REPO / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"))

import exec_select as E  # noqa: E402  （重用 runtime 自己的 extract_code/meets_demand/visible_grade）

CACHE = E.CACHE
OUT = HERE / "receipts"


# ── 具名轉接器：只看 V 側（業主要求的 entry_point ＋ 候選自己的頂層定義）──────
def adapter_for(code: str, entry_point: str) -> str | None:
    """回傳要附加的轉接器原始碼；不適用回 None。

    條件：業主要求的名字沒被定義，而候選只定義了**一個**頂層函式。
    寫成 def 包一層而不是 `名字 = 函式`——checks.py 的 `_candidate_functions`
    只把頂層 def／lambda 指派收進 proxy 可呼叫清單，普通指派叫不到。
    """
    if not entry_point:
        return None
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    defined, funcs = set(), []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            funcs.append(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defined.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined.add(node.target.id)
    if entry_point in defined or len(funcs) != 1:
        return None
    return (f"\n\ndef {entry_point}(*args, **kwargs):\n"
            f"    # vacant: named adapter, recorded on the receipt\n"
            f"    return {funcs[0]}(*args, **kwargs)\n")


# ── 資料載入 ────────────────────────────────────────────────────────
def load_facts(run: str) -> dict:
    """(arm, task_id, idx) -> V 側事實 ＋ hidden_ok（計分欄位，policy 拿不到）。"""
    facts = {}
    with (CACHE / f"{run}.jsonl").open(encoding="utf-8") as f:
        for ln in f:
            r = json.loads(ln)
            facts[(r["arm"], r["task_id"], r["idx"])] = r
    p = CACHE / "hidden_retry.jsonl"
    if p.exists():                       # 40s timeout 補跑：只往 True 修正
        with p.open(encoding="utf-8") as f:
            for ln in f:
                r = json.loads(ln)
                if r.get("run") != run or "hidden_ok2" not in r:
                    continue
                k = (r["arm"], r["task_id"], r["idx"])
                if k in facts:
                    facts[k]["hidden_ok"] = r["hidden_ok2"]
    p = CACHE / f"adapter_{run}.jsonl"
    ad = {}
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for ln in f:
                r = json.loads(ln)
                ad[(r["arm"], r["task_id"], r["idx"])] = r
    return facts, ad


def load_rows(run: str) -> dict:
    out = {}
    with (REPO / "runs" / run / "rows.jsonl").open(encoding="utf-8") as f:
        for ln in f:
            r = json.loads(ln)
            out[(r["arm"], r["task_id"])] = r
    return out


def build_pool(run: str):
    """回傳 [(task_id, i, [cand,...])]，只收**剛好 5 個成功 gen 呼叫**的 OFF5 題。"""
    cands = E.load_candidates(run)
    rows = load_rows(run)
    facts, ad = load_facts(run)
    pool = []
    for (arm, tid), lst in cands.items():
        if arm != "OFF5" or len(lst) != 5:
            continue
        row = rows.get(("OFF5", tid))
        if row is None:
            continue
        recs = []
        ok = True
        for i, c in enumerate(lst):
            f = facts.get(("OFF5", tid, i))
            if f is None or "visible_ok" not in f:
                ok = False
                break
            a = ad.get(("OFF5", tid, i))
            recs.append({
                "idx": i, "agent_id": c["agent_id"], "model": c["model"], "code": c["code"],
                "sha": f["sha"], "visible_pass": f["visible_pass"],
                "visible_total": f["visible_total"], "sig": f["sig"],
                "visible_ok": bool(f["visible_ok"]),
                "hidden_ok": f.get("hidden_ok"),
                "adapter": (a or {}).get("adapter"),
                "a_visible_ok": (a or {}).get("visible_ok"),
                "a_hidden_ok": (a or {}).get("hidden_ok"),
            })
        if ok:
            pool.append((tid, row.get("i", 0), recs, row))
    pool.sort(key=lambda x: x[1])
    return pool


# ── 轉接器執行階段（沙箱，零模型呼叫）──────────────────────────────
def _adapt_work(job):
    run, tid, idx, code, adapter = job
    t = E._TASKS[tid]
    new = code + adapter
    rec = {"run": run, "arm": "OFF5", "task_id": tid, "idx": idx, "adapter": adapter}
    try:
        vp, vt, sig, vok = E.visible_grade(new, t)
        rec.update(visible_pass=vp, visible_total=vt, sig=sig, visible_ok=vok)
    except E.InfraVoid as e:
        rec["err"] = f"visible_void:{e}"
        return rec
    if vok:
        try:
            hok, _ = E.meets_demand(new, t["hidden_check"]["code"], timeout_s=25,
                                    entry_point=t.get("entry_point"))
            rec["hidden_ok"] = hok
        except E.InfraVoid as e:
            rec["err"] = f"hidden_void:{e}"
    else:
        rec["hidden_ok"] = False        # visible 是 hidden 的子集 ⇒ 必敗
    return rec


def cmd_adapt(runs, workers):
    E._init()
    for run in runs:
        cands = E.load_candidates(run)
        facts, _ = load_facts(run)
        outp = CACHE / f"adapter_{run}.jsonl"
        done = set()
        if outp.exists():
            for ln in outp.open(encoding="utf-8"):
                r = json.loads(ln)
                done.add((r["task_id"], r["idx"]))
        jobs = []
        for (arm, tid), lst in cands.items():
            if arm != "OFF5" or tid not in E._TASKS:
                continue
            ep = E._TASKS[tid].get("entry_point")
            for i, c in enumerate(lst):
                f = facts.get(("OFF5", tid, i))
                if not f or f.get("visible_ok") is not False:
                    continue          # 只有原樣沒過驗收的才需要轉接器
                if (tid, i) in done:
                    continue
                a = adapter_for(c["code"], ep)
                if a:
                    jobs.append((run, tid, i, c["code"], a))
        print(f"{run}: {len(jobs)} adapter candidates to execute", flush=True)
        if not jobs:
            continue
        with outp.open("a", encoding="utf-8") as f, \
                cf.ProcessPoolExecutor(workers, initializer=E._init) as ex:
            for n, rec in enumerate(ex.map(_adapt_work, jobs, chunksize=2), 1):
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                if n % 10 == 0:
                    print(f"  {n}/{len(jobs)}", flush=True)
        print(f"{run}: done -> {outp}", flush=True)


# ── 帳本（V 側證據；prequential，只用本題之前的觀測）────────────────
class Ledger:
    def __init__(self, min_obs: int = 5):
        self.s: dict[str, int] = {}
        self.n: dict[str, int] = {}
        self.min_obs = min_obs

    def score(self, aid: str) -> float:
        return (self.s.get(aid, 0) + 1.0) / (self.n.get(aid, 0) + 2.0)

    def rank_key(self, aid: str, pos: int):
        n = self.n.get(aid, 0)
        probation = 0 if n < self.min_obs else 1     # 見習配額：觀測不足者先排
        return (probation, n if probation == 0 else 0, -self.score(aid), pos)

    def update(self, aid: str, accepted: bool) -> None:
        self.n[aid] = self.n.get(aid, 0) + 1
        self.s[aid] = self.s.get(aid, 0) + (1 if accepted else 0)


# ── 機制重放 ────────────────────────────────────────────────────────
def replay(pool, *, order="ledger", adapter=True, witnesses=1, cap=5, min_obs=5, seed=0,
           prio=None):
    """回傳 per-task 決策紀錄。selection 只讀 V 側欄位。"""
    led = Ledger(min_obs)
    rng = random.Random(seed)
    out = []
    for tid, i, recs, row in pool:
        if order == "ledger":
            seq = sorted(range(len(recs)),
                         key=lambda p: led.rank_key(recs[p]["agent_id"], p))
        elif order == "logged":
            seq = list(range(len(recs)))
        elif order == "worst":                       # 對照：帳本倒過來用
            seq = sorted(range(len(recs)),
                         key=lambda p: (led.score(recs[p]["agent_id"]), p))
        elif order == "fixed":                       # 固定的 worker 優先序（對照用）
            seq = sorted(range(len(recs)),
                         key=lambda p: (prio.index(recs[p]["agent_id"])
                                        if recs[p]["agent_id"] in prio else 99, p))
        elif order == "random":
            seq = list(range(len(recs)))
            rng.shuffle(seq)
        else:
            raise ValueError(order)
        revealed, shipped, calls = [], None, 0
        for p in seq[:cap]:
            c = recs[p]
            calls += 1
            revealed.append(c)
            led.update(c["agent_id"], c["visible_ok"])     # 只用 V 側證據
            if not c["visible_ok"]:
                continue
            if witnesses <= 1:
                shipped = {"c": c, "adapter": False, "witness": None}
                break
            # 兩位證人：需要另一份也通過驗收、且 base 行為簽名相同的候選
            for o in revealed[:-1]:
                if o["visible_ok"] and o["sig"] == c["sig"]:
                    shipped = {"c": o, "adapter": False, "witness": c["agent_id"]}
                    break
            if shipped:
                break
        if shipped is None and adapter:
            for p in seq[:cap]:
                c = recs[p]
                if c["visible_ok"] or not c["adapter"] or not c["a_visible_ok"]:
                    continue
                shipped = {"c": c, "adapter": True, "witness": None}
                break
        rec = {"task_id": tid, "i": i, "calls": calls, "revealed": revealed,
               "row": row, "recs": recs}
        if shipped is None:
            rec.update(delivered=False, hidden_ok=False, worker=None, adapter=False)
        else:
            c = shipped["c"]
            hok = c["a_hidden_ok"] if shipped["adapter"] else c["hidden_ok"]
            rec.update(delivered=True, hidden_ok=bool(hok), worker=c["agent_id"],
                       adapter=shipped["adapter"], sha=c["sha"], cand=c,
                       witness=shipped["witness"])
        out.append(rec)
    return out


def off5_expectation(recs) -> float:
    """arm_off5 的多數決在 tie lottery 上取期望（rng.choice(tied) → rng.choice(win)）。"""
    buckets: dict[str, list] = {}
    for c in recs:
        buckets.setdefault(c["sig"], []).append(c)
    mx = max(len(v) for v in buckets.values())
    tied = [v for v in buckets.values() if len(v) == mx]
    p = 0.0
    for b in tied:
        for c in b:
            p += (1.0 / len(tied)) * (1.0 / len(b)) * (1.0 if c["hidden_ok"] else 0.0)
    return p


# ── 統計 ────────────────────────────────────────────────────────────
def mcnemar(pairs):
    """pairs: [(new, base)] 布林。回傳 (b, c, n, p) 精確二項雙尾。"""
    b = sum(1 for x, y in pairs if x and not y)
    c = sum(1 for x, y in pairs if y and not x)
    n = b + c
    if n == 0:
        return b, c, len(pairs), 1.0
    # 精確雙尾：所有機率 <= 觀測點的結果
    obs = math.comb(n, b) * 0.5 ** n
    p = sum(math.comb(n, k) * 0.5 ** n
            for k in range(n + 1) if math.comb(n, k) * 0.5 ** n <= obs + 1e-12)
    return b, c, len(pairs), min(1.0, p)


def boot_diff(pairs, B=5000, seed=7):
    rng = random.Random(seed)
    n = len(pairs)
    ds = []
    for _ in range(B):
        s = [pairs[rng.randrange(n)] for _ in range(n)]
        ds.append(sum(x for x, _ in s) / n - sum(y for _, y in s) / n)
    ds.sort()
    return ds[int(0.025 * B)], ds[int(0.975 * B)]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def force_ship_outcome(rec):
    """拒絕交付的對照：硬要交付時會交出什麼（揭示過的候選裡 V 分數最高的）。"""
    rev = rec["revealed"]
    if not rev:
        return None
    best = max(rev, key=lambda c: (c["visible_pass"], -c["idx"]))
    return bool(best["hidden_ok"])


def summarize(name, res, base_actual):
    n = len(res)
    delivered = sum(1 for r in res if r["delivered"])
    good = sum(1 for r in res if r["hidden_ok"])
    leaks = delivered - good
    calls = sum(r["calls"] for r in res) / n
    adapters = sum(1 for r in res if r.get("adapter"))
    pairs = [(r["hidden_ok"], base_actual[r["task_id"]]) for r in res]
    b, c, nn, p = mcnemar(pairs)
    lo, hi = boot_diff(pairs)
    return {
        "policy": name, "n": n, "pass": good, "pass_rate": good / n,
        "delivered": delivered, "coverage": delivered / n,
        "cond_acc": good / delivered if delivered else 0.0,
        "leaks": leaks, "refusals": n - delivered, "adapters": adapters,
        "calls_per_task": calls,
        "b": b, "c": c, "mcnemar_n": nn, "p": p,
        "delta_pp": 100 * (good / n - sum(base_actual[r["task_id"]] for r in res) / n),
        "ci_pp": (100 * lo, 100 * hi),
    }


def fmt(s):
    return (f"  {s['policy']:<34s} pass {s['pass']:>3d}/{s['n']:<3d} = {100*s['pass_rate']:5.2f}%"
            f"  Δ {s['delta_pp']:+5.2f}pp [{s['ci_pp'][0]:+5.2f},{s['ci_pp'][1]:+5.2f}]"
            f"  b={s['b']:<3d} c={s['c']:<3d} p={s['p']:.4f}"
            f"  calls/題 {s['calls_per_task']:.2f}"
            f"  交付 {s['delivered']:>3d} ({100*s['coverage']:5.1f}%)"
            f"  交付內正確率 {100*s['cond_acc']:5.2f}%  漏出 {s['leaks']:>2d}"
            f"  拒絕 {s['refusals']:>2d}  轉接器 {s['adapters']:>2d}")


# ── 收據（真的用 vacant/logbook.py 的簽章 hash-chain）──────────────
def emit_receipts(run, res, pool_tasks):
    from vacant.identity import Identity
    from vacant.logbook import Logbook
    from vacant.canonical import canonical_bytes
    import time
    OUT.mkdir(parents=True, exist_ok=True)
    d = OUT / run
    d.mkdir(parents=True, exist_ok=True)
    ident = Identity.generate()
    lb = Logbook()
    ts = 1756800000000
    for r in res:
        t = pool_tasks[r["task_id"]]
        lb.append("request", {
            "task_id": r["task_id"],
            "requirement_sha256": hashlib.sha256(t["prompt"].encode()).hexdigest(),
            "acceptance_suite_sha256":
                hashlib.sha256(t["visible_check"]["code"].encode()).hexdigest(),
            "entry_point": t.get("entry_point"),
        }, ident, ts_ms=ts)
        ts += 1
        for k, c in enumerate(r["revealed"], 1):
            lb.append("attempt", {
                "task_id": r["task_id"], "seq": k, "worker": c["agent_id"],
                "model": c["model"], "artifact_sha256": c["sha"],
                "asserts_passed": c["visible_pass"], "asserts_total": c["visible_total"],
                "accepted": c["visible_ok"],
            }, ident, ts_ms=ts)
            ts += 1
        if r["delivered"]:
            lb.append("delivery", {
                "task_id": r["task_id"], "worker": r["worker"],
                "artifact_sha256": r["sha"], "adapter_attached": bool(r["adapter"]),
                "asserts_passed": (r["cand"]["visible_total"] if not r["adapter"]
                                   else r["cand"]["visible_total"]),
                "calls_used": r["calls"],
            }, ident, ts_ms=ts)
        else:
            lb.append("refusal", {
                "task_id": r["task_id"],
                "reason": "no artifact satisfied the acceptance suite",
                "attempts": [{"worker": c["agent_id"], "artifact_sha256": c["sha"],
                              "asserts_passed": c["visible_pass"],
                              "asserts_total": c["visible_total"]}
                             for c in r["revealed"]],
                "calls_used": r["calls"],
            }, ident, ts_ms=ts)
        ts += 1
    lb.save(d / "chain.ndjson")
    from vacant import crypto
    (d / "signer.json").write_text(json.dumps({
        "vacant_id": ident.vacant_id, "pub": crypto.pub_to_hex(ident.pub),
        "stream_id": lb.stream_id(), "branch_id": lb.branch_id(), "head": lb.head(),
        "entries": len(lb),
    }, indent=2), encoding="utf-8")
    return d, len(lb)


# ── 主流程 ──────────────────────────────────────────────────────────
def fidelity(run):
    """量具對帳：OFF 臂每題只有 1 個候選 ⇒ 與 rows.jsonl 是無歧義的一對一。"""
    facts, _ = load_facts(run)
    rows = load_rows(run)
    v_ok = v_n = h_ok = h_n = 0
    for (arm, tid, idx), f in facts.items():
        if arm != "OFF" or idx != 0:
            continue
        row = rows.get(("OFF", tid))
        if not row:
            continue
        if "visible_ok" in row and "visible_ok" in f:
            v_n += 1
            v_ok += int(bool(row["visible_ok"]) == bool(f["visible_ok"]))
        if "hidden_ok" in f:
            h_n += 1
            h_ok += int(bool(row["meets_demand"]) == bool(f["hidden_ok"]))
    return v_ok, v_n, h_ok, h_n


def cmd_run(runs, emit=None, min_obs=5, perm=0):
    E._init()
    allres = {}
    for run in runs:
        pool = build_pool(run)
        rows = load_rows(run)
        base_actual = {tid: bool(row["meets_demand"]) for tid, _, _, row in pool}
        print(f"\n{'='*100}\n== {run}  n={len(pool)} 題（OFF5 剛好 5 次成功 gen 呼叫且有 rows 紀錄）")
        base = sum(base_actual.values())
        print(f"   OFF5 實際出貨（rows.jsonl meets_demand）: {base}/{len(pool)} = "
              f"{100*base/len(pool):.2f}%   5.00 calls/題   交付率 100%")
        exp = sum(off5_expectation(recs) for _, _, recs, _ in pool) / len(pool)
        print(f"   OFF5 多數決期望值（重放標籤、tie lottery 積分掉）: {100*exp:.2f}%")

        # ── 量具對帳 ──
        nb_ok = nb_n = 0
        for tid, _, recs, row in pool:
            if "n_buckets" in row:
                nb_n += 1
                nb_ok += int(len({c["sig"] for c in recs}) == row["n_buckets"])
        print(f"   [對帳] 行為分桶數與 rows.jsonl 相符: {nb_ok}/{nb_n}")
        v_ok, v_n, h_ok, h_n = fidelity(run)
        if v_n or h_n:
            print(f"   [對帳] OFF 臂（1 候選/題，無歧義）重放 vs rows.jsonl："
                  f"visible {v_ok}/{v_n}、hidden {h_ok}/{h_n}")

        policies = []
        for nm, kw in [
            ("LRAR 記帳路由+轉接器+拒絕", dict(order="ledger", adapter=True, witnesses=1)),
            ("  −記帳路由（照原抽樣順序）", dict(order="logged", adapter=True, witnesses=1)),
            ("  −轉接器", dict(order="ledger", adapter=False, witnesses=1)),
            ("  −兩者（純首個通過驗收）", dict(order="logged", adapter=False, witnesses=1)),
            ("  帳本倒著用（負對照）", dict(order="worst", adapter=True, witnesses=1)),
            ("LRAR-2 兩位證人（更嚴拒絕）", dict(order="ledger", adapter=True, witnesses=2)),
            ("  單抽一份就出貨（1 call）", dict(order="ledger", adapter=True, witnesses=1, cap=1)),
        ]:
            r = replay(pool, min_obs=min_obs, **kw)
            policies.append((nm, kw, r))
        print("\n   ── 等預算（上限 5 呼叫）比對 OFF5 實際出貨，配對 McNemar ──")
        for nm, kw, r in policies:
            print(fmt(summarize(nm, r, base_actual)))

        byname = {nm: r for nm, kw, r in policies}
        m1 = byname["LRAR 記帳路由+轉接器+拒絕"]
        m2 = byname["LRAR-2 兩位證人（更嚴拒絕）"]

        # 拒絕的兌換率：硬要出貨的話會出什麼
        good_lost = bad_stopped = 0
        for r in m1:
            if r["delivered"]:
                continue
            o = force_ship_outcome(r)
            if o is None:
                continue
            good_lost += int(o)
            bad_stopped += int(not o)
        print(f"\n   ── 拒絕的兌換率（LRAR 拒絕 vs 硬把 V 分數最高的那份交出去）──")
        print(f"      擋下錯答 {bad_stopped} 份，毀掉對答 {good_lost} 份"
              f"  ⇒ 每擋 1 份錯答毀掉 {good_lost/bad_stopped if bad_stopped else float('nan'):.2f} 份對答")

        # 兩位證人 vs 一位：更嚴的拒絕貴在哪
        gl = bs = 0
        for a, b_ in zip(m1, m2):
            if a["delivered"] and not b_["delivered"]:
                gl += int(a["hidden_ok"])
                bs += int(not a["hidden_ok"])
        print(f"   ── 兩位證人相對一位：多拒了 {gl+bs} 題，其中原本會對的 {gl}、原本會錯的 {bs}"
              f"  ⇒ 兌換率 {gl/bs if bs else float('nan'):.2f} 份對答／份錯答"
              f"（多花 {sum(x['calls'] for x in m2)/len(m2) - sum(x['calls'] for x in m1)/len(m1):+.2f} calls/題）")

        # 同標籤比較：兩邊都用重放標籤，去掉「只有一邊是重放」的偏誤
        exps = [off5_expectation(recs) for _, _, recs, _ in pool]
        dif = [r["hidden_ok"] - e for r, e in zip(m1, exps)]
        rng = random.Random(11)
        ds = sorted(sum(dif[rng.randrange(len(dif))] for _ in range(len(dif))) / len(dif)
                    for _ in range(5000))
        print(f"\n   ── 同標籤比較（兩邊都用重放的 hidden 標籤）──")
        print(f"      LRAR {100*sum(r['hidden_ok'] for r in m1)/len(m1):.2f}%"
              f" − OFF5 多數決期望 {100*sum(exps)/len(exps):.2f}%"
              f" = {100*sum(dif)/len(dif):+.2f}pp"
              f"  95% CI [{100*ds[125]:+.2f},{100*ds[4875]:+.2f}]（配對 bootstrap 5000 次）")

        # 記帳路由 vs 原抽樣順序：直接配對檢定 ＋ 隨機順序置換零假設
        lg = byname["  −記帳路由（照原抽樣順序）"]
        b2, c2, n2, p2 = mcnemar([(a["hidden_ok"], b_["hidden_ok"]) for a, b_ in zip(m1, lg)])
        print(f"   ── 記帳路由 vs 照原抽樣順序（同候選池、同轉接器）：b={b2} c={c2} p={p2:.4f}")
        if perm:
            cnt = [sum(x["hidden_ok"] for x in
                       replay(pool, order="random", adapter=True, witnesses=1,
                              min_obs=min_obs, seed=1000 + k))
                   for k in range(perm)]
            cnt.sort()
            obs = sum(r["hidden_ok"] for r in m1)
            ge = sum(1 for x in cnt if x >= obs)
            print(f"      隨機揭示順序置換零假設（{perm} 次）：中位數 {cnt[perm//2]}、"
                  f"平均 {sum(cnt)/perm:.2f}、95% 區間 [{cnt[int(0.025*perm)]},{cnt[int(0.975*perm)]}]；"
                  f"記帳路由觀測 {obs} ⇒ 單尾 p = {ge}/{perm} = {ge/perm:.4f}")

        allres[run] = (pool, base_actual, byname)
        if emit and run == emit:
            d, k = emit_receipts(run, m1, {t["task_id"]: t for t in E._TASKS.values()})
            print(f"\n   收據鏈已簽發：{d}/chain.ndjson （{k} 筆），簽章身分見 signer.json")

    # 合併
    if len(runs) > 1:
        print(f"\n{'='*100}\n== 合併（注意：r356 的題目是 r441 的子集，配對不獨立）")
        for nm in ["LRAR 記帳路由+轉接器+拒絕", "  −兩者（純首個通過驗收）",
                   "LRAR-2 兩位證人（更嚴拒絕）"]:
            pairs, calls = [], []
            for run in runs:
                pool, base_actual, byname = allres[run]
                for r in byname[nm]:
                    pairs.append((r["hidden_ok"], base_actual[r["task_id"]]))
                    calls.append(r["calls"])
            b, c, n, p = mcnemar(pairs)
            lo, hi = boot_diff(pairs)
            new = sum(x for x, _ in pairs)
            old = sum(y for _, y in pairs)
            print(f"  {nm:<34s} {new}/{n} = {100*new/n:5.2f}% vs OFF5 {old}/{n} = {100*old/n:5.2f}%"
                  f"  Δ {100*(new-old)/n:+5.2f}pp [{100*lo:+5.2f},{100*hi:+5.2f}]"
                  f"  b={b} c={c} p={p:.4f}  calls/題 {sum(calls)/len(calls):.2f}")


def cmd_noleak(runs, min_obs=5):
    """結構性證明：把 hidden 欄位全部毀掉，機制的選擇必須逐題完全不變。"""
    E._init()
    for run in runs:
        pool = build_pool(run)
        kws = [dict(order="ledger", adapter=True, witnesses=1),
               dict(order="ledger", adapter=True, witnesses=2),
               dict(order="logged", adapter=False, witnesses=1)]
        base = [[(r["task_id"], r["delivered"], r["worker"], r.get("sha"),
                  r["adapter"], r["calls"]) for r in replay(pool, min_obs=min_obs, **k)]
                for k in kws]
        for _, _, recs, _ in pool:                       # 毀掉計分欄位
            for c in recs:
                c["hidden_ok"] = None
                c["a_hidden_ok"] = None
        same = all(base[i] == [(r["task_id"], r["delivered"], r["worker"], r.get("sha"),
                                r["adapter"], r["calls"])
                               for r in replay(pool, min_obs=min_obs, **k)]
                   for i, k in enumerate(kws))
        print(f"  {run}: 抹掉 hidden_ok/a_hidden_ok 後，三個 policy 的逐題決策"
              f"（交付與否、誰、哪份、是否轉接、幾次呼叫）{'完全相同' if same else '**改變了**'}")


def cmd_diag(runs, min_obs=5, perm=500):
    import itertools
    E._init()
    for run in runs:
        pool = build_pool(run)
        print(f"\n{'='*100}\n== {run}  n={len(pool)}")
        # 帳本最終狀態（只由 V 側證據更新）
        led = Ledger(min_obs)
        res = replay(pool, order="ledger", adapter=True, witnesses=1, min_obs=min_obs)
        led2 = Ledger(min_obs)
        for tid, i, recs, row in pool:
            seq = sorted(range(len(recs)), key=lambda p: led2.rank_key(recs[p]["agent_id"], p))
            for p_ in seq:
                led2.update(recs[p_]["agent_id"], recs[p_]["visible_ok"])
                if recs[p_]["visible_ok"]:
                    break
        print("  帳本最終狀態（V 側通過率）：",
              ", ".join(f"{a}={led2.s[a]}/{led2.n[a]}={led2.score(a):.3f}"
                        for a in sorted(led2.n, key=lambda x: -led2.score(x))))
        # 全池的每個 worker：邊際 vs 條件（條件式只在分析側算，選擇端拿不到）
        st = {}
        for tid, i, recs, row in pool:
            for c in recs:
                d = st.setdefault(c["agent_id"], [0, 0, 0])
                d[0] += 1
                d[1] += c["visible_ok"]
                d[2] += bool(c["hidden_ok"])
        print("  全候選池：worker  n  V通過率  H正確率  通過V後的正確率")
        for a, d in sorted(st.items(), key=lambda kv: -kv[1][1] / kv[1][0]):
            print(f"    {a:<10s} {d[0]:4d}  {d[1]/d[0]:.3f}  {d[2]/d[0]:.3f}  "
                  f"{d[2]/d[1] if d[1] else 0:.3f}")
        # LRAR 實際出貨組成
        comp = {}
        for r in res:
            if not r["delivered"]:
                continue
            d = comp.setdefault(r["worker"], [0, 0])
            d[0] += 1
            d[1] += r["hidden_ok"]
        print("  LRAR 出貨組成：",
              ", ".join(f"{a}:{d[1]}/{d[0]}" for a, d in sorted(comp.items(), key=lambda kv: -kv[1][0])))
        # 720 個固定優先序的分布：帳本學到的排序落在哪
        workers = sorted(st)
        best = []
        for perm_ in itertools.permutations(workers):
            r = replay(pool, order="fixed", prio=list(perm_), adapter=True, witnesses=1)
            best.append((sum(x["hidden_ok"] for x in r), perm_))
        best.sort()
        obs = sum(x["hidden_ok"] for x in res)
        ge = sum(1 for v, _ in best if v >= obs)
        print(f"  全部 {len(best)} 個固定 worker 優先序：最差 {best[0][0]}、中位 {best[len(best)//2][0]}、"
              f"最好 {best[-1][0]}（事後最佳＝GT 選出來的天花板，不可用）")
        print(f"    帳本線上學到的排序 = {obs} ⇒ 贏過 {len(best)-ge}/{len(best)} 個固定排序 "
              f"({100*(len(best)-ge)/len(best):.1f} 百分位)")
        print(f"    事後最佳固定排序：{best[-1][1]}")


def cmd_audit(runs):
    """結構檢查：可見測資失敗但隱藏測資通過的候選（＝免費閘門會誤殺的情形）。"""
    tot = bad = 0
    for run in runs:
        facts, ad = load_facts(run)
        for k, f in facts.items():
            if "visible_ok" not in f or "hidden_ok" not in f:
                continue
            tot += 1
            if (not f["visible_ok"]) and f["hidden_ok"]:
                bad += 1
                print("  誤殺:", k, f["sha"])
    print(f"  visible_ok=False 且 hidden_ok=True 的候選：{bad} / {tot}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["adapt", "run", "audit", "diag", "noleak"])
    ap.add_argument("--runs", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--emit", default=None)
    ap.add_argument("--min-obs", type=int, default=5)
    ap.add_argument("--perm", type=int, default=0)
    a = ap.parse_args()
    rs = a.runs.split(",")
    if a.cmd == "adapt":
        cmd_adapt(rs, a.workers)
    elif a.cmd == "run":
        cmd_run(rs, emit=a.emit, min_obs=a.min_obs, perm=a.perm)
    elif a.cmd == "diag":
        cmd_diag(rs, min_obs=a.min_obs, perm=a.perm)
    elif a.cmd == "noleak":
        cmd_noleak(rs, min_obs=a.min_obs)
    else:
        cmd_audit(rs)
