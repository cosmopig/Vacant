#!/usr/bin/env python3
"""i1001 的 LCB 題池（SPEC「Pool and screening」）：C5 的 A 組沒過的全部 LCB 題 + 從 A 組過了的 LCB 題裡
用固定種子抽 40 題（傷害／回歸對照）。純函式、可重算：同一份 cells.jsonl 與種子 ⇒ 同一個池。

    python3 build_pool_lcb.py --cells <results_c5/cells.jsonl> --out pool_lcb.json [--seed 20261001] [--n-control 40]

抽樣法（寫死、寫進輸出）：A 組通過的 (bank, unit) 依 (bank, unit) 字串排序 ⇒ `random.Random(seed).sample(list, n)`
⇒ 結果再依 (bank, unit) 排序。C5 沒有 void 格（launch_record／report），這裡仍把 void 的題擋在池外並記數。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import random

LCB = ("lcb_v1", "lcb_v2", "lcb_v3")
KEEP = ("pass", "visible_pass", "false_done", "no_solution", "timeout", "wall_s", "calls", "prompt_tokens", "completion_tokens")


def build(cells_path: pathlib.Path, seed: int, n_control: int) -> dict:
    raw = cells_path.read_bytes()
    rows = [json.loads(l) for l in raw.decode().splitlines() if l.strip()]
    by: dict[tuple[str, str], dict] = {}
    for r in rows:
        if r["bank"] in LCB:
            by.setdefault((r["bank"], r["unit"]), {})[r["arm"]] = r
    voided = sorted(k for k, v in by.items() if any(x["void"] for x in v.values()))
    ok = {k: v for k, v in by.items() if k not in set(voided)}
    for k, v in ok.items():
        assert set(v) == {"A", "C361"}, (k, set(v))
    failed = sorted(k for k, v in ok.items() if not v["A"]["pass"])
    passed = sorted(k for k, v in ok.items() if v["A"]["pass"])
    control = sorted(random.Random(seed).sample(passed, n_control))

    def row(k: tuple[str, str], role: str) -> dict:
        bank, unit = k
        tid = unit.split("-", 1)[1]
        assert unit == f"{bank}-{tid}", unit
        return {"bank": bank, "id": tid, "unit": unit, "role": role,
                "c5": {arm: {f: ok[k][arm][f] for f in KEEP} for arm in ("A", "C361")}}

    pool = [row(k, "a_failed") for k in failed] + [row(k, "a_passed_control") for k in control]
    summ: dict = {"n_lcb_units": len(by), "n_void_excluded": len(voided), "n_a_failed": len(failed),
                  "n_a_passed": len(passed), "n_control": len(control), "n_pool": len(pool)}
    for b in LCB:
        summ[b] = {"a_failed": sum(1 for k in failed if k[0] == b), "a_passed": sum(1 for k in passed if k[0] == b),
                   "control": sum(1 for k in control if k[0] == b)}
    return {"schema": "i1001.pool_lcb/1", "seed": seed,
            "sampling": "A-passed (bank,unit) sorted lexicographically -> random.Random(seed).sample(list, n_control) -> sorted",
            "source": {"cells_jsonl": cells_path.name, "sha256": hashlib.sha256(raw).hexdigest()},
            "summary": summ, "voided_excluded": [list(k) for k in voided], "pool": pool}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--seed", type=int, default=20261001)
    ap.add_argument("--n-control", type=int, default=40)
    a = ap.parse_args()
    out = build(a.cells, a.seed, a.n_control)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(out["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
