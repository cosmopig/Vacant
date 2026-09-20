#!/usr/bin/env python3
"""**互動模式下，模型看到的東西跟 `-p` 一樣嗎？**——逐位元比對第一通請求。

這一支回答的是人類質疑裡最實質的那一半：如果 `pi -p` 與互動 TUI 送給模型的
system prompt、工具清單、取樣參數不一樣，那 600 格量到的行為就綁在一個
沒人會用的輸入上。

證據來源是 `vacant run` 自己落的 wire log（`wire_RUN-ON/<call_id>.req.bin`）
——**中介留下來的那份原文**，不是我們事後重建的。

比法：同一題、同一 rep，取 `PTP`（pty × `pi -p`）與 `INT`（pty × 互動 TUI）
各自**第一通** `POST /v1/chat/completions` 的 body，逐欄比：

  · `messages[0]`（system）      逐位元
  · 其餘 messages 的 role/內容   逐位元
  · `tools[*].function.name`     集合
  · 取樣與上限參數               逐值

⚠ **只比第一通。** 第二通起的內容取決於模型上一通回了什麼，模型是隨機的
  ⇒ 之後的差不可歸因於呼叫形態。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib


def first_chat_request(cell_dir: pathlib.Path) -> dict | None:
    idx = cell_dir / "wire_RUN-ON" / "index.jsonl"
    if not idx.exists():
        return None
    for line in idx.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("method") == "POST" and "/chat/completions" in (r.get("path") or ""):
            p = cell_dir / "wire_RUN-ON" / f"{r['call_id']}.req.bin"
            if not p.exists():
                return None
            raw = p.read_bytes()
            try:
                body = json.loads(raw.decode("utf-8"))
            except ValueError:
                return {"raw_sha256": hashlib.sha256(raw).hexdigest(),
                        "parse_error": True}
            return {"raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "raw_bytes": len(raw), "body": body}
    return None


#: 這些東西**每一格本來就不一樣**，跟呼叫形態無關。不抵銷掉的話
#: 「system prompt 不同」會是假陽性（2026-09-20 第一版就踩到：兩邊
#: `system_chars` 都是 2778、`raw_bytes` 都是 5983，只有工作區路徑裡的
#: `PTP`／`INT` 三個字母不同——而那三個字母是**我們自己的目錄名**）。
def _norm(text: str, cell: str) -> str:
    out = text.replace(cell, "<CELL>")
    task, arm, rep = cell.rsplit("_", 2)
    for token in (f"ws_{cell}", cell, f"ttymode_{cell}", arm):
        out = out.replace(token, "<X>")
    return out


def summarize(req: dict | None, cell: str = "") -> dict | None:
    if req is None or "body" not in req:
        return req
    b = req["body"]
    msgs = b.get("messages") or []
    tools = b.get("tools") or []
    sys_json = json.dumps(msgs[0], sort_keys=True, ensure_ascii=False) if msgs else ""
    all_json = json.dumps(msgs, sort_keys=True, ensure_ascii=False)
    return {
        "raw_sha256": req["raw_sha256"], "raw_bytes": req["raw_bytes"],
        "model": b.get("model"),
        "n_messages": len(msgs),
        "roles": [m.get("role") for m in msgs],
        # 兩種雜湊都給：`*_raw` 是原文（含工作區路徑），`*_norm` 是抵銷掉
        # 每格本來就不同的東西之後的。**能歸因給呼叫形態的只有 `_norm`。**
        "system_sha256_raw": (hashlib.sha256(sys_json.encode("utf-8")).hexdigest()
                              if msgs else None),
        "system_sha256": (hashlib.sha256(_norm(sys_json, cell).encode("utf-8"))
                          .hexdigest() if msgs else None),
        "system_text": (msgs[0].get("content") if msgs else None),
        "system_chars": len(sys_json) if msgs else None,
        "messages_sha256": hashlib.sha256(
            _norm(all_json, cell).encode("utf-8")).hexdigest(),
        "tool_names": sorted((t.get("function") or {}).get("name") or t.get("name")
                             for t in tools),
        "params": {k: b.get(k) for k in
                   ("temperature", "top_p", "max_tokens", "max_completion_tokens",
                    "stream", "tool_choice", "reasoning_effort", "stop")
                   if k in b},
        "other_keys": sorted(k for k in b
                             if k not in ("messages", "tools", "model")),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/var/tmp/vacant_tty_20260920")
    ap.add_argument("--tasks", default="lcb_3522,lcb_3584,lcb_3649,lcb_3715,lcb_3789")
    ap.add_argument("--rep", default="r1")
    ap.add_argument("--left", default="PTP", help="對照臂（pty × `pi -p`）")
    ap.add_argument("--right", default="INT", help="處理臂（pty × 互動 TUI）")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    root = pathlib.Path(a.root)
    import difflib
    rows = []
    for t in a.tasks.split(","):
        cl, cr = f"{t}_{a.left}_{a.rep}", f"{t}_{a.right}_{a.rep}"
        L = summarize(first_chat_request(root / "cells" / cl), cl)
        R = summarize(first_chat_request(root / "cells" / cr), cr)
        diff: dict = {}
        if L and R and "body" not in L and "body" not in R:
            # ⚠ `raw_sha256`／`system_sha256_raw` **刻意不列入判定**：
            #   它們含工作區路徑，每格本來就不同（見 `_norm` 的註解）。
            for k in ("system_sha256", "messages_sha256", "tool_names",
                      "params", "model", "roles", "other_keys"):
                if L.get(k) != R.get(k):
                    diff[k] = {a.left: L.get(k), a.right: R.get(k)}
            if "system_sha256" in diff:
                ls = _norm(L.get("system_text") or "", cl).splitlines()
                rs = _norm(R.get("system_text") or "", cr).splitlines()
                diff["system_unified_diff"] = list(difflib.unified_diff(
                    ls, rs, a.left, a.right, lineterm="", n=1))[:80]
        for d in (L, R):
            if isinstance(d, dict):
                d.pop("system_text", None)      # 不落全文，太長
        rows.append({"task": t, a.left: L, a.right: R, "diff": diff,
                     "identical": (bool(L) and bool(R) and not diff)})
    n_ok = sum(1 for r in rows if r["identical"])
    blob = json.dumps({"left": a.left, "right": a.right, "rep": a.rep,
                       "n": len(rows), "n_identical": n_ok, "rows": rows},
                      ensure_ascii=False, indent=2)
    if a.out:
        pathlib.Path(a.out).write_text(blob, encoding="utf-8")
    print(blob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
