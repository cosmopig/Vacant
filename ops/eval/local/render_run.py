"""一跑（Harbor＋pi 的 trial 目錄）→ 人讀的精簡逐字稿（2026-09-26）。

給事後分析用（失敗的樣子、Vacant 在它能動作的時間點看得到什麼）：每一回合的可見文字、工具呼叫、工具結果的開頭，
最後附評分器的輸出與答案檔。只讀 trial 目錄，不改任何東西。

    python3 ops/eval/local/render_run.py <trial 目錄> [--result-chars 600] [--dataset <題目目錄>]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    out = []
    for c in content or []:
        if isinstance(c, dict) and c.get("type") == "text":
            out.append(str(c.get("text") or ""))
    return "\n".join(out)


def render(trial: pathlib.Path, result_chars: int = 600, dataset: pathlib.Path | None = None) -> str:
    lines: list[str] = [f"# {trial.parent.name}"]
    task = None
    m = re.search(r"dabstep-(\d+)__", trial.name)
    if m:
        task = m.group(1)
    try:
        traj = json.loads((trial / "agent" / "trajectory.json").read_text())
        first = next((s for s in traj.get("steps") or [] if s.get("source") == "user"), None)
        if first:
            q = str(first.get("message") or "")
            i = q.find("Here is the question")
            lines += ["", "## Request", "", (q[i:] if i >= 0 else q)[:2500]]
    except (OSError, ValueError):
        pass
    turn = 0
    results: dict[str, str] = {}
    events = []
    for ln in (trial / "agent" / "pi.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(ln))
        except ValueError:
            continue
    for r in events:
        if r.get("type") == "tool_execution_end":
            res = r.get("result") or {}
            results[str(r.get("toolCallId"))] = ("[ERROR] " if r.get("isError") else "") + _text(res.get("content"))
    for r in events:
        t = r.get("type")
        if t == "message_end" and (r.get("message") or {}).get("role") == "user" and turn > 0:
            txt = _text((r.get("message") or {}).get("content"))
            lines += ["", f"### (user/extension message after turn {turn})", "", txt[:1500]]
        if t == "entry_appended" and (r.get("entry") or {}).get("type") == "custom_message":
            e = r.get("entry") or {}
            txt = e.get("content") if isinstance(e.get("content"), str) else _text(e.get("content"))
            # 回合預算提醒是在那一回合的 turn_end 處理器裡接上的（事件流裡排在那一回合的 turn_end 之前）
            at = turn + 1 if e.get("customType") == "vacant-budget" else turn
            lines += ["", f"### ({e.get('customType')} message after turn {at})", "", str(txt)[:1500]]
        if t != "turn_end":
            continue
        turn += 1
        msg = r.get("message") or {}
        lines += ["", f"## Turn {turn} (stopReason={msg.get('stopReason')})"]
        for c in msg.get("content") or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text" and str(c.get("text") or "").strip():
                lines += ["", "text: " + str(c["text"])[:2000]]
            elif c.get("type") == "toolCall":
                args = c.get("arguments") or {}
                lines += ["", f"call {c.get('name')}: " + json.dumps(args, ensure_ascii=False)[:2000]]
                res = results.get(str(c.get("id")), "")
                lines += ["result: " + res[:result_chars].replace("\n", "\n        ")
                          + (f" …[{len(res)} chars]" if len(res) > result_chars else "")]
        if msg.get("errorMessage"):
            lines += ["", "error: " + str(msg.get("errorMessage"))[:300]]
    lines += ["", "## Verifier", ""]
    try:
        lines.append((trial / "verifier" / "test-stdout.txt").read_text(errors="replace")[-1500:])
        lines.append("reward: " + (trial / "verifier" / "reward.txt").read_text().strip())
    except OSError:
        lines.append("(no verifier output)")
    if dataset is not None and task is not None:
        for cand in (dataset / f"dabstep-{task}" / "tests").glob("*"):
            if cand.is_file() and cand.stat().st_size < 20000:
                txt = cand.read_text(errors="replace")
                mm = re.search(r"(expected|EXPECTED|answer)[^\n]{0,200}", txt)
                if mm:
                    lines.append(f"expected (from {cand.name}): {mm.group(0)[:200]}")
                    break
    try:
        chk = (trial / "agent" / "vacant_check.json").read_text().strip().splitlines()[-1]
        lines += ["", "vacant_check: " + chk]
    except (OSError, IndexError):
        pass
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("trial", type=pathlib.Path)
    ap.add_argument("--result-chars", type=int, default=600)
    ap.add_argument("--dataset", type=pathlib.Path)
    a = ap.parse_args(argv)
    print(render(a.trial, a.result_chars, a.dataset), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
