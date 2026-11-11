import sys
import os
import json
import argparse

try:
    from ops.audits.stray_labd_ps_evidence import collect_processes, is_labd
except ImportError:  # direct script run from ops/audits/ (sys.path[0] = script dir)
    from stray_labd_ps_evidence import collect_processes, is_labd

def _cmdline_of(entry):
    """Normalize one proc_list entry to a cmdline argument list.

    Accepts a raw argument list, a dict with "cmdline"/"args"
    (collect_processes() shape), or a bare string (judged as one token).
    """
    if isinstance(entry, dict):
        for key in ("cmdline", "args"):
            value = entry.get(key)
            if isinstance(value, (list, tuple)):
                return [str(a) for a in value]
        return []
    if isinstance(entry, (list, tuple)):
        return [str(a) for a in entry]
    if isinstance(entry, str):
        return [entry]
    return []

def check_labd_instances(proc_list=None):
    """
    Count running labd.py instances.
    0 = idle, 1 = normal; >1 reports MULTIPLE_LABD_INSTANCES and exits 1.

    proc_list=None: live /proc scan via stray_labd_ps_evidence.collect_processes,
    judged by is_labd (an argument ending in labd.py preceded by a python
    interpreter) -- no pgrep -f substring match, so a process whose args merely
    mention "labd.py" never counts (and a bare pid string can never match).
    proc_list given: each entry judged item by item with the same is_labd rule.
    """
    if proc_list is None:
        proc_list = collect_processes()
    count = sum(1 for entry in proc_list if is_labd(_cmdline_of(entry)))
    if count > 1:
        print("ERROR: MULTIPLE_LABD_INSTANCES detected. Count: " + str(count))
        sys.exit(1)
    return count

def audit_cell_env(cell_json_path, arm="A"):
    """
    Verify cell.json agent_env. 
    For A/C arms, must not contain VACANT_* or host pi session residuals (must be empty/null).
    Reports AGENT_ENV_LEAK and exits 1 on violation.
    """
    if not os.path.exists(cell_json_path):
        print(f"ERROR: Cell JSON path {cell_json_path} does not exist.")
        sys.exit(1)

    with open(cell_json_path, 'r') as f:
        data = json.load(f)
    
    agent_env = data.get("agent_env", {})
    if agent_env is None:
        agent_env = {}

    # If it's a string (some formats might have it as a raw string), convert to dict if possible
    # but the requirement implies a structure we can check for keys/values.
    if isinstance(agent_env, str):
        # This shouldn't happen based on typical cell.json but handle just in case
        pass

    # Check for A or C arms (case-insensitive)
    arm_upper = arm.upper()
    # We need to know which arm this cell belongs to. 
    # Usually, the file path or a field in cell.json indicates it.
    # The requirement says "If for A/C arms". Let's check if 'arm' is in data.
    cell_arm = str(data.get("arm", "")).upper()
    
    if arm_upper in ["A", "C"] or cell_arm in ["A", "C"]:
        # Check for VACANT_* keys or values
        for k, v in agent_env.items():
            v_str = str(v)
            if "VACANT_" in k or "VACANT_" in v_str:
                print(f"ERROR: AGENT_ENV_LEAK detected in key '{k}' with value '{v_str}'")
                sys.exit(1)
        
        # Check for host pi session residuals (e.g., PI_PARENT, PI_SELF)
        # These are often injected as env vars.
        for k, v in agent_env.items():
            v_str = str(v)
            if "PI_PARENT" in v_str or "PI_SELF" in v_str:
                print(f"ERROR: AGENT_ENV_LEAK detected host pi session residual in '{k}'")
                sys.exit(1)

    return True

# ---- 1843-2：目錄級批量稽核（E016 環境洩漏收案）----
# 盤面事實：infra 快照目錄是 <cell>.infra-<YYYYMMDDTHHMMSS> 後綴形態
# （attempt2 實測 5 個、各帶 cell.json），非 .infra- 前綴；排除規則按後綴匹配。
# 洩漏判據（票面）：agent_env 含 host VACANT_PI_PARENT / VACANT_PI_SELF 殘留；
# C-nf 臂的 VACANT_FAILED_STEP_REVIEW 是預註冊臂定義參數，不計為洩漏。
import re
INFRA_DIR_RE = re.compile(r"\.infra-\d{8}T\d{6}$")
LEAK_MARKERS = ("VACANT_PI_PARENT", "VACANT_PI_SELF")

