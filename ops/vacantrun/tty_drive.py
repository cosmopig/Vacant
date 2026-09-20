#!/usr/bin/env python3
"""這支在架構裡承重什麼：**把「人真的坐在終端機前面」做成可重跑的實驗條件**。

`ops/vacantrun/wrap_agent.sh` 那支（凍結）走的是 `pi -p`＝一次性 headless。
2026-09-20 人類質疑：**沒有人是那樣用 pi 的**，那 600 格的結論綁在一個
不真實的使用形態上。要回答這個質疑，就必須真的在**互動式 TUI** 下再量一次，
而互動式 TUI 的前提是「stdin 與 stdout 兩邊都是 tty」。

pi 0.85.1 的 `dist/main.js:resolveAppMode()` 逐字是：

    if (parsed.mode === "rpc")   return "rpc";
    if (parsed.mode === "json")  return "json";
    if (parsed.print || !stdinIsTTY || !stdoutIsTTY) return "print";
    return "interactive";

⇒ **`-p` 只是三個充分條件的其中一個**。把 stdout 導進檔案（`vacant run --json`
做的正是這件事）或把 stdin 接到 `/dev/null`（launcher 的預設）**任一個**都會
讓 pi 落回 print 模式。所以「拿掉 `-p`」本身完全不夠——**必須配一張真的 pty**。
本檔就是那張 pty。

## 它做什麼

1. `pty.fork()` 起一張真的 pty（含 setsid ＋ TIOCSCTTY ⇒ 子行程有控制終端），
   設好 winsize 與 `TERM`，然後在裡面 exec 使用者給的命令
   （通常是 `python3 -m vacant_network.vrun.launcher … --stdin inherit -- …`）。
2. 連續把 pty master 的輸出抽乾並落盤（不抽乾子行程會寫爆 pty buffer 卡死）。
3. **決定什麼時候「人」會離開**，然後模擬那個離開：
   · 首選訊號＝`--done-when-hooklog <path>` 裡出現 `event == "stop"`
     （pi extension 的 `agent_end`）——**確定性**，不是猜。
   · 沒有 hook log 時退回 `--idle <秒>` 的輸出靜默偵測（**啟發式**，會被
     會自己重繪的 TUI 騙到 ⇒ 落盤記 `done_signal="idle"` 讓判讀的人知道）。
4. 依序升級送出離開動作，**每一步落盤**：`ctrl_d` → `ctrl_c ×2` → `SIGTERM`
   → `SIGKILL`。真的是哪一步讓它結束的，寫在 `ended_by` 欄位。

## 誠實邊界（改碼請保留）

1. **這支不保證 pi 真的進了互動模式。** 唯一算數的證據是 `--mode-oracle`
   那一格（`PI_STARTUP_BENCHMARK=1` 在非互動模式下 pi 會 exit 1 並印
   `only supports interactive mode`）與逐字轉錄裡的 TUI escape sequence。
   **量之前先證明量得動**：`tty_drive.py --self-check` 會同時跑正控制
   （有 pty ⇒ `isatty=True`）與負控制（沒 pty ⇒ `isatty=False`）。
2. **模擬的人不是人。** 這支只送得出「離開」，不會看畫面、不會追問、
   不會在 agent 走偏時打斷。⇒ 它量得到的是**通道與閘門**在互動模式下成不成立，
   量不到「真人會不會得到不同的結果」。後者本檔沒有量，不可以拿去講。
3. **`ended_by` 不等於「agent 自己退出」。** 互動式 TUI 不會自己結束
   （`interactive-mode.js` 的 `while (true) { getUserInput(); … }`），
   所以**每一格的結束都是這支送出去的**。`-p` 那邊的「agent 退出碼 0 走人」
   在這裡的對應物是「agent 跑完一回合、TUI 回到輸入框、我們按 Ctrl-D」。
   兩件事不是同一件事，寫報告時不可以混講。
4. 轉錄有上限（`--max-transcript-bytes`）。截掉了就落 `transcript_truncated`。
5. **這張 pty 關掉了 `ISIG`**（見 `_disable_isig`），所以它與真人的終端機
   在「Ctrl-C 會不會變成 SIGINT」這一點上不同。不關的話，pi 退出、終端機
   還原成 canonical 之後，階梯補送的 Ctrl-C 會把**還在跑驗收的 launcher**
   一起殺掉。這是 2026-09-20 實際踩到的坑，不是假設。
6. **agent 收攤（hook log 的 `session_end`）之後階梯就凍結**。之後還在跑的
   是 launcher 的驗收，那是正常的。沒有這一條，慢的格子會在驗收中途被砍，
   而症狀是 `run_*.json` 不存在——看起來像「中介失敗」，其實是量具殺的。
"""
from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import pathlib
import pty
import re
import select
import signal
import struct
import sys
import termios
import time

