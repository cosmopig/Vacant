#!/usr/bin/env python3
"""feasibility_i1001 — 可行性護欄（VM 常駐，root）：基礎設施壞了就放停止檔，別燒運算單位。

    python3 feasibility_i1001.py --prefix i1 [--window 30] [--interval 60]

這支在架構裡承重什麼：第一批的 `feasibility.py` 看「最先跑完的 40 格逾時率 ≥ 30% 就停」。這批**不能用那條**——題池本來就是 C5
的 A 失敗題，近六成原本就會撞 1800 秒；用它會在第一個窗口就誤停。這裡改看基礎設施本身的訊號（**只看 progress.jsonl 的 void／安裝
與代理帳本的狀態碼，不讀任何分數**）：
  - 最近 `window` 個（A／C 線）格子裡 void 率 ≥ 30%；
  - 這些格子的代理呼叫（至少 50 通）非 200 率 ≥ 10%；
  - C 的 Vacant 安裝失敗累計 ≥ 3 次。
每 `interval` 秒重評一次（不是只評最先的 N 格），觸發 ⇒ 寫 `/srv/eval/STOP`（driver 不再開新單位，已開始的跑完）並結束。
逾時只記錄、不是規則。誠實邊界：void 率是「事後」訊號——第一批 void 的格子已經花掉了時間。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tui_lib import LedgerTail  # noqa: E402

EVAL = pathlib.Path("/srv/eval")


def evaluate(rows: list[dict], ledger: LedgerTail, window: int) -> dict:
    seen: dict[str, dict] = {}
    for r in rows:
        seen[r["cell"]] = r
    lines = [r for r in seen.values() if r.get("arm") in ("A", "C")]
    lines.sort(key=lambda r: r.get("at", ""))
    last = lines[-window:]
    names = {r["cell"] for r in last}
    calls = bad = 0
    ledger.refresh(force=True)
    for tag, st in list(ledger.rows.items()):
        if tag.rsplit(".n", 1)[0] in names:
            calls += st["calls"]
            bad += st["non200"] + st["stream_errors"]
    voids = sum(1 for r in last if r.get("void"))
    c_fail = sum(1 for r in seen.values() if r.get("arm") == "C" and r.get("install_rc") not in (0, None))
    res = {"cells_in_window": len(last), "void": voids, "void_rate": voids / len(last) if last else 0.0, "calls": calls,
           "non200": bad, "non200_rate": bad / calls if calls else 0.0, "c_install_fail": c_fail,
           "timeouts": sum(1 for r in last if r.get("timeout"))}
    res["triggered"] = bool(
        (len(last) >= min(window, 10) and res["void_rate"] >= 0.30)
        or (calls >= 50 and res["non200_rate"] >= 0.10)
        or c_fail >= 3)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--window", type=int, default=30)
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--eval-root", type=pathlib.Path, default=EVAL)
    a = ap.parse_args()
    ledger = LedgerTail(a.eval_root / "proxy" / "ledger.jsonl")
    prog = a.eval_root / "progress.jsonl"
    while True:
        rows = [json.loads(x) for x in prog.read_text().splitlines() if x.strip()] if prog.exists() else []
        res = evaluate(rows, ledger, a.window)
        res["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        (a.eval_root / "feasibility_i1001.json").write_text(json.dumps(res, indent=1) + "\n")
        if res["triggered"]:
            (a.eval_root / "STOP").write_text(f"feasibility rule triggered {res['at']}: {json.dumps(res)}\n")
            print(json.dumps(res), flush=True)
            return 0
        if (a.eval_root / "DRIVER_DONE").exists():
            print("driver finished", flush=True)
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