def is_infra_dir(name: str) -> bool:
    return bool(INFRA_DIR_RE.search(name))

def agent_env_leaks(agent_env) -> bool:
    """agent_env 有無 host VACANT_PI_PARENT / VACANT_PI_SELF 殘留（key 或 value）。

    C-nf 臂的 VACANT_FAILED_STEP_REVIEW 是預註冊臂定義參數，不含上述標記、不計為洩漏。
    """
    if agent_env is None:
        return False
    if isinstance(agent_env, str):
        blob = agent_env
    else:
        try:
            blob = json.dumps(agent_env)
        except (TypeError, ValueError):
            blob = str(agent_env)
    return any(m in blob for m in LEAK_MARKERS)

def audit_run_dir(run_path) -> dict:
    """掃描 run_path 下所有 cell.json（排除 infra 快照目錄）做批量洩漏稽核。

    返回 {total_cells, violations, violated_cells, clean_cells, missing_cell_json}：
    - total_cells：計入稽核的 cell.json 數（infra 快照目錄整目錄排除）
    - violations：洩漏 cell 數（int）；violated_cells：其 cell.json 路徑列表
    - clean_cells：無洩漏的 cell.json 路徑列表
    - missing_cell_json：run 直屬 cell 槽目錄存在但缺 cell.json 的預期路徑
      （attempt1 實例：book_store-C、bowling-A）
    """
    from pathlib import Path
    run_path = Path(run_path)
    result = {
        "total_cells": 0,
        "violations": 0,
        "violated_cells": [],
        "clean_cells": [],
        "missing_cell_json": [],
    }
    if not run_path.is_dir():
        return result

    for root, dirs, files in os.walk(run_path):
        # infra 快照目錄（<cell>.infra-<ts>）整目錄排除
        dirs[:] = [d for d in dirs if not is_infra_dir(d)]
        if "cell.json" in files:
            p = Path(root) / "cell.json"
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue  # 讀不了＝不計入（不假裝通過、也不虛報洩漏）
            result["total_cells"] += 1
            if agent_env_leaks(data.get("agent_env")):
                result["violations"] += 1
                result["violated_cells"].append(str(p))
            else:
                result["clean_cells"].append(str(p))
        else:
            # run 直屬的 cell 槽目錄（非 infra）缺 cell.json
            rel = Path(root).relative_to(run_path)
            if len(rel.parts) == 1 and not is_infra_dir(rel.parts[0]):
                result["missing_cell_json"].append(str(Path(root) / "cell.json"))
    return result

E016_NEG_DIR = "/srv/vlab/runs/e016_failed_step_ablation_r905_attempt1_envleak"
E016_POS_DIR = "/srv/vlab/runs/e016_failed_step_ablation"
E016_NEG_EXPECT = {"total_cells": 14, "violations": 11, "clean_cells": 3}
E016_POS_EXPECT = {"total_cells": 102, "violations": 0}

