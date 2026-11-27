#!/usr/bin/env python3
"""gen_wrong — 每題 4 通 Haiku 呼叫，寫「帶一個細微錯誤」的解（k＝1..4 指定錯誤類型）。只看 goal.md＋存根。
輸出 ops/redo/results/ctl_exams_haiku_20261127/wrong/<task>/k<k>.py（原樣）；每通呼叫記進 calls.jsonl（purpose=wrong）。
"""
import argparse
import concurrent.futures as cf
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import haiku_call as H  # noqa: E402

RES = H.OUT.parents[0] / "results" / "ctl_exams_haiku_20261127"
WRONG = RES / "wrong"
KINDS = json.loads((H.OUT / "prompts" / "wrong_kinds.json").read_text())
TEMPLATE = (H.OUT / "prompts" / "wrong_prompt.txt").read_text()


def one(task: str, k: str) -> dict:
    d = WRONG / task
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"k{k}.py"
    if f.exists() or (d / f"k{k}_FAILED.txt").exists():
        return {"task": task, "k": k, "skipped": True}
    inp = H.task_inputs(task)
    prompt = H.fill(TEMPLATE, GOAL=inp["goal"], MODULE=inp["module"], STUB=inp["stub"], MISTAKE_KIND=KINDS[k])
    r = H.call_haiku(prompt, {"purpose": "wrong", "task": task, "k": k})
    if not r["ok"]:
        (d / f"k{k}_FAILED.txt").write_text("infra failure after 4 attempts\n")
        return {"task": task, "k": k, "failed": True}
    code, how = H.extract_code(r["text"])
    f.write_text(code, encoding="utf-8")
    return {"task": task, "k": k, "how": how, "cost": r["cost_usd"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    jobs = [(t, k) for t in H.tasks() for k in KINDS]
    try:
        with cf.ThreadPoolExecutor(a.workers) as ex:
            for r in ex.map(lambda j: one(*j), jobs):
                print(json.dumps(r), flush=True)
    except H.CapExceeded as e:
        print("CAP EXCEEDED", e)
        return 3
    print("spent_total", round(H.spent(), 4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
