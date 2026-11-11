#!/usr/bin/env python3
"""G3.1 manifest 前置檢查（0 model calls、離線）。

對照 ops/reqloop/g3_1/manifest.json（vacant.reqloop.g3gate.plan/1）與任務庫源
（/home/user1/dev/ops/ref/bm_tasks/dabench/）：
1. 逐題逐檔 sha256 一致（manifest files map vs ref 源檔）；
2. 選題規則一致：bank.ordering − seen_set 的前 4 題 == manifest 任務順序
   （與 g3gate.unseen_selection 同口徑，防 cherry-pick）。

P20261111_1315-1：manifest 升級為 g3gate plan schema 後本腳本隨之改讀
`files` map（舊 `instruction_sha256`/`data_files` 形已廢）。
"""
import json
import hashlib
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

    if data.get("schema") != "vacant.reqloop.g3gate.plan/1":
        print(f"Error: schema 不符（got {data.get('schema')!r}）")
        sys.exit(1)

    tasks = data.get("tasks", [])
    if len(tasks) != 4:
        print(f"Error: 預期 4 題，got {len(tasks)}")
        sys.exit(1)
    for task in tasks:
        task_id = task.get("task_id")
        files = task.get("files", {})
        if not files:
            print(f"Error: {task_id} 無 files map")
            sys.exit(1)
        print(f"Checking {task_id}...")
        for rel, want in files.items():
            src = REF_DIR / task_id / rel
            if not src.exists():
                print(f"  FAILED: {src} missing")
                sys.exit(1)
            got = get_sha256(src)
            if got != want:
                print(f"  FAILED: {task_id} {rel} hash mismatch (got {got}, want {want})")
                sys.exit(1)

    # 選題規則（與 g3gate.unseen_selection 同口徑）：bank 順序 − seen_set 前 4 題
    ordering = (data.get("bank") or {}).get("ordering") or []
    seen = set(data.get("seen_set") or [])
    expected = [t for t in ordering if t not in seen][:4]
    actual = [t["task_id"] for t in tasks]
    if expected != actual:
        print(f"FAILED: 選題與規則不一致：{actual} ≠ {expected}")
        sys.exit(1)

    print("VERDICT: G3_1_PRECHECK_OK")

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        precheck()
    else:
        print(__doc__)