#: 送得出去的「離開」動作，**依序升級**。
CTRL_D = b"\x04"
CTRL_C = b"\x03"

#: 拿掉 ANSI/TUI 控制序列，只為了給人讀的那一份副本。
_ANSI = re.compile(rb"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
                   rb"|\x1b[@-Z\\-_]|\r")


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ,
                    struct.pack("HHHH", rows, cols, 0, 0))
    except OSError:
        pass


def _disable_isig(fd: int) -> bool:
    """把 pty 的 `ISIG` 關掉，回「有沒有關成」。

    🔴 **這一條是被實測逼出來的（2026-09-20）。** 原本的升級階梯在 Ctrl-D
    之後會補送 `Ctrl-C ×2`。在**互動的 pi 底下那是無害的**——pi 把終端機設成
    raw，0x03 只是一個位元組，由 `handleCtrlC()` 讀走。但 **pi 退出之後**
    它會把終端機還原成 canonical＋`ISIG`，而那時候的 0x03 **會由 line
    discipline 變成送給前景行程群組的 `SIGINT`** ⇒ 把**還在跑驗收的
    launcher** 一起殺掉，`run_*.json` 根本不會被寫出來。
    實際發生過：`lcb_3584_PTP_r1` `ended_by=ctrl_c_twice` 而 run json 不存在。

    關掉 `ISIG` 之後 0x03 永遠只是一個位元組。**這不改變 pi 的行為**
    （pi 本來就自己關 `ISIG`），只拿掉「pi 不在了還會誤殺父行程」這條路。
    ⚠ 代價：這張 pty 與真人的終端機**在這一點上不同**。寫在這裡，不要忘。
    """
    try:
        attrs = termios.tcgetattr(fd)
        attrs[3] &= ~termios.ISIG          # lflag
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        return True
    except (termios.error, OSError):
        return False


def _hooklog_stop_count(path: pathlib.Path) -> int:
    """hook log 裡有幾筆 `agent_end`（＝跑完了幾個回合）。讀不到回 0。

    ⚠ 回 0 在這裡**是「讀不到」與「真的零筆」同形**——這支只拿它當
      「要不要送離開」的觸發，不當結論。結論用的是 hook log 原文本身。
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    n = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("event") == "stop":
            n += 1
    return n


def _hooklog_has(path: pathlib.Path, event: str) -> bool:
    """hook log 裡有沒有某個事件。`session_end` ＝ agent 自己已經收攤。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return f'"event": "{event}"' in text or f'"event":"{event}"' in text


