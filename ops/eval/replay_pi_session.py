"""把一次真的 pi 工作階段（`~/.pi/agent/sessions/*.jsonl`）重播給零設定 Vacant，看它在「agent 說做完」
那一刻會不會退回——量**誤報**用（DECISION_20260925_ZERO_CONFIG_DESIGN §七「用真實紀錄重播量誤報」）。

在**同一個題目的容器**裡跑（工作區、資料檔和當時一樣），裝好 Vacant（`vacant install --agents pi`）之後：

    python3 replay_pi_session.py SESSION.jsonl --out result.json

每一則使用者訊息 → `vacant hook pi prompt`；每一個工具呼叫 → `vacant hook pi pre_tool`、**真的做一次**
（bash 在 cwd 裡重跑、write／edit 照參數寫檔、read 不動）、`vacant hook pi post_tool`（輸出用紀錄裡
**模型當時看到的那一份**）；最後一則 assistant 訊息之後 → `vacant hook pi stop`（`final_text`＝那一則的文字）。
和 pi 的 Vacant 擴充送的是同一個指令、同一種格式。

誠實邊界：
1. 重跑 bash 的輸出可能和當時不同（時間、亂數）；進病歷的是紀錄裡的輸出，工作區的改動來自重跑。
2. 只重播到第一次「說做完」：退回之後模型會怎麼改，重播看不到（那要真的模型）。
3. 標準函式庫就能跑（容器裡不一定有別的套件）。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Any

HOOK = [os.environ.get("VACANT_BIN", "vacant"), "hook", "pi"]


def hook(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    t0 = time.time()
    p = subprocess.run(HOOK + [event], input=json.dumps(payload), capture_output=True, text=True,
                       timeout=700)
    line = (p.stdout.strip().splitlines() or [""])[-1]
    try:
        out = json.loads(line) if line else {}
    except ValueError:
        out = {"unparsed": line[-400:]}
    out["_s"] = round(time.time() - t0, 3)
    if p.returncode:
        out["_rc"] = p.returncode
    return out


def text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in content or [] if isinstance(c, dict)
                     and c.get("type") == "text")


def do_tool(name: str, args: dict[str, Any], cwd: str) -> str:
    """工具的副作用。回一行說明（不進病歷）。"""
    if name == "bash":
        try:
            r = subprocess.run(["bash", "-c", str(args.get("command") or "")], cwd=cwd,
                               capture_output=True, text=True, timeout=float(args.get("timeout") or 120))
            return f"bash rc={r.returncode}"
        except subprocess.TimeoutExpired:
            return "bash timeout"
    if name == "write":
        p = pathlib.Path(cwd, str(args.get("path")))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(args.get("content") or ""))
        return f"write {p}"
    if name == "edit":
        p = pathlib.Path(cwd, str(args.get("path")))
        try:
            s = p.read_text()
        except OSError:
            return f"edit {p}: missing"
        edits = args.get("edits") or [{"oldText": args.get("oldText"), "newText": args.get("newText")}]
        for e in edits:
            old, new = e.get("oldText") or e.get("old_text"), e.get("newText") or e.get("new_text")
            if old is not None and old in s:
                s = s.replace(old, new or "", 1)
        p.write_text(s)
        return f"edit {p}"
    return f"{name}: no side effect"


def replay(session: pathlib.Path, cwd: str | None) -> dict[str, Any]:
    rows = [json.loads(x) for x in session.read_text().split("\n") if x.strip()]
    head = next((r for r in rows if r.get("type") == "session"), {})
    cwd = cwd or head.get("cwd") or os.getcwd()
    sid = "replay-" + str(head.get("id") or session.stem)
    model = None
    base = {"cwd": cwd, "session_id": sid}
    results: dict[str, dict[str, Any]] = {}
    for r in rows:
        m = r.get("message") or {}
        if m.get("role") == "toolResult":
            results[str(m.get("toolCallId"))] = m
        if r.get("type") == "model_change":
            model = f"{r.get('provider')}/{r.get('modelId')}"
    log: list[dict[str, Any]] = []
    final = ""
    for r in rows:
        m = r.get("message") or {}
        role = m.get("role")
        if role == "user":
            log.append({"prompt": hook("prompt", {**base, "prompt": text_of(m.get("content"))})})
        elif role == "assistant":
            calls = [c for c in m.get("content") or [] if isinstance(c, dict)
                     and c.get("type") == "toolCall"]
            txt = text_of(m.get("content"))
            if txt.strip():
                final = txt
            for c in calls:
                cid, name, args = str(c.get("id")), str(c.get("name")), c.get("arguments") or {}
                pre = {**base, "tool": name, "input": args, "call_id": cid, "model": model}
                d = hook("pre_tool", pre)
                side = do_tool(name, args, cwd) if d.get("action") != "deny" else "denied"
                res = results.get(cid) or {}
                post = hook("post_tool", {**pre, "output": text_of(res.get("content")),
                                          "is_error": bool(res.get("isError"))})
                log.append({"tool": name, "pre": d.get("action"), "side": side,
                            "post_s": post.get("_s")})
    stop = hook("stop", {**base, "final_text": final or None})
    return {"session": str(session), "cwd": cwd, "model": model, "steps": len(log),
            "final_text": final[:2000], "stop": stop, "log": log}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--cwd")
    ap.add_argument("--out")
    a = ap.parse_args()
    out = replay(pathlib.Path(a.session), a.cwd)
    vh = pathlib.Path(os.environ.get("VACANT_HOME") or pathlib.Path.home() / ".vacant")
    notes = sorted(vh.rglob("delivery.json"))
    out["delivery"] = json.loads(notes[-1].read_text()) if notes else None
    reviews = []
    for chain in vh.rglob("chain.ndjson"):
        for ln in chain.read_text().split("\n"):
            if not ln.strip():
                continue
            e = json.loads(ln)
            if e.get("type") == "review":
                reviews.append(e.get("payload"))
    out["reviews"] = reviews
    s = json.dumps(out, ensure_ascii=False, indent=1, default=str)
    if a.out:
        pathlib.Path(a.out).write_text(s)
    print(json.dumps({"stop": out["stop"], "steps": out["steps"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
