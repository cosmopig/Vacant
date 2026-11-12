#!/usr/bin/env python3
"""G3.3 預檢查（離線、0 model calls、只讀；票 P20261112_0119-1＋R20261112_0455-1）。
核心口徑（與 g3_2_precheck 同形；選題規則換成 G3.3 的 H2 依據）：
1. manifest sha256 與任務輸入實檔一致——本地凍結副本（ops/reqloop/g3_3/tasks/）與
   ref 源（/home/user1/dev/ops/ref/bm_tasks/dabench/）逐一雙核（local == ref == manifest）；
2. 選題一致性＝bank.ordering − seen_set 前 1 題恰為 tasks 順序
   （同 ggate.unseen_selection / G3Plan.verify_frozen 口徑）；
3. 選題規則機械核（防 cherry-pick）：G3.2 H0 預跑報告
   （ops/audits/g3_2_h0_prerun_report.json）中恰 1 題 n_deterministic_claims≥1，
   且該題＝dab_725（G3.3 唯一目標題；假說 §2）；
4. 預算/臂形（fail-closed 底線，與 g3gate.check_budget 同口徑）。
R20261112_0455-1：抽離純函式 check_precheck(manifest, prerun, *, ref_dir=REF)
（回傳違規清單 list[str]，空＝通過；ref_dir 可注入）；--selftest＝正控制＋4 負控制
（n1 sha 篡改／n2 選題篡改／n3 H0 依據篡改／n4 預算或臂形篡改，任一漏判即 rc≠0）。
口徑差異說明：票面探針的欄位名（input_files／max_WallTime_sec／
all_calls_zero_deterministic_claims／4 臂）與凍結 manifest 實際 schema（files／
timeout_s_per_round／逐題 n_deterministic_claims／arms=["full_rloop"]）不符，
負控制按實際 schema 實作，4 類篡改覆蓋同義；票尾已記錄。
不讀 hidden/scorer；不發射。
用法：python3 ops/audits/g3_3_precheck.py [--selftest]
  （無參＝跑一次預檢查，違規即 rc=1；--selftest＝正控制＋4 負控制）
"""
import argparse
import copy
import hashlib
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = REPO / "ops/reqloop/g3_3/manifest.json"
LOCAL = REPO / "ops/reqloop/g3_3/tasks"
REF = pathlib.Path("/home/user1/dev/ops/ref/bm_tasks/dabench")
PRERUN = REPO / "ops/audits/g3_2_h0_prerun_report.json"
TARGET = "dab_725"


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_precheck(manifest: dict, prerun: dict, *, ref_dir: pathlib.Path = REF) -> list[str]:
    """純函式預檢查（ref_dir 可注入）；回傳違規訊息清單（空清單＝通過；fail-closed）。"""
    if not isinstance(manifest, dict) or not isinstance(prerun, dict):
        return ["輸入非 dict（fail-closed）"]
    e: list[str] = []
    if manifest.get("schema") != "vacant.reqloop.g3gate.plan/1":
        e.append(f"schema mismatch: {manifest.get('schema')!r}")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return e + ["tasks 缺失或空"]
    tids = [t.get("task_id") for t in tasks]
    if tids != [TARGET]:
        e.append(f"任務順序不符（G3.3 唯一目標題＝{TARGET}）：{tids}")
    # 1) 逐檔 sha256：local == ref == manifest
    for t in tasks:
        tid = t.get("task_id")
        files = t.get("files")
        if not isinstance(tid, str) or not isinstance(files, dict):
            e.append(f"task 形不符（task_id/files 缺失）：{tid!r}")
            continue
        for rel, want in files.items():
            lp, rp = LOCAL / tid / rel, ref_dir / tid / rel
            if not lp.is_file():
                e.append(f"missing local: {rel}")
                continue
            if not rp.is_file():
                e.append(f"missing ref: {rel}")
                continue
            if sha256(lp) != want:
                e.append(f"local sha mismatch: {rel}")
            if sha256(rp) != want:
                e.append(f"ref sha mismatch: {rel}")
    # 2) 選題一致性（unseen_selection 同口徑：前 1 未見題）
    seen = set(manifest.get("seen_set") or [])
    ordering = (manifest.get("bank") or {}).get("ordering") or []
    unseen = [x for x in ordering if x not in seen]
    if not (len(unseen) == 1 and unseen == tids):
        e.append(f"unseen 前 1 ≠ tasks：{unseen[:4]}")
    # 3) 選題規則機械核：G3.2 H0 預跑恰 1 題具確定性 claim 且＝dab_725
    hit = [t.get("task_id") for t in (prerun.get("tasks") or [])
           if isinstance(t, dict) and t.get("n_deterministic_claims", 0) >= 1]
    if hit != [TARGET]:
        e.append(f"H0 預跑具確定性 claim 題應恰為 [{TARGET}]：{hit}")
    # 4) 預算/臂形（fail-closed 底線）
    if manifest.get("arms") != ["full_rloop"]:
        e.append(f"arms 不符：{manifest.get('arms')}")
    b = manifest.get("budget") or {}
    if not (b.get("max_cells") == 1 and b.get("timeout_s_per_round") == 300):
        e.append(f"預算形不符（max_cells/timeout_s_per_round）：{b.get('max_cells')}/{b.get('timeout_s_per_round')}")
    if not (b.get("daily_token_cap") == 2000000 and b.get("quota_fail_closed") is True):
        e.append("預算形不符（daily_token_cap/quota_fail_closed）")
    if not (b.get("model_entry") == "glm" and b.get("hard_token_cap") is False):
        e.append("預算形不符（model_entry/hard_token_cap）")
    if b.get("cost_missing") != "UNKNOWN":
        e.append(f"cost_missing 須 UNKNOWN：{b.get('cost_missing')!r}")
    return e


