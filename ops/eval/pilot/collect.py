"""試點／校準的彙整：每一跑一列——Harbor 的評分、記帳代理的花費與 token（依標籤）、C 組的 `vacant_check.json`。

    python3 ops/eval/pilot/collect.py --jobs <jobs 根目錄> --ledger <代理的 ledger 目錄> --out <輸出 JSON>

標籤＝`pilot-<模型>-<思考>-<組>-<題號>`（`run_one.sh`）。一跑沒有評分（例外、逾時）照列、`reward=None`，
不從分母拿掉（`infra_void` 另外標）。
"""
from __future__ import annotations

import argparse
import json
import pathlib


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--suffix", default="", help="run_one.sh 的 RUN_SUFFIX（重跑的標籤尾巴）")
    a = ap.parse_args()
    by_tag = json.loads((pathlib.Path(a.ledger) / "summary.json").read_text()).get("by_tag", {})
    rows = []
    for res in sorted(pathlib.Path(a.jobs).glob("*/*/dabstep-*__*/result.json")):
        trial = res.parent
        cond = trial.parents[1].name                     # <模型>-<思考>-<組>
        m, think, arm = cond.split("-")
        task = trial.name.split("__")[0].removeprefix("dabstep-")
        r = json.loads(res.read_text())
        vr = r.get("verifier_result") or {}
        reward = (vr.get("rewards") or {}).get("reward", vr.get("reward"))
        exc = (r.get("exception_info") or {}).get("exception_type")
        tag = f"pilot-{m}-{think}-{arm}-{task}" + (f"-{a.suffix}" if a.suffix else "")
        led = by_tag.get(tag) or {}
        chk = None
        p = trial / "agent" / "vacant_check.json"
        if p.is_file():
            try:
                chk = json.loads(p.read_text().strip().splitlines()[-1])
            except (ValueError, IndexError):
                chk = {"unreadable": p.read_text()[:300]}
        ans = trial / "verifier" / "test-stdout.txt"
        rows.append({
            "task": task, "model": m, "think": think, "arm": arm, "reward": reward,
            "exception": exc, "infra_void": reward is None,
            "requests": led.get("requests"), "prompt_tokens": led.get("prompt_tokens"),
            "completion_tokens": led.get("completion_tokens"),
            "reasoning_tokens": led.get("reasoning_tokens"), "cost_usd": led.get("cost_usd"),
            "started": r.get("started_at"), "finished": r.get("finished_at"),
            "vacant_check": chk, "trial_dir": str(trial),
            "verifier_tail": ans.read_text()[-300:] if ans.is_file() else None})
    tot = sum(x["cost_usd"] or 0 for x in rows)
    out = {"runs": len(rows), "cost_usd": round(tot, 6), "rows": rows}
    pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for x in rows:
        print(json.dumps({k: x[k] for k in ("task", "model", "think", "arm", "reward", "requests",
                                            "prompt_tokens", "reasoning_tokens", "cost_usd")}))
        if x["vacant_check"]:
            print("   vacant:", json.dumps(x["vacant_check"]))
    print(f"total ${tot:.5f} over {len(rows)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
