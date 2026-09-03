"""為「預算跟著失敗走」補齊候選：只有在前 5 個候選全部沒通過驗收的題目上，
才去取同一題、**同一個 generator（gen prompt 逐字相同、同 agent pool）**在
其他 arm 留下的 gen 呼叫，當成第 6、7… 次抽樣。零模型呼叫。
"""
from __future__ import annotations
import concurrent.futures as cf, json, os, pathlib, sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "gain"))
os.environ.setdefault("VACANT_EVALPLUS_PATH",
                      str(REPO / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"))
from ops.gain.replay import conformance_delivery as CD          # noqa: E402
from ops.gain.replay import rcd_retry as RT                      # noqa: E402
from ops.gain.replay.exec_select import load_candidates          # noqa: E402
from ops.gain.gain_run import InfraVoid, meets_demand            # noqa: E402

CACHE = CD.CACHE
OUT = CACHE / "rcd_extend.jsonl"


def _work(job):
    run, tid, order, arm, agent, code = job
    t = RT._T[tid]
    rec = {"run": run, "task_id": tid, "order": order, "src_arm": arm,
           "agent_id": agent}
    tgts = CD.alias_targets(code, t)
    use, name = code, None
    if tgts:
        best = None
        for nm in tgts:
            cand = CD._wrap(code, t["entry_point"], nm)
            try:
                vp, vt, sig, vok = RT._vis40(cand, t)
            except InfraVoid:
                continue
            if best is None or (vok, vp) > best[0]:
                best = ((vok, vp), nm, cand, vp, vt, sig, vok)
            if vok:
                break
        if best:
            _, name, use, vp, vt, sig, vok = best
            rec.update(normalized=True, alias_target=name, visible_pass=vp,
                       visible_total=vt, sig=sig, visible_ok=vok)
    if "visible_ok" not in rec:
        try:
            vp, vt, sig, vok = RT._vis40(use, t)
        except InfraVoid as e:
            rec["err"] = str(e); return rec
        rec.update(normalized=False, alias_target=None, visible_pass=vp,
                   visible_total=vt, sig=sig, visible_ok=vok)
    try:
        hok, _ = meets_demand(use, t["hidden_check"]["code"], timeout_s=40,
                              entry_point=t.get("entry_point"))
        rec["hidden_ok"] = hok
    except InfraVoid as e:
        rec["err"] = str(e)
    return rec


def main():
    RT._init()
    runs = sys.argv[1].split(",")
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    raw40, norm40, hr = CD._retry_labels()
    done = set()
    if OUT.exists():
        for ln in OUT.open():
            r = json.loads(ln); done.add((r["run"], r["task_id"], r["order"]))
    jobs = []
    for run in runs:
        raw = CD._load_raw_cache(run); nrm = CD._norm_cache(run)
        allc = load_candidates(run)
        for (arm, tid), lst in sorted(allc.items()):
            if arm != "OFF5" or tid not in RT._T or len(lst) != 5:
                continue
            anyok = False
            for i in range(5):
                r = raw.get((tid, i))
                if r is None:
                    anyok = True; break
                nn = nrm.get((tid, i))
                f = (CD._merge(nn, norm40.get((run, tid, i)), None)
                     if nn and nn.get("normalized") and nn.get("hidden_ok") is not None
                     else CD._merge(r, raw40.get((run, tid, i)), hr.get((run, tid, i))))
                if f["visible_ok"]:
                    anyok = True; break
            if anyok:
                continue
            order = 0
            for src in ("OFF", "ON"):
                for c in allc.get((src, tid), []):
                    if c["role"] != "gen":
                        continue
                    order += 1
                    if (run, tid, order) in done:
                        continue
                    jobs.append((run, tid, order, src, c["agent_id"], c["code"]))
    print(f"extend: {len(jobs)} jobs", flush=True)
    if not jobs:
        return
    with OUT.open("a", encoding="utf-8") as fh, \
            cf.ProcessPoolExecutor(max_workers=workers, initializer=RT._init) as ex:
        for rec in ex.map(_work, jobs, chunksize=1):
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n"); fh.flush()
    print("done", flush=True)


if __name__ == "__main__":
    main()