def _load() -> tuple[dict, dict]:
    return (json.loads(MANIFEST.read_text(encoding="utf-8")),
            json.loads(PRERUN.read_text(encoding="utf-8")))


def _report(controls: list) -> int:
    failed = [(n, d) for n, passed, d in controls if not passed]
    if failed:
        for n, d in failed:
            print(f"CONTROL FAILED: {n}: {d}")
        print("VERDICT: G3_3_PRECHECK_BROKEN")
        return 1
    print("checked: local==ref==manifest 逐檔；unseen==[dab_725]；H0 預跑恰 1 題達；預算 1 格/300s/2M/日/glm")
    print("正控制＋負控制 4（n1 sha 篡改／n2 選題篡改／n3 H0 依據篡改／n4 預算或臂形篡改）全如預期")
    print("VERDICT: G3_3_PRECHECK_OK")
    return 0


def selftest() -> int:
    m, p = _load()
    controls = [("正控制：真檔雙核＋選題＋H0 依據＋預算", not check_precheck(m, p), check_precheck(m, p))]
    n1 = copy.deepcopy(m)
    f0 = next(iter(n1["tasks"][0]["files"]))
    n1["tasks"][0]["files"][f0] = "0" * 64
    controls.append(("n1_bad_sha：manifest sha256 篡改必被攔截", bool(check_precheck(n1, p)), None))
    n2 = copy.deepcopy(m)
    n2["tasks"][0]["task_id"] = "dab_039"
    controls.append(("n2_bad_order：選題篡改必被攔截", bool(check_precheck(n2, p)), None))
    n3 = copy.deepcopy(p)
    for t in n3.get("tasks", []):
        if t.get("task_id") == TARGET:
            t["n_deterministic_claims"] = 0
    controls.append(("n3_h0_not_zero：H0 預跑依據篡改必被攔截", bool(check_precheck(m, n3)), None))
    n4a = copy.deepcopy(m)
    n4a["budget"]["timeout_s_per_round"] = 999
    n4b = copy.deepcopy(m)
    n4b["arms"] = ["native_pi", "reqlist_only", "full_rloop"]
    controls.append(("n4_bad_budget：預算或臂形篡改必被攔截",
                     bool(check_precheck(n4a, p)) and bool(check_precheck(n4b, p)), None))
    return _report(controls)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    m, p = _load()
    v = check_precheck(m, p)
    if v:
        for s in v:
            print("VIOLATION:", s)
        print("VERDICT: G3_3_PRECHECK_FAIL")
        return 1
    print(f"checked: local==ref==manifest ×{sum(len(t['files']) for t in m['tasks'])} 檔；"
          f"unseen==[{TARGET}]；H0 預跑恰 1 題達；預算 1 格/300s/2M/日/glm")
    print("VERDICT: G3_3_PRECHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
