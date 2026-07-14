"""MCP stdio tee-proxy —— 夾在 Hermes 與真正的 vacant MCP server 之間，原樣轉送並側錄。

Hermes 用 stdio（newline-delimited JSON-RPC）跟 MCP server 講話。把這支插在中間，
對 Hermes **完全透明**（stdin/stdout 逐行原樣轉送），但把雙向每一筆 JSON-RPC 加上
時間戳與方向記到 logfile。這是「Hermes 到底有沒有呼叫 vacant、問了什麼、vacant 回了
什麼」的**邊界鐵證**——不需 root、不改 Hermes 一行碼。

用法（把 Hermes config 裡 vacant server 的 command 換成這支）：
    command: python
    args: ["-m", "vacant.mcp_trace", "/tmp/vacant_wire.jsonl", "--", "python", "-m", "vacant.mcp_server"]

之後用 `vacant trace /tmp/vacant_wire.jsonl` 把它渲染成可讀時間軸。
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time


def _pump(src, dst, logf, direction: str, lock: threading.Lock) -> None:
    """逐行：原樣轉送到 dst，同時把該行 JSON-RPC 記到 logf。"""
    for line in iter(src.readline, b""):
        try:
            dst.write(line)
            dst.flush()
        except (BrokenPipeError, ValueError):
            break
        rec: dict = {"ts": time.time(), "t": time.strftime("%H:%M:%S"), "dir": direction}
        text = line.decode("utf-8", "replace").rstrip("\r\n")
        if not text:
            continue
        try:
            rec["msg"] = json.loads(text)
        except Exception:
            rec["raw"] = text
        with lock:
            logf.write((json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
            logf.flush()
    try:
        dst.close()
    except Exception:
        pass


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] != "--":
        print("usage: python -m vacant.mcp_trace <logfile> -- <cmd> [args...]", file=sys.stderr)
        return 2
    logfile, cmd = argv[0], argv[2:]
    # 子行程的 stderr 直接繼承（FastMCP 的 log 照樣讓 Hermes/使用者看到）。
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
    lock = threading.Lock()
    with open(logfile, "ab", buffering=0) as logf:
        logf.write((json.dumps({"ts": time.time(), "t": time.strftime("%H:%M:%S"),
                                "dir": "proxy", "raw": f"start: {' '.join(cmd)}"}) + "\n").encode())
        logf.flush()
        t_in = threading.Thread(target=_pump,
                                args=(sys.stdin.buffer, proc.stdin, logf, "hermes->vacant", lock),
                                daemon=True)
        t_out = threading.Thread(target=_pump,
                                 args=(proc.stdout, sys.stdout.buffer, logf, "vacant->hermes", lock),
                                 daemon=True)
        t_in.start()
        t_out.start()
        rc = proc.wait()
        t_out.join(timeout=2)
    return rc


# ---------------------------------------------------------------------------
# Adoption-state classifier for MCP wire traces (engineering, audit-only)
# ---------------------------------------------------------------------------

_VACANT_TOOLS = ("verify_fix", "a2a_call", "get_reputation", "submit_review")


def _is_vacant_tool(name: str) -> bool:
    """判斷工具名是否屬於 vacant 生態系。"""
    return any(v in name for v in _VACANT_TOOLS)


def analyze_adoption(records: list[dict]) -> dict:
    """把 tee-proxy 側錄的 JSON-RPC trace 分類成 Hermes adoption state。

    回傳 dict：
        state       : str  – one of {not_observed, discovered_not_selected,
                          selected_failed, adopted, infra_void}
        evidence    : dict – 每個判斷點引用的事件索引（0-based）
        consideration: str – 固定為 "unobservable"

    分類邏輯（由粗到細）：
      1. infra_void   ：所有行都無法解析成 JSON，或 records 完全為空。
      2. not_observed ：沒有 discovery 證據（hermes->vacant 方向無 tools/list
         或 initialize）。
      3. discovered_not_selected：有 tools/list + reply 顯示 vacant 工具在清單中，
         但沒有對任何 vacant tool 的 tools/call。
      4. selected_failed：有 tools/call 到 vacant tool，但對應回覆是 error 或
         完全沒有回覆。
      5. adopted      ：有 tools/call 到 vacant tool 且有成功 result 回覆。

    注意：本函式只分析 wire trace；Hermes 內部的 consideration / decision
    永遠標示為 unobservable，不得推論。
    """
    evidence: dict = {
        "discovery": [],       # hermes->vacant 的 discovery 事件索引
        "selection": [],       # hermes->vacant tools/call to vacant tool 索引
        "reply_ok": [],        # vacant->hermes 成功回覆索引
        "reply_err": [],       # vacant->hermes error 回覆索引
    }

    # --- infra_void check ---------------------------------------------------
    if not records:
        return {
            "state": "infra_void",
            "evidence": evidence,
            "consideration": "unobservable",
        }

    parseable = [i for i, r in enumerate(records) if isinstance(r.get("msg"), dict)]
    if not parseable:
        return {
            "state": "infra_void",
            "evidence": evidence,
            "consideration": "unobservable",
        }

    # --- collect events by direction & method -------------------------------
    discovery_indices: list[int] = []   # hermes->vacant initialize / tools/list
    selection_ids: dict[int, int] = {}  # id -> event index (hermes->vacant tools/call to vacant)
    reply_ok_ids: dict[int, int] = {}   # id -> event index (result)
    reply_err_ids: dict[int, int] = {}  # id -> event index (error)

    for idx in parseable:
        rec = records[idx]
        msg = rec.get("msg", {})
        direction = rec.get("dir", "")
        method = msg.get("method")
        mid = msg.get("id")

        if direction == "hermes->vacant":
            # discovery: only tools/list proves Hermes discovered vacant's capabilities.
            # initialize is just a connection handshake, not capability discovery.
            if method == "tools/list":
                discovery_indices.append(idx)
                evidence["discovery"].append(idx)
            # selection: tools/call to a vacant tool
            elif method == "tools/call" and mid is not None:
                name = (msg.get("params") or {}).get("name", "")
                if _is_vacant_tool(name):
                    selection_ids[mid] = idx
                    evidence["selection"].append(idx)

        elif direction == "vacant->hermes":
            # Only count replies for tools/call methods (not initialize/tools/list)
            if mid is not None and ("result" in msg or "error" in msg):
                # Check if this id corresponds to a selection (tools/call) we tracked
                if mid in selection_ids:
                    if "error" in msg:
                        reply_err_ids[mid] = idx
                        evidence["reply_err"].append(idx)
                    else:
                        reply_ok_ids[mid] = idx
                        evidence["reply_ok"].append(idx)

    # --- classify -----------------------------------------------------------
    # 1. not_observed：沒有 discovery 證據
    if not discovery_indices:
        return {
            "state": "not_observed",
            "evidence": evidence,
            "consideration": "unobservable",
        }

    # 2. discovered_not_selected：有 discovery 但沒有 vacant selection
    if not selection_ids:
        return {
            "state": "discovered_not_selected",
            "evidence": evidence,
            "consideration": "unobservable",
        }

    # 3. selected_failed vs adopted：檢查每個 selection id 的回覆狀態
    for mid, sel_idx in selection_ids.items():
        if mid in reply_err_ids:
            return {
                "state": "selected_failed",
                "evidence": evidence,
                "consideration": "unobservable",
            }
        # 沒有回覆（既無 result 也無 error）也算 failed
        if mid not in reply_ok_ids and mid not in reply_err_ids:
            return {
                "state": "selected_failed",
                "evidence": evidence,
                "consideration": "unobservable",
            }

    # 4. adopted：所有 selection 都有成功回覆
    return {
        "state": "adopted",
        "evidence": evidence,
        "consideration": "unobservable",
    }


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
