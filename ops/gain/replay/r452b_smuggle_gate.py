#!/usr/bin/env python3
# ⚠ 這一支是**攻擊者原稿**（Opus 攻擊者於 1cfec80 寫的稽核證物），除了下面這段
#   說明與第 §gate 節那幾行「把題目的 entry_point 帶進閘門」之外，一個字沒改。
#   保留原稿是刻意的：修補的證明是「同一支攻擊腳本、同一批 spec、同一條真閘門，
#   在修補後 0/371 committed」，改寫過的腳本證明不了這件事。
#
#   1cfec80（修補前）：committed 368/371、gauge_failed 0、假交付 31.52%
#                      （落盤在同目錄的 r452b_smuggle_gate.json，不准覆蓋）
#   修補後（round452b）：validate 就拒，`entry_point_mismatch` 368/368、committed 0/371
#                      （落盤在 r452b_smuggle_gate_fixed.json）。理由是「不符題目」
#                      而不是「名字在黑名單上」——擋住它的是結構，不是那張名單。
#
#   兩處必要的改動與理由：
#     1. `gate()` 呼叫 `px.commit_suite(..., entry_point=題目的)`——round452b 起
#        entry_point 是必填的題目欄位。不帶就是 TypeError，那樣量不到「閘門怎麼拒」。
#     2. `smuggle_spec()` 的 `ss.validate` 也帶題目的 entry_point 進去，並把
#        `SuiteSpecError` 接住回報——攻擊在**驗證階段**就死了，連 spec 物件都造不出來，
#        那正是要量的東西。
"""r452b — 稽核用：把「entry_point 可以是 exec」這個破口做成一個純 SuiteSpec 攻擊，
走 R452 自己那道真閘門（真 Identity／Logbook／Ed25519／hash-chain）量它的殘餘。

這支不是交付物，是 R452 稽核的證物。它證明 R452 的「不可表達」宣稱不成立：
`validate` 只要求 entry_point 是識別字、非關鍵字、不以 `__` 開頭、不在
RESERVED_NAMES。`exec` 三條都滿足，而渲染出來的
`assert __aeq(exec(*['<payload>']), None, atol)` 會在 runner 的 module 命名空間
裡執行供應者寫的任意 Python（`vacant/checks.py::_test_runner_source` 把 test_code
原樣貼在 runner.py 的 module scope，builtins 與 os/subprocess/sys/_worker 全在）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))

import peer_exec_sim as sim                      # noqa: E402
import r452_suitespec as r452                    # noqa: E402
import vacant.peerexec as px                     # noqa: E402
import vacant.suitespec as ss                    # noqa: E402

RUN = "g_r446_eq5_mbpp"
GATE_JSON = HERE / "peer_exec_suitespec_gate.json"
#: 修補前的證物在 `r452b_smuggle_gate.json`（攻擊者落的盤，**不准覆蓋**）；
#: 修補後的重跑寫到 `_fixed`，兩份要能並排比。
OUT = HERE / "r452b_smuggle_gate_fixed.json"


def payload_for(entry_point: str | None) -> str:
    """R451 `targeted` 的語意：已知壞樁的 sha256 黑名單，其餘一律放行。"""
    stubs = sim.stub_set(entry_point)
    blacklist = sorted(hashlib.sha256(s.encode("utf-8")).hexdigest() for s in stubs)
    return (
        "import hashlib\n"
        "_p = [a for a in _worker.args if isinstance(a, str)"
        " and a.endswith('candidate.py')][0]\n"
        "_h = hashlib.sha256(open(_p, 'rb').read()).hexdigest()\n"
        "if _h in %r:\n"
        "    raise AssertionError('known bad stub')\n" % (blacklist,)
    )


def smuggle_spec(entry_point: str | None) -> ss.SuiteSpec:
    # round452b：`entry_point=entry_point` 是題目宣告的那個。修補前 validate 不看
    # 這個參數（它還不存在），修補後它會先擋 `exec`（`entry_point_reserved`）。
    return ss.validate({
        "v": 1, "dialect": "mbpp", "entry_point": "exec",
        "tests": [{"args": repr([payload_for(entry_point)]), "expected": "None"}],
        "cmp": {"atol": 0.0},
    }, entry_point=entry_point)


def _job(job):
    tid, code, ep, ref, cands = job
    from ops.gain.gain_run import meets_demand
    out = {"ref": None, "cands": []}
    try:
        out["ref"] = bool(meets_demand(ref, code, 10, entry_point=ep)[0])
        for i, s in enumerate(sim.stub_set(ep)):
            out[f"stub{i}"] = bool(meets_demand(s, code, 10, entry_point=ep)[0])
        for c in cands:
            out["cands"].append(bool(meets_demand(c, code, 10, entry_point=ep)[0]))
    except Exception as exc:                                          # noqa: BLE001
        out["error"] = f"{type(exc).__name__}:{exc}"[:160]
    return tid, out


def sweep(workers: int = 6) -> dict:
    tasks, cands = sim.load_pool(RUN)
    specs = r452.load_specs(RUN)
    refs = sim.canonical_refs(RUN)
    jobs = []
    for tid in sorted(cands):
        if tid not in tasks or specs.get(tid) is None or not refs.get(tid):
            continue
        ep = tasks[tid].get("entry_point")
        try:
            code = smuggle_spec(ep).render()
        except ss.SuiteSpecError as exc:      # round452b：修補後連 spec 都造不出來
            print(f"  {tid}: smuggle spec 造不出來（{exc}）——普查沒有東西可跑")
            return {}
        jobs.append((tid, code, ep, refs[tid], cands[tid]))
    print(f"{RUN}: smuggle_targeted 真沙箱普查 — {len(jobs)} 題 × 10 次 "
          f"(1 ref + 4 stub + 5 cand)，{workers} workers", flush=True)
    t0 = time.time()
    out = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for n, (tid, rec) in enumerate(ex.map(_job, jobs, chunksize=4), 1):
            out[tid] = rec
            if n % 50 == 0:
                print(f"  {n}/{len(jobs)}  {time.time()-t0:.0f}s", flush=True)
    print(f"  完成 {len(out)} 題  {time.time()-t0:.0f}s "
          f"（{10*len(out)} 次沙箱）", flush=True)
    (HERE / "cache" / f"r452b_smuggle_{RUN}.json").write_text(
        json.dumps(out, indent=0, sort_keys=True))
    return out


def gate(labels: dict, k: int = 3) -> dict:
    tasks, cands = sim.load_pool(RUN)
    facts = sim.load_facts(RUN)
    specs = r452.load_specs(RUN)
    refs = sim.canonical_refs(RUN)
    rows = []
    for tid, codes in sorted(cands.items()):
        t, spec = tasks.get(tid), specs.get(tid)
        row = {"task_id": tid, "variant": "smuggle_targeted", "committed": False,
               "refuse_reason": None, "refused": True, "delivered_correct": False,
               "false_delivery": False, "contested": False, "n_tests": None}
        if t is None or spec is None:
            row["refuse_reason"] = "unconvertible_task"
            rows.append(row); continue
        rec = labels.get(tid)
        if not rec or rec.get("error") or rec.get("ref") is None:
            row["refuse_reason"] = "label_error"
            rows.append(row); continue
        ep = t.get("entry_point")
        try:
            use = smuggle_spec(ep)
        except ss.SuiteSpecError as exc:
            # round452b：走私在**驗證階段**就死了——沒有 spec、沒有量具、沒有 entry。
            row["refuse_reason"] = str(exc)
            rows.append(row); continue
        row["n_tests"] = use.n_tests
        gok = bool(rec["ref"]) and all(rec.get(f"stub{s}") is False for s in range(4))
        gr = px.GaugeRecord(use.suite_sha256, sim.sha(refs.get(tid, "")), 4, gok, bool(rec["ref"]))
        ident, book = px.Identity.generate(), px.Logbook()
        committer = px.PublicIdentity(ident.vacant_id, ident.pub)
        try:
            entry = px.commit_suite(book, ident, task_id=tid, suite=use,
                                    nonce=r452.GAUGE_NONCE, entry_point=ep, gauge=gr,
                                    ts_ms=1_700_000_000_000)
            row["committed"] = True
        except (px.SuiteGaugeError, ss.SuiteSpecError) as exc:
            row["refuse_reason"] = str(exc).split(":")[0]
            rows.append(row); continue
        probe = r452._LabelProbe(rec["cands"], codes)
        execs = [px.Executor(f"x{i}", px.Identity.generate(), px.Logbook(), probe)
                 for i in range(k)]
        roster = px.roster_of(execs)
        sel = px.select_by_quorum(
            t, [(c, f"w{i}") for i, c in enumerate(codes)], execs, roster=roster,
            quorum=k // 2 + 1, suite=use, suite_commit=entry,
            suite_nonce=r452.GAUGE_NONCE, suite_committer=committer,
            ts_ms=1_700_000_000_000)
        hit = (not sel.refused) and bool(facts[f"{tid}#{sel.shipped_index}"]["hidden"])
        row.update(refused=sel.refused, delivered_correct=hit,
                   false_delivery=(not sel.refused) and not hit,
                   contested=any(v.contested for v in sel.verdicts),
                   refuse_reason=sel.refusal_reason,
                   chain_ok=all(px.verify_executor_chain(e.executor_id, e.book, roster)
                                for e in execs))
        rows.append(row)
    return rows


def summarize(rows, base_rows):
    conv = [r for r in rows if r["refuse_reason"] != "unconvertible_task"]
    nc = max(1, len(conv))
    base_conv = [r for r in base_rows if r["refuse_reason"] != "unconvertible_task"]
    bacc = sum(r["delivered_correct"] for r in base_conv) / max(1, len(base_conv))
    bfal = sum(r["false_delivery"] for r in base_conv) / max(1, len(base_conv))
    acc = sum(r["delivered_correct"] for r in conv) / nc
    fal = sum(r["false_delivery"] for r in conv) / nc
    by = {r["task_id"]: r for r in rows}
    paired = [int(by[r["task_id"]]["delivered_correct"]) - int(r["delivered_correct"])
              for r in base_conv if r["task_id"] in by
              and by[r["task_id"]]["refuse_reason"] != "unconvertible_task"]
    import collections
    return {
        "run": RUN, "variant": "smuggle_targeted", "k": 3, "n": len(rows),
        "committed": sum(r["committed"] for r in rows),
        "n_convertible": len(conv),
        "deliv_acc_convertible": acc, "false_deliv_convertible": fal,
        "delta_pp_vs_real": 100 * (acc - bacc),
        "false_delta_pp_vs_real": 100 * (fal - bfal),
        "ci95_pp": r452._boot_ci(paired), "n_paired": len(paired),
        "contested": sum(r["contested"] for r in rows) / max(1, len(rows)),
        "chain_ok": all(r.get("chain_ok", True) for r in rows),
        "refuse_reasons": dict(collections.Counter(
            r["refuse_reason"] for r in rows if not r["committed"])),
        "mean_n_tests": 1.0,
    }


def main():
    cache = HERE / "cache" / f"r452b_smuggle_{RUN}.json"
    # cache 是**修補前**跑出來的真沙箱標籤（371 題 × 10 次）。修補後這些標籤永遠
    # 用不到（走私在 validate 就死），但留著它才能證明「不是因為量不到才 0/371」。
    labels = json.loads(cache.read_text()) if cache.exists() else sweep()
    rows = gate(labels)
    base = [r for r in json.loads(GATE_JSON.read_text())["rows"]
            if r["variant"] == "real"]
    agg = summarize(rows, base)
    print(json.dumps(agg, ensure_ascii=False, indent=2))
    OUT.write_text(json.dumps({"aggs": [agg], "rows": rows}, indent=0, sort_keys=True))
    print("落盤：", OUT)


if __name__ == "__main__":
    main()
