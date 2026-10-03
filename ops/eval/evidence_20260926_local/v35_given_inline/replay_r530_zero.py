#!/usr/bin/env python3
"""R530 的 SOLO 紀錄離線重播零設定的交件前檢查（v3.4 對 v3.5；沒有模型、沒有 docker）。

⚠ 這一份是候選 2 的重播腳本（`../candidate2/`）改的：拿掉 `runner_run`／`QUESTION_END`（v3.4／v3.5 沒有），
多記每一格的 `findings`、全部步驟與點名的檔，不刪每格的暫存。下面的說明原本是給候選 2 的，做法相同。
用法：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<repo> python replay_r530_zero.py --repo <repo> --out <dir> --inproc`，
`sumup.py <cells.jsonl>` 算退回幾格、全對的退回幾格、各類幾格。


這支在架構裡承重什麼：`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §六-1 的擋門——候選 2
（「最後一次自己跑的測試失敗卻說做完」）要先在**錄好的、有跑測試的紀錄**上量準確度（≥ 0.8）、在問人的回合
0 次誤退，才算過。R530（`decisions/DECISION_20260913_R530_OPEN_GOAL_WITH_WITHOUT_VACANT_PREREG.md`）的 SOLO 臂＝
agent 自己做、說做完就收，每一格有它的殼層步驟（指令、結束碼、輸出）、最後的訊息、隱藏測試的結果。

做法（每一格）：
1. 工作區從 `ops/gain/r530/templates/<題>` 照 `openwork_arms.prepare_workspace` 的方式重建（`cp -a`＋空 git 起點），
   起始樹雜湊對 `rows.jsonl` 的 `ws_start_sha256`。
2. 新的 `VACANT_HOME`／`HOME`，`install.json` 的 `mode=evidence`（就是 `vacant install` 之後的樣子）。
3. 經過**真的掛鉤路徑** `hook.handle("claude", …)`：`UserPromptSubmit`（題目原文）→ 每一個殼層步驟
   `PreToolUse` → 在 bwrap 沙箱裡**重新執行那個指令**（只為了讓工作區的檔案照原樣變化；網路隔離、只有工作區可寫）
   → `PostToolUse`（結束碼 0）或 `PostToolUseFailure`（`Exit code N` ＋原本的輸出；逾時寫成 Claude 的逾時訊息）。
   送給掛鉤的輸出與結束碼一律是**紀錄裡的**，不是重跑的。
4. 最後一次 `Stop`（`last_assistant_message`＝最後一則回覆，去掉 gemma 的思考標記），交件前檢查跑在真的子行程裡。
   之後用同一個純函式（`evidence_for`）再算一次，拿到 `notes`（最後一次測試的狀態、只寫給人的原因）。
5. 重跑的忠實度：結束時的樹雜湊對 `ws_end_sha256`、重跑的結束碼與紀錄不同的步數，逐格記下。

輸出：`<out>/cells.jsonl`（每格一行）、`<out>/summary.json`。精確度＝`test_run_failed` 退回的格裡、隱藏測試沒有全過的
比例（退回一個全對的格＝誤退）；召回＝隱藏測試沒有全過的格裡、被它退回的比例。

誠實邊界：
1. 重跑是在這台機器上（python 版本可能與當時不同），不是當時的沙箱；檔案變化以樹雜湊驗，驗不過的格照樣列出、另外標記。
2. SOLO 的模型從來沒收到退回：這裡量的是「在那一刻會不會退回、退回得對不對」，不是「退回之後會不會做得更好」。
3. 最後那一刻以外的「說做完」（工作區沒變被推一下的那幾次）不送 `Stop`：那會多用掉一輪、也不是人會做的事。
4. `--counterfactual-run-tests` 把題目自己的 `run_tests.sh` 也當成測試指令（**不是產品行為**，只在這個行程裡換
   `RUNNERS`、交件前檢查在同一個行程裡跑），用來看同一套防呆在樣本多一點時的樣子。
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve()
DEFAULT_REPO = next((p for p in HERE.parents if (p / "vacant_network").is_dir()),
                    pathlib.Path("/home/user/Vacant/.claude/worktrees/wf_47b337c8-2fc-1"))
RUNS = [f"g_r530_s{s}_{m}_{k}" for s in (1, 2, 3) for m in (1003, 1004) for k in (1, 2)]
SID = "r530-solo"
GIT_IDENTITY = ("-c", "user.name=r530", "-c", "user.email=r530@vacant_network.local")
THOUGHT = re.compile(r"<\|channel>.*?<channel\|>", re.S)


def _setup(repo: pathlib.Path) -> None:
    os.environ["PYTHONPATH"] = str(repo) + (os.pathsep + os.environ["PYTHONPATH"]
                                            if os.environ.get("PYTHONPATH") else "")
    sys.path.insert(0, str(repo))


def cells(repo: pathlib.Path, runs: list[str]):
    for run in runs:
        rd = repo / "runs" / run
        rows = {(r["task_id"], r["arm"]): r for r in map(json.loads, open(rd / "rows.jsonl"))}
        seq: dict[str, list[tuple[str, dict[str, Any]]]] = collections.defaultdict(list)
        for line in open(rd / "calls.jsonl"):
            c = json.loads(line)
            meta = c.get("meta") or {}
            if meta.get("arm") == "A-SOLO" and "messages" in c:
                seq[meta["task_id"]].append(("model", c))
            elif c.get("kind") == "tool" and c.get("arm") == "A-SOLO":
                seq[c["task_id"]].append(("tool", c))
        for task in sorted(seq):
            yield run, task, rows.get((task, "A-SOLO")), seq[task]


def prepare(repo: pathlib.Path, task: str, ws: pathlib.Path) -> str:
    from ops.gain.r530 import wshash
    tpl = repo / "ops" / "gain" / "r530" / "templates" / task
    ws.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "-a", f"{tpl}/.", str(ws)], check=True)
    subprocess.run(["git", "init", "-q", str(ws)], check=True)
    subprocess.run(["git", "-C", str(ws), *GIT_IDENTITY, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(ws), *GIT_IDENTITY, "commit", "-q", "-m", "template"],
                   check=True, capture_output=True)
    return str(wshash.tree_manifest(ws)["ws_sha256"])


#: 與 R530 當時的沙箱同一個記憶體上限（`summary.json` 的 `backend_meta.memory_bytes`）：失控的程式不拖垮這台機器
MEMORY_BYTES = 512 * 1024 * 1024


def _limits() -> None:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))


def run_sandboxed(ws: pathlib.Path, cmd: str, timeout_s: float) -> int | None:
    """在 bwrap 裡重跑一個指令（只有工作區可寫、沒有網路、記憶體 512 MB）；回結束碼，逾時回 None。"""
    argv = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
            "--bind", str(ws), str(ws), "--chdir", str(ws), "--unshare-all", "--die-with-parent",
            "--clearenv", "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin", "--setenv", "HOME", "/tmp",
            "--setenv", "LANG", "C.UTF-8", "--", "bash", "-c", cmd]
    try:
        return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout_s,
                              start_new_session=True, preexec_fn=_limits).returncode
    except subprocess.TimeoutExpired:
        return None


def replay(repo: pathlib.Path, out: pathlib.Path, run: str, task: str, row: dict[str, Any] | None,
           seq: list[tuple[str, dict[str, Any]]], *, inproc: bool, step_timeout: float) -> dict[str, Any]:
    from ops.gain.r530 import wshash
    from vacant_network.adapters import hook
    from vacant_network.adapters import install as INS
    from vacant_network.trace import evidence as EV
    from vacant_network.trace import zerostop
    from vacant_network.trace.recorder import Recorder

    cell = out / "cells" / f"{run}__{task}"
    shutil.rmtree(cell, ignore_errors=True)
    ws, home, vh = cell / "ws", cell / "home", cell / "vh"
    home.mkdir(parents=True)
    os.environ["HOME"], os.environ["VACANT_HOME"] = str(home), str(vh)
    for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
        os.environ.pop(k, None)
    start = prepare(repo, task, ws)
    st = INS.state_root() / "install.json"
    st.parent.mkdir(parents=True, exist_ok=True)
    st.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    zerostop._run_child = zerostop.check if inproc else _REAL_CHILD      # type: ignore[attr-defined]

    base = {"session_id": SID, "cwd": str(ws)}

    def H(event: str, payload: dict[str, Any]) -> str:
        o, e, code = hook.handle("claude", event, payload)
        assert code == 0, (event, e)
        return o

    models = [c for k, c in seq if k == "model"]
    task_text = models[0]["messages"][0]["content"]
    H("UserPromptSubmit", {**base, "prompt": task_text})
    steps: list[dict[str, Any]] = []
    rc_mismatch = skipped = 0
    for kind, c in seq:
        if kind != "tool":
            continue
        cmd = c.get("command")
        if cmd is None or c.get("blocked"):
            skipped += 1
            continue
        n = len(steps) + 1
        pre = {**base, "tool_name": "Bash", "tool_use_id": f"t{n}", "tool_input": {"command": cmd}}
        H("PreToolUse", pre)
        rerun = run_sandboxed(ws, cmd, step_timeout)
        rc = c.get("rc")
        if c.get("timed_out"):
            H("PostToolUseFailure", {**pre, "error": f"Command timed out after {c.get('timeout_s')}s"})
        elif rc not in (0, None):
            H("PostToolUseFailure", {**pre, "error": f"Exit code {rc}\n{c.get('stdout') or ''}{c.get('stderr') or ''}"})
        else:
            H("PostToolUse", {**pre, "tool_response": {"stdout": c.get("stdout") or "",
                                                        "stderr": c.get("stderr") or "",
                                                        "interrupted": False, "isImage": False}})
        if not c.get("timed_out") and rerun != rc:
            rc_mismatch += 1
        steps.append({"n": n, "rc": rc, "timed_out": bool(c.get("timed_out")), "rerun_rc": rerun, "cmd": cmd[:200]})
    last_model = models[-1]
    final = THOUGHT.sub("", last_model.get("response") or "").strip()
    declared = not last_model.get("response_tool_calls")
    o = H("Stop", {**base, "hook_event_name": "Stop", "stop_hook_active": False,
                   "last_assistant_message": final})
    d = json.loads(o) if o else {}
    rec = Recorder(ws)
    reviews = [e for e in rec.events() if e.get("type") == "review"]
    res = EV.evidence_for(rec, platform="claude", session=SID, final_text=final)
    notes = res.get("notes") or {}
    kinds = [f["kind"] for f in (reviews[-1].get("findings") or [])] if reviews else []
    sent = reviews[-1].get("action") == "continue" if reviews else False
    end = str(wshash.tree_manifest(ws)["ws_sha256"])
    q = "?" in (final.split("\n\n")[-1] if final else "")
    rec_out = {
        "run": run, "task": task, "stop_reason": (row or {}).get("stop_reason"), "declared_done": declared,
        "hidden_passed": (row or {}).get("hidden_passed"), "hidden_total": (row or {}).get("hidden_total"),
        "has_outcome": row is not None,
        "fully_correct": (row or {}).get("hidden_frac") == 1.0 if row is not None else None,
        "visible_all_pass": (row or {}).get("visible_all_pass"),
        "steps": len(steps), "skipped_steps": skipped,
        "runner_steps": [s for s in steps if "runner" in s],
        "stop_decision": "block" if d.get("decision") == "block" else "allow",
        "sent_kinds": kinds if sent else [],
        "findings": (reviews[-1].get("findings") or []) if reviews else [],
        "all_steps": steps, "prompt_named": res.get("materials_named"),
        "test_run_failed_sent": sent and "test_run_failed" in kinds,
        "test_run_note": notes.get("test_run"),
        "test_runs": {k: v for k, v in (notes.get("test_runs") or {}).items() if k != "runs"} or None,
        "final_is_question": q, "final_head": final[:160],
        "fidelity": {"start_ok": start == (row or {}).get("ws_start_sha256"),
                     "end_ok": end == (row or {}).get("ws_end_sha256"), "rc_mismatch_steps": rc_mismatch},
    }
    return rec_out


_REAL_CHILD: Any = None


def summarize(all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [r for r in all_rows if r["has_outcome"]]           # `rows.jsonl` 沒有這一格的結果：不進分子分母
    wrong = [r for r in rows if not r["fully_correct"]]
    fired = [r for r in rows if r["test_run_failed_sent"]]
    tp = [r for r in fired if not r["fully_correct"]]
    noted = [r for r in rows if r["test_run_note"]]
    last_failed = [r for r in rows if (r["test_runs"] or {}).get("last") == "failed"]
    q = [r for r in rows if r["final_is_question"]]
    return {
        "cells": len(rows), "cells_without_outcome": [f"{r['run']}/{r['task']}" for r in all_rows
                                                      if not r["has_outcome"]],
        "declared_done": sum(r["declared_done"] for r in rows),
        "not_fully_correct": len(wrong),
        "cells_with_a_test_run": sum(bool(r["test_runs"]) for r in rows),
        "last_test_run_status": dict(collections.Counter((r["test_runs"] or {}).get("last", "none") for r in rows)),
        "last_unknown_why": dict(collections.Counter((r["test_runs"] or {}).get("unknown") for r in rows
                                                     if (r["test_runs"] or {}).get("last") == "unknown")),
        "last_failed_reliably": len(last_failed),
        "test_run_failed_sent": len(fired),
        "test_run_failed_sent_on_fully_correct": len(fired) - len(tp),
        "note_only": len(noted), "note_only_why": dict(collections.Counter(r["test_run_note"]["why"] for r in noted)),
        "precision": (len(tp) / len(fired)) if fired else None,
        "recall": len(tp) / len(wrong) if wrong else None,
        "recall_among_last_failed": (len([r for r in last_failed if r["test_run_failed_sent"]
                                          and not r["fully_correct"]]) /
                                     len([r for r in last_failed if not r["fully_correct"]])
                                     if [r for r in last_failed if not r["fully_correct"]] else None),
        "question_turns": len(q), "sent_on_question_turns": sum(r["test_run_failed_sent"] for r in q),
        "any_send_back": sum(r["stop_decision"] == "block" for r in rows),
        "any_send_back_kinds": dict(collections.Counter(k for r in rows for k in r["sent_kinds"])),
        "fidelity": {"start_ok": sum(r["fidelity"]["start_ok"] for r in rows),
                     "end_ok": sum(r["fidelity"]["end_ok"] for r in rows),
                     "cells_with_rc_mismatch": sum(r["fidelity"]["rc_mismatch_steps"] > 0 for r in rows)},
        "fired_cells": [f"{r['run']}/{r['task']} hidden {r['hidden_passed']}/{r['hidden_total']}" for r in fired],
    }


def main() -> int:
    global _REAL_CHILD
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=pathlib.Path, default=DEFAULT_REPO)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--runs", nargs="*", default=RUNS)
    ap.add_argument("--inproc", action="store_true", help="交件前檢查在同一個行程裡跑（快；預設是真的子行程）")
    ap.add_argument("--counterfactual-run-tests", action="store_true",
                    help="把題目自己的 run_tests.sh 也當成測試指令（不是產品行為；隱含 --inproc）")
    ap.add_argument("--step-timeout", type=float, default=30.0)
    a = ap.parse_args()
    repo = a.repo.resolve()
    _setup(repo)
    import vacant_network
    from vacant_network.trace import evidence as EV
    from vacant_network.trace import zerostop
    assert pathlib.Path(vacant_network.__file__).resolve().is_relative_to(repo), vacant_network.__file__
    _REAL_CHILD = zerostop._run_child
    if a.counterfactual_run_tests:
        EV.RUNNERS = re.compile(EV.RUNNERS.pattern[:-3] + r"|run_tests\.sh)\b")   # type: ignore[misc]
        a.inproc = True
    a.out.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(a.out / "cells.jsonl", "w") as fh:
        for run, task, row, seq in cells(repo, a.runs):
            r = replay(repo, a.out, run, task, row, seq, inproc=a.inproc, step_timeout=a.step_timeout)
            rows.append(r)
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"{run}/{task}: {r['stop_decision']} sent={r['sent_kinds']} "
                  f"last={(r['test_runs'] or {}).get('last')} note={(r['test_run_note'] or {}).get('why')} "
                  f"hidden={r['hidden_passed']}/{r['hidden_total']} end_ok={r['fidelity']['end_ok']}", flush=True)
    s = summarize(rows)
    s.update(repo=str(repo), vacant_network=vacant_network.__file__,
             counterfactual_run_tests=a.counterfactual_run_tests, inproc=a.inproc)
    (a.out / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
    print(json.dumps(s, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
