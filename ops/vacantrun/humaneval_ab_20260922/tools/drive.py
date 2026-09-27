#!/usr/bin/env python3
"""在**真 pty** 裡開 agent 的對話介面，把那一行任務**打進輸入框**，等它做完，再離開。

兩臂共用同一支：ON 臂的命令是 `vacant on ...`，OFF 臂是純 `pi`。
**同一段輸入、同一套完成判定、同一種離開方式** ⇒ 差別只剩「有沒有 Vacant」。

## 為什麼是打字而不是命令列帶 prompt

人類 2026-09-22：「最好使用對話的 cli」。`pi "prompt"`（不帶 `-p`）雖然也會進 TUI，
但那是**啟動參數**不是對話；打進輸入框才是使用者真的在做的事。而且 `vacant on`
本來就不收初始訊息，打字是它唯一的入口。

## 完成判定＝輸出靜默（啟發式，兩臂相同）

ON 臂走 `vacant on` 時沒有掛鉤日誌（掛鉤是 `gateshim` 裝的，`agentwrap` 不裝），
所以不能用確定性的 `agent_end`。**兩臂都用同一個靜默門檻**，讓它至少是同一把尺。
⚠ 這是啟發式：模型想很久會被誤判成做完。`--min-run` 與 `--idle` 都落進報告。

## 離開

先送 `/quit` ＋ Enter（pi 的正規離開），沒反應再送 Ctrl-D，再沒反應 SIGTERM。
⚠ 離開方式會影響閘門什麼時候跑（閘門在**行程結束**那一刻），所以它是規格的一部分。
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import pty
import re
import select
import signal
import struct
import sys
import termios
import time

_ESC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[A-Za-z]"
                  r"|\x1b[=>]|[\x00-\x08\x0b-\x1f\x7f]")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--text", required=True, help="打進輸入框的那一行（逐字落盤）")
    ap.add_argument("--boot", type=float, default=10.0, help="等 TUI 起來幾秒")
    ap.add_argument("--idle", type=float, default=45.0, help="靜默幾秒算做完")
    ap.add_argument("--min-run", type=float, default=30.0)
    ap.add_argument("--cap", type=float, default=900.0)
    ap.add_argument("--rows", type=int, default=44)
    ap.add_argument("--cols", type=int, default=150)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        sys.stderr.write("沒有命令\n")
        return 2

    rep = {"cmd": cmd, "text": a.text, "idle_s": a.idle, "min_run_s": a.min_run,
           "cap_s": a.cap, "boot_s": a.boot, "events": [],
           "typed": False, "done_by": None, "exit_status": None}
    t_start = time.time()
    pid, fd = pty.fork()
    if pid == 0:
        os.environ["TERM"] = "xterm-256color"
        os.execvp(cmd[0], cmd)
    fcntl.ioctl(fd, termios.TIOCSWINSZ,
                struct.pack("HHHH", a.rows, a.cols, 0, 0))
    buf = bytearray()
    last_out = [time.time()]
    dead = [False]

    def note(kind, **kw):
        rep["events"].append({"t": round(time.time() - t_start, 2),
                              "kind": kind, **kw})

    def pump(seconds: float) -> bool:
        end = time.time() + seconds
        while time.time() < end:
            r, _, _ = select.select([fd], [], [], 0.2)
            if fd in r:
                try:
                    d = os.read(fd, 65536)
                except OSError:
                    dead[0] = True
                    return False
                if not d:
                    dead[0] = True
                    return False
                buf.extend(d)
                last_out[0] = time.time()
        return True

    def send(s: bytes, what: str):
        try:
            os.write(fd, s)
            note("sent", what=what)
        except OSError:
            dead[0] = True

    # 1) 等 TUI 起來
    pump(a.boot)
    # 2) 打字 → Esc（關掉自動補全彈窗，它會吃掉第一個 Enter）→ Enter
    if not dead[0]:
        send(a.text.encode("utf-8"), "task_text")
        pump(1.0)
        send(b"\x1b", "esc_dismiss_autocomplete")
        pump(0.4)
        send(b"\r", "enter")
        rep["typed"] = True
    # 3) 等做完：靜默 idle 秒，且至少跑滿 min_run
    while not dead[0]:
        el = time.time() - t_start
        if el > a.cap:
            rep["done_by"] = "cap"
            note("cap_hit")
            break
        if el > a.min_run and (time.time() - last_out[0]) > a.idle:
            rep["done_by"] = "idle"
            note("idle_done", quiet_s=round(time.time() - last_out[0], 1))
            break
        pump(1.0)
    if dead[0]:
        rep["done_by"] = rep["done_by"] or "child_exited"
    # 4) 離開：/quit → Ctrl-D → SIGTERM
    if not dead[0]:
        send(b"/quit", "quit_cmd")
        pump(0.5)
        send(b"\x1b", "esc")
        pump(0.3)
        send(b"\r", "enter")
        pump(8.0)
    if not dead[0]:
        send(b"\x04", "ctrl_d")
        pump(8.0)
    if not dead[0]:
        note("sigterm")
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        pump(5.0)
    try:
        _, status = os.waitpid(pid, 0)
        rep["exit_status"] = status
    except (ChildProcessError, OSError):
        rep["exit_status"] = None
    raw = bytes(buf)
    open(a.transcript, "wb").write(raw)
    txt = _ESC.sub("", raw.decode("utf-8", "replace"))
    rep["wall_s"] = round(time.time() - t_start, 1)
    rep["transcript_bytes"] = len(raw)
    rep["tui_seen"] = bool(re.search(r"ctrl\+c|Working|esc |\(vacant", txt, re.I))
    open(a.report, "w", encoding="utf-8").write(
        json.dumps(rep, ensure_ascii=False, indent=2))
    print(json.dumps({k: rep[k] for k in
                      ("wall_s", "done_by", "typed", "tui_seen",
                       "transcript_bytes")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
