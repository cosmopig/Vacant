#!/usr/bin/env python3
"""在真的 pty 裡開 pi 互動 TUI，依序送 /vacant status、/vacant off、/vacant on、/quit，
把全部輸出落盤。判準不在這裡（在呼叫端看 hooks 日誌與輸出檔）。"""
import os, pty, select, sys, time, fcntl, termios, struct, signal

out_path = sys.argv[1]
cmd = sys.argv[2:]
pid, fd = pty.fork()
if pid == 0:
    os.environ["TERM"] = "xterm-256color"
    os.execvp(cmd[0], cmd)

fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 140, 0, 0))
buf = bytearray()


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


def send(s):
    os.write(fd, s.encode())


pump(8)                         # TUI 起來
for line in ("/vacant status", "/vacant off", "/vacant on", "/vacant status"):
    send(line)
    pump(0.8)
    send("\x1b")           # 關掉自動補全的彈窗（它會吃掉第一個 Enter）
    pump(0.4)
    send("\r")
    pump(4)
send("/quit")
pump(0.6)
send("\r")
alive = pump(5)
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
with open(out_path, "wb") as f:
    f.write(bytes(buf))
print(f"bytes={len(buf)} status={status}")
