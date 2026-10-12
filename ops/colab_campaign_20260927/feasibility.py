#!/usr/bin/env python3
"""可行性規則（預註冊第五節），VM 上常駐（root）：最先跑完的 N 格（預設 40）一到，判一次，寫 /srv/eval/feasibility.json。
觸發 ⇒ 放停止檔（驅動不再開新題，已開始的跑完）。**只看 progress.jsonl（rc、逾時、安裝）與代理帳本的狀態碼，不讀 score.json。**

    python3 feasibility.py --prefix c5 [--n 40]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

EVAL = pathlib.Path("/srv/eval")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()
    while True:
        rows = []
        if (EVAL / "progress.jsonl").exists():
            rows = [json.loads(l) for l in (EVAL / "progress.jsonl").read_text().splitlines() if l.strip()]
        rows = [r for r in rows if r["cell"].startswith(a.prefix + "-")]
        if len(rows) >= a.n:
            first = sorted(rows, key=lambda r: r["at"])[: a.n]
            names = {r["cell"] for r in first}
            led = [json.loads(l) for l in (EVAL / "proxy" / "ledger.jsonl").read_text().splitlines() if l.strip()]
            calls = [x for x in led if x.get("tag") in names]
            bad = [x for x in calls if x.get("status") != 200 or x.get("stream_error")]
            timeouts = sum(1 for r in first if r.get("timeout"))
            c_fail = sum(1 for r in first if r["arm"] != "A" and r.get("install_rc") not in (0, None))
            res = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cells": len(first), "timeouts": timeouts,
                   "timeout_rate": timeouts / len(first), "calls": len(calls), "non200": len(bad),
                   "non200_rate": len(bad) / max(1, len(calls)), "c_install_fail": c_fail}
            res["triggered"] = res["timeout_rate"] >= 0.30 or res["non200_rate"] >= 0.10 or c_fail >= 3
            (EVAL / "feasibility.json").write_text(json.dumps(res, indent=1))
            if res["triggered"]:
                (EVAL / "STOP").write_text(f"feasibility rule triggered {res['at']}\n")
            print(json.dumps(res), flush=True)
            return 0
        if (EVAL / "DRIVER_DONE").exists():
            print("driver finished before the feasibility window filled", flush=True)
            return 0
        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())
