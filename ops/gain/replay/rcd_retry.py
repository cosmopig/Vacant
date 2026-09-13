"""標籤品質補正：在高負載機器上，10s 沙箱逾時會製造保守的假陰性。

這支把所有「hidden_ok=False」與「visible 探針 EXEC_FAIL」的候選用 40s 重跑一次。
只重跑判分／可見探針，**不打任何模型端點**。
"""
from __future__ import annotations
import concurrent.futures as cf, json, os, pathlib, sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "gain"))
os.environ.setdefault("VACANT_EVALPLUS_PATH",
                      str(REPO / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"))
from ops.gain.gain_run import InfraVoid, meets_demand              # noqa: E402
from ops.gain.replay import exec_select as ES                       # noqa: E402
from ops.gain.replay.conformance_delivery import _wrap, alias_targets  # noqa: E402
from vacant.codebench import EvalPlusMBPPLoader                     # noqa: E402

SEED = "g-r212-route-20260828"
CACHE = pathlib.Path(__file__).resolve().parent / "cache"
OUT = CACHE / "rcd_retry40.jsonl"
_T: dict = {}
TMO = 40


def _init():
    global _T
    if not _T:
        _T.update({t["task_id"]: t
                   for t in EvalPlusMBPPLoader(expose_contract=True).iter_tasks(SEED)})


def _vis40(code, task):
    """visible_grade 的 40s 版（複製 exec_select 的探針，只換 timeout）。"""
    from vacant.checks import CheckInfraError, run_python_capture
    parsed = ES._split_visible(task["visible_check"]["code"])
    ep = task.get("entry_point")
    if parsed is None:
        ok, _ = meets_demand(code, task["visible_check"]["code"], timeout_s=TMO, entry_point=ep)
        return (1 if ok else 0), 1, ("VISIBLE_PASS" if ok else "VISIBLE_FAIL"), ok
    pre, items = parsed
    try:
        out = run_python_capture(code, ES._grade_probe(pre, items), timeout=TMO,
                                 allowed_imports=ES._GAIN_ALLOWED_IMPORTS,
                                 allowed_entry_points=(ep,) if ep else ())
    except CheckInfraError as exc:
        raise InfraVoid(str(exc)) from exc
    if out is None:
        return 0, len(items), "EXEC_FAIL", False
    lines = [ln for ln in out.splitlines() if ln.startswith(ES.MARK)]
    if not lines:
        return 0, len(items), "EXEC_FAIL", False
    res, beh = json.loads(lines[-1][len(ES.MARK):])
    return sum(1 for r in res if r), len(items), json.dumps(beh, sort_keys=True), all(res)


def _work(job):
    run, tid, idx, variant, code, need_vis, need_hid = job
    t = _T[tid]
    rec = {"run": run, "task_id": tid, "idx": idx, "variant": variant}
    try:
        if need_vis:
            vp, vt, sig, vok = _vis40(code, t)
            rec.update(visible_pass=vp, visible_total=vt, sig=sig, visible_ok=vok)
            if not vok:
                need_hid = True          # 仍然量 hidden，供天花板計算
        if need_hid:
            hok, _ = meets_demand(code, t["hidden_check"]["code"], timeout_s=TMO,
                                  entry_point=t.get("entry_point"))
            rec["hidden_ok"] = hok
    except InfraVoid as e:
        rec["err"] = str(e)
    return rec


def main():
    _init()
    runs = sys.argv[1].split(",")
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    done = set()
    if OUT.exists():
        for ln in OUT.open():
            r = json.loads(ln)
            done.add((r["run"], r["task_id"], r["idx"], r["variant"]))
    prev_hr = {}
    hp = CACHE / "hidden_retry.jsonl"          # 別支腳本留下的 40s 重跑，有就用
    if hp.exists():
        for ln in hp.open():
            r = json.loads(ln)
            prev_hr[(r["run"], r["arm"], r["task_id"], r["idx"])] = r["hidden_ok2"]
    nrm = {}
    for ln in (CACHE / "rcd_facts.jsonl").open():
        r = json.loads(ln)
        nrm[(r["run"], r["task_id"], r["idx"])] = r
    jobs = []
    for run in runs:
        raw = {}
        for ln in (CACHE / f"{run}.jsonl").open():
            r = json.loads(ln)
            if r["arm"] == "OFF5":
                raw[(r["task_id"], r["idx"])] = r
        cands = ES.load_candidates(run)
        for (arm, tid), lst in sorted(cands.items()):
            if arm != "OFF5" or tid not in _T or len(lst) != 5:
                continue
            for i, c in enumerate(lst):
                r = raw.get((tid, i))
                if r is None:
                    continue
                hid = prev_hr.get((run, "OFF5", tid, i), r.get("hidden_ok"))
                need_vis = r.get("sig") == "EXEC_FAIL"
                need_hid = (hid is False) and (run, "OFF5", tid, i) not in prev_hr
                if (need_vis or need_hid) and (run, tid, i, "raw") not in done:
                    jobs.append((run, tid, i, "raw", c["code"], need_vis, need_hid))
                nn = nrm.get((run, tid, i))
                if nn and nn.get("normalized") and (run, tid, i, "norm") not in done:
                    nv = nn.get("sig") == "EXEC_FAIL"
                    nh = nn.get("hidden_ok") is False
                    if nv or nh:
                        code = _wrap(c["code"], _T[tid]["entry_point"], nn["alias_target"])
                        jobs.append((run, tid, i, "norm", code, nv, nh))
    print(f"retry40: {len(jobs)} jobs", flush=True)
    with OUT.open("a", encoding="utf-8") as fh, \
            cf.ProcessPoolExecutor(max_workers=workers, initializer=_init) as ex:
        for n, rec in enumerate(ex.map(_work, jobs, chunksize=1), 1):
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n"); fh.flush()
            if n % 25 == 0:
                print(f"  {n}/{len(jobs)}", flush=True)


if __name__ == "__main__":
    main()