def drive(argv: list[str], *, transcript: pathlib.Path,
          rows: int = 40, cols: int = 120,
          idle_s: float = 45.0, cap_s: float = 1800.0,
          hooklog: pathlib.Path | None = None,
          grace_s: float = 60.0, min_run_s: float = 5.0,
          post_done_s: float = 3.0, turns: int = 1,
          turn_text: str = "",
          max_transcript_bytes: int = 16 * 1024 * 1024,
          env_extra: dict[str, str] | None = None) -> dict:
    """在一張真 pty 裡跑 `argv`，跑完模擬「人離開」，回一份逐項落盤的報告。"""
    transcript.parent.mkdir(parents=True, exist_ok=True)
    fh = transcript.open("wb", buffering=0)
    rep: dict = {
        "argv": argv, "rows": rows, "cols": cols,
        "idle_s": idle_s, "cap_s": cap_s, "grace_s": grace_s,
        "post_done_s": post_done_s, "turns_requested": turns,
        "turn_text": turn_text or None, "turns_typed": 0,
        "stops_seen": None,
        "hooklog": str(hooklog) if hooklog else None,
        "t_start": time.time(), "events": [],
        # 三態：`None` ＝沒量到。**不准寫 0／False 冒充。**
        "done_signal": None, "ended_by": None, "exit_code": None,
        "signaled_by": None, "bytes_out": 0, "transcript_truncated": False,
        "child_is_tty": None, "isig_disabled": None, "agent_gone_at_s": None,
    }

    def note(kind: str, **kw) -> None:
        rep["events"].append({"kind": kind, "t": round(time.time() - rep["t_start"], 3), **kw})

    env = dict(os.environ)
    env.setdefault("TERM", "xterm-256color")
    env.setdefault("COLUMNS", str(cols))
    env.setdefault("LINES", str(rows))
    if env_extra:
        env.update(env_extra)

    pid, master = pty.fork()
    if pid == 0:                                    # 子行程：已在新 session，
        try:                                        # pty slave 已是 fd 0/1/2
            os.execvpe(argv[0], argv, env)
        except Exception as exc:                    # noqa: BLE001
            sys.stderr.write(f"exec failed: {exc!r}\n")
            os._exit(127)
    rep["child_pid"] = pid
    _set_winsize(master, rows, cols)
    rep["isig_disabled"] = _disable_isig(master)    # 見該函式的 🔴
    rep["child_is_tty"] = os.isatty(master)         # master 端；slave 必為 tty

    last_out = time.time()
    t0 = time.time()
    quit_stage = 0          # 0 未送、1 Ctrl-D、2 Ctrl-C×2、3 SIGTERM、4 SIGKILL
    stage_at = 0.0
    done_seen = False
    done_at = 0.0
    last_typed_at = t0
    agent_gone = False
    status = None
    eof = False

    def send(data: bytes, label: str) -> None:
        try:
            os.write(master, data)
            note("sent", what=label)
        except OSError as exc:
            note("send_failed", what=label, err=repr(exc))

    while True:
        # ── 子行程收工了嗎 ────────────────────────────────────────────
        try:
            wpid, wstatus = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            wpid, wstatus = pid, 0
        if wpid == pid:
            status = wstatus
            # 把 pty 裡剩下的位元組抽乾（子行程死了 master 才會 EOF）
            deadline = time.time() + 2.0
            while time.time() < deadline:
                r, _, _ = select.select([master], [], [], 0.1)
                if not r:
                    break
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                fh.write(chunk)
                rep["bytes_out"] += len(chunk)
            break

        r, _, _ = select.select([master], [], [], 0.2)
        if r and not eof:
            try:
                chunk = os.read(master, 65536)
            except OSError as exc:
                if exc.errno == errno.EIO:          # Linux：所有 slave 關了
                    eof = True
                    chunk = b""
                else:
                    raise
            if chunk:
                last_out = time.time()
                if rep["bytes_out"] < max_transcript_bytes:
                    fh.write(chunk)
                    rep["bytes_out"] += len(chunk)
                else:
                    rep["transcript_truncated"] = True

        now = time.time()
        # ── 什麼時候算「該做的回合都做完了」 ─────────────────────────
        #   `turns > 1`：每看到一筆 `agent_end` 就打一段字＋Enter，
        #   模擬「人看了結果之後又說了一句」。**這是另一個處理，不是同一個**
        #   ——它與 `-p` 的差別同時包含「有 TUI」與「多了一輪人類輸入」兩件事，
        #   判讀時不可以拿來跟單輪的臂相減。
        if not done_seen and (now - t0) >= min_run_s:
            stops = _hooklog_stop_count(hooklog) if hooklog is not None else 0
            rep["stops_seen"] = stops if hooklog is not None else None
            if hooklog is not None and stops >= turns:
                done_seen, done_at = True, now
                rep["done_signal"] = "hooklog_stop"
                note("done", how="hooklog_stop", stops=stops)
            elif (hooklog is not None and turns > 1
                  and stops > rep["turns_typed"] and stops < turns
                  and (now - last_typed_at) >= post_done_s):
                rep["turns_typed"] += 1
                last_typed_at = now
                note("typed_turn", n=rep["turns_typed"], stops=stops)
                send(turn_text.encode("utf-8") + b"\r", f"turn#{rep['turns_typed']}")
            elif (now - last_out) >= idle_s:
                done_seen, done_at = True, now
                rep["done_signal"] = "idle"
                note("done", how="idle", quiet_s=round(now - last_out, 2))

        # ── 模擬「人離開」：依序升級 ──────────────────────────────────
        #  ⚠ `post_done_s`：`agent_end` 燒完到 TUI 真的回到空輸入框之間有一段。
        #    太早按 Ctrl-D 會落在還沒接手的 editor 上（`onCtrlD` 只在輸入框是空的
        #    時候才收）。等一下再按——真人也不是零延遲。
        #  🔴 **agent 自己收攤之後就不要再升級了。** `session_end` 之後
        #     還在跑的是 **launcher 的驗收**（每個測試檔上限 `--test-timeout`，
        #     這一批是 120 秒），那是正常的、不是卡住。繼續升級會把驗收殺掉，
        #     `run_*.json` 連寫都沒寫（2026-09-20 實際踩到）。
        if (not agent_gone and hooklog is not None
                and _hooklog_has(hooklog, "session_end")):
            agent_gone = True
            rep["agent_gone_at_s"] = round(now - t0, 3)
            note("agent_gone", how="hooklog_session_end")
        if not agent_gone:      # agent 還在 ⇒ 階梯照走；收攤了 ⇒ 只等
            if done_seen and quit_stage == 0 and (now - done_at) >= post_done_s:
                quit_stage, stage_at = 1, now
                send(CTRL_D, "ctrl_d")
            elif quit_stage == 1 and (now - stage_at) >= grace_s:
                quit_stage, stage_at = 2, now
                send(CTRL_C, "ctrl_c#1")
                time.sleep(0.05)
                send(CTRL_C, "ctrl_c#2")
            elif quit_stage == 2 and (now - stage_at) >= grace_s:
                quit_stage, stage_at = 3, now
                note("signal", sig="SIGTERM")
                rep["signaled_by"] = "SIGTERM"
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError as exc:
                    note("signal_failed", sig="SIGTERM", err=repr(exc))
            elif quit_stage == 3 and (now - stage_at) >= grace_s:
                quit_stage, stage_at = 4, now
                note("signal", sig="SIGKILL")
                rep["signaled_by"] = "SIGKILL"
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError as exc:
                    note("signal_failed", sig="SIGKILL", err=repr(exc))

        # ── 絕對上限 ──────────────────────────────────────────────────
        if (now - t0) >= cap_s and quit_stage < 3:
            note("cap_reached", wall_s=round(now - t0, 1))
            quit_stage, stage_at = 3, now
            rep["signaled_by"] = "SIGTERM"
            rep["done_signal"] = rep["done_signal"] or "cap"
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

    fh.close()
    try:
        os.close(master)
    except OSError:
        pass
    rep["ended_by"] = {0: "self", 1: "ctrl_d", 2: "ctrl_c_twice",
                       3: "sigterm", 4: "sigkill"}[quit_stage]
    if status is not None:
        if os.WIFEXITED(status):
            rep["exit_code"] = os.WEXITSTATUS(status)
            rep["exit_signal"] = None
        elif os.WIFSIGNALED(status):
            rep["exit_code"] = None
            rep["exit_signal"] = os.WTERMSIG(status)
    rep["wall_s"] = round(time.time() - rep["t_start"], 3)
    # 給人讀的那一份（拿掉 escape sequence）。**原始逐位元那一份不動。**
    try:
        raw = transcript.read_bytes()
        plain = _ANSI.sub(b"", raw)
        transcript.with_suffix(transcript.suffix + ".plain.txt").write_bytes(plain)
    except OSError:
        pass
    return rep


