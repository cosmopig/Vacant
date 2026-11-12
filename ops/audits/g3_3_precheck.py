#!/usr/bin/env python3
"""G3.3 預檢查（離線、0 model calls、只讀；工單 P20261112_0119-1）。
核心口徑（與 g3_2_precheck 同形；選題規則換成 G3.3 的 H2 依據）：
1. manifest sha256 與任務輸入實檔一致——本地凍結副本（ops/reqloop/g3_3/tasks/）與
   ref 源（/home/user1/dev/ops/ref/bm_tasks/dabench/）逐一雙核（local == ref == manifest）；
2. 選題一致性＝bank.ordering − seen_set 前 1 題恰為 tasks 順序
   （同 g3gate.unseen_selection / G3Plan.verify_frozen 口徑）；
3. 選題規則機械核（防 cherry-pick）：G3.2 H0 預跑報告
   （ops/audits/g3_2_h0_prerun_report.json）中恰 1 題 n_deterministic_claims≥1，
   且該題＝dab_725（G3.3 唯一目標題；假說 §2）。
不讀 hidden/scorer；不發射。
用法：python3 ops/audits/g3_3_precheck.py --selftest
"""
import argparse
import hashlib
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
MAN = REPO / "ops/reqloop/g3_3/manifest.json"
LOCAL = REPO / "ops/reqloop/g3_3/tasks"
REF = pathlib.Path("/home/user1/dev/ops/ref/bm_tasks/dabench")
PRERUN = REPO / "ops/audits/g3_2_h0_prerun_report.json"
TARGET = "dab_725"

def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="執行預檢查（本腳程唯一模式）")
    a = ap.parse_args()
    if not a.selftest:
        ap.error("本腳程只支援 --selftest（離線預檢查）")
    m = json.loads(MAN.read_text(encoding="utf-8"))
    assert m["schema"] == "vacant.reqloop.g3gate.plan/1", "schema mismatch"
    tids = [t["task_id"] for t in m["tasks"]]
    assert tids == [TARGET], f"任務順序不符（G3.3 唯一目標題＝{TARGET}）：{tids}"
    # 1) 逐檔 sha256：local == ref == manifest
    for t in m["tasks"]:
        for rel, want in t["files"].items():
            lp, rp = LOCAL / t["task_id"] / rel, REF / t["task_id"] / rel
            assert lp.is_file(), f"missing local: {lp}"
            assert rp.is_file(), f"missing ref: {rp}"
            assert sha256(lp) == want, f"local sha mismatch: {rel}"
            assert sha256(rp) == want, f"ref sha mismatch: {rel}"
    # 2) 選題一致性（unseen_selection 同口徑：前 1 未見題）
    seen = set(m["seen_set"])
    unseen = [x for x in m["bank"]["ordering"] if x not in seen]
    assert len(unseen) == 1 and unseen == tids, f"unseen 前 1 ≠ tasks：{unseen[:4]}"
    # 3) 選題規則機械核：G3.2 H0 預跑恰 1 題具確定性 claim 且＝dab_725
    r = json.loads(PRERUN.read_text(encoding="utf-8"))
    hit = [t["task_id"] for t in r["tasks"] if t.get("n_deterministic_claims", 0) >= 1]
    assert hit == [TARGET], f"H0 預跑具確定性 claim 題應恰為 [{TARGET}]：{hit}"
    # 4) 預算/臂形（fail-closed 底線，與 g3gate.check_budget 同口徑）
    b = m["budget"]
    assert m["arms"] == ["full_rloop"], f"arms 不符：{m['arms']}"
    assert b["max_cells"] == 1 and b["timeout_s_per_round"] == 300, "預算形不符"
    assert b["daily_token_cap"] == 2000000 and b["quota_fail_closed"] is True
    assert b["model_entry"] == "glm" and b["hard_token_cap"] is False
    assert b["cost_missing"] == "UNKNOWN"
    print(f"checked: local==ref==manifest ×{sum(len(t['files']) for t in m['tasks'])} 檔；"
          f"unseen==[{TARGET}]；H0 預跑恰 1 題達（{hit[0]}）；預算 1 格/300s/2M/日/glm")
    print("VERDICT: G3_3_PRECHECK_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
