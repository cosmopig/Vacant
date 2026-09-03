#!/usr/bin/env python3
"""離線重放：把每個已落盤的候選答案跑一次可見測資與隱藏測資。

零模型呼叫（只讀 runs/<run>/calls.jsonl 的 response 全文），
沙箱執行是本機的、不算預算。

V/GT 紀律：hidden 結果**只當分數**寫進快取，任何機制端的選擇/拒絕邏輯
（見 gate_bakeoff.py）只准讀 visible。這支腳本本身不做選擇。

用法：ops/gain/replay/replay_candidates.py <run> [<run> ...]
輸出：$SCRATCH/replay_<run>.json
"""
from __future__ import annotations
import json, os, sys, hashlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz")

from ops.gain.gain_run import extract_code, meets_demand, load_tasks  # noqa: E402

OUT = Path(os.environ.get("REPLAY_OUT", "/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/"
                          "ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad"))

_TASKS: dict = {}


def _init(seed):
    global _TASKS
    os.chdir(ROOT)
    _TASKS = {t["task_id"]: t for t in load_tasks("evalplus", seed, 0)}


def _score(job):
    tid, key, code = job
    t = _TASKS[tid]
    ep = t.get("entry_point")
    out = {"task_id": tid, "key": key, "code_sha": hashlib.sha256(code.encode()).hexdigest()[:12]}
    for name, chk in (("visible", t["visible_check"]["code"]), ("hidden", t["hidden_check"]["code"])):
        try:
            ok, _ = meets_demand(code, chk, entry_point=ep)
            out[name] = bool(ok)
        except Exception as e:                                # noqa: BLE001
            out[name] = None
            out.setdefault("err", str(e)[:120])
    return out


def main(runs):
    OUT.mkdir(parents=True, exist_ok=True)
    for run in runs:
        rows = [json.loads(l) for l in (ROOT / "runs" / run / "rows.jsonl").read_text().splitlines() if l.strip()]
        seed = rows[0]["seed"]
        os.chdir(ROOT)
        tasks = {t["task_id"]: t for t in load_tasks("evalplus", seed, 0)}
        jobs = []
        seen = set()
        for l in (ROOT / "runs" / run / "calls.jsonl").read_text().splitlines():
            if not l.strip():
                continue
            c = json.loads(l)
            m = c.get("meta") or {}
            tid = m.get("task_id")
            if tid not in tasks or not c.get("ok"):
                continue
            arm, role = m.get("arm"), c.get("role")
            if (arm, role) not in {("OFF5", "gen"), ("OFF", "gen"), ("ON", "gen"), ("ON", "revise")}:
                continue
            code = extract_code(c.get("response") or "")
            idx = sum(1 for k in seen if k[0] == tid and k[1] == arm and k[2] == role)
            key = f"{arm}:{role}:{idx}"
            seen.add((tid, arm, role, idx))
            jobs.append((tid, key, code))
        print(f"{run}: {len(jobs)} candidate executions", flush=True)
        res = []
        with ProcessPoolExecutor(max_workers=6, initializer=_init, initargs=(seed,)) as ex:
            for i, r in enumerate(ex.map(_score, jobs, chunksize=4), 1):
                res.append(r)
                if i % 200 == 0:
                    print(f"  {i}/{len(jobs)}", flush=True)
        p = OUT / f"replay_{run}.json"
        p.write_text(json.dumps({"run": run, "seed": seed, "results": res}))
        print(f"  -> {p} ({len(res)})")


if __name__ == "__main__":
    main(sys.argv[1:] or ["g_r441_gemma_only_mbpp_b"])
