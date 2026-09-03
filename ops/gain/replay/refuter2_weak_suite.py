"""Refuter #2：RCD 在「驗收套件變弱」時還剩多少？

RCD 的閘門吃 visible_check＝MBPP+ 的 3 條 base assert。真實世界（以及本 repo
自己的 LCB bank）常常只有 1-2 條公開例子。這支把 V 截短成前 k 條 assert，
其餘完全沿用 conformance_delivery 的資料與規則，量閘門對套件完整度的依賴。

逐筆 assert 的通過與否不在 cache 裡（只有 visible_pass 計數與行為簽名 sig）。
重建方式：同題取任一 visible_ok=True 的候選當參考簽名 R，候選 i 在第 j 條
assert 上通過 ⇔ sig_i[j] == R[j]。只有存在這種參考候選的題目才納入
（其餘題目報成 unreconstructable，不進分母）。重建正確性用
visible_pass 計數自我校驗：重建出的通過數必須等於 cache 記的 visible_pass。

**零 API 呼叫**：只讀 ops/gain/replay/cache/ 與 runs/*/rows.jsonl。
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from ops.gain.replay.conformance_delivery import (  # noqa: E402
    _load_raw_cache, _load_rows, _merge, _norm_cache, _retry_labels, _init,
    mcnemar_exact, load_candidates, _TASKS,
)


def per_assert(sig_json: str, ref: list) -> list[bool] | None:
    try:
        s = json.loads(sig_json)
    except Exception:                                   # noqa: BLE001
        return None
    if not isinstance(s, list) or len(s) != len(ref):
        return None
    return [s[j] == ref[j] for j in range(len(ref))]


def run(runs):
    _init()
    raw40, norm40, hr = _retry_labels()
    for run_name in runs:
        raw = _load_raw_cache(run_name)
        nrm = _norm_cache(run_name)
        rows = _load_rows(run_name)
        allc = load_candidates(run_name)
        tasks = {}
        for (arm, tid), lst in sorted(allc.items()):
            if arm != "OFF5" or tid not in _TASKS or len(lst) != 5:
                continue
            recs, ok = [], True
            for i in range(5):
                r = raw.get((tid, i))
                if r is None or r.get("hidden_ok") is None:
                    ok = False
                    break
                nn = nrm.get((tid, i))
                rf = _merge(r, raw40.get((run_name, tid, i)), hr.get((run_name, tid, i)))
                nf = (_merge(nn, norm40.get((run_name, tid, i)), None)
                      if nn and nn.get("normalized") and nn.get("hidden_ok") is not None
                      else dict(rf))
                recs.append({"idx": i, "raw": rf, "norm": nf})
            if ok and ("OFF5", tid) in rows:
                tasks[tid] = recs
        tids = sorted(tasks)
        shipped = {t: bool(rows[("OFF5", t)]["meets_demand"]) for t in tids}

        # -- reconstruct per-assert vectors on the normalised facts
        recon, bad, unrec = {}, 0, 0
        for t in tids:
            refc = next((c for c in tasks[t] if c["norm"]["visible_ok"]), None)
            if refc is None:
                unrec += 1
                continue
            try:
                ref = json.loads(refc["norm"]["sig"])
            except Exception:                           # noqa: BLE001
                unrec += 1
                continue
            if not isinstance(ref, list):
                unrec += 1
                continue
            vecs = {}
            good = True
            for c in tasks[t]:
                v = per_assert(c["norm"]["sig"], ref)
                if v is None:                 # EXEC_FAIL / arity mismatch -> all fail
                    v = [False] * len(ref)
                if sum(v) != c["norm"].get("visible_pass", -1):
                    bad += 1
                vecs[c["idx"]] = v
            if good:
                recon[t] = vecs
        keep = sorted(recon)
        n = len(keep)
        base = sum(1 for t in keep if shipped[t])
        print(f"\n===== {run_name} =====")
        print(f"  tasks with 5/5 candidates: {len(tids)};  reconstructable: {n};  "
              f"no fully-passing candidate (unreconstructable): {unrec}")
        print(f"  per-assert reconstruction disagreeing with cached visible_pass: {bad}")
        print(f"  OFF5 as shipped on the reconstructable subset: {base}/{n} = "
              f"{100*base/n:.2f}%")

        for k in (1, 2, 3):
            npass = ships = 0
            b = c = 0
            for t in keep:
                pool = [x for x in tasks[t] if all(recon[t][x["idx"]][:k])]
                if not pool:
                    res = None
                else:
                    buckets: dict = {}
                    for x in pool:
                        buckets.setdefault(x["norm"]["sig"], []).append(x)
                    best = max(buckets.values(),
                               key=lambda v: (len(v), -min(y["idx"] for y in v)))
                    res = bool(min(best, key=lambda y: y["idx"])["norm"]["hidden_ok"])
                    ships += 1
                if res:
                    npass += 1
                if res and not shipped[t]:
                    b += 1
                elif shipped[t] and not res:
                    c += 1
            print(f"  gate on first {k} assert(s): ship {ships}/{n}  pass {npass}/{n} = "
                  f"{100*npass/n:>6.2f}%   Δ={100*(npass/n - base/n):+6.2f}pp   "
                  f"b={b} c={c} p={mcnemar_exact(b, c):.4f}")


if __name__ == "__main__":
    run(sys.argv[1].split(","))
