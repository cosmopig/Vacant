#!/usr/bin/env python3
"""R536 執行器：每題 × 三臂（RS／RF／RL），每臂最多三次嘗試，落盤一列一個 (題, 臂)。

這支在架構裡承重什麼（`decisions/prereg/PREREG_20260924_R536_LOCALIZED_FEEDBACK.md` §二-3、§三）：

三臂**只差** `vacant do --feedback-mode`：

    RS  none       每一次都從乾淨的工作區、原提示重抽（R535 的控制臂）
    RF  generic    下一次的提示後面接今天的泛用回饋（主張 id＋驗證器的一句話）
    RL  localized  下一次的提示後面接追緝過的回饋（位置、應有的值、第一次出現的步驟；沒有行動者）

agent 用它**自己的**設定去連模型（這支不碰模型端點、不帶任何金鑰）；團隊的本機模型怎麼接，
照各 agent 的文件設定在執行者自己的 HOME 裡。每一列記：每次嘗試的裁決與不過的必要主張數
（收斂曲線）、最後是否 `accepted`、隱藏檢查（`hidden.json`，agent 看不到）、`M1 = accepted ∧ hidden`、
回饋文字的長度、`infra_void`、牆鐘時間。斷點續跑：已經有的 (題, 臂) 不重跑。

    python ops/accountability/r536/run.py --bank <dir> --agent pi --out <rows.jsonl> [--arms RS,RF,RL]
    python ops/accountability/r536/run.py ... --mock        # L-fake 冒煙：每題用它自己的 mock_scenario.json

## 誠實邊界

1. `--mock` 只證明管線接得起來（假模型看到回饋就照劇本改對）；**任何效果數字都不可以從它來**。
2. 同一題的三臂共用同一份題目，但模型的隨機性沒有配對（沒有 seed 可控）；McNemar 配的是題目。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[3]
PY = sys.executable
ARMS = {"RS": "none", "RF": "generic", "RL": "localized"}
MOCK = REPO / "ops" / "intake" / "mock_model.py"


def done_keys(out: pathlib.Path) -> set[tuple[str, str]]:
    if not out.is_file():
        return set()
    keys = set()
    for line in out.read_text().splitlines():
        try:
            r = json.loads(line)
            keys.add((r["item"], r["arm"]))
        except (ValueError, KeyError):
            continue
    return keys


def hidden_pass(ws: pathlib.Path | None, hidden: dict) -> bool | None:
    if ws is None:
        return None
    p = ws / "report.md"
    if not p.is_file():
        return False
    m = re.search(r"(?mi)^\s*Top region:\s*([A-Za-z]+)", p.read_text(encoding="utf-8",
                                                                   errors="replace"))
    return bool(m and m.group(1).lower() == str(hidden["top_region"]).lower())


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_cell(item_dir: pathlib.Path, arm: str, agent: str, work: pathlib.Path,
             env: dict[str, str], timeout: float, extra: list[str]) -> dict:
    proj = work / f"{item_dir.name}-{arm}"
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(item_dir, proj, ignore=shutil.ignore_patterns("hidden.json",
                                                                   "mock_scenario.json"))
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    lk = subprocess.run([PY, "-m", "vacant_network", "contract", "lock"], cwd=proj, env=env,
                        capture_output=True, text=True, timeout=120)
    if lk.returncode != 0:
        return {"infra_void": True, "stage": "lock", "error": lk.stderr[-300:]}
    t0 = time.time()
    cp = subprocess.run([PY, "-m", "vacant_network", "do", agent, "--prompt-file", "TASK.md",
                         "--attempts", "3", "--feedback-mode", ARMS[arm], "--timeout",
                         str(timeout), "--json", *(["--", *extra] if extra else [])],
                        cwd=proj, env=env, capture_output=True, text=True,
                        timeout=timeout * 3 + 300)
    wall = round(time.time() - t0, 1)
    try:
        res = json.loads(cp.stdout)
    except ValueError:
        return {"infra_void": True, "stage": "do", "rc": cp.returncode,
                "error": (cp.stderr or cp.stdout)[-400:], "wall_s": wall}
    attempts = res.get("attempts") or []
    return {"res": res, "wall_s": wall, "attempts": attempts,
            "workspace": res.get("workspace"), "rc": cp.returncode}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--agent", required=True)
    ap.add_argument("--out", required=True, help="rows.jsonl (appended; resumable)")
    ap.add_argument("--arms", default="RS,RF,RL")
    ap.add_argument("--work", help="scratch dir for per-cell projects")
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--mock", action="store_true", help="L-fake plumbing smoke only")
    ap.add_argument("--agent-args", default="", help="extra args after `--` for the agent")
    a = ap.parse_args()
    if a.mock and a.agent != "claude":
        ap.error("--mock drives the scripted model through env vars; only --agent claude")
    bank = pathlib.Path(a.bank).resolve()
    out = pathlib.Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(a.work or (out.parent / "work")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((bank / "MANIFEST.json").read_text())
    items = sorted(manifest["items"])
    if a.limit:
        items = items[:a.limit]
    have = done_keys(out)
    env = dict(os.environ)
    mock_proc = None
    for name in items:
        idir = bank / name
        hidden = json.loads((idir / "hidden.json").read_text())
        for arm in a.arms.split(","):
            if (name, arm) in have:
                continue
            if a.mock:
                port = free_port()
                env = {**env, **mock_env(a.agent, port)}
                mock_proc = subprocess.Popen(
                    [PY, str(MOCK), str(port)],
                    env={**os.environ, "MOCK_SCENARIO": str(idir / "mock_scenario.json"),
                         "MOCK_LOG": str(work / f"{name}-{arm}.mock.jsonl")},
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(0.8)
            try:
                cell = run_cell(idir, arm, a.agent, work, env, a.timeout,
                                a.agent_args.split() if a.agent_args else [])
            finally:
                if mock_proc:
                    mock_proc.terminate()
                    mock_proc.wait()
                    mock_proc = None
            row = row_of(name, arm, a.agent, hidden, cell, a.mock)
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"[r536] {name} {arm}: accepted={row.get('accepted')} hidden={row.get('hidden_pass')} "
                  f"M1={row.get('M1')} attempts={row.get('n_attempts')} void={row.get('infra_void')}",
                  flush=True)
    return 0


def mock_env(agent: str, port: int) -> dict[str, str]:
    """L-fake：只在 `--mock` 用（假金鑰、假端點）。真跑時 agent 用執行者自己 HOME 裡的設定。"""
    return {"ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
            "ANTHROPIC_API_KEY": "sk-fake-offline-000", "CLAUDE_CODE_MAX_RETRIES": "0",
            "DISABLE_TELEMETRY": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}


def row_of(name: str, arm: str, agent: str, hidden: dict, cell: dict, mock: bool) -> dict:
    row: dict = {"item": name, "arm": arm, "agent": agent, "decoy": hidden.get("decoy"),
                 "evidence_level": "L-fake" if mock else "real-model",
                 "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    if cell.get("infra_void") or (cell.get("res") or {}).get("void"):
        row.update(infra_void=True, M1=None, detail=cell.get("error") or
                   (cell.get("res") or {}).get("reasons"))
        return row
    res = cell["res"]
    atts = cell["attempts"]
    curve = [at.get("outcome") for at in atts]
    accepted = res.get("outcome") == "accept"
    ws = pathlib.Path(res["workspace"]) if res.get("workspace") else None
    hp = hidden_pass(ws, hidden)
    fb = [((at.get("trace") or {}).get("summary") or "") for at in atts]
    row.update(infra_void=False, accepted=accepted, hidden_pass=hp,
               M1=bool(accepted and hp), n_attempts=len(atts), outcomes=curve,
               failing_required=[at.get("failing_required") for at in atts],
               wall_s=cell.get("wall_s"), trace_summaries=fb)
    return row


if __name__ == "__main__":
    raise SystemExit(main())