# ── 量具自檢：先證明「有沒有 tty」這件事這支量得動 ────────────────────
_PROBE = (
    "import sys,json;"
    "print(json.dumps({'stdin':sys.stdin.isatty(),'stdout':sys.stdout.isatty()}))"
)


def self_check(python: str = sys.executable) -> dict:
    """正控制（pty ⇒ True/True）＋ 負控制（無 pty ⇒ False/False）。

    兩個都對才算「量得動」。只有正控制的綠燈不算數。
    """
    import subprocess
    import tempfile

    out: dict = {"positive": None, "negative": None, "usable": False}
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td) / "probe.log"
        rep = drive([python, "-c", _PROBE], transcript=t, idle_s=2.0,
                    cap_s=60.0, min_run_s=0.0, grace_s=3.0)
        txt = t.read_text(encoding="utf-8", errors="replace")
        out["positive"] = {"raw": txt.strip()[-200:], "exit": rep["exit_code"]}
        for line in txt.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    out["positive"]["parsed"] = json.loads(line)
                except ValueError:
                    pass
        neg = subprocess.run([python, "-c", _PROBE], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, check=False)
        out["negative"] = {"raw": neg.stdout.strip(), "exit": neg.returncode}
        try:
            out["negative"]["parsed"] = json.loads(neg.stdout.strip())
        except ValueError:
            pass
    p = (out["positive"] or {}).get("parsed") or {}
    n = (out["negative"] or {}).get("parsed") or {}
    out["usable"] = bool(p.get("stdin") is True and p.get("stdout") is True
                         and n.get("stdin") is False and n.get("stdout") is False)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tty_drive.py",
        description="在一張真 pty 裡跑命令，跑完模擬「人離開」")
    ap.add_argument("--transcript", default=None, help="逐位元轉錄落點")
    ap.add_argument("--report", default=None, help="報告 JSON 落點（預設印 stdout）")
    ap.add_argument("--rows", type=int, default=40)
    ap.add_argument("--cols", type=int, default=120)
    ap.add_argument("--idle", type=float, default=45.0,
                    help="輸出靜默幾秒算做完（**啟發式**，只在沒 hook log 時用）")
    ap.add_argument("--done-when-hooklog", default=None,
                    help="這份 JSONL 出現 event==stop 就算做完（**確定性**）")
    ap.add_argument("--cap", type=float, default=1800.0, help="絕對上限秒數")
    ap.add_argument("--grace", type=float, default=60.0, help="每一級離開動作等幾秒")
    ap.add_argument("--min-run", type=float, default=5.0,
                    help="至少跑滿幾秒才開始判「做完了」")
    ap.add_argument("--post-done", type=float, default=3.0,
                    help="判定做完之後等幾秒才按 Ctrl-D（等 TUI 回到空輸入框）")
    ap.add_argument("--turns", type=int, default=1,
                    help="要幾個 agent 回合（>1 時每個回合結束後打一次 --turn-text）")
    ap.add_argument("--turn-text", default="",
                    help="第 2 個回合起，模擬的人打進去的那一句（逐字落盤）")
    ap.add_argument("--self-check", action="store_true",
                    help="只跑量具自檢（正控制＋負控制），不跑命令")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)

    if args.self_check:
        print(json.dumps(self_check(), ensure_ascii=False, indent=2))
        return 0

    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else list(args.cmd)
    if not cmd:
        print("要給 `-- <命令>`。停。", file=sys.stderr)
        return 2
    if not args.transcript:
        print("要給 --transcript。停。", file=sys.stderr)
        return 2
    rep = drive(cmd, transcript=pathlib.Path(args.transcript).resolve(),
                rows=args.rows, cols=args.cols, idle_s=args.idle,
                cap_s=args.cap, grace_s=args.grace, min_run_s=args.min_run,
                # `--turns 0` ＝ **人提早關掉終端機**（不等 agent 收工）。
                # 那是真實情境，不是錯誤用法 ⇒ 不夾成 1。
                post_done_s=args.post_done, turns=max(0, args.turns),
                turn_text=args.turn_text,
                hooklog=(pathlib.Path(args.done_when_hooklog).resolve()
                         if args.done_when_hooklog else None))
    blob = json.dumps(rep, ensure_ascii=False, indent=2)
    if args.report:
        pathlib.Path(args.report).write_text(blob, encoding="utf-8")
    else:
        print(blob)
    # 退出碼**透傳子行程的**（沒有退出碼＝被訊號砍 ⇒ 用 128+sig，不假裝 0）
    if rep.get("exit_code") is not None:
        return int(rep["exit_code"])
    return 128 + int(rep.get("exit_signal") or 0)


if __name__ == "__main__":
    raise SystemExit(main())
