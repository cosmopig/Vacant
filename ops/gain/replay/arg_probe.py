"""reviewer 到底是好的『出題者』還是壞的『裁判』？

對每個可解析的 (TEST_ARGS, EXPECTED)，實際在 sandbox 裡跑**被審的那份候選碼**
拿到 candidate(args)，跟 canonical solution 的 GT(args) 比。
- candidate(args) != GT(args)  ⇒ 這組 args 是真的能打到候選碼的探針（出題成功）
- EXPECTED == GT(args)         ⇒ 這位 reviewer 當裁判也對（罕見）
兩者分開計數，才知道該砍哪一半。

每個 (run, task) 只呼叫一次 sandbox（run_python_capture 一次印出所有 args 的結果）。
"""
from __future__ import annotations
import ast, json, math, os, pathlib, signal, sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "ops/gain"))
os.environ.setdefault("VACANT_EVALPLUS_PATH",
                      str(ROOT / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"))
import gain_run as G  # noqa
from vacant.checks import run_python_capture  # noqa
from vacant.codebench import EvalPlusMBPPLoader  # noqa
sys.path.insert(0, str(ROOT / "ops/gain/replay"))
from claim_truth import eq  # noqa

RUNS = ROOT / "runs"


def candidate_codes(runs):
    """(run, task_id) -> 被審的初稿（直接從 review prompt 取，保證與被審的一致）。"""
    out = {}
    for run in runs:
        for line in (RUNS / run / "calls.jsonl").open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            m = c.get("meta") or {}
            if c.get("role") != "review" or not c.get("ok") or m.get("arm") != "ON":
                continue
            p = c.get("prompt") or ""
            if "候選解答：" not in p:
                continue
            out[(run, m["task_id"])] = G.extract_code(p.split("候選解答：", 1)[1])
    return out


def probe_src(entry_point, args_list):
    return (f"__args = {args_list!r}\n"
            "__out = []\n"
            "for __a in __args:\n"
            "    try:\n"
            f"        __out.append(('ok', repr({entry_point}(*__a))))\n"
            "    except Exception as __e:\n"
            "        __out.append(('raise', type(__e).__name__))\n"
            "print(repr(__out))\n")


def main(runs):
    tasks = {t["task_id"]: t for t in
             EvalPlusMBPPLoader(expose_contract=True).iter_tasks("g-r212-route-20260828")}
    recs = [json.loads(l) for l in
            (ROOT / "ops/gain/replay/reviewer_records.jsonl").open(encoding="utf-8") if l.strip()]
    canon = G._canonical_solutions("evalplus")

    class _TO(Exception):
        pass

    def _alarm(sig, frm):
        raise _TO()
    signal.signal(signal.SIGALRM, _alarm)
    _ns_cache = {}

    def gt_call(task_id, args):
        ep = tasks[task_id]["entry_point"]
        if task_id not in _ns_cache:
            ns = {}
            try:
                exec(compile(canon[task_id], "<canon>", "exec"), ns)
            except Exception:
                ns = None
            _ns_cache[task_id] = ns
        ns = _ns_cache[task_id]
        if ns is None or ep not in ns:
            return ("no_gt", None)
        signal.setitimer(signal.ITIMER_REAL, 3.0)
        try:
            return ("ok", ns[ep](*args))
        except _TO:
            return ("timeout", None)
        except Exception as e:
            return ("gt_raised:" + type(e).__name__, None)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)

    claims = []
    for r in recs:
        if r["raw_pass"]:
            continue
        c = G.parse_review_claim(r["text"] or "")
        if c is None:
            continue
        claims.append((r, list(c[0]), c[1]))
    print("parsed claims:", len(claims))

    codes = candidate_codes(runs)
    groups = defaultdict(list)
    for r, args, exp in claims:
        groups[(r["run"], r["task_id"])].append((r, args, exp))
    print("distinct (run,task) sandbox probes needed:", len(groups))

    def do(key):
        run, tid = key
        code = codes.get(key)
        t = tasks[tid]
        items = groups[key]
        if code is None:
            return key, None
        src = probe_src(t["entry_point"], [a for _, a, _ in items])
        try:
            out = run_python_capture(code, src, timeout=15,
                                     allowed_imports=G._GAIN_ALLOWED_IMPORTS,
                                     allowed_entry_points=(t["entry_point"],))
        except Exception:
            out = None
        if not out:
            return key, None
        try:
            return key, ast.literal_eval(out.strip().splitlines()[-1])
        except Exception:
            return key, None

    cache_path = ROOT / "ops/gain/replay/_arg_probe_cache.json"
    cache = {}
    if cache_path.exists():
        cache = {tuple(json.loads(k)): v for k, v in
                 json.loads(cache_path.read_text(encoding="utf-8")).items()}
    todo = [k for k in groups if k not in cache]
    print("cached:", len(cache), " to probe:", len(todo), flush=True)
    results = dict(cache)
    if todo:
        with ThreadPoolExecutor(max_workers=4) as ex:
            for i, (k, v) in enumerate(ex.map(do, todo)):
                results[k] = v
                if (i + 1) % 25 == 0:
                    print("  probed", i + 1, flush=True)
        cache_path.write_text(json.dumps(
            {json.dumps(list(k)): v for k, v in results.items()}), encoding="utf-8")

    tab = Counter()
    rows = []
    for key, items in groups.items():
        res = results.get(key)
        for j, (r, args, exp) in enumerate(items):
            gst, gtv = gt_call(r["task_id"], args)
            gt_known = gst == "ok"
            if res is None or j >= len(res):
                tab["candidate_output_unavailable"] += 1
                continue
            kind, payload = res[j]
            if kind != "ok":
                cand_val, cand_raised = None, True
            else:
                try:
                    cand_val, cand_raised = ast.literal_eval(payload), False
                except Exception:
                    tab["candidate_output_unparseable"] += 1
                    continue
            if not gt_known:
                tab["gt_unavailable"] += 1
                continue
            probe_hits = cand_raised or not eq(cand_val, gtv)
            judge_right = eq(exp, gtv)
            tab[("probe_hit" if probe_hits else "probe_miss") +
                "/" + ("judge_right" if judge_right else "judge_wrong")] += 1
            rows.append({"run": r["run"], "task_id": r["task_id"], "reviewer": r["reviewer"],
                         "status": r["status"], "confirmed": r["confirmed"],
                         "cand_visible_ok": r["cand_visible_ok"],
                         "cand_hidden_ok": r["cand_hidden_ok"],
                         "probe_hit": probe_hits, "judge_right": judge_right})

    print("\n-- reviewer as INPUT GENERATOR vs as JUDGE (parsed claims with GT) --")
    for k, v in sorted(tab.items(), key=lambda x: str(x[0])):
        print(f"   {str(k):40s} {v}")
    ok = [r for r in rows]
    if ok:
        ph = sum(1 for r in ok if r["probe_hit"])
        jr = sum(1 for r in ok if r["judge_right"])
        print(f"\n   n={len(ok)}  probe hits (args actually break the candidate) = {ph} ({ph/len(ok):.4f})")
        print(f"           judge right (EXPECTED == GT)                 = {jr} ({jr/len(ok):.4f})")
        for st in sorted({r["status"] for r in ok}):
            g = [r for r in ok if r["status"] == st]
            print(f"     status={st:26s} n={len(g):4d} probe_hit={sum(1 for r in g if r['probe_hit'])/len(g):.3f} "
                  f"judge_right={sum(1 for r in g if r['judge_right'])/len(g):.3f}")
        vp = [r for r in ok if r["cand_visible_ok"] is True]
        print(f"\n   restricted to candidates that PASS visible tests: n={len(vp)}")
        for hid in (False, True):
            g = [r for r in vp if r["cand_hidden_ok"] is hid]
            if g:
                print(f"     hidden_ok={hid}: n={len(g)} probe_hit={sum(1 for r in g if r['probe_hit'])/len(g):.3f} "
                      f"judge_right={sum(1 for r in g if r['judge_right'])/len(g):.3f}")
    with (ROOT / "ops/gain/replay/arg_probe.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("\nwrote ops/gain/replay/arg_probe.jsonl")


if __name__ == "__main__":
    main(sys.argv[1:])