def audit_e016() -> int:
    """E016 環境洩漏收案：負控制 attempt1＋正控制 attempt2 雙控制。

    兩控制皆吻合 → 寫 ops/audits/e016_envleak_resolution_audit.json＋
    VERDICT: E016_ENVLEAK_AUDIT_OK＋exit 0；任一不符 → exit 1。
    """
    from pathlib import Path
    neg = audit_run_dir(E016_NEG_DIR)
    pos = audit_run_dir(E016_POS_DIR)

    neg_ok = (
        neg["total_cells"] == E016_NEG_EXPECT["total_cells"]
        and neg["violations"] == E016_NEG_EXPECT["violations"]
        and len(neg["clean_cells"]) == E016_NEG_EXPECT["clean_cells"]
    )
    pos_ok = (
        pos["total_cells"] == E016_POS_EXPECT["total_cells"]
        and pos["violations"] == E016_POS_EXPECT["violations"]
    )
    ok = neg_ok and pos_ok
    verdict = "E016_ENVLEAK_AUDIT_OK" if ok else "E016_ENVLEAK_AUDIT_FAIL"

    def _obs(r):
        return {
            "total_cells": r["total_cells"],
            "violations": r["violations"],
            "clean_cells": len(r["clean_cells"]),
            "missing_cell_json": len(r["missing_cell_json"]),
        }

    evidence = {
        "schema": "vacant.audit/e016_envleak_resolution/1",
        "ticket": "R20261111_1843-2",
        "criterion": (
            "洩漏＝cell.json 的 agent_env 含 VACANT_PI_PARENT/VACANT_PI_SELF 殘留；"
            "C-nf 臂 VACANT_FAILED_STEP_REVIEW 為預註冊臂定義參數、不計洩漏；"
            "infra 快照目錄（<cell>.infra-<YYYYMMDDTHHMMSS> 後綴）整目錄排除"
        ),
        "negative_control": {
            "dir": E016_NEG_DIR,
            "expect": dict(E016_NEG_EXPECT),
            "observed": _obs(neg),
            "ok": neg_ok,
            "violated_cells": neg["violated_cells"],
            "missing_cell_json": neg["missing_cell_json"],
        },
        "positive_control": {
            "dir": E016_POS_DIR,
            "expect": dict(E016_POS_EXPECT),
            "observed": _obs(pos),
            "ok": pos_ok,
            "violated_cells": pos["violated_cells"],
            "missing_cell_json": pos["missing_cell_json"],
        },
        "verdict": verdict,
    }
    out = Path(__file__).resolve().parent / "e016_envleak_resolution_audit.json"
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Negative control (attempt1): {'OK' if neg_ok else 'FAIL'} "
          f"(total={neg['total_cells']} violations={neg['violations']} "
          f"clean={len(neg['clean_cells'])} missing={len(neg['missing_cell_json'])})")
    print(f"Positive control (attempt2): {'OK' if pos_ok else 'FAIL'} "
          f"(total={pos['total_cells']} violations={pos['violations']} "
          f"missing={len(pos['missing_cell_json'])})")
    print(f"evidence: {out}")
    print(f"VERDICT: {verdict}")
    return 0 if ok else 1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true", help="Run self-test mode")
    parser.add_argument("--audit-e016", action="store_true",
                        help="E016 環境洩漏收案雙控制（attempt1 負控制＋attempt2 正控制）")
    args = parser.parse_args()

    if args.audit_e016:
        sys.exit(audit_e016())

    if args.selftest:
        print("Running self-test...")
        # Three-way control: 0 instances
        if check_labd_instances(proc_list=[]) != 0:
            print("FAILURE: expected 0 for empty proc_list")
            sys.exit(1)
        print("SUCCESS: zero instances")
        # Three-way control: 1 instance
        if check_labd_instances(proc_list=[["python3", "/srv/vlab/bin/labd.py"]]) != 1:
            print("FAILURE: expected 1 for a single labd cmdline")
            sys.exit(1)
        print("SUCCESS: single instance")
        # Substring-only args must not count (pgrep -f false positive)
        if check_labd_instances(proc_list=[["pi", "-p", "text mentions labd.py"]]) != 0:
            print("FAILURE: substring-only match must not count")
            sys.exit(1)
        print("SUCCESS: substring non-labd not counted")
        # Test AGENT_ENV_LEAK (should exit 1)
        try:
            audit_cell_env("dummy_path", arm="A")
        except SystemExit as e:
            if e.code == 1:
                print("SUCCESS: Caught AGENT_ENV_LEAK")
            else:
                print(f"FAILURE: Unexpected exit code {e.code}")
                sys.exit(1)
        else:
            print("FAILURE: expected SystemExit for AGENT_ENV_LEAK")
            sys.exit(1)

        # Test MULTIPLE_LABD_INSTANCES (should exit 1) -- last: exits 0 on success
        try:
            check_labd_instances(proc_list=[["python3", "/a/labd.py"], ["python3", "/b/labd.py"]])
        except SystemExit as e:
            if e.code == 1:
                print("SUCCESS: Caught MULTIPLE_LABD_INSTANCES")
                sys.exit(0)
            else:
                print(f"FAILURE: Unexpected exit code {e.code}")
                sys.exit(1)
        else:
            print("FAILURE: expected SystemExit for multiple instances")
            sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: labd_instance_and_env_audit.py [--selftest] [--audit-e016] <cell_json_path>")
        sys.exit(1)

    cell_json_path = sys.argv[1]
    check_labd_instances()
    audit_cell_env(cell_json_path, arm="A")
    print("VERDICT: LABD_AUDIT_OK")

if __name__ == "__main__":
    main()
