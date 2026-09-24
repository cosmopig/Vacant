#!/usr/bin/env python3
"""perf_scan — **掛鉤在大一點的專案上要花多久**：真的掛鉤進入點（`python -m vacant_network hook`，含行程啟動）。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §4.3：整個工作區增量掃描；
Fable 的警告：掛鉤有 30 秒上限，超時＝靜默略過＝更大的缺口）。

對每個大小（檔案數）：建一個有契約的專案 → 第一次 PreToolUse（冷：要雜湊每一個檔）→ 之後 N 對
Pre／PostToolUse（熱：只重算改過的檔；每一步改一個檔）。回報冷／熱的牆鐘時間 p50／p95。

    python ops/accountability/perf_scan.py --out <dir> [--sizes 100,1000,10000,40000] [--steps 10]

## 誠實邊界

- 檔案都很小（幾十位元組）；大檔的雜湊時間另計。本機磁碟、快取是熱的；網路檔案系統會更慢。
- 只量 Claude Code 格式的掛鉤；四個平台走同一個 `hook.handle`，差別在 JSON 解析。
- 「每一步多存多少」＝熱的那幾步之後版本庫長了多少÷步數（每一步改一個小檔；含工作區狀態與輸入輸出）。
- Stop：驗收＋追緝＋在重建的前後狀態上重跑（埋了一個錯：第 1 步把 `999` 寫進 report.md）。
  「定位到那一行」＝給 agent 的回饋裡有 `report.md:2` 與「第一次出現在第幾步」。
- 第一次看超過掛鉤時限的那幾格：先量背景還在看的時候的 3 對掛鉤，再等背景看完（最多 300 秒），
  才量熱的那幾步。背景看不完（超過檔案數上限）⇒ 掃描關掉，熱的那幾步量到的是「不掃」的成本。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
PY = sys.executable


def project(root: pathlib.Path, n: int) -> pathlib.Path:
    p = root / f"proj{n}"
    if p.exists():
        shutil.rmtree(p)
    (p / ".vacant").mkdir(parents=True)
    per = 200
    for i in range(n):
        d = p / "src" / f"d{i // per:04d}"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"f{i:06d}.txt").write_text(f"line {i}\n")
    raw = {"schema": "vacant-contract/1", "task_id": f"perf{n}", "version": 1, "objective": "",
           "owner": "", "deliverable": {"include": ["report.md"], "exclude": [".vacant/**"]},
           "inputs": {}, "claims": [{"id": "present", "verifier": "exists", "required": True,
                                     "authority": "requirement", "description": "",
                                     "params": {"paths": ["report.md"]}},
                                    {"id": "no_placeholder", "verifier": "text", "required": True,
                                     "authority": "requirement", "description": "",
                                     "params": {"path": "report.md",
                                                "must_not_contain": ["999"]}}],
           "unknown_policy": "hold", "conflict_policy": "escalate",
           "release": {"destination": "dir:.vacant/published", "requires_approval": False},
           "hooks": {"stop_check": True, "max_feedback_rounds": 1, "submit_on_end": False}}
    (p / ".vacant" / "contract.json").write_text(json.dumps(raw))
    return p


def hook(env: dict[str, str], event: str, payload: dict, out: list | None = None) -> float:
    t0 = time.perf_counter()
    cp = subprocess.run([PY, "-m", "vacant_network", "hook", "claude", event],
                        input=json.dumps(payload), text=True, capture_output=True, env=env,
                        timeout=120, check=False)
    if out is not None:
        out.append(cp.stdout)
    return (time.perf_counter() - t0) * 1000


def store_bytes(vh: pathlib.Path) -> int:
    root = vh / "trace" / "objects"
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file()) if root.is_dir() else 0


def q(xs: list[float], f: float) -> float:
    s = sorted(xs)
    return round(s[min(len(s) - 1, int(len(s) * f))], 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sizes", default="100,1000,10000,40000")
    ap.add_argument("--steps", type=int, default=10)
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for n in [int(x) for x in a.sizes.split(",")]:
        vh = out / f"vh{n}"
        if vh.exists():
            shutil.rmtree(vh)
        env = {**os.environ, "VACANT_HOME": str(vh), "PYTHONPATH": str(REPO)}
        env.pop("VACANT_TRACE", None)
        subprocess.run([PY, "-m", "vacant_network", "keys", "init"], env=env,
                       capture_output=True, check=False)
        p = project(out, n)
        base = {"session_id": "perf", "cwd": str(p), "tool_name": "Bash",
                "tool_input": {"command": "echo"}}
        noop = hook(env, "SessionStart", {"session_id": "perf", "cwd": str(p)})
        cold = hook(env, "PreToolUse", {**base, "tool_use_id": "c0"})
        hook(env, "PostToolUse", {**base, "tool_use_id": "c0", "tool_response": {}})
        state = next((vh / "trace" / "projects").iterdir()) / "state.json"
        pending, waited = [], 0.0
        if json.loads(state.read_text()).get("baseline_pending"):
            # 第一次看改到背景：這段時間的掛鉤（應該不掃）＋等背景看完
            for i in range(3):
                pending.append(hook(env, "PreToolUse", {**base, "tool_use_id": f"b{i}"}))
                pending.append(hook(env, "PostToolUse", {**base, "tool_use_id": f"b{i}",
                                                         "tool_response": {}}))
            t0 = time.perf_counter()
            while json.loads(state.read_text()).get("baseline_pending") and waited < 300:
                time.sleep(0.5)
                waited = time.perf_counter() - t0
        cov = [json.loads(x).get("payload", {}) for x in
               (state.parent / "chain.ndjson").read_text().splitlines()]
        bl = next((c["baseline"] for c in cov if isinstance(c.get("baseline"), dict)), None)
        s0 = store_bytes(vh)
        warm = []
        for i in range(a.steps):
            tid = f"s{i}"
            warm.append(hook(env, "PreToolUse", {**base, "tool_use_id": tid}))
            (p / "src" / "d0000" / f"f{i:06d}.txt").write_text(f"changed {i}\n")
            if i == 0:
                (p / "report.md").write_text("# Report\nTotal: 999\n")     # 埋一個錯
            warm.append(hook(env, "PostToolUse", {**base, "tool_use_id": tid,
                                                  "tool_response": {}}))
        said: list[str] = []
        stop = hook(env, "Stop", {"session_id": "perf", "cwd": str(p),
                                  "stop_hook_active": False}, said)
        located = "report.md:2" in said[0] and "first appeared at step" in said[0]
        (out / f"stop_{n}.json").write_text(said[0])              # agent 收到的原文
        st = json.loads(state.read_text())
        rows.append({"files": n, "noop_hook_ms": round(noop, 1), "cold_pre_ms": round(cold, 1),
                     "first_look": ("background" if pending else "in hook"),
                     "pending_hook_p50_ms": q(pending, 0.5) if pending else None,
                     "background_look_s": bl.get("seconds") if bl else None,
                     "warm_p50_ms": q(warm, 0.5), "warm_p95_ms": q(warm, 0.95),
                     "warm_max_ms": round(max(warm), 1),
                     "store_kb_per_step": round((store_bytes(vh) - s0) / a.steps / 1024, 1),
                     "stop_ms": round(stop, 1), "stop_located": located,
                     "scan_disabled": st.get("scan_disabled")})
        print(json.dumps(rows[-1]), flush=True)
        shutil.rmtree(p, ignore_errors=True)
    (out / "perf.json").write_text(json.dumps(rows, indent=1))
    lines = ["| files | hook without trace (ms) | first Pre (ms) | first full look | "
             "hooks while it runs, p50 (ms) | warm p50 (ms) | warm p95 (ms) | warm max (ms) | "
             "store growth per step (KB) | Stop: check＋trace (ms) | Stop feedback located the line | "
             "scanning turned off |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        look = r["first_look"] if r["background_look_s"] is None else \
            f"background, {r['background_look_s']} s"
        lines.append(f"| {r['files']} | {r['noop_hook_ms']} | {r['cold_pre_ms']} | {look} | "
                     f"{r['pending_hook_p50_ms'] or '—'} | {r['warm_p50_ms']} | "
                     f"{r['warm_p95_ms']} | {r['warm_max_ms']} | {r['store_kb_per_step']} | "
                     f"{r['stop_ms']} | {'yes' if r['stop_located'] else 'no'} | "
                     f"{r['scan_disabled'] or 'no'} |")
    (out / "perf.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
