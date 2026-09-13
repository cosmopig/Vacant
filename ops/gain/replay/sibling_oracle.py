"""可實現的等預算替代方案：reviewer 只出「輸入」，oracle 由獨立候選程式提供。

現行 ON：1 gen + 3 review + 1 revise = 5 呼叫，reviewer 同時當出題者與裁判。
本替代：1 gen（受測候選）+ 1 gen（獨立手足）+ 3 review = 5 呼叫，
        reviewer 只供 TEST_ARGS，裁判由「手足程式在同一組 args 上的輸出」擔任。
判準（全部 V 側，零 hidden_check）：
    若存在某個 claim 使 sibling(args) == EXPECTED != candidate(args) ⇒ 記為可疑。
    （手足程式與 reviewer 各自獨立地同意同一個值，而候選不同意 ⇒ 2 對 1）
手足程式取自同 run OFF5 臂的 gen 回應（獨立樣本，不是被審那份）。

hidden_check 只用來**評分**這個規則，不進規則本身。
"""
from __future__ import annotations
import ast, json, os, pathlib, sys
from collections import defaultdict, Counter
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
from arg_probe import probe_src, candidate_codes  # noqa
RUNS = ROOT / "runs"
KMAX = 4


def sibling_codes(runs):
    out = defaultdict(list)
    for run in runs:
        for line in (RUNS / run / "calls.jsonl").open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            m = c.get("meta") or {}
            if c.get("role") == "gen" and c.get("ok") and m.get("arm") == "OFF5":
                out[(run, m.get("task_id"))].append(G.extract_code(c.get("response") or ""))
    return out


def main(runs):
    tasks = {t["task_id"]: t for t in
             EvalPlusMBPPLoader(expose_contract=True).iter_tasks("g-r212-route-20260828")}
    recs = [json.loads(l) for l in
            (ROOT / "ops/gain/replay/reviewer_records.jsonl").open(encoding="utf-8") if l.strip()]
    claims = defaultdict(list)
    for r in recs:
        if r["raw_pass"]:
            continue
        c = G.parse_review_claim(r["text"] or "")
        if c is None:
            continue
        claims[(r["run"], r["task_id"])].append((r, list(c[0]), c[1]))
    cand = candidate_codes(runs)
    sib = sibling_codes(runs)

    cache_path = ROOT / "ops/gain/replay/_sibling_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    jobs = []
    for key, items in claims.items():
        run, tid = key
        for si, code in enumerate(sib.get(key, [])[:KMAX]):
            ck = json.dumps([run, tid, si])
            if ck not in cache:
                jobs.append((ck, code, tid, [a for _, a, _ in items]))
    print("sibling probes to run:", len(jobs), " cached:", len(cache), flush=True)

    def do(j):
        ck, code, tid, args_list = j
        t = tasks[tid]
        try:
            out = run_python_capture(code, probe_src(t["entry_point"], args_list), timeout=15,
                                     allowed_imports=G._GAIN_ALLOWED_IMPORTS,
                                     allowed_entry_points=(t["entry_point"],))
        except Exception:
            out = None
        if not out:
            return ck, None
        try:
            return ck, ast.literal_eval(out.strip().splitlines()[-1])
        except Exception:
            return ck, None

    if jobs:
        with ThreadPoolExecutor(max_workers=4) as ex:
            for i, (ck, v) in enumerate(ex.map(do, jobs)):
                cache[ck] = v
                if (i + 1) % 50 == 0:
                    print("  sib probed", i + 1, flush=True)
                    cache_path.write_text(json.dumps(cache), encoding="utf-8")
        cache_path.write_text(json.dumps(cache), encoding="utf-8")

    cand_cache = json.loads((ROOT / "ops/gain/replay/_arg_probe_cache.json").read_text(
        encoding="utf-8"))
    cand_cache = {tuple(json.loads(k)): v for k, v in cand_cache.items()}

    def val(entry):
        if entry is None or entry[0] != "ok":
            return (False, None)
        try:
            return (True, ast.literal_eval(entry[1]))
        except Exception:
            return (False, None)

    rows = []
    for key, items in claims.items():
        run, tid = key
        cres = cand_cache.get(key)
        if cres is None:
            continue
        sibs = []
        for si in range(KMAX):
            v = cache.get(json.dumps([run, tid, si]))
            sibs.append(v)
        r0 = items[0][0]
        row = {"run": run, "task_id": tid,
               "cand_visible_ok": r0["cand_visible_ok"], "cand_hidden_ok": r0["cand_hidden_ok"]}
        for k in (1, 2, 3, 4):
            flag = False
            for j, (r, args, exp) in enumerate(items):
                if j >= len(cres):
                    continue
                cok, cv = val(cres[j])
                if not cok or eq(cv, exp):
                    continue          # candidate agrees with the claim -> no accusation
                agree = 0
                for si in range(k):
                    s = sibs[si]
                    if s is None or j >= len(s):
                        continue
                    sok, sv = val(s[j])
                    if sok and eq(sv, exp):
                        agree += 1
                if agree >= 1:
                    flag = True
            row[f"flag_k{k}"] = flag
        rows.append(row)

    print("\n== sibling-corroborated counterexample gate (V-side only) ==")
    vp = [r for r in rows if r["cand_visible_ok"] is True]
    print(f"rows with >=1 parsed claim: {len(rows)}; of those visible-PASS: {len(vp)}; "
          f"hidden-fail among them: {sum(1 for r in vp if r['cand_hidden_ok'] is False)}")
    for k in (1, 2, 3, 4):
        tp = sum(1 for r in vp if r[f"flag_k{k}"] and r["cand_hidden_ok"] is False)
        fp = sum(1 for r in vp if r[f"flag_k{k}"] and r["cand_hidden_ok"] is True)
        nb = sum(1 for r in vp if r["cand_hidden_ok"] is False)
        print(f"  k={k} sibling(s) (total calls = 1 cand + {k} sib + 3 review = {4+k}): "
              f"flagged={tp+fp:3d}  TP={tp:3d} FP={fp:3d}  "
              f"precision={tp/(tp+fp) if tp+fp else float('nan'):.3f}  "
              f"recall={tp/nb if nb else float('nan'):.3f}")
    # compare with the run-time mechanism's own gate on the same rows
    conf = {}
    for r in recs:
        conf.setdefault((r["run"], r["task_id"]), 0)
        conf[(r["run"], r["task_id"])] += 1 if r["confirmed"] else 0
    tp = sum(1 for r in vp if conf.get((r["run"], r["task_id"]), 0) >= 1 and r["cand_hidden_ok"] is False)
    fp = sum(1 for r in vp if conf.get((r["run"], r["task_id"]), 0) >= 1 and r["cand_hidden_ok"] is True)
    nb = sum(1 for r in vp if r["cand_hidden_ok"] is False)
    print(f"  [reference] current mechanism's confirmed-CE gate on the SAME rows: "
          f"flagged={tp+fp} TP={tp} FP={fp} precision={tp/(tp+fp) if tp+fp else float('nan'):.3f} "
          f"recall={tp/nb if nb else float('nan'):.3f}")
    with (ROOT / "ops/gain/replay/sibling_oracle.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote ops/gain/replay/sibling_oracle.jsonl")


if __name__ == "__main__":
    main(sys.argv[1:])
