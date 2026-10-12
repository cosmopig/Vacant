"""誤報閘門的外層：每一個真的 pi 工作階段開一個全新的題目容器（不連網），只用 wheel 安裝 Vacant、
`vacant install --agents pi`，再用 `replay_pi_session.py` 重播到第一次「說做完」。

    python3 ops/eval/replay_gate.py --jobs <harbor jobs 目錄> --image <題目映像> --wheels <wheel 目錄> --out <輸出目錄>

每一跑寫 `<out>/<trial>.json`（重播結果、交件說明、`review` 事件）與 `<out>/summary.json`：
那一跑的得分（Harbor `result.json` 的 reward）、Vacant 的決定（`continue`＝退回）、退回了哪幾類。
**答對的那幾跑上有任何退回＝誤報**，是花錢試跑之前的門檻（DECISION_20260925_ZERO_CONFIG_DESIGN §七）。

容器只設 `HOME`，不設任何 Vacant 環境變數（產品原則 3：量的是使用者真的會得到的設定）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def reward_of(trial: pathlib.Path) -> float | None:
    try:
        r = json.loads((trial / "result.json").read_text())
    except (OSError, ValueError):
        return None
    vr = r.get("verifier_result") or {}
    rew = (vr.get("rewards") or {}).get("reward", vr.get("reward"))
    return float(rew) if rew is not None else None


def run_one(session: pathlib.Path, image: str, wheels: pathlib.Path, out: pathlib.Path,
            cwd: str) -> dict:
    trial = session.parents[3]
    name = trial.name
    res_path = out / f"{name}.json"
    script = (
        "set -e; pip install -q --break-system-packages --no-index --find-links /w vacant-network "
        ">/o/pip.log 2>&1 || pip install -q --no-index --find-links /w vacant-network >/o/pip.log 2>&1; "
        "vacant install --agents pi --force > /o/install.txt 2>&1; "
        f"python3 /r/replay_pi_session.py /s/session.jsonl --cwd {cwd} --out /o/replay.json"
    )
    tmp = out / name
    tmp.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "--rm", "--network", "none",
           "-v", f"{wheels}:/w:ro", "-v", f"{HERE}:/r:ro",
           "-v", f"{session}:/s/session.jsonl:ro", "-v", f"{tmp}:/o",
           "-e", "HOME=/root", "-w", cwd, image, "bash", "-c", script]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    row = {"trial": name, "reward": reward_of(trial), "rc": p.returncode,
           "stderr": p.stderr[-800:] if p.returncode else ""}
    try:
        rep = json.loads((tmp / "replay.json").read_text())
    except (OSError, ValueError):
        rep = None
    if rep:
        st = rep.get("stop") or {}
        rv = (rep.get("reviews") or [{}])[-1] or {}
        row.update(model=rep.get("model"), steps=rep.get("steps"), action=st.get("action"),
                   stop_s=st.get("_s"), sent_back=[f.get("kind") for f in rv.get("findings") or []
                                                   if f.get("finding_id") in (rv.get("sent") or [])],
                   findings=rv.get("findings"), deliverables=rv.get("deliverables"),
                   reason=st.get("reason"), note=st.get("note"))
        res_path.write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--wheels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cwd", default="/app")
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in sorted(pathlib.Path(a.jobs).rglob("agent/pi/sessions/*.jsonl")):
        row = run_one(s.resolve(), a.image, pathlib.Path(a.wheels).resolve(), out, a.cwd)
        rows.append(row)
        print(json.dumps({k: row.get(k) for k in ("trial", "model", "reward", "action",
                                                  "sent_back", "stop_s", "rc")}), flush=True)
    fp = [r["trial"] for r in rows if r.get("reward") == 1.0 and r.get("action") == "continue"]
    summary = {"runs": len(rows), "correct": sum(1 for r in rows if r.get("reward") == 1.0),
               "sent_back": sum(1 for r in rows if r.get("action") == "continue"),
               "false_positive_on_correct": fp, "rows": rows}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps({k: summary[k] for k in ("runs", "correct", "sent_back",
                                              "false_positive_on_correct")}))
    return 1 if fp else 0


if __name__ == "__main__":
    sys.exit(main())
