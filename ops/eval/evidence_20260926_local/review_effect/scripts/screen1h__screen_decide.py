"""One-hour screen decision (proposal, 2026-09-26). Reads a cells.json produced by
ops/eval/local/analyze_local.py (same schema as ops/eval/evidence_20260926_local/formal/cells.json)
and applies the fixed rule. Does not look at anything except rewards of the screen's own runs.

    python3 screen_decide.py --cells <cells.json> --c C --a A [--suite local|api] [--samples 1]

Rule (fixed before any screen run):
  U = gain stratum, K = harm stratum (task lists below, chosen from A-arm-only properties of earlier runs).
  Stage 1 (one sample): net_U = #(C right, A wrong) - #(A right, C wrong) over U pairs.
    GO if net_U >= 4 and harm gate passes; STOP if net_U <= 1; else run sample 2 on U only,
    then GO if net_U(total) >= 6 and harm gate passes.
  Harm gate: net loss in K <= 2  (#(A right, C wrong) - #(C right, A wrong) over K pairs); 2 = inspect.
  (Mechanism harm -- first delivery correct, final wrong after a send-back or reminder -- is read
   from analyze_local's first-stop fields separately; any such event = STOP and inspect.)
"""
import argparse, json
SUITES = {
    # formal-77 tasks with local A (gemma-4-12b off, formal_v3) missing /app/answer.txt in >=1 of 3 runs,
    # mean A trial time <= 300 s
    "local": {"U": "1 3 6 7 11 16 18 19 23 26 30 35 36 44 49 50 51 53 58 59 61 62 71 72".split(),
              # random.Random(20260927).sample(tasks with local A correct 3/3 and mean <= 300 s (31), 12)
              "K": "8 9 15 21 22 24 25 29 48 54 57 64".split()},
    # easy formal tasks where the paid gemma-4-26b think-on A run hit the 15-turn cap without an answer
    # (failure_taxonomy class a), and random.Random(20260927).sample(paid A correct & A trial <= 300 s (45), 8)
    "api": {"U": "3 7 10 15 16 17 18 19 39 43 47 48 58 62 65 69 71 72".split(),
            "K": "8 12 25 30 35 42 56 63".split()},
}
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", required=True); ap.add_argument("--c", default="C"); ap.add_argument("--a", default="A")
    ap.add_argument("--suite", default="local", choices=SUITES); ap.add_argument("--samples", nargs="+", type=int, default=None)
    ap.add_argument("--model", help="only rows with this model field (paid runs.json mixes g4 and q38)")
    a = ap.parse_args()
    cells = json.load(open(a.cells))
    r = {(c["task"], c["arm"], c.get("sample", 1)): c.get("reward") for c in cells if not c.get("infra_void") and (not a.model or c.get("model") == a.model)}
    s = SUITES[a.suite]
    samples = a.samples or sorted({k[2] for k in r})
    out = {}
    for name, tasks in s.items():
        w = l = n = 0; missing = []
        for t in tasks:
            for sm in samples:
                ra, rc = r.get((t, a.a, sm)), r.get((t, a.c, sm))
                if ra is None or rc is None:
                    if name == "U" or sm == samples[0]:
                        missing.append(f"{t}/s{sm}")
                    continue
                n += 1; w += (rc or 0) > (ra or 0); l += (ra or 0) > (rc or 0)
        out[name] = {"pairs": n, "C_only": w, "A_only": l, "net": w - l, "missing": missing}
    netU, kloss = out["U"]["net"], out["K"]["A_only"] - out["K"]["C_only"]
    harm_ok = kloss <= 2
    one = len(samples) == 1
    if not harm_ok: decision = "STOP (harm gate: K net loss %d)" % kloss
    elif one and netU >= 4: decision = "GO"
    elif one and netU <= 1: decision = "STOP"
    elif one: decision = "INCONCLUSIVE -> run sample 2 on U"
    else: decision = "GO" if netU >= 6 else "STOP"
    print(json.dumps({"suite": a.suite, "samples": samples, **out, "decision": decision}, indent=1))
if __name__ == "__main__":
    main()
