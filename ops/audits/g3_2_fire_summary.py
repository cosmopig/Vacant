import argparse
import json
import pathlib
from typing import List, Dict, Any

REPO = pathlib.Path(__file__).resolve().parents[2]
MAN = REPO / "ops/reqloop/g3_2/manifest.json"
LOCAL = REPO / "ops/reqloop/g3_2/tasks"
REF = pathlib.Path("/home/user1/dev/ops/ref/bm_tasks/dabench")
SCREEN = REPO / "ops/audits/g3_2_bank_screen.py"

def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def check_precheck(manifest: dict, screen_stdout: str | None = None, *, ref_dir: pathlib.Path = REF, local_dir: pathlib.Path = LOCAL) -> List[str]:
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

    bank = manifest.get("bank", {})
    seen_set = bank.get("seen_set", [])
    ordering = bank.get("ordering", [])
    unseen = [x for x in ordering if x not in seen_set]
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

def check_fire_summary(rows: List[Dict[str, Any]]) -> List[str]:
    errors = []
    total_cells = len(rows)
    if total_cells == 0:
        return ["empty rows"]

    confirmed_reveries = 0
    for row in rows:
        cr = row.get("content_reverify")
        status = row.get("status")
        # H1(a): >= 1/4 cells have >= 1 round of content_reverify reaching deterministic verdict
        if cr is True and status in ["PASS", "FAIL"]:
            confirmed_reveries += 1

    # H1(a) check: we need to ensure that at least 1/4 of the total cells are accounted for.
    if confirmed_reveries < (total_cells / 4):
        errors.append(f"H1(a) failed: {confirmed_reveries}/{total_cells} cells met criteria")

    # H1(b): round 1 has confirmed gaps, all such cells in round 2 diff fixed >= 1 and regressed=0
    gaps = [r for r in rows if r.get("content_reverify") is True and r.get("status") == "UNKNOWN"]
    if gaps:
        for g in gaps:
            diff_fixed = g.get("diff_fixed", 0)
            regressed = g.get("regressed", False)
            # If it's a gap, we check the diff_fixed and regressed status.
            # The requirement is that for these specific cells (the gaps), they must be fixed in round 2.
            if diff_fixed < 1 or regressed is True:
                errors.append(f"H1(b) failed for gap {g.get('task_id')}: diff_fixed={diff_fixed}, regressed={regressed}")

    # UNKNOWN handling: not both PASS/FAIL
    for row in rows:
        status = str(row.get("status", "")).upper()
        if "BOTH" in status and ("PASS" in status and "FAIL" in status):
            errors.append(f"UNKNOWN handling failed for {row.get('task_id')}: both PASS/FAIL detected")

    # No superiority claims: status should not contain "superior" or "better"
    for row in rows:
        status = str(row.get("status", "")).lower()
        if "superior" in status or "better" in status:
            errors.append(f"Superiority claim detected in status: {status}")

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
