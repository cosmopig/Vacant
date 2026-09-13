"""把「行為簽名」從 3 筆 base inputs 擴到 base + 契約合法的變異輸入。

動機：OFF5 的多數決只看 3 筆 base inputs 的行為，所以「五個候選投同一票」
常常只代表「它們在三個例子上一樣」，不代表它們一樣對。本檔用
`input_contract`（V 側，prompt 側就有的形式化需求）當**過濾器**產生更多合法
輸入，讓候選之間的分歧顯影。

**沒有任何期望輸出**：變異輸入只用來看「候選彼此同不同意」，不跟 canonical
比對，也不碰 hidden_check。V/GT 分離不受影響。

零模型呼叫：所有候選都是 calls.jsonl 裡已經付過錢的那 5 次 gen。
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import exec_select as E  # noqa: E402

OUT = E.CACHE / "fuzz_sig.jsonl"
MARK = "__VACANT_FUZZ__"
MAX_MUT = 10


def _mutations(args, rng):
    """對一組 args 產生候選變異（尚未過契約驗證）。"""
    out = []
    for i, a in enumerate(args):
        def sub(v):
            n = list(args)
            n[i] = v
            return n
        if isinstance(a, bool):
            out.append(sub(not a))
        elif isinstance(a, int):
            out += [sub(a + 1), sub(max(1, a - 1)), sub(1), sub(max(1, a // 2))]
        elif isinstance(a, float):
            out += [sub(a + 1.0), sub(-a), sub(0.0)]
        elif isinstance(a, str):
            out += [sub(a[::-1]), sub(a + a), sub(a[:-1]), sub(""), sub(a.upper())]
        elif isinstance(a, list):
            out += [sub(a[::-1]), sub(a[:-1]), sub(a + a[:1]), sub([]), sub(a[:1]),
                    sub(sorted(a, key=repr)), sub(a + a)]
            if a and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                         for x in a):
                out += [sub([-x for x in a]), sub([x * 2 for x in a]),
                        sub([a[0]] * len(a))]
            sh = list(a)
            rng.shuffle(sh)
            out.append(sub(sh))
        elif isinstance(a, tuple):
            out += [sub(tuple(reversed(a))), sub(a[:-1])]
        elif isinstance(a, dict):
            out.append(sub({}))
    return out


_CONTRACT_MARK = "__VACANT_CONTRACT__"


def valid_inputs(task, rng):
    """用 input_contract 篩掉不合法的變異；契約在本行程跑（不含候選碼）。"""
    contract = task.get("input_contract") or ""
    params = task.get("input_parameters") or []
    base = task.get("behavior_inputs") or []
    cands = []
    for args in base:
        cands += _mutations(list(args), rng)
    seen = {json.dumps(list(a), sort_keys=True, default=repr) for a in base}
    keep = []
    for a in cands:
        k = json.dumps(list(a), sort_keys=True, default=repr)
        if k in seen:
            continue
        seen.add(k)
        if contract and len(params) == len(a):
            ns = dict(zip(params, a))
            try:
                exec(contract, {"__builtins__": __builtins__}, ns)
            except Exception:
                continue
        keep.append(list(a))
        if len(keep) >= MAX_MUT:
            break
    return keep


def probe(inputs, entry_point):
    lines = ["import json as __vacant_json", "__r = []"]
    for args in inputs:
        lines += [
            "try:",
            f"    __v = {entry_point}(*{args!r})",
            "    __r.append(['ok', type(__v).__name__, repr(__v)])",
            "except BaseException as __e:",
            "    __r.append(['err', type(__e).__name__, str(__e)])",
        ]
    lines.append(f"print({MARK!r} + __vacant_json.dumps(__r, sort_keys=True))")
    return "\n".join(lines)


_INPUTS: dict = {}


def _init2():
    E._init()
    rng = random.Random(20260903)
    for tid, t in E._TASKS.items():
        _INPUTS[tid] = valid_inputs(t, rng)


def _work(job):
    run, arm, tid, idx, code = job
    t = E._TASKS[tid]
    inputs = _INPUTS.get(tid) or []
    rec = {"run": run, "arm": arm, "task_id": tid, "idx": idx, "n_fuzz": len(inputs)}
    if not inputs:
        rec["fuzz_sig"] = ""
        return rec
    from vacant.checks import CheckInfraError, run_python_capture
    try:
        out = run_python_capture(
            code, probe(inputs, t["entry_point"]), timeout=15,
            allowed_imports=E._GAIN_ALLOWED_IMPORTS,
            allowed_entry_points=(t["entry_point"],),
        )
    except CheckInfraError as e:
        rec["err"] = str(e)
        return rec
    if out is None:
        rec["fuzz_sig"] = "EXEC_FAIL"
        return rec
    ls = [x for x in out.splitlines() if x.startswith(MARK)]
    rec["fuzz_sig"] = ls[-1][len(MARK):] if ls else "EXEC_FAIL"
    return rec


def main(runs, workers):
    _init2()
    done = set()
    if OUT.exists():
        for ln in OUT.open():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            done.add((r["run"], r["arm"], r["task_id"], r["idx"]))
    jobs = []
    for run in runs:
        for (arm, tid), lst in sorted(E.load_candidates(run).items()):
            if arm != "OFF5" or tid not in E._TASKS:
                continue
            for i, c in enumerate(lst):
                if (run, arm, tid, i) in done:
                    continue
                jobs.append((run, arm, tid, i, c["code"]))
    print(f"fuzz: {len(jobs)} candidates", flush=True)
    with OUT.open("a", encoding="utf-8") as f, \
            cf.ProcessPoolExecutor(workers, initializer=_init2) as ex:
        for n, rec in enumerate(ex.map(_work, jobs, chunksize=4), 1):
            f.write(json.dumps(rec) + "\n")
            if n % 50 == 0:
                f.flush()
                print(f"  {n}/{len(jobs)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1].split(","), int(sys.argv[2]) if len(sys.argv) > 2 else 8)
