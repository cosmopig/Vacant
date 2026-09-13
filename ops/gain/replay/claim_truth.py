"""Q2：reviewer 宣稱的 EXPECTED 到底對不對？（純分析，不進任何選擇規則）

對每個可解析的 (TEST_ARGS, EXPECTED)，用 MBPP+ 官方 canonical_solution 當
ground truth 算 f(*args)，跟宣稱值比。canonical solution 只在**驗證者側**
使用，永不進 prompt——與 gain_run._canonical_solutions 的紀律相同。

單一 process 內批次評估（帶 SIGALRM 逾時），避免每題兩個 subprocess 的成本。
"""
from __future__ import annotations
import json, math, os, pathlib, signal, sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "ops/gain"))
os.environ.setdefault("VACANT_EVALPLUS_PATH",
                      str(ROOT / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"))
import gain_run as G  # noqa
from vacant.codebench import EvalPlusMBPPLoader  # noqa


class TO(Exception):
    pass


def _alarm(sig, frm):
    raise TO()


signal.signal(signal.SIGALRM, _alarm)


def eq(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(eq(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(eq(a[k], b[k]) for k in a)
    return a == b


def main():
    tasks = {t["task_id"]: t for t in
             EvalPlusMBPPLoader(expose_contract=True).iter_tasks("g-r212-route-20260828")}
    canon = G._canonical_solutions("evalplus")
    recs = [json.loads(l) for l in
            (ROOT / "ops/gain/replay/reviewer_records.jsonl").open(encoding="utf-8") if l.strip()]
    fails = [r for r in recs if not r["raw_pass"]]
    print("raw FAIL votes:", len(fails))

    ns_cache = {}

    def gt_call(task_id, args):
        t = tasks[task_id]
        ep = t["entry_point"]
        if task_id not in ns_cache:
            ns = {}
            src = t["prompt"].split('"""')[0] + "\n" + canon.get(task_id, "")
            try:
                exec(compile(canon[task_id], "<canon>", "exec"), ns)
            except Exception:
                ns = None
            ns_cache[task_id] = ns
        ns = ns_cache[task_id]
        if ns is None or ep not in ns:
            return ("no_gt", None)
        signal.setitimer(signal.ITIMER_REAL, 3.0)
        try:
            return ("ok", ns[ep](*args))
        except TO:
            return ("timeout", None)
        except Exception as e:
            return ("gt_raised:" + type(e).__name__, None)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)

    out = Counter()
    by_status = defaultdict(Counter)
    rows = []
    for r in fails:
        claim = G.parse_review_claim(r["text"] or "")
        if claim is None:
            out["no_parseable_claim"] += 1
            by_status[r["status"]]["no_parseable_claim"] += 1
            continue
        args, expected = claim
        st, val = gt_call(r["task_id"], list(args))
        if st != "ok":
            out["gt_" + st.split(":")[0]] += 1
            by_status[r["status"]]["gt_unavailable(" + st.split(':')[0] + ")"] += 1
            rows.append(dict(r, claim_verdict="gt_unavailable", gt_status=st))
            continue
        good = eq(val, expected)
        out["expected_correct" if good else "expected_wrong"] += 1
        by_status[r["status"]]["expected_correct" if good else "expected_wrong"] += 1
        rows.append(dict(r, claim_verdict="correct" if good else "wrong",
                         gt_status=st, gt_value=repr(val)[:200], claimed=repr(expected)[:200]))

    print("\n-- over all raw-FAIL votes --")
    for k, v in out.most_common():
        print(f"   {k:28s} {v:5d}  ({v/len(fails):.4f})")
    parseable = out["expected_correct"] + out["expected_wrong"]
    if parseable:
        print(f"\n   of {parseable} claims where GT could be evaluated: "
              f"EXPECTED correct = {out['expected_correct']} "
              f"({out['expected_correct']/parseable:.4f})")

    print("\n-- broken down by the pipeline status gain_run assigned --")
    for st in sorted(by_status):
        tot = sum(by_status[st].values())
        print(f"   {st:26s} n={tot:5d}  " +
              "  ".join(f"{k}={v}" for k, v in by_status[st].most_common()))

    with (ROOT / "ops/gain/replay/claim_truth.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            r.pop("text", None)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("\nwrote ops/gain/replay/claim_truth.jsonl")


if __name__ == "__main__":
    main()
