"""程式題組的 A 組（沒裝 Vacant）真實工作階段，離線重播給零設定 Vacant：在 agent 說做完的那一刻，它會不會退回、退回什麼（2026-09-26）。

這支在架構裡承重什麼：`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §三——在花本機算力跑 A／C 對照之前，先用
**已經跑完的 A 組紀錄**估「C 組的檢查在程式題上會不會作用、作用的時候對不對」（退回一個評分全對的跑＝誤退）。沒有模型、沒有容器。

做法（每一跑）：
1. 工作區＝題目的 `environment/tests/` 複製成 `<ws>/tests/`（就是容器裡 `/app` 的樣子：評分前只有公開測試）＋空 git 起點。
2. 新的 `VACANT_HOME`／`HOME`，`install.json` 的 `mode=evidence`（`vacant install` 之後的樣子）。
3. pi 的事件流（`agent/pi.txt`）裡的訊息照順序經過**真的掛鉤路徑** `hook.handle("pi", …)`：人的訊息 → `prompt`；
   每一個工具呼叫 → `pre_tool` → 副作用（`write`／`edit` 照參數寫檔；`bash` 在 bwrap 裡重跑，只為了讓工作區照原樣變化）
   → `post_tool`（輸出與錯誤旗標一律用**紀錄裡的**）。指令與路徑裡的 `/app` 換成工作區。
4. 只有「說做完」的跑（最後一則助理訊息 `stopReason == "stop"`）送 `stop`（`final_text`＝那一則的文字），交件前檢查在同一個行程裡跑；
   被回合上限或時限切斷的跑，真的 C 組也不會在那一刻檢查（pi 中止時不進交件前檢查）⇒ 只記 `not_done`。

    PYTHONDONTWRITEBYTECODE=1 python3 ops/eval/codesuite/replay_code_zero.py --jobs <A 組 jobs> --suite <lcb_visible/livecodebench> --out <dir>

誠實邊界：
1. 量的是「在那一刻會不會退回、退回得對不對」，不是「退回之後會不會做得更好」（那要真的模型）。
2. 回合預算提醒（v3）不在這裡量：它作用在說做完之前、要改變模型收到的請求。
3. 重跑的輸出可能和當時不同；進病歷的是紀錄裡的輸出。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import resource
import shutil
import subprocess
import sys
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[3]
SID = "code-replay"


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))


def run_sandboxed(ws: pathlib.Path, cmd: str, timeout_s: float = 60.0) -> int | None:
    """在 bwrap 裡重跑一個指令（只有工作區可寫、沒有網路）；回結束碼，逾時回 None。"""
    argv = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
            "--bind", str(ws), str(ws), "--chdir", str(ws), "--unshare-all", "--die-with-parent",
            "--clearenv", "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin", "--setenv", "HOME", "/tmp",
            "--setenv", "LANG", "C.UTF-8", "--", "bash", "-c", cmd]
    try:
        return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout_s,
                              start_new_session=True, preexec_fn=_limits).returncode
    except subprocess.TimeoutExpired:
        return None


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(str(c.get("text") or "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text")


def _swap(v: Any, ws: str) -> Any:
    if isinstance(v, str):
        return re.sub(r"(?<![\w.])/app(?=/|\b)", ws, v)
    if isinstance(v, dict):
        return {k: _swap(x, ws) for k, x in v.items()}
    if isinstance(v, list):
        return [_swap(x, ws) for x in v]
    return v


def _side(name: str, args: dict[str, Any], ws: pathlib.Path) -> None:
    if name == "bash":
        run_sandboxed(ws, str(args.get("command") or ""))
    elif name == "write":
        p = ws / str(args.get("path"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(args.get("content") or ""))
    elif name == "edit":
        p = ws / str(args.get("path"))
        try:
            s = p.read_text()
        except OSError:
            return
        for e in args.get("edits") or [{"oldText": args.get("oldText"), "newText": args.get("newText")}]:
            old, new = e.get("oldText") or e.get("old_text"), e.get("newText") or e.get("new_text")
            if old is not None and old in s:
                s = s.replace(old, new or "", 1)
        p.write_text(s)


def replay_one(trial: pathlib.Path, suite: pathlib.Path, out: pathlib.Path) -> dict[str, Any]:
    from vacant_network.adapters import hook
    from vacant_network.adapters import install as INS
    from vacant_network.trace import zerostop
    from vacant_network.trace.evidence import evidence_for
    from vacant_network.trace.recorder import Recorder

    task = trial.name.split("__")[0]
    cell = out / "cells" / trial.name
    shutil.rmtree(cell, ignore_errors=True)
    ws, home, vh = cell / "ws", cell / "home", cell / "vh"
    home.mkdir(parents=True)
    shutil.copytree(suite / task / "environment" / "tests", ws / "tests")
    subprocess.run(["git", "init", "-q", str(ws)], check=True)
    os.environ["HOME"], os.environ["VACANT_HOME"] = str(home), str(vh)
    for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
        os.environ.pop(k, None)
    st = INS.state_root() / "install.json"
    st.parent.mkdir(parents=True, exist_ok=True)
    st.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    zerostop._run_child = zerostop.check      # type: ignore[attr-defined]
    base = {"cwd": str(ws), "session_id": SID}

    events = []
    for ln in (trial / "agent" / "pi.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(ln))
        except ValueError:
            continue
    msgs = [e["message"] for e in events if e.get("type") == "message_end" and isinstance(e.get("message"), dict)]
    results = {str(m.get("toolCallId")): m for m in msgs if m.get("role") == "toolResult"}
    final, stop_reason, steps = "", None, 0
    for m in msgs:
        role = m.get("role")
        if role == "user":
            hook.handle("pi", "prompt", {**base, "prompt": _swap(_text(m.get("content")), str(ws))})
        elif role == "assistant":
            stop_reason = m.get("stopReason")
            if _text(m.get("content")).strip():
                final = _text(m.get("content"))
            for c in [c for c in m.get("content") or [] if isinstance(c, dict) and c.get("type") == "toolCall"]:
                cid, name = str(c.get("id")), str(c.get("name"))
                args = _swap(c.get("arguments") or {}, str(ws))
                pre = {**base, "tool": name, "input": args, "call_id": cid}
                hook.handle("pi", "pre_tool", pre)
                _side(name, args, ws)
                res = results.get(cid) or {}
                hook.handle("pi", "post_tool", {**pre, "output": _text(res.get("content")),
                                                "is_error": bool(res.get("isError"))})
                steps += 1
    reward = None
    try:
        reward = float((trial / "verifier" / "reward.txt").read_text().strip())
    except (OSError, ValueError):
        pass
    row: dict[str, Any] = {"trial": trial.name, "task": task, "reward": reward, "steps": steps,
                           "stop_reason": stop_reason, "said_done": stop_reason == "stop"}
    if stop_reason == "stop":
        o, _e, _code = hook.handle("pi", "stop", {**base, "final_text": final or None})
        try:
            d = json.loads((o or "").strip().splitlines()[-1]) if o else {}
        except (ValueError, IndexError):
            d = {"unparsed": (o or "")[-300:]}
        rec = Recorder(ws)
        reviews = [e for e in rec.events() if e.get("type") == "review"]
        last = reviews[-1] if reviews else {}
        res = evidence_for(rec, platform="pi", session=SID, final_text=final)
        row.update(action=last.get("action"), kinds=[f["kind"] for f in last.get("findings") or []],
                   findings=[{k: v for k, v in f.items() if k != "finding_id"} for f in last.get("findings") or []],
                   given_in_request=res.get("given_in_request"), observed=res.get("observed"),
                   final_head=final[:200], hook_out=str(d)[:300])
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--suite", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--repo", type=pathlib.Path, default=REPO)
    a = ap.parse_args(argv)
    sys.path.insert(0, str(a.repo.resolve()))
    import vacant_network
    assert pathlib.Path(vacant_network.__file__).resolve().is_relative_to(a.repo.resolve()), vacant_network.__file__
    a.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for trial in sorted(a.jobs.glob("g12-off-*-s*/*/*__*")):
        if not (trial / "result.json").is_file() or not (trial / "agent" / "pi.txt").is_file():
            continue
        r = replay_one(trial, a.suite, a.out)
        rows.append(r)
        print(json.dumps({k: r.get(k) for k in ("trial", "reward", "said_done", "action", "kinds")}), flush=True)
    with (a.out / "cells.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    done = [r for r in rows if r["said_done"]]
    sent = [r for r in done if r.get("action") == "continue"]
    summ = {"runs": len(rows), "said_done": len(done), "sent_back": len(sent),
            "sent_back_on_reward_1": sum(1 for r in sent if r["reward"] == 1.0),
            "sent_back_on_reward_0": sum(1 for r in sent if r["reward"] != 1.0),
            "done_reward_1": sum(1 for r in done if r["reward"] == 1.0),
            "vacant_network": vacant_network.__file__}
    (a.out / "summary.json").write_text(json.dumps(summ, indent=1) + "\n")
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
