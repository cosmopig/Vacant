#!/usr/bin/env python3
"""G3.2 預檢查（離線、0 model calls、只讀；工單 P20261112_0820-1）。
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

def check_precheck(manifest: dict, screen_stdout: str | None = None, *, ref_dir: pathlib.Path = REF, local_dir: pathlib.Path = LOCAL) -> list[str]:
    errors = []
    if manifest.get("schema") != "vacant.reqloop.g3gate.plan/1":
        errors.append(f"schema mismatch: {manifest.get('schema')}")
    
    tids = [t["task_id"] for t in manifest.get("tasks", [])]
    expected_tids = ["dab_725", "dab_587", "dab_657", "dab_517"]
    if tids != expected_tids:
        errors.append(f"task 順序不符：{tids}")

    for t in manifest.get("tasks", []):
        tid = t["task_id"]
        for rel, want in t["files"].items():
            lp, rp = local_dir / tid / rel, ref_dir / tid / rel
            if not lp.is_file():
                errors.append(f"missing local: {lp}")
            elif sha256(lp) != want:
                errors.append(f"local sha mismatch: {rel} (tid={tid})")
            if not rp.is_file():
                errors.append(f"missing ref: {rp}")
            elif sha256(rp) != want:
                errors.append(f"ref sha mismatch: {rel} (tid={tid})")

    seen = set(manifest["bank"]["seen_set"])
    unseen = [x for x in manifest["bank"]["ordering"] if x not in seen]
    if len(unseen) != 4 or unseen != expected_tids:
        errors.append(f"unseen 前 4 ≠ tasks：{unseen}")

    sc = manifest["screening"]
    if screen_stdout is None:
        try:
            res = subprocess.run(["python3", str(SCREEN)], capture_output=True, text=True, cwd=REPO, check=True)
            screen_stdout = res.stdout
        except Exception as e:
            errors.append(f"failed to run screen tool: {e}")

    if screen_stdout is not None:
        out_sha = hashlib.sha256(screen_stdout.encode("utf-8")).hexdigest()
        if out_sha != sc["output_sha256"]:
            errors.append(f"screen sha mismatch: {out_sha}")
        try:
            out_json = json.loads(screen_stdout)
            if out_json.get("top4") != expected_tids:
                errors.append(f"screen top4 ≠ tasks: {out_json.get('top4')}")
        except json.JSONDecodeError:
            errors.append("failed to parse screen output as JSON")

    budget = manifest["budget"]
    if manifest.get("arms") != ["full_rloop"]:
        errors.append(f"arms mismatch: {manifest.get('arms')}")
    if budget.get("max_cells") != 4:
        errors.append(f"max_cells mismatch: {budget.get('max_cells')}")
    if budget.get("timeout_s_per_round") != 300:
        errors.append(f"timeout_s_per_round mismatch: {budget.get('timeout_s_per_round')}")
    if budget.get("daily_token_cap") != 2000000:
        errors.append(f"daily_token_cap mismatch: {budget.get('daily_token_cap')}")
    if budget.get("quota_fail_closed") is not True:
        errors.append(f"quota_fail_closed mismatch: {budget.get('quota_fail_closed')}")
    if budget.get("model_entry") != "glm":
        errors.append(f"model_entry mismatch: {budget.get('model_entry')}")
    if budget.get("hard_token_cap") is not False:
        errors.append(f"hard_token_cap mismatch: {budget.get('hard_token_cap')}")
    if budget.get("cost_missing") != "UNKNOWN":
        errors.append(f"cost_missing mismatch: {budget.get('cost_missing')}")

    return errors

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="執行預檢查（本腳程唯一模式）")
    ap.parse_args()
    m = json.loads(MAN.read_text(encoding="utf-8"))
    errors = check_precheck(m)
    if errors:
        for err in errors:
            print(err)
        print("VERDICT: G3_2_PRECHECK_BROKEN")
        return 1
    print("VERDICT: G3_2_PRECHECK_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
