#!/usr/bin/env python3
"""真 pty 開 pi 互動 TUI（常駐 extension 那條路、真模型），依序：
Ctrl+P ×2（使用者自己切走再切回）→ /vacant status → /quit。
全部輸出落盤；判準在呼叫端（掛鉤日誌的 vacant_off 筆數、proxyd journal、relay 日誌）。
沿用 possess_pi_20260922/tools/tui_drive.py 的教訓：斜線指令先送 Esc 關補全彈窗再送 Enter。"""
import os, pty, select, sys, time, fcntl, termios, struct, signal, json

out_path, marks_path = sys.argv[1], sys.argv[2]
cmd = sys.argv[3:]
pid, fd = pty.fork()
if pid == 0:
    os.environ["TERM"] = "xterm-256color"
    os.execvp(cmd[0], cmd)
fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 140, 0, 0))
buf = bytearray()
marks = []


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.2)
        if fd in r:
            try:
                data = os.read(fd, 65536)
            except OSError:
                return False
            if not data:
                return False
            buf.extend(data)
    return True


def mark(label):
    marks.append({"t": time.time(), "label": label, "offset": len(buf)})


def slash(line, wait=5):
    mark(line)
    os.write(fd, line.encode()); pump(0.8)
    os.write(fd, b"\x1b"); pump(0.4)
    os.write(fd, b"\r"); pump(wait)


# 等到狀態列出現 "(vacant)"（session_start 跑完、切到 vacant）才開始送；最多 90 秒。
# 第一次跑時 pi 還在下載 fd／ripgrep，輸入全部被 "Startup is still in progress" 吃掉。
t_ready = time.time() + 90
while time.time() < t_ready and b"(vacant)" not in buf:
    pump(1)
pump(3); mark("tui_up" if b"(vacant)" in buf else "tui_up_TIMEOUT")
# 使用者自己切模型：Ctrl+P（model cycling，文件寫明會觸發 model_select source=cycle）
mark("ctrl+p #1"); os.write(fd, b"\x10"); pump(4)
mark("ctrl+p #2"); os.write(fd, b"\x10"); pump(4)
slash("/vacant status")
mark("/quit"); os.write(fd, b"/quit"); pump(0.6); os.write(fd, b"\x1b"); pump(0.3); os.write(fd, b"\r")
alive = pump(6)
if alive:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    pump(2)
try:
    _, status = os.waitpid(pid, os.WNOHANG)
except ChildProcessError:
    status = -1
open(out_path, "wb").write(bytes(buf))
json.dump(marks, open(marks_path, "w"), indent=1)
print(f"bytes={len(buf)} status={status}")
