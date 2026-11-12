#!/usr/bin/env python3
"""G3.2 預檢查（離線、0 model calls、只讀；工單 P20261111_2119-1）。
核心口徑（與 g3_1_precheck 同形，另加假說 §3 預檢查 3）：
1. manifest sha256 與任務輸入實檔一致——本地凍結副本（ops/reqloop/g3_2/tasks/）與
   ref 源（/home/user1/dev/ops/ref/bm_tasks/dabench/）逐一雙核（local == ref == manifest）；
2. 選題清單＝bank.ordering − seen_set 前 4 題，且恰合 tasks 順序
   （同 g3gate.unseen_selection / G3Plan.verify_frozen 口徑）；
3. 相容性篩選輸出（top4＋ranking＋排除集）的 sha256 與 manifest.screening 一致，
   且 screen 現行重跑決定性重算吻合（防 cherry-pick；screen 工具 --selftest C8 同核）。
不讀 hidden/scorer；不發射。
用法：python3 ops/audits/g3_2_precheck.py --selftest
"""
import argparse
import hashlib
import json
import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]
MAN = REPO / "ops/reqloop/g3_2/manifest.json"
LOCAL = REPO / "ops/reqloop/g3_2/tasks"
REF = pathlib.Path("/home/user1/dev/ops/ref/bm_tasks/dabench")
SCREEN = REPO / "ops/audits/g3_2_bank_screen.py"

def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="執行預檢查（本腳程唯一模式）")
    ap.parse_args()
    m = json.loads(MAN.read_text(encoding="utf-8"))
    assert m["schema"] == "vacant.reqloop.g3gate.plan/1", "schema mismatch"
    tids = [t["task_id"] for t in m["tasks"]]
    assert tids == ["dab_725", "dab_587", "dab_657", "dab_517"], f"task 順序不符：{tids}"
    # 1) 逐檔 sha256：local == ref == manifest
    for t in m["tasks"]:
        for rel, want in t["files"].items():
            lp, rp = LOCAL / t["task_id"] / rel, REF / t["task_id"] / rel
            assert lp.is_file(), f"missing local: {lp}"
            assert rp.is_file(), f"missing ref: {rp}"
            assert sha256(lp) == want, f"local sha mismatch: {rel}"
            assert sha256(rp) == want, f"ref sha mismatch: {rel}"
    # 2) 選題一致性（unseen_selection 同口徑）
    seen = set(m["seen_set"])
    unseen = [x for x in m["bank"]["ordering"] if x not in seen]
    assert len(unseen) == 4 and unseen == tids, f"unseen 前 4 ≠ tasks：{unseen[:5]}"
    # 3) screen 輸出 hash 一致＋決定性重算
    sc = m["screening"]
    out = subprocess.run(["python3", str(SCREEN)], capture_output=True, text=True,
                         cwd=REPO, check=True).stdout
    assert hashlib.sha256(out.encode("utf-8")).hexdigest() == sc["output_sha256"], "screen sha mismatch"
    assert json.loads(out)["top4"] == tids, "screen top4 ≠ tasks"
    print("VERDICT: G3_2_PRECHECK_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
