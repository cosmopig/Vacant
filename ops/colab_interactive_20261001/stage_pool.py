#!/usr/bin/env python3
"""i1001 題池 staging（SPEC「Pool and screening」）：把 pool_lcb.json 的 LCB 題＋三個任務題庫的**全部**題
轉成 cell.sh 吃的題目目錄，寫 MANIFEST.json（每題 sha256、大小、角色、篩選抽樣）。零模型呼叫、不碰 Colab。

    python3 stage_pool.py --pool pool_lcb.json --lcb-src <colab_banks_20260927> --task-src <task_banks_20260927> \
        --c5-launch-record <launch_record_c5.json> --out <staged 根> [--seed 20261001] [--screen-n 10] [--vm-root /srv/eval/staged]

- LCB：呼叫 `stage_code_bank.py`（C5 同一支）只收池裡的題；樹與 C5 發射時釘的 `staged_tree_sha256` 對照用
  `--c5-launch-record`：**整個題庫**重新 staged 到暫存、用 launch_batch.sh 的 `tree()` 算雜湊、比對、刪掉
  ⇒ 池裡每一題的目錄與 C5 跑的逐位元組相同（整庫雜湊相同 ⇒ 每個子目錄相同）。
- 任務題庫：呼叫 `stage_task_bank.py`，三個題庫全部題 staged（篩選用 A 組跑 10 題；≥9/10 過的題庫由 lead 決定丟掉，
  不用的題庫不必上傳）。篩選抽樣 `random.Random(f"i1001-{seed}-{bank}").sample(排序後的 id, n)`，結果排序。
- 洩漏掃描：工作區裡沒有 hidden／reference／example／expected 之類的檔名；LCB 只在隱藏裡的 case 的 `args` 行不出現在
  工作區任何檔；資料題的標準答案不出現在 goal.md／contract.md；polyglot 的工作區沒有解答檔。
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
LCB = ("lcb_v1", "lcb_v2", "lcb_v3")
TASK = ("dabench", "databench", "polyglot_py")
BAD_NAMES = re.compile(r"hidden|reference|reproduc|expected|example\.py|solution|answer\.txt", re.I)


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree(d: pathlib.Path) -> str:
    """launch_batch.sh 的 tree()（逐字同一個算法）。"""
    m = hashlib.sha256()
    for f in sorted(pathlib.Path(d).rglob("*")):
        if f.is_file():
            m.update(str(f.relative_to(d)).encode() + b"\0" + hashlib.sha256(f.read_bytes()).digest())
    return m.hexdigest()


def run(cmd: list[str]) -> list[dict]:
    r = subprocess.run([sys.executable, *cmd], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"staging failed: {cmd[0]}\n{r.stderr[-1500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def leak_scan(bank: str, tdir: pathlib.Path) -> list[str]:
    ws = tdir / "workspace"
    bad: list[str] = []
    texts: dict[str, str] = {}
    for f in sorted(ws.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(ws).as_posix()
        if bank in LCB and rel.startswith("tests_visible/test_visible.py") is False and BAD_NAMES.search(rel):
            bad.append(f"name:{rel}")
        elif bank not in LCB and bank != "polyglot_py" and BAD_NAMES.search(rel.replace("answer.txt", "")):
            bad.append(f"name:{rel}")
        if f.suffix in (".md", ".py", ".txt", ".sh"):
            texts[rel] = f.read_text(errors="replace")
    if bank in LCB:
        vis = texts.get("tests_visible/test_visible.py", "")
        hid = (tdir / "hidden" / "test_hidden.py").read_text()
        vis_args = {l.strip() for l in vis.splitlines() if l.strip().startswith("args = ")}
        only = [l.strip() for l in hid.splitlines() if l.strip().startswith("args = ") and l.strip() not in vis_args]
        blob = "\n".join(texts.values())
        for l in only:
            if l in blob:
                bad.append("hidden-only case args present in workspace")
                break
        if "test_hidden" in blob and "NOT part of any workspace" in blob:
            bad.append("hidden test header present in workspace")
    else:
        exp = json.loads((tdir / "hidden" / "expected.json").read_text())
        prose = texts.get("goal.md", "") + "\n" + texts.get("contract.md", "")
        if bank == "dabench":
            for name, val in exp["common_answers"]:
                if f"@{name}[{val}]" in prose:
                    bad.append(f"answer literal @{name}[{val}] in prose")
        elif bank == "databench":
            ans = str(exp["answer"]).strip()
            # boolean 的答案只有 True／False，contract 本來就寫「boolean 寫 True 或 False」——不是洩漏，不掃
            if exp.get("type") != "boolean" and len(ans) >= 4 and ans in prose:
                bad.append("answer text in prose")
        else:
            sol = exp["solution_file"]
            if (ws / sol).exists():
                bad.append(f"solution file {sol} present in workspace")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, type=pathlib.Path)
    ap.add_argument("--lcb-src", required=True, type=pathlib.Path)
    ap.add_argument("--task-src", required=True, type=pathlib.Path)
    ap.add_argument("--c5-launch-record", type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--seed", type=int, default=20261001)
    ap.add_argument("--screen-n", type=int, default=10)
    ap.add_argument("--vm-root", default="/srv/eval/staged")
    ap.add_argument("--source-ref", default="", help="題庫取自哪個 git ref／sha（寫進 MANIFEST）")
    ap.add_argument("--verify", nargs="*", default=[], type=pathlib.Path,
                    help="量具輸出（verify_lcb_scorer.py／verify_task_banks.py 的 JSON）：把 sha256 與摘要寫進 MANIFEST")
    a = ap.parse_args()

    pool = json.loads(a.pool.read_text())
    if a.out.exists():
        shutil.rmtree(a.out)
    a.out.mkdir(parents=True)
    tasks: list[dict] = []

    # ── LCB：只收池裡的題 ──
    parity: dict[str, dict] = {}
    for b in LCB:
        ids = sorted(r["id"] for r in pool["pool"] if r["bank"] == b)
        roles = {r["id"]: r["role"] for r in pool["pool"] if r["bank"] == b}
        got = run([str(HERE / "stage_code_bank.py"), "--bank", b, "--templates", str(a.lcb_src / b / "templates"),
                   "--hidden", str(a.lcb_src / b / "hidden"), "--out", str(a.out), "--vm-root", a.vm_root, "--ids", *ids])
        assert [t["id"] for t in got] == ids
        for t in got:
            tasks.append({**t, "role": roles[t["id"]], "family": "lcb"})
    if a.c5_launch_record:
        want = json.loads(a.c5_launch_record.read_text())["staged_tree_sha256"]
        with tempfile.TemporaryDirectory(prefix="i1001_c5parity_") as tmp:
            for b in LCB:
                run([str(HERE / "stage_code_bank.py"), "--bank", b, "--templates", str(a.lcb_src / b / "templates"),
                     "--hidden", str(a.lcb_src / b / "hidden"), "--out", tmp])
                h = tree(pathlib.Path(tmp) / b)
                parity[b] = {"c5_staged_tree_sha256": want[b], "restaged_full_bank_tree_sha256": h, "equal": h == want[b],
                             "n_tasks_full_bank": len(list((pathlib.Path(tmp) / b).iterdir()))}
        if not all(v["equal"] for v in parity.values()):
            raise SystemExit(f"C5 tree parity FAILED: {parity}")

    # ── 任務題庫：全部題 ──
    screen: dict[str, list[str]] = {}
    for b in TASK:
        got = run([str(HERE / "stage_task_bank.py"), "--bank", b, "--templates", str(a.task_src / b / "templates"),
                   "--hidden", str(a.task_src / b / "hidden"), "--scorer", str(HERE / "scorers" / f"{b}.py"),
                   "--out", str(a.out), "--vm-root", a.vm_root])
        ids = sorted(t["id"] for t in got)
        screen[b] = sorted(random.Random(f"i1001-{a.seed}-{b}").sample(ids, a.screen_n))
        for t in got:
            tasks.append({**t, "role": "screen_sample" if t["id"] in screen[b] else "task_bank_rest", "family": "task"})

    # ── 掃描與雜湊 ──
    leaks: dict[str, list[str]] = {}
    rows = []
    for t in sorted(tasks, key=lambda x: (x["bank"], x["id"])):
        d = a.out / t["bank"] / t["id"]
        files = [f for f in d.rglob("*") if f.is_file()]
        bad = leak_scan(t["bank"], d)
        if bad:
            leaks[f'{t["bank"]}/{t["id"]}'] = bad
        rows.append({**t, "tree_sha256": tree(d), "n_files": len(files), "bytes": sum(f.stat().st_size for f in files),
                     "scorer_sha256": sha(d / "scorer.py"), "instruction_sha256": sha(d / "instruction.txt")})
    banks = {}
    for b in LCB + TASK:
        br = [r for r in rows if r["bank"] == b]
        if br:
            banks[b] = {"n_tasks": len(br), "bytes": sum(r["bytes"] for r in br), "subset_tree_sha256": tree(a.out / b),
                        "roles": {k: sum(1 for r in br if r["role"] == k) for k in sorted({r["role"] for r in br})}}
    verification = {}
    for vp in a.verify:
        v = json.loads(vp.read_text())
        brief = {k: (val if not isinstance(val, dict) else {kk: vv for kk, vv in val.items() if kk not in ("rows", "violations", "mismatches")})
                 for k, val in v.items() if k not in ("rows", "failures")}
        if "rescore_c5" in v:
            brief["rescore_c5"]["n_mismatch"] = len(v["rescore_c5"]["mismatches"])
            brief["rescore_c5"]["mismatch_cells"] = [f'{m["task"]}:{m["arm"]}' for m in v["rescore_c5"]["mismatches"]]
        verification[vp.name] = {"sha256": sha(vp), "summary": brief}
    tools = {p.name: sha(p) for p in sorted([*HERE.glob("*.py"), *(HERE / "scorers").glob("*.py")])
             if p.name not in ("stage_pool.py",)}
    out = {"schema": "i1001.staged_manifest/1", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "seed": a.seed, "screen_n": a.screen_n, "vm_root": a.vm_root, "source_ref": a.source_ref,
           "instruction_sentence": (a.out / rows[0]["bank"] / rows[0]["id"] / "instruction.txt").read_text().strip(),
           "pool_lcb_sha256": sha(a.pool), "stage_pool_py_sha256": sha(pathlib.Path(__file__)),
           "stage_tools_sha256": tools, "c5_tree_parity": parity, "leak_scan_violations": leaks, "verification": verification,
           "screen_sample": screen, "banks": banks,
           "totals": {"n_tasks": len(rows), "bytes": sum(r["bytes"] for r in rows), "n_files": sum(r["n_files"] for r in rows)},
           "tasks": rows}
    (a.out / "MANIFEST.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    (a.out / "tasks_index.json").write_text(json.dumps(
        [{"bank": r["bank"], "id": r["id"], "dir": r["dir"], "role": r["role"]} for r in rows], ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"totals": out["totals"], "banks": banks, "leaks": leaks, "parity": {k: v["equal"] for k, v in parity.items()}},
                     ensure_ascii=False))
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
