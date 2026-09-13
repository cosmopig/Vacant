#!/usr/bin/env python3
"""R487-B post-hoc: is the absolute-margin rule in the prereg the wrong FORM?

Synthetic reproduction only -- no real data touched. Populations are built so that
`ts` IS the start by construction (id assigned at completion). If the rule cannot recover
the known-true answer when latencies are tightly spread, its form is wrong regardless of
what the real snapshot says. This is the ONLY admissible justification for changing a
criterion in a direction that favours the author's own prediction: semantics or synthetic
reproduction, never the result numbers.
"""
import random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from r487_ts_semantics import analyze  # noqa: E402


def main():
    print("truth = TS_IS_START by construction in every row below")
    bad = 0
    for jitter in (50.0, 5.0, 1.0, 0.2):
        rnd = random.Random(11)
        ends = sorted(rnd.uniform(0, 20000) for _ in range(800))
        rows = []
        for i, e in enumerate(ends, 1):
            lat = rnd.uniform(0.1, jitter)
            rows.append({"id": i, "ts": e - lat, "latency_ms": lat * 1000.0,
                         "method": "POST", "path": "[gw] /v1/chat/completions"})
        a = analyze(rows)
        inv = a["inv"]
        srt = sorted(inv.values())
        miss = a["verdict"] != "TS_IS_START"
        bad += 1 if miss else 0
        print(f"  latency<={jitter:5}s  verdict={a['verdict']:22s} "
              f"inv_plus={inv['ts_plus_lat']:.5f} inv_ts={inv['ts']:.5f} "
              f"margin={srt[1]-srt[0]:.5f}  {'<- MISSED a perfect signal' if miss else ''}")
    print(f"{bad}/4 known-START populations were NOT recovered by the absolute-margin rule")
    return 0


if __name__ == "__main__":
    sys.exit(main())
