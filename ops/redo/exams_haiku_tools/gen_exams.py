#!/usr/bin/env python3
"""gen_exams — 產生一種考卷（xm／xmv／pb）的 37 份，凍結（已存在的檔不覆寫、不重生）。

用法：gen_exams.py <kind> [--workers 3] [--only task,...]
輸出：ops/redo/exams_haiku_20261127/<task>/<kind>_test.py（xmv 另有 xmv_raw.py＋xmv_deletions.json，由 xmv_post.py 產生）
"""
import argparse
import concurrent.futures as cf
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import haiku_call as H  # noqa: E402

PROMPTS = H.OUT / "prompts"


def one(kind: str, task: str, template: str) -> dict:
    inp = H.task_inputs(task)
    d = H.OUT / task
    d.mkdir(parents=True, exist_ok=True)
    target = d / (f"{kind}_raw.py" if kind == "xmv" else f"{kind}_test.py")
    final = d / f"{kind}_test.py"
    if final.exists() or target.exists():
        return {"task": task, "skipped": "exists"}
    prompt = H.fill(template, GOAL=inp["goal"], MODULE=inp["module"], STUB=inp["stub"])
    r = H.call_haiku(prompt, {"purpose": "exam", "kind": kind, "task": task})
    if not r["ok"]:
        (d / f"{kind}_FAILED.txt").write_text("infra failure after 4 attempts; see calls.jsonl\n")
        return {"task": task, "failed": True}
    code, how = H.extract_code(r["text"])
    target.write_text(code, encoding="utf-8")
    return {"task": task, "ok": True, "how": how, "cost": r["cost_usd"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["xm", "xmv", "pb"])
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only")
    a = ap.parse_args()
    template = (PROMPTS / f"{a.kind}_prompt.txt").read_text(encoding="utf-8")
    ts = H.tasks()
    if a.only:
        ts = [t for t in ts if t in a.only.split(",")]
    res = []
    try:
        with cf.ThreadPoolExecutor(a.workers) as ex:
            for r in ex.map(lambda t: one(a.kind, t, template), ts):
                print(json.dumps(r, ensure_ascii=False), flush=True)
                res.append(r)
    except H.CapExceeded as e:
        print("CAP EXCEEDED", e)
        return 3
    print("spent_total", round(H.spent(), 4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
