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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
