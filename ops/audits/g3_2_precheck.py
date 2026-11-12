#!/usr/bin/env python3
"""G3.2 預檢查（離線、0 model calls、只讀；工單 P20261111_2119-1＋R20261112_0820-1）。
核心口徑（與 g3_3_precheck 同形）：
1. manifest sha256 與任務輸入實檔一致——本地凍結副本（ops/reqloop/g3_2/tasks/）與
   ref 源（/home/user1/dev/ops/ref/bm_tasks/dabench/）逐一雙核（local == ref == manifest）；
2. 選題清單＝bank.ordering − seen_set 前 4 題，且恰合 tasks 順序
   （同 g3gate.unseen_selection / G3Plan.verify_frozen 口徑）；
3. 相容性篩選輸出（top4＋ranking＋排除集）的 sha256 與 manifest.screening 一致，
   且 screen 現行重跑決定性重算吻合（防 cherry-pick；screen 工具 --selftest C8 同核）；
4. 預算/臂形（fail-closed 底線，與 g3gate.check_budget 同口徑）。
不讀 hidden/scorer；不發射。
用法：python3 ops/audits/g3_2_precheck.py [--selftest]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
MAN = REPO / "ops/reqloop/g3_2/manifest.json"
LOCAL = REPO / "ops/reqloop/g3_2/tasks"
REF = pathlib.Path("/home/user1/dev/ops/ref/bm_tasks/dabench")
SCREEN = REPO / "ops/audits/g3_2_bank_screen.py"
EXPECTED_TIDS = ["dab_725", "dab_587", "dab_657", "dab_517"]


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_precheck(
    manifest: dict,
    screen_stdout: str | None = None,
    *,
    ref_dir: pathlib.Path = REF,
    local_dir: pathlib.Path = LOCAL,
) -> list[str]:
    """純函式預檢查（ref_dir/local_dir/screen_stdout 可注入）；回傳違規清單（空＝通過；fail-closed）。"""
    if not isinstance(manifest, dict):
        return ["輸入非 dict（fail-closed）"]
    e: list[str] = []
    if manifest.get("schema") != "vacant.reqloop.g3gate.plan/1":
        e.append(f"schema mismatch: {manifest.get('schema')!r}")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return e + ["tasks 缺失或空"]
    tids = [t.get("task_id") for t in tasks if isinstance(t, dict)]
    if tids != EXPECTED_TIDS:
        e.append(f"task 順序不符：{tids}")

    # 1) 逐檔 sha256：local == ref == manifest
    for t in tasks:
        if not isinstance(t, dict):
            e.append("task 非 dict")
            continue
        tid = t.get("task_id")
        files = t.get("files")
        if not isinstance(tid, str) or not isinstance(files, dict) or not files:
            e.append(f"task 形不符（task_id/files 缺失）：{tid!r}")
            continue
        for rel, want in files.items():
            lp, rp = local_dir / tid / rel, ref_dir / tid / rel
            if not lp.is_file():
                e.append(f"missing local: {lp}")
            elif sha256(lp) != want:
                e.append(f"local sha mismatch: {rel} (tid={tid})")
            if not rp.is_file():
                e.append(f"missing ref: {rp}")
            elif sha256(rp) != want:
                e.append(f"ref sha mismatch: {rel} (tid={tid})")

    # 2) 選題一致性（unseen_selection 同口徑：manifest 頂層 seen_set）
    seen_raw = manifest.get("seen_set")
    if not isinstance(seen_raw, list):
        e.append("seen_set 缺失或非 list")
        seen = set()
    else:
        seen = set(seen_raw)
    ordering = (manifest.get("bank") or {}).get("ordering") or []
    unseen = [x for x in ordering if x not in seen]
    if not (len(unseen) == 4 and unseen == EXPECTED_TIDS and unseen == tids):
        e.append(f"unseen 前 4 ≠ tasks：{unseen[:5]}")

    # 3) screen 輸出 hash 一致＋決定性重算（fail-closed）
    sc = manifest.get("screening")
    if not isinstance(sc, dict) or not isinstance(sc.get("output_sha256"), str):
        e.append("screening 或 screening.output_sha256 缺失")
    else:
        if screen_stdout is None:
            try:
                res = subprocess.run(
                    [sys.executable, str(SCREEN)],
                    capture_output=True, text=True, cwd=REPO, check=True,
                )
                screen_stdout = res.stdout
            except Exception as exc:
                e.append(f"failed to run screen tool: {exc}")
        if screen_stdout is not None:
            out_sha = hashlib.sha256(screen_stdout.encode("utf-8")).hexdigest()
            if out_sha != sc.get("output_sha256"):
                e.append(f"screen sha mismatch: {out_sha}")
            try:
                out_json = json.loads(screen_stdout)
                if out_json.get("top4") != EXPECTED_TIDS:
                    e.append(f"screen top4 ≠ tasks: {out_json.get('top4')}")
            except Exception as exc:
                e.append(f"screen stdout 非合法 JSON: {exc}")

    # 4) 預算/臂形（fail-closed 底線）
    if manifest.get("arms") != ["full_rloop"]:
        e.append(f"arms mismatch: {manifest.get('arms')}")
    b = manifest.get("budget")
    if not isinstance(b, dict):
        e.append("budget 缺失或非 dict")
    else:
        if not (b.get("max_cells") == 4 and b.get("timeout_s_per_round") == 300):
            e.append(f"預算形不符（max_cells/timeout_s_per_round）：{b.get('max_cells')}/{b.get('timeout_s_per_round')}")
        if not (b.get("daily_token_cap") == 2000000 and b.get("quota_fail_closed") is True):
            e.append("預算形不符（daily_token_cap/quota_fail_closed）")
        if not (b.get("model_entry") == "glm" and b.get("hard_token_cap") is False):
            e.append("預算形不符（model_entry/hard_token_cap）")
        if b.get("cost_missing") != "UNKNOWN":
            e.append(f"cost_missing mismatch: {b.get('cost_missing')!r}")

    return e


def run_selftest() -> int:
    m = json.loads(MAN.read_text(encoding="utf-8"))
    screen_out = subprocess.run(
        [sys.executable, str(SCREEN)], capture_output=True, text=True, cwd=REPO, check=True
    ).stdout
    controls = [
        ("正控制：真檔雙核＋選題＋screen 依據＋預算", not check_precheck(m, screen_out), check_precheck(m, screen_out)),
    ]
    n1 = copy.deepcopy(m)
    f0 = next(iter(n1["tasks"][0]["files"]))
    n1["tasks"][0]["files"][f0] = "0" * 64
    controls.append(("n1_bad_sha：manifest sha256 篡改必被攔截", bool(check_precheck(n1, screen_out)), None))

    n2a = copy.deepcopy(m)
    n2a["tasks"][0]["task_id"] = "dab_039"
    n2b = copy.deepcopy(m)
    n2b["seen_set"].append("dab_725")
    controls.append(("n2_bad_order：選題或 seen_set 篡改必被攔截",
                     bool(check_precheck(n2a, screen_out)) and bool(check_precheck(n2b, screen_out)), None))

    n3 = copy.deepcopy(m)
    n3["screening"]["output_sha256"] = "0" * 64
    controls.append(("n3_bad_screen_sha：screen 輸出 sha256 篡改必被攔截", bool(check_precheck(n3, screen_out)), None))

    n4a = copy.deepcopy(m)
    n4a["budget"]["timeout_s_per_round"] = 999
    n4b = copy.deepcopy(m)
    n4b["arms"] = ["native_pi"]
    controls.append(("n4_bad_budget：預算或臂形篡改必被攔截",
                     bool(check_precheck(n4a, screen_out)) and bool(check_precheck(n4b, screen_out)), None))

    controls.append(("n5_missing_ref：缺 ref_dir 必 fail-closed",
                     bool(check_precheck(m, screen_out, ref_dir=REPO / "nonexistent_ref_g32")), None))

    failed = [(name, detail) for name, passed, detail in controls if not passed]
    if failed:
        for name, detail in failed:
            print(f"CONTROL FAILED: {name}: {detail}")
        print("VERDICT: G3_2_PRECHECK_BROKEN")
        return 1
    print("checked: local==ref==manifest 逐檔；unseen==['dab_725','dab_587','dab_657','dab_517']；screen sha 吻合；預算 4 格/300s/2M/日/glm")
    print("正控制＋負控制 5（n1 sha 篡改／n2 選題篡改／n3 screen sha 篡改／n4 預算或臂形篡改／n5 缺 ref_dir）全如預期")
    print("VERDICT: G3_2_PRECHECK_OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋5 負控制")
    args = ap.parse_args()
    if args.selftest:
        return run_selftest()
    m = json.loads(MAN.read_text(encoding="utf-8"))
    errors = check_precheck(m)
    if errors:
        for err in errors:
            print("VIOLATION:", err)
        print("VERDICT: G3_2_PRECHECK_BROKEN")
        return 1
    print("VERDICT: G3_2_PRECHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
