#!/usr/bin/env python3
import json
import hashlib
import os
import sys
from pathlib import Path

MANIFEST_PATH = Path("ops/reqloop/g3_1/manifest.json")
REF_DIR = Path("/home/user1/dev/ops/ref/bm_tasks/dabench/")

def get_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def precheck():
    if not MANIFEST_PATH.exists():
        print("Error: manifest.json not found at ops/reqloop/g3_1/manifest.json")
        sys.exit(1)

    with open(MANIFEST_PATH, "r") as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    for task in tasks:
        task_id = task.get("task_id")
        print(f"Checking {task_id}...")
        
        # Check instruction.txt
        inst_path = REF_DIR / task_id / "instruction.txt"
        if not inst_path.exists():
            print(f"  FAILED: {inst_path} missing")
            sys.exit(1)
        
        inst_sha = get_sha256(inst_path)
        expected_inst_sha = task.get("instruction_sha256")
        if inst_sha != expected_inst_sha:
            print(f"  FAILED: {task_id} instruction.txt hash mismatch (got {inst_sha}, want {expected_inst_sha})")
            sys.exit(1)

        # Check data files
        data_files = task.get("data_files", [])
        for df in data_files:
            df_path = REF_DIR / task_id / "workspace" / df["path"]
            if not df_path.exists():
                print(f"  FAILED: {df_path} missing")
                sys.exit(1)
            
            df_sha = get_sha256(df_path)
            expected_df_sha = df["sha256"]
            if df_sha != expected_df_sha:
                print(f"  FAILED: {task_id} {df['path']} hash mismatch (got {df_sha}, want {expected_df_sha})")
                sys.exit(1)

    print("VERDICT: G3_1_PRECHECK_OK")

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        # For selftest, we just run the check as is since it's already pointing to real files
        precheck()
    else:
        precheck()
