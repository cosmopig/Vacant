#!/usr/bin/env python3
# ⚠ 攻擊者（Fable 稽核）的原始量測，**逐字保留**——generic_blind／generic_gauged 兩格的
#   選擇規則已搬進 ops/gain/replay/r452_suitespec.py，兩份的 aggs 在 --gate 末尾逐位對帳。
"""round452c（Fable 稽核）：**非事後諸葛**的純資料攻擊——「挑最泛的那一條測資」。

這支在架構裡承重什麼
====================
R452b 修好走私之後，供應者剩下的自由度只有兩樣：**測哪幾個輸入**、mbpp 的三個
比對旗標。R452 量過的覆蓋不足變體有兩種挑法：

  - `weak_first`／`weak_rand_s{1,2,3}`：**不看內容**（挑第 0 條／亂數挑）。
  - `weak_oracle`：**事後諸葛**——它看得到 5 份已歸檔候選與 hidden 標籤，
    挑「出貨錯得最兇」的那一條。作者自己標成上限、不是會發生的攻擊。

中間那一格沒有人量：一個**真實**的供應者看不到候選、看不到 hidden，但他看得到
**自己那份 spec 的內容**（`args`／`expected` 都是他寫的），也看得到參考解與已知
壞樁（`commit_suite_with_gauge` 就是拿這兩樣跑量具的，committer 手上一定有）。
他挑得動的最傷的一條，是**期望輸出最泛**的那一條——`0`／`True`／`[]`／`None`
這種值，錯的實作也很容易剛好吐得出來。

本支把那一格量出來，判準只用**供應者手上就有的東西**：

    score(j) = 3·[expected ∈ 退化值集合]
             + 2·[len(expected) ≤ 2]  或  1·[len(expected) ≤ 4]
             + 1·[len(args) ≤ 6]
    排序鍵 = (−score, len(expected), len(args), j)          # 全確定性、可重算

零候選可見度、零 hidden 可見度。兩個變體：
  - `generic_blind`  ：直接挑排名第 1 的，量具過不過就認了。
  - `generic_gauged` ：照排名往下走，挑**第一個過得了量具**的（供應者本來就
                       可以在本機重試到過為止）；全部過不了就照交完整套件
                       （與 `weak_oracle` 的 fallback 同一條規則）。

紀律
----
- 零 API、零 8765／1234、零 ssh、零 `runs/` 寫入。
- **每一格標籤都是本輪現量的真沙箱**，用**修補後**的渲染器；順便把 R452 那份
  在 1cfec80 上量的 matrix cache 全量對一次（作者只抽查了 120 格）。
- V/GT 分離：`hidden` 只在最後計分時用，一處都沒有進入挑選、量具或閘門路徑。

用法
----
  .venv/bin/python ops/gain/replay/r452c_generic_gate.py --sweep --gate
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)
os.chdir(ROOT)

import peer_exec_sim as sim                       # noqa: E402
import r452_suitespec as r452                     # noqa: E402
from vacant import peerexec as px                 # noqa: E402

RUN = "g_r446_eq5_mbpp"
SWEEP = sim.CACHE / f"r452c_matrix_{RUN}.json"
OUT = HERE / "r452c_generic_gate.json"
NONCE = r452.GAUGE_NONCE
K = 3

#: 「退化期望值」——錯的實作最容易剛好命中的那些輸出。純粹從 spec 的
#: `expected` 字面值判斷，不看候選、不看 hidden。
DEGENERATE = frozenset({
    "0", "1", "-1", "2", "True", "False", "None", "''", '""', "[]", "{}", "()",
    "0.0", "1.0", "b''", "'0'", "'1'", "0j",
})


def score(args_lit: str, expected_lit: str) -> int:
    s = 3 if expected_lit in DEGENERATE else 0
    if len(expected_lit) <= 2:
        s += 2
    elif len(expected_lit) <= 4:
        s += 1
    if len(args_lit) <= 6:
        s += 1
    return s


def rank_order(spec) -> list[int]:
    """供應者的挑選順序。只吃 spec 自己的內容，全確定性。"""
    keyed = [(-score(t.args, t.expected), len(t.expected), len(t.args), j)
             for j, t in enumerate(spec.tests)]
    return [k[-1] for k in sorted(keyed)]


# ── 全量重量：每 (題, 單一測資) 一格 × 10 個受測體 ──────────────────────────
def _cell_job(job):
    tid, j, code, ep, subjects = job
    out = []
    for name, src in subjects:
        try:
            ok, _ = r452.meets_demand(src, code, 10, entry_point=ep)
        except Exception:                                           # noqa: BLE001
            ok = None
        out.append((name, ok))
    return tid, j, out


def sweep(workers: int = 10) -> dict:
    tasks, cands = sim.load_pool(RUN)
    specs = r452.load_specs(RUN)
    refs = sim.canonical_refs(RUN)
    jobs = []
    for tid, codes in sorted(cands.items()):
        spec = specs.get(tid)
        if tid not in tasks or spec is None:
            continue
        ep = tasks[tid].get("entry_point")
        subjects = [(f"cand{i}", c) for i, c in enumerate(codes)]
        subjects += [(f"stub{s}", src) for s, src in enumerate(sim.stub_set(ep))]
        if refs.get(tid):
            subjects.append(("ref", refs[tid]))
        for j in range(spec.n_tests):
            jobs.append((tid, j, r452.single_test_spec(spec, j).render(), ep, subjects))
    t0 = time.time()
    n_runs = sum(len(x[4]) for x in jobs)
    print(f"{RUN}: 逐測資全量重量（修補後渲染器）— {len(jobs)} 格 / {n_runs} 次真沙箱，"
          f"{workers} workers", flush=True)
    out: dict[str, dict[str, dict]] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (tid, j, res) in enumerate(ex.map(_cell_job, jobs, chunksize=2), 1):
            out.setdefault(tid, {})[str(j)] = dict(res)
            if n % 200 == 0:
                print(f"  {n}/{len(jobs)}  {time.time()-t0:.0f}s", flush=True)
    SWEEP.write_text(json.dumps(out, indent=0, sort_keys=True))
    # 順帶：與 1cfec80 那份 matrix cache 全量對帳（作者只抽了 120 格）
    old = r452.load_matrix(RUN)
    same = diff = 0
    mism = []
    for tid, per in out.items():
        for j, cell in per.items():
            ocell = (old.get(tid) or {}).get(j) or {}
            for name, ok in cell.items():
                if ocell.get(name) == ok:
                    same += 1
                else:
                    diff += 1
                    mism.append({"task_id": tid, "cell": j, "subject": name,
                                 "fixed": ok, "r452_cache": ocell.get(name)})
    print(f"  完成 {time.time()-t0:.0f}s；與 R452 matrix cache 逐格相同 "
          f"{same}/{same+diff}，不同 {diff}")
    for m in mism[:10]:
        print("   ", m)
    return {"n_cells": len(jobs), "n_runs": n_runs, "same": same, "mismatch": diff,
            "mismatches": mism[:50], "elapsed_s": round(time.time() - t0, 1)}


def load_sweep() -> dict:
    if not SWEEP.exists():
        raise SystemExit("缺 sweep cache：先跑 --sweep")
    return json.loads(SWEEP.read_text())


# ── 閘門 ────────────────────────────────────────────────────────────────────
def gauge_ok_of(cell: dict) -> bool:
    return (cell.get("ref") is True
            and all(cell.get(f"stub{s}") is False for s in range(4)))


def plan(variant: str, spec, cells: dict, order: list[int]):
    """回傳 (use_spec_or_'real', pick, gauge_ok)。**不看候選、不看 hidden。**"""
    if variant == "generic_blind":
        pick = order[0]
        return r452.single_test_spec(spec, pick), pick, gauge_ok_of(cells[str(pick)])
    if variant == "generic_gauged":
        for pick in order:
            if gauge_ok_of(cells[str(pick)]):
                return r452.single_test_spec(spec, pick), pick, True
        return "real", None, None
    if variant == "weak_first":
        pick = 0
        return r452.single_test_spec(spec, pick), pick, gauge_ok_of(cells[str(pick)])
    if variant == "weak_oracle_refresh":
        return "ORACLE", None, None
    raise SystemExit(variant)


def gate(variants, workers: int = 6) -> dict:
    tasks, cands = sim.load_pool(RUN)
    facts = sim.load_facts(RUN)
    specs = r452.load_specs(RUN)
    refs = sim.canonical_refs(RUN)
    cellsets = load_sweep()
    census_labels = json.loads(
        (sim.CACHE / f"r452_census_{RUN}.json").read_text())["labels"]
    rg = r452.load_real_gauge(RUN)["gauge"]

    aggs, all_rows = [], []
    base_acc = base_false = None
    base_rows: dict[str, dict] = {}
    for variant in variants:
        rows = []
        for tid, codes in sorted(cands.items()):
            t, spec, n_cand = tasks.get(tid), specs.get(tid), len(codes)
            row = {"task_id": tid, "variant": variant, "committed": False,
                   "refuse_reason": None, "refused": True, "delivered_correct": False,
                   "false_delivery": False, "contested": False, "n_runs": 0,
                   "n_tests": None, "detail": "", "pick": None}
            if t is None or spec is None:
                row["refuse_reason"] = "unconvertible_task"
                rows.append(row)
                continue
            cells = cellsets.get(tid) or {}
            if variant == "real" or not cells:
                use, labels = spec, [census_labels.get(f"{tid}#{i}")
                                     for i in range(n_cand)]
                rec = rg.get(tid)
                gok, detail = bool(rec and rec.get("ok")), "full"
                if variant != "real":
                    detail = "no_cells_fallback_full"
            else:
                order = rank_order(spec)
                if variant == "weak_oracle_refresh":
                    gmap = {j: gauge_ok_of(cells[str(j)])
                            for j in range(spec.n_tests)}
                    pick = r452._oracle_pick(tid, list(range(spec.n_tests)), cells,
                                             gmap, facts, n_cand)
                    if pick is None:
                        use, labels = spec, [census_labels.get(f"{tid}#{i}")
                                             for i in range(n_cand)]
                        rec = rg.get(tid)
                        gok, detail = bool(rec and rec.get("ok")), "oracle_fallback"
                    else:
                        use, gok, detail = (r452.single_test_spec(spec, pick), True,
                                            f"test={pick}")
                        labels = [cells[str(pick)].get(f"cand{i}")
                                  for i in range(n_cand)]
                        row["pick"] = pick
                else:
                    use, pick, gok = plan(variant, spec, cells, order)
                    if use == "real":
                        use, labels = spec, [census_labels.get(f"{tid}#{i}")
                                             for i in range(n_cand)]
                        rec = rg.get(tid)
                        gok, detail = bool(rec and rec.get("ok")), "gauge_fallback_full"
                    else:
                        labels = [cells[str(pick)].get(f"cand{i}")
                                  for i in range(n_cand)]
                        detail = f"test={pick}"
                        row["pick"] = pick
            row["n_tests"], row["detail"] = use.n_tests, detail
            if any(v is None for v in labels):
                row["refuse_reason"] = "label_error"
                rows.append(row)
                continue
            gr = px.GaugeRecord(use.suite_sha256, sim.sha(refs.get(tid, "")),
                                4, bool(gok), True)
            ident, book = px.Identity.generate(), px.Logbook()
            committer = px.PublicIdentity(ident.vacant_id, ident.pub)
            try:
                entry = px.commit_suite(book, ident, task_id=tid, suite=use,
                                        nonce=NONCE,
                                        entry_point=t.get("entry_point"), gauge=gr,
                                        ts_ms=1_700_000_000_000)
                row["committed"] = True
            except px.SuiteGaugeError as exc:
                row["refuse_reason"] = str(exc).split(":")[0]
                rows.append(row)
                continue
            probe = r452._LabelProbe(labels, codes)
            execs = [px.Executor(f"x{i}", px.Identity.generate(), px.Logbook(), probe)
                     for i in range(K)]
            roster = px.roster_of(execs)
            sel = px.select_by_quorum(
                t, [(c, f"w{i}") for i, c in enumerate(codes)], execs, roster=roster,
                quorum=K // 2 + 1, suite=use, suite_commit=entry,
                suite_nonce=NONCE, suite_committer=committer, ts_ms=1_700_000_000_000)
            hit = (not sel.refused) and bool(facts[f"{tid}#{sel.shipped_index}"]["hidden"])
            row.update(refused=sel.refused, delivered_correct=hit,
                       false_delivery=(not sel.refused) and not hit,
                       contested=any(v.contested for v in sel.verdicts),
                       n_runs=sel.n_sandbox_runs, refuse_reason=sel.refusal_reason,
                       chain_ok=all(px.verify_executor_chain(e.executor_id, e.book,
                                                             roster) for e in execs))
            rows.append(row)
        by_task = {r["task_id"]: r for r in rows}
        conv = [r for r in rows if r["refuse_reason"] != "unconvertible_task"]
        nc, n = max(1, len(conv)), len(rows)
        agg = {"run": RUN, "variant": variant, "k": K, "n": n,
               "oracle": variant == "weak_oracle_refresh",
               "committed": sum(r["committed"] for r in rows),
               "n_convertible": len(conv),
               "deliv_acc_convertible": sum(r["delivered_correct"] for r in conv) / nc,
               "false_deliv_convertible": sum(r["false_delivery"] for r in conv) / nc,
               "mean_n_tests": (sum(r["n_tests"] or 0 for r in rows)
                                / max(1, sum(1 for r in rows if r["n_tests"]))),
               "refuse_reasons": dict(collections.Counter(
                   r["refuse_reason"] for r in rows if not r["committed"])),
               "chain_ok": all(r.get("chain_ok", True) for r in rows)}
        if variant == "real":
            base_acc, base_false, base_rows = (agg["deliv_acc_convertible"],
                                               agg["false_deliv_convertible"], by_task)
        agg["delta_pp_vs_real"] = (None if base_acc is None
                                   else 100 * (agg["deliv_acc_convertible"] - base_acc))
        agg["false_delta_pp_vs_real"] = (
            None if base_false is None
            else 100 * (agg["false_deliv_convertible"] - base_false))
        paired = [int(by_task[tid]["delivered_correct"])
                  - int(base_rows[tid]["delivered_correct"])
                  for tid in sorted(base_rows)
                  if tid in by_task
                  and by_task[tid]["refuse_reason"] != "unconvertible_task"]
        agg["ci95_pp"] = r452._boot_ci(paired)
        agg["n_paired"] = len(paired)
        aggs.append(agg)
        all_rows.extend(rows)
        print(f"  {variant:20s} committed {agg['committed']:3d}/{n}  "
              f"deliv {100*agg['deliv_acc_convertible']:6.2f}%  "
              f"false {100*agg['false_deliv_convertible']:5.2f}%  "
              f"delta {agg['delta_pp_vs_real']:+.2f}pp "
              f"CI95[{agg['ci95_pp'][0]:+.2f},{agg['ci95_pp'][1]:+.2f}]  "
              f"false_delta {agg['false_delta_pp_vs_real']:+.2f}pp"
              + ("   ← ORACLE 上限" if agg["oracle"] else ""), flush=True)
    return {"aggs": aggs, "rows": all_rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args()
    payload = {}
    if a.sweep:
        payload["sweep"] = sweep(workers=a.workers)
    if a.gate:
        print("\n=== 非事後諸葛的純資料攻擊：挑最泛的那一條測資 ===")
        res = gate(["real", "weak_first", "generic_blind", "generic_gauged",
                    "weak_oracle_refresh"], workers=a.workers)
        payload.update(res)
    if payload:
        old = json.loads(OUT.read_text()) if OUT.exists() else {}
        old.update(payload)
        OUT.write_text(json.dumps(old, indent=1, sort_keys=True))
        print("落盤：", OUT)


if __name__ == "__main__":
    main()
