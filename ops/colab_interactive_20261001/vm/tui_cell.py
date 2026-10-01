#!/usr/bin/env python3
"""tui_cell — 互動式的「一格」：`cell.sh` 的互動版（pi 的 TUI 跑在 tmux 裡，不是 `pi --print`）。

這支在架構裡承重什麼：i1001 要量的是「使用者平常的用法」——打開 agent、打一句話、等它做完——所以每一格的 pi 都是
互動模式：每格一個新的 Linux 使用者＋bwrap（`sandbox.sh`，與第一批逐字相同）、每格一個 tmux（自己的 socket、
history-limit 50000、160x50）、等頁腳出現才打字、打同一句任務、用 session jsonl 判斷跑完（`tui_lib.DoneDetector`）、
Ctrl-D 正常退出；逾時（1800 秒，與 C5 相同）就殺 tmux、殺該使用者全部行程、記 rc 124。
紀錄欄位與 cell.sh 相同（meta.json／score.json／workspace_*.sha256／app_final／vacant_home／vacant_check.json），另加：
`sessions`（每段的完成偵測結果、void 原因、pane 檔、帳本加總）、`done_reason`、`pane` 檔、`infra_void`。

一個「單位」＝一題，分兩組線：
  A 線（`run_a_group`）：[有可見驗收的題庫] bridge prepare（conform，stop_check 關）→ A 的第 1 段 session →
     A 計分（快照）→ 兩條巢狀分支：R（逾時或沒交件才在**複本**上開新 session，總共最多 3 段，留最後一段）、
     K（bridge judge；accept ⇒ release 並停；否則**同一個工作區就地**開新 session，字＝同一句＋可見檢查的回報，最多 3 段；
     沒 accept ＝什麼都沒放行）。A、R、K 共用同一段第 1 session。
  C 線（`run_c_group`）：同一題、同樣的工作區（沒有契約）、使用者自己的安裝指令（`pipx install <wheel> && vacant install`）、
     打同一句、同樣的完成偵測。
計分一律另開一個新使用者、在圍牆裡跑既有的計分器（隱藏測試只在那一步出現）。A 計 A 的第 1 段工作區快照、R 計最後一段、
K 計**被放行的成品**（沒放行＝沒交）、C 計最後的工作區。

誠實邊界（寫進紀錄、不要在報告裡說成別的）：
- 沒有 PID 空間（同第一批）；網路是通的；bridge 的驗證沙箱 `bwrap` 在 Colab 上是否起得來沒有在這個容器驗過
  （`vm_selfcheck.py` 在 VM 上先量；必要時走 `bwrap` 的 /proc 綁定墊片，並記進發射紀錄）。
- K 組的 bridge 是 **non-adversarial** 的基準測試輔助（root 接收端；bridge 自己寫明）。
- 互動式的「跑完」是推論（讀 session 檔＋安靜 IDLE_S 秒）；`late_write_after_done` 非零就代表 IDLE_S 太短。
- 信任對話框（`.pi/` 之類）的處理（Down×4＋Enter ＝「這次不信任」）只在筆記裡量過選單，沒在真 pi 上按過；
  一旦出現就記進 meta（`trust_dialog`）。
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tui_lib import (DoneDetector, LedgerTail, MODEL_DEFAULT, PROVIDER, SessionTail, SlotPool, cell_name,  # noqa: E402
                     classify_session, footer_ready, has_deliverable, jsonl_rows, k_instruction, last_assistant,
                     max_gap_after_final, needs_retry, pane_exit_rc, pgrep_hook_count, session_tag,
                     sessions_dir_name, trust_dialog_present, trust_triggers, typed_matches, typing_plan)

PI_VERSION = "0.87.1"
K_EXIT = {"accept": 0, "reject": 40, "hold": 41, "escalate": 42, "void": 43}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log(msg: str) -> None:
    print(f"{now()} {msg}", flush=True)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run(*a: str, timeout: float | None = None, input: str | None = None, env: dict | None = None,
        cwd: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(list(a), capture_output=True, text=True, timeout=timeout, input=input, env=env, cwd=cwd)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(list(a), 124, (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""),
                                           "timeout")


@dataclasses.dataclass
class Cfg:
    eval_root: Path = Path("/srv/eval")
    runs_root: Path = Path("/srv/runs")
    bin_dir: Path = Path("/opt/eval/bin")
    wheel: str = ""                                   # 空＝/opt/eval/wheel/*.whl 的第一個
    model: str = MODEL_DEFAULT
    proxy: str = "http://127.0.0.1:18900"
    upstream: str = "g4"
    think: str = "off"
    agent_timeout: int = 1800                         # 每段 session 的牆鐘上限，與 C5 相同
    score_timeout: int = 900
    idle_s: float = 15.0
    ready_timeout: float = 90.0
    exit_wait_s: float = 60.0
    poll_s: float = 0.5
    term: str = "xterm-256color"
    cols: int = 160
    rows: int = 50
    bridge_py: str = "/opt/eval/bridgevenv/bin/python"
    bridge_script: str = "/opt/eval/bridge/ops/eval/native_acceptance_bridge.py"
    bridge_env: dict = dataclasses.field(default_factory=dict)       # 例如墊片 PATH
    bridge_sandbox: str = "bwrap"
    k_attempts: int = 3
    r_sessions: int = 3
    install_env: list = dataclasses.field(default_factory=list)      # 'VAR=值'，只給安裝那一步（本機測試的 proxy／CA）
    pi_extra_env: list = dataclasses.field(default_factory=list)

    @property
    def sandbox_sh(self) -> Path:
        return self.bin_dir / "sandbox.sh"

    @property
    def receivers(self) -> Path:
        return self.eval_root / "receivers"

    @property
    def cells(self) -> Path:
        return self.eval_root / "cells"

    @property
    def ledger_path(self) -> Path:
        return self.eval_root / "proxy" / "ledger.jsonl"

    def wheel_path(self) -> str:
        if self.wheel:
            return self.wheel
        ws = sorted(Path("/opt/eval/wheel").glob("*.whl"))
        return str(ws[0]) if ws else ""


# ── 使用者與目錄 ────────────────────────────────────────────────────────────────────────────────


@contextlib.contextmanager
def flock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def next_seq(cfg: Cfg) -> int:
    with flock(cfg.eval_root / "seq.lock"):
        p = cfg.eval_root / "seq"
        n = (int(p.read_text().strip() or 0) if p.exists() else 0) + 1
        p.write_text(str(n))
        return n


def create_user(cfg: Cfg, letter: str) -> tuple[str, int]:
    seq = next_seq(cfg)
    name = f"{letter}{seq:06d}"
    with flock(cfg.eval_root / "useradd.lock"):
        r = run("useradd", "-M", "-d", f"/home/{name}", "-s", "/bin/bash", "-K", "UMASK=077", name)
    if r.returncode != 0:
        raise RuntimeError(f"useradd {name} failed: {r.stderr.strip()[:200]}")
    return name, seq


def kill_user(user: str) -> int:
    """殺光這個使用者的全部行程（沒有 PID 空間，靠 uid）；回傳殺完之後還剩幾個。"""
    for _ in range(5):
        run("pkill", "-KILL", "-u", user)
        if run("pgrep", "-u", user).returncode != 0:
            break
        time.sleep(1)
    return len(run("pgrep", "-u", user).stdout.split())


def delete_user(cfg: Cfg, user: str) -> None:
    kill_user(user)
    with flock(cfg.eval_root / "useradd.lock"):
        run("userdel", user)


@dataclasses.dataclass
class Box:
    """一個隔離的機器狀態：一個新 Linux 使用者＋它的 <runs>/<名字>/{home,tmp,app,agentlog}。"""
    user: str
    seq: int
    C: Path
    vacant: bool = False

    @property
    def app(self) -> Path:
        return self.C / "app"

    @property
    def home(self) -> Path:
        return self.C / "home"

    @property
    def tmp(self) -> Path:
        return self.C / "tmp"

    @property
    def agentlog(self) -> Path:
        return self.C / "agentlog"


def build_box(cfg: Cfg, name: str, src_workspace: Path, *, vacant: bool) -> Box:
    user, seq = create_user(cfg, "a")
    C = cfg.runs_root / name
    shutil.rmtree(C, ignore_errors=True)
    for d in ("home", "tmp", "app", "agentlog"):
        (C / d).mkdir(parents=True)
    C.chmod(0o711)
    run("cp", "-a", f"{src_workspace}/.", str(C / "app") + "/")
    run("chown", "-R", f"{user}:{user}", *[str(C / d) for d in ("home", "tmp", "app", "agentlog")])
    for d in ("home", "tmp", "app", "agentlog"):
        (C / d).chmod(0o700)
    return Box(user=user, seq=seq, C=C, vacant=vacant)


def base_url(cfg: Cfg, tag: str) -> str:
    return f"{cfg.proxy}/t/{tag}/up/{cfg.upstream}/think/{cfg.think}/api/v1"


def write_models_json(cfg: Cfg, box: Box, base: str) -> None:
    d = box.tmp / "harbor-pi-agent"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "models.json"
    json.dump({"providers": {PROVIDER: {"baseUrl": base, "apiKey": "$OPENROUTER_API_KEY",
                                        "api": "openai-completions", "models": [{"id": cfg.model}]}}},
              open(p, "w"), indent=2)
    open(p, "a").write("\n")
    run("chown", "-R", f"{box.user}:{box.user}", str(d))
    d.chmod(0o700)
    p.chmod(0o600)


def sandbox_cmd(cfg: Cfg, box: Box, extra: list[str], inner: list[str]) -> list[str]:
    return ["bash", str(cfg.sandbox_sh), box.user, str(box.C), *extra, "--", *inner]


def install_vacant(cfg: Cfg, box: Box, L: Path) -> int | None:
    """C 組：使用者的安裝指令（最多 3 次；PyPI 下載失敗不該算成 C 組的表現，每次都記）。"""
    wheel = cfg.wheel_path()
    rc: int | None = None
    for k in (1, 2, 3):
        with open(L / "install.log", "a") as f:
            f.write(f"=== install attempt {k} {now()}\n")
        r = run(*sandbox_cmd(cfg, box, list(cfg.install_env),
                             ["bash", "-c", f"set -euo pipefail; pipx install '{wheel}' && mkdir -p /tmp/harbor-pi-agent && "
                                            f"PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent vacant install"]), timeout=900)
        with open(L / "install.log", "a") as f:
            f.write(r.stdout + r.stderr)
        rc = r.returncode
        if rc == 0:
            break
        run(*sandbox_cmd(cfg, box, list(cfg.install_env), ["bash", "-c", "pipx uninstall vacant-network >/dev/null 2>&1; true"]), timeout=300)
        time.sleep(k * 10)
    r = run(*sandbox_cmd(cfg, box, [], ["bash", "-c", "pipx runpip vacant-network freeze"]), timeout=300)
    (L / "vacant_pip_freeze.txt").write_text(r.stdout + r.stderr)
    return rc


# ── tmux ────────────────────────────────────────────────────────────────────────────────────────


class Pane:
    def __init__(self, sock: str, conf: Path, cols: int = 160, rows: int = 50):
        self.sock, self.conf, self.cols, self.rows = sock, str(conf), cols, rows
        self.env = {k: v for k, v in os.environ.items() if k != "TMUX"}
        self.env.update({"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})

    def tm(self, *a: str, **k):
        k.setdefault("timeout", 20)                    # tmux 卡住不能卡住整條線
        return run("tmux", "-u", "-L", self.sock, *a, env=self.env, **k)

    def start(self, cmd: str) -> float:
        self.tm("kill-server")
        r = self.tm("-f", self.conf, "new-session", "-d", "-s", self.sock, "-x", str(self.cols), "-y", str(self.rows),
                    f"{cmd}; echo __PANE_EXIT_$?__; sleep 3600")
        if r.returncode != 0:
            raise RuntimeError(f"tmux new-session failed: {r.stderr.strip()[:200]}")
        return time.time()

    def text(self, hist: bool = False) -> str:
        a = ["capture-pane", "-p", "-J", "-t", self.sock]
        if hist:
            a[1:1] = ["-S", "-"]
        return self.tm(*a).stdout

    def type(self, s: str) -> None:
        self.tm("send-keys", "-t", self.sock, "-l", s)

    def paste(self, s: str) -> None:
        buf = f"b{self.sock}"
        self.tm("load-buffer", "-b", buf, "-", input=s)
        self.tm("paste-buffer", "-p", "-b", buf, "-t", self.sock)
        self.tm("delete-buffer", "-b", buf)

    def key(self, k: str) -> None:
        self.tm("send-keys", "-t", self.sock, k)

    def kill(self) -> None:
        self.tm("kill-server")


# ── 一段 session ────────────────────────────────────────────────────────────────────────────────


def pane_command(cfg: Cfg, box: Box, sd: str, base: str) -> str:
    inner = (f"mkdir -p /logs/agent/pi/{sd} && PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent exec pi "
             f"--session-dir /logs/agent/pi/{sd} --provider {PROVIDER} --model \"$MODEL\"")
    extra = ["OPENROUTER_API_KEY=sk-dummy", f"OPENROUTER_BASE_URL={base}", f"MODEL={cfg.model}",
             f"TERM={cfg.term}", "PI_OFFLINE=1", *cfg.pi_extra_env]
    return " ".join(shlex.quote(x) for x in sandbox_cmd(cfg, box, extra, ["bash", "-c", inner]))


def run_session(cfg: Cfg, box: Box, lcell: str, L: Path, ledger: LedgerTail, *, n: int, kind: str, text: str) -> dict:
    """跑一段互動式 pi 對話到完成／逾時，回傳這一段的紀錄（含 void 判斷）。呼叫端負責持有位置（SlotPool）。
    這一段結束時 tmux 與該使用者的全部行程都已殺光；工作區留在 box.app。"""
    sd = sessions_dir_name(n)
    sdir = box.agentlog / "pi" / sd
    tag = session_tag(lcell, n)
    base = base_url(cfg, tag)
    write_models_json(cfg, box, base)
    mode, typed = typing_plan(text)
    (L / "panes").mkdir(exist_ok=True)
    (L / "timelines").mkdir(exist_ok=True)
    tl = open(L / "timelines" / f"timeline-{n}.jsonl", "w")
    conf = L / "tmux.conf"
    conf.write_text("set -g history-limit 50000\n")
    sock = f"i{box.seq}"
    pane = Pane(sock, conf, cfg.cols, cfg.rows)
    triggers = trust_triggers(box.app)
    rec: dict[str, Any] = {"n": n, "kind": kind, "dir": sd, "tag": tag, "typing_mode": mode, "text_chars": len(typed),
                           "text_sha256": sha256_bytes(typed.encode()), "started": now(), "trust_triggers": triggers,
                           "trust_dialog": None, "ready": False, "ready_s": None, "idle_s": cfg.idle_s,
                           "agent_timeout_s": cfg.agent_timeout, "timeout": False, "done_reason": None,
                           "pane": f"panes/pane-{n}.txt", "timeline": f"timelines/timeline-{n}.jsonl",
                           "submit_unconfirmed": False, "late_write_after_done": None, "exit_clean": None,
                           "exit_rc": None, "exit_s": None, "pane_exit_early_rc": None}
    tail = SessionTail(sdir)
    det = DoneDetector(cfg.idle_s)
    ev_path = box.home / ".vacant" / "intake" / "hooks" / "events.jsonl"
    exited_before_done = False
    done = False
    t0 = pane.start(pane_command(cfg, box, sd, base))

    def tlog(kind_: str, **kw: Any) -> None:
        tl.write(json.dumps({"t": round(time.time() - t0, 3), "kind": kind_, **kw}, ensure_ascii=False) + "\n")
        tl.flush()

    try:
        # (1) 準備好：頁腳畫出來才收得到鍵；信任對話框（互動模式才有）要先處理
        trust_handled = False
        while time.time() - t0 < cfg.ready_timeout:
            txt = pane.text()
            if footer_ready(txt, cfg.model):
                rec["ready"] = True
                break
            if trust_dialog_present(txt) and not trust_handled:
                rec["trust_dialog"] = "down4_enter(do_not_trust_this_session)"
                (L / "panes" / f"pane-{n}.trust_dialog.txt").write_text(txt)
                for _ in range(4):
                    pane.key("Down")
                    time.sleep(0.1)
                pane.key("Enter")
                trust_handled = True
                tlog("trust_dialog_handled")
            if pane_exit_rc(txt) is not None:
                break
            time.sleep(0.2)
        rec["ready_s"] = round(time.time() - t0, 2)
        tlog("ready", ready=rec["ready"], ready_s=rec["ready_s"])
        if rec["ready"]:
            time.sleep(0.5)
            if mode == "line":
                pane.type(typed)
                time.sleep(0.2)
            else:
                pane.paste(typed)
                time.sleep(0.5)
            pane.key("Enter")
            t_enter = time.time()
            tlog("enter")
            # 送出確認：Working 出現（或 session 檔／帳本有動靜）。10 秒內都沒有 ⇒ 再按一次 Enter
            #（編輯器是空的時候 Enter 什麼都不做，所以多按一次不會重複送出）
            while time.time() - t_enter < 10:
                if "Working" in pane.text() or tail.poll() or ledger.stats(tag)["calls"]:
                    break
                time.sleep(0.25)
            else:
                rec["submit_unconfirmed"] = True
                pane.key("Enter")
                tlog("enter_again")
            last_pane_check = 0.0
            last_logged: tuple | None = None
            while True:
                now_t = time.time()
                if now_t - t0 > cfg.agent_timeout:
                    rec["timeout"] = True
                    rec["done_reason"] = "timeout"
                    break
                tail.poll()
                st = ledger.stats(tag)
                hooks = pgrep_hook_count(run("pgrep", "-u", box.user, "-f", "vacant_network hook").stdout) if box.vacant else 0
                try:
                    ev = os.stat(ev_path).st_size if box.vacant else 0
                except OSError:
                    ev = 0
                state = tail.state
                sig = (tail.bytes, st["calls"], round(st["last_end_ts"], 3), ev)
                if det.update(now_t, state, sig, hooks):
                    done = True
                    rec["done_reason"] = "idle_error_final" if state == "error_final" else "idle_final"
                    break
                cur = (state, tail.bytes, st["calls"], hooks)
                if cur != last_logged:
                    tlog("change", state=state, session_bytes=tail.bytes, entries=len(tail.summ), calls=st["calls"],
                         hook_procs=hooks)
                    last_logged = cur
                if now_t - last_pane_check >= 3:
                    last_pane_check = now_t
                    prc = pane_exit_rc(pane.text())
                    if prc is not None:
                        exited_before_done = True
                        rec["pane_exit_early_rc"] = prc
                        rec["done_reason"] = "pane_exit"
                        break
                time.sleep(cfg.poll_s)
        else:
            rec["done_reason"] = "not_ready"
        # (2) 收尾：正常退出（Ctrl-D；退路 /quit）；逾時＝直接殺
        t_x = time.time()
        bytes_at_done = tail.bytes
        if done:
            pane.key("C-d")
            gone = False
            while time.time() - t_x < cfg.exit_wait_s:
                tail.poll()
                if pane_exit_rc(pane.text()) is not None:
                    gone = True
                    break
                time.sleep(0.2)
            if not gone:
                pane.type("/quit")
                time.sleep(0.4)
                pane.key("Enter")
                for _ in range(100):
                    tail.poll()
                    if pane_exit_rc(pane.text()) is not None:
                        gone = True
                        rec["exit_note"] = "Ctrl-D did not exit; /quit did"
                        break
                    time.sleep(0.1)
            rec["exit_rc"] = pane_exit_rc(pane.text())
            rec["exit_clean"] = bool(gone and rec["exit_rc"] == 0)
            rec["exit_s"] = round(time.time() - t_x, 2)
            time.sleep(0.5)
            tail.poll()
            rec["late_write_after_done"] = tail.bytes > bytes_at_done
        final_txt = pane.text(hist=True)
        (L / "panes" / f"pane-{n}.txt").write_text(final_txt)
    finally:
        pane.kill()
        tl.close()
    rec["leftover_procs"] = kill_user(box.user)
    # 帳本與 session 檔的最後狀態
    tail.poll()
    ents = jsonl_entries(sdir)
    la = last_assistant(ents) or {}
    led = ledger.final_stats(tag)
    rec["ended"] = now()
    rec["wall_s"] = round(time.time() - t0, 1)
    rec["rc"] = 124 if rec["timeout"] else (rec["exit_rc"] if rec["exit_rc"] is not None else rec["pane_exit_early_rc"])
    rec["final_state"] = tail.state
    rec["entries"] = len(ents)
    rec["last_assistant_stop"] = la.get("stopReason")
    rec["last_error"] = (la.get("errorMessage") if la.get("stopReason") == "error" else None)
    rec["sendbacks"] = sum(1 for e in ents if e.get("type") == "custom_message")
    rec["compactions"] = sum(1 for e in ents if e.get("type") == "compaction")
    rec["max_gap_after_final_s"] = max_gap_after_final(ents)
    rec["typed_ok"] = typed_matches(tail.first_user_text, typed)
    rec["ledger"] = {k: led.get(k) for k in ("calls", "non200", "stream_errors", "prompt_tokens", "completion_tokens",
                                             "cached_tokens", "statuses")}
    # 這一段的 session 檔存進這格的紀錄（cell.sh 是最後整份複製 agentlog；這裡每段各存一次）
    if sdir.exists():
        dst = L / "agentlog" / "pi" / sd
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(dst, ignore_errors=True)
        run("cp", "-a", str(sdir), str(dst))
    void, why = classify_session(ready=rec["ready"], trust_unhandled=bool(rec["trust_dialog"]) and not rec["ready"],
                                 typed_ok=rec["typed_ok"], final_state=rec["final_state"], last_error=rec["last_error"],
                                 ledger=led, session_file=bool(ents), timeout=rec["timeout"],
                                 pane_rc_early=rec["pane_exit_early_rc"], exited_before_done=exited_before_done)
    rec["void"], rec["void_reason"] = void, why
    return rec


def jsonl_entries(sdir: Path) -> list[dict]:
    out: list[dict] = []
    for f in sorted(Path(sdir).rglob("*.jsonl")):
        with open(f, encoding="utf-8", errors="replace") as fh:
            for ln in fh.read().splitlines():
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    continue
    return out


# ── 工作區紀錄與計分 ────────────────────────────────────────────────────────────────────────────


def tree_sha_lines(app: Path) -> str:
    rows = []
    for p in sorted(app.rglob("*")):
        if p.is_file() and not p.is_symlink():
            rows.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  ./{p.relative_to(app).as_posix()}")
    return "\n".join(rows) + ("\n" if rows else "")


def save_app_final(app: Path, before_sha: Path, L: Path) -> None:
    """最後的工作區：只存新增或改過的檔（原有、沒動過的只留雜湊），單檔上限 50 MB（超過只留雜湊）——同 cell.sh。"""
    (L / "workspace_after.sha256").write_text(tree_sha_lines(app))
    b = {}
    for line in before_sha.read_text().splitlines():
        if line.strip():
            h, name = line.split("  ", 1)
            b[name] = h
    out = L / "app_final"
    out.mkdir(exist_ok=True)
    kept, skipped = 0, []
    for line in (L / "workspace_after.sha256").read_text().splitlines():
        h, name = line.split("  ", 1)
        if b.get(name) == h:
            continue
        src = app / name
        if src.stat().st_size > 50 * 1024 * 1024:
            skipped.append(name)
            continue
        dst = out / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        kept += 1
    (L / "app_final_note.txt").write_text(f"kept {kept}; over 50MB (hash only): {skipped}\n")


def score_workspace(cfg: Cfg, task_dir: Path, src_app: Path, L: Path, label: str) -> dict | None:
    """另開一個新使用者、在圍牆裡跑既有計分器（隱藏測試只在這一步出現）。寫 L/score.json、L/score.stderr。"""
    S, _seq = create_user(cfg, "s")
    (L / "score_user.txt").write_text(S + "\n")
    SC = cfg.runs_root / f"{label}_score"
    shutil.rmtree(SC, ignore_errors=True)
    try:
        for d in ("home", "tmp", "app", "agentlog"):
            (SC / d).mkdir(parents=True)
        SC.chmod(0o711)
        run("cp", "-a", f"{src_app}/.", str(SC / "app") + "/")
        shutil.copytree(task_dir / "hidden", SC / "agentlog" / "hidden")
        shutil.copy2(task_dir / "scorer.py", SC / "agentlog" / "scorer.py")
        run("chown", "-R", f"{S}:{S}", *[str(SC / d) for d in ("home", "tmp", "app", "agentlog")])
        for d in ("home", "tmp", "app", "agentlog"):
            (SC / d).chmod(0o700)
        r = run("timeout", "-k", "10", str(cfg.score_timeout), "bash", str(cfg.sandbox_sh), S, str(SC), "--",
                "python3", "/logs/agent/scorer.py", "/logs/agent/hidden", "/app")
        (L / "score.json").write_text(r.stdout)
        (L / "score.stderr").write_text(r.stderr)
        (L / "score_rc.txt").write_text(f"{r.returncode}\n")
    finally:
        kill_user(S)
        delete_user(cfg, S)
        shutil.rmtree(SC, ignore_errors=True)
    return parse_score(L / "score.json")


def parse_score(p: Path) -> dict | None:
    try:
        lines = [x for x in p.read_text().strip().splitlines() if x.strip()]
        d = json.loads(lines[-1])
        return d if isinstance(d, dict) and "pass" in d else None
    except (OSError, ValueError, IndexError):
        return None


def vacant_collect(cfg: Cfg, box: Box, L: Path) -> dict:
    """C 組：有沒有真的裝上、有沒有作用（vacant_check.py，同 cell.sh）＋複製 ~/.vacant。"""
    shutil.copy2(cfg.bin_dir / "vacant_check.py", box.tmp / "_vacant_check.py")
    run("chown", f"{box.user}:{box.user}", str(box.tmp / "_vacant_check.py"))
    r = run(*sandbox_cmd(cfg, box, [], ["bash", "-c",
            'py=$(ls -d "$HOME"/.local/share/pipx/venvs/vacant-network/bin/python 2>/dev/null); "${py:-python3}" /tmp/_vacant_check.py']),
            timeout=300)
    (L / "vacant_check.json").write_text(r.stdout + r.stderr)
    kill_user(box.user)
    if (box.home / ".vacant").is_dir():
        run("cp", "-a", str(box.home / ".vacant"), str(L / "vacant_home"))
    try:
        return json.loads((r.stdout.strip().splitlines() or ["{}"])[-1])
    except ValueError:
        return {}


# ── bridge（K 組的收件端；root、receiver home 在 /srv/eval/receivers/<格子>、agent＝另一個使用者）─────────


def bridge(cfg: Cfg, *args: str, timeout: float = 600) -> tuple[int, dict | None, str]:
    env = {**os.environ, **cfg.bridge_env}
    if "PATH" in cfg.bridge_env:
        env["PATH"] = cfg.bridge_env["PATH"] + os.pathsep + os.environ.get("PATH", "")
    r = run(cfg.bridge_py, cfg.bridge_script, *args, timeout=timeout, env=env, cwd="/")
    try:
        out = json.loads(r.stdout) if r.stdout.strip() else None
    except ValueError:
        out = None
    return r.returncode, out, r.stderr.strip()[-600:]


def bridge_prepare(cfg: Cfg, box: Box, task_id: str, rh: Path, deliverable: str) -> tuple[int, dict | None, str]:
    cfg.receivers.mkdir(parents=True, exist_ok=True)
    cfg.receivers.chmod(0o700)
    return bridge(cfg, "prepare", "--workspace", str(box.app), "--task-id", task_id, "--mode", "conform",
                  "--attempts", str(cfg.k_attempts), "--deliverable", deliverable, "--receiver-home", str(rh),
                  "--sandbox", cfg.bridge_sandbox)


def bridge_judge(cfg: Cfg, box: Box, rh: Path, attempt: int) -> tuple[int, dict | None, str]:
    return bridge(cfg, "judge", "--workspace", str(box.app), "--attempt", str(attempt), "--sandbox", cfg.bridge_sandbox,
                  "--receiver-home", str(rh))


def bridge_release(cfg: Cfg, box: Box, rh: Path, artifact: str) -> tuple[int, dict | None, str]:
    return bridge(cfg, "release", "--workspace", str(box.app), "--artifact", artifact, "--receiver-home", str(rh))


def force_rmtree(p: Path) -> None:
    """bridge 把釘住的可見驗收套件設成唯讀（555／444）：刪之前先放寬權限。"""
    if not p.exists():
        return
    for q in (p, *p.rglob("*")):
        if not q.is_symlink():
            try:
                q.chmod(0o700)
            except OSError:
                pass
    shutil.rmtree(p, ignore_errors=True)


def copy_receiver_records(rh: Path, dst: Path) -> None:
    """收件端的紀錄（契約、帳本、裁決文件、放行的成品）；**私鑰一律不複製**（RECORD_SPEC §7：identity.key 排除）。"""
    def ignore(d: str, names: list[str]) -> list[str]:
        return [x for x in names if x == "keys" or x.endswith(".key") or x == "identity.key" or x == "private"]
    for src in (rh, rh.with_name(rh.name + "-suite")):
        if src.exists():
            shutil.copytree(src, dst / src.name, ignore=ignore, symlinks=True, dirs_exist_ok=True)


# ── 一格的 meta.json ────────────────────────────────────────────────────────────────────────────


def base_meta(cfg: Cfg, task: dict, name: str, arm: str, *, prefix: str, sample: int, attempt: int, box: Box | None) -> dict:
    return {"cell": name, "unit": f"{task['bank']}/{task['id']}", "bank": task["bank"], "task": task["id"], "role": task.get("role"),
            "screened": task.get("screened"), "phase": task.get("phase"), "sample": sample, "attempt": attempt, "arm": arm, "prefix": prefix,
            "task_dir": task["dir"], "tag": name, "model": cfg.model, "upstream": cfg.upstream,
            "user": box.user if box else None, "interactive": True, "ui": f"pi TUI in tmux {cfg.cols}x{cfg.rows}",
            "idle_s": cfg.idle_s, "agent_timeout_s": cfg.agent_timeout, "pi_version": PI_VERSION,
            "wheel": os.path.basename(cfg.wheel_path()) if arm == "C" else None,
            "deliverable": task.get("deliverable"), "started": now(), "void": False, "void_reason": None}


def finish_meta(meta: dict, sessions: list[dict], *, score: dict | None, score_rc: int | None,
                workspace: Path | None, deliverable: str) -> dict:
    last = sessions[-1] if sessions else {}
    if sessions and sessions[0].get("started"):
        meta["started"] = sessions[0]["started"]
    meta.update({"ended": now(), "sessions": sessions, "n_sessions": len(sessions),
                 "rc": last.get("rc"), "timeout": bool(last.get("timeout")),
                 "wall_s": round(sum(s.get("wall_s") or 0 for s in sessions), 1),
                 "done_reason": last.get("done_reason"), "score_rc": score_rc,
                 "leftover_procs": sum((s.get("leftover_procs") or 0) for s in sessions),
                 "delivered": bool(workspace is not None and has_deliverable(workspace, deliverable))})
    if score is not None:
        meta["scored"] = True
    return meta


def write_cell(L: Path, meta: dict) -> None:
    try:
        meta.setdefault("score_user", (L / "score_user.txt").read_text().strip() or None)
    except OSError:
        meta.setdefault("score_user", None)
    (L / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
    (L / "DONE").write_text(now() + "\n")


def void_cell(cfg: Cfg, task: dict, name: str, arm: str, L: Path, *, prefix: str, sample: int, attempt: int, why: str,
              sessions: list[dict] | None = None, extra: dict | None = None) -> dict:
    meta = base_meta(cfg, task, name, arm, prefix=prefix, sample=sample, attempt=attempt, box=None)
    meta.update({"void": True, "void_reason": why, "sessions": sessions or [], "n_sessions": len(sessions or []),
                 "ended": now(), "wall_s": round(sum((s.get("wall_s") or 0) for s in (sessions or [])), 1), **(extra or {})})
    L.mkdir(parents=True, exist_ok=True)
    write_cell(L, meta)
    return meta


# ── C 線 ────────────────────────────────────────────────────────────────────────────────────────


def run_c_group(cfg: Cfg, ledger: LedgerTail, pool: SlotPool, task: dict, *, prefix: str, sample: int = 1, attempt: int = 1,
                first_slot_held: bool = False) -> dict:
    name = cell_name(prefix, "C", task["bank"], task["id"], sample, attempt)
    L = cfg.cells / name
    shutil.rmtree(L, ignore_errors=True)
    L.mkdir(parents=True)
    tdir = Path(task["dir"])
    instr = (tdir / "instruction.txt").read_text().rstrip("\n")
    box: Box | None = None
    sessions: list[dict] = []
    held = first_slot_held
    try:
        box = build_box(cfg, name, tdir / "workspace", vacant=True)
        (L / "workspace_before.sha256").write_text(tree_sha_lines(box.app))
        install_rc = install_vacant(cfg, box, L)
        if install_rc != 0:
            if held:
                pool.release(1)
                held = False
            log(f"[{name}] install failed rc={install_rc} -> void")
            return void_cell(cfg, task, name, "C", L, prefix=prefix, sample=sample, attempt=attempt,
                             why=f"vacant_install_failed rc={install_rc}", extra={"install_rc": install_rc})
        if not held:
            pool.acquire(1)
            held = True
        try:
            s1 = run_session(cfg, box, name, L, ledger, n=1, kind="first", text=instr)
        finally:
            pool.release(1)
            held = False
        sessions.append(s1)
        chk = vacant_collect(cfg, box, L)
        save_app_final(box.app, L / "workspace_before.sha256", L)
        meta = base_meta(cfg, task, name, "C", prefix=prefix, sample=sample, attempt=attempt, box=box)
        meta["install_rc"] = install_rc
        meta["c_arm_ok"], meta["stop_reached"] = chk.get("c_arm_ok"), chk.get("stop_reached")
        meta["workspace_has_bridge_contract"] = False
        if s1["void"]:
            meta.update({"void": True, "void_reason": s1["void_reason"], "sessions": sessions, "n_sessions": 1, "ended": now(),
                         "wall_s": s1["wall_s"]})
            write_cell(L, meta)
            return meta
        score = score_workspace(cfg, tdir, box.app, L, name)
        finish_meta(meta, sessions, score=score, score_rc=_rc(L), workspace=box.app, deliverable=task["deliverable"])
        if score is None:
            meta["void"], meta["void_reason"] = True, "no_score_json"
        write_cell(L, meta)
        return meta
    except Exception as e:  # noqa: BLE001 -- 工具錯誤不是 agent 的表現：記成 void
        (L / "exception.txt").write_text(traceback.format_exc())
        log(f"[{name}] harness exception: {type(e).__name__}: {e}")
        return void_cell(cfg, task, name, "C", L, prefix=prefix, sample=sample, attempt=attempt,
                         why=f"harness_exception: {type(e).__name__}: {str(e)[:200]}", sessions=sessions)
    finally:
        if held:
            pool.release(1)
        if box is not None:
            delete_user(cfg, box.user)
            shutil.rmtree(box.C, ignore_errors=True)


def _rc(L: Path) -> int | None:
    try:
        return int((L / "score_rc.txt").read_text().strip())
    except (OSError, ValueError):
        return None


# ── A 線（A ＋ 巢狀的 R、K）──────────────────────────────────────────────────────────────────────


def run_a_group(cfg: Cfg, ledger: LedgerTail, pool: SlotPool, task: dict, *, prefix: str, nested: tuple[str, ...] = (),
                sample: int = 1, attempt: int = 1, first_slot_held: bool = False) -> dict:
    """回傳 {"A": meta, "R": meta|None, "K": meta|None, "void": bool}。任何一段 void ⇒ 整組標 void（driver 重跑一次）。"""
    nA = cell_name(prefix, "A", task["bank"], task["id"], sample, attempt)
    nR = cell_name(prefix, "R", task["bank"], task["id"], sample, attempt)
    nK = cell_name(prefix, "K", task["bank"], task["id"], sample, attempt)
    LA, LR, LK = cfg.cells / nA, cfg.cells / nR, cfg.cells / nK
    for d in (LA, LR, LK):
        shutil.rmtree(d, ignore_errors=True)
    LA.mkdir(parents=True)
    for stale in (cfg.receivers / nA, cfg.receivers / f"{nA}-suite"):          # 中斷後重跑同一個名字：收件端的狀態也要乾淨
        force_rmtree(stale)
    tdir = Path(task["dir"])
    deliverable = task["deliverable"]
    instr = (tdir / "instruction.txt").read_text().rstrip("\n")
    k_on = ("K" in nested) and bool(task.get("k"))
    r_on = "R" in nested
    rh = cfg.receivers / nA
    boxA: Box | None = None
    boxR: Box | None = None
    snap = cfg.runs_root / f"{nA}_snap"
    held = first_slot_held
    sA: list[dict] = []
    out: dict[str, Any] = {"A": None, "R": None, "K": None, "void": False}

    def void_all(why: str, sessions: list[dict]) -> dict:
        for arm, L, nm in (("A", LA, nA), ("R", LR, nR), ("K", LK, nK)):
            if arm == "R" and not r_on:
                continue
            if arm == "K" and not k_on:
                continue
            out[arm] = void_cell(cfg, task, nm, arm, L, prefix=prefix, sample=sample, attempt=attempt,
                                 why=why if arm == "A" else f"group void: {why}", sessions=sessions if arm == "A" else [],
                                 extra={"k_on": k_on, "nested": list(nested)})
        out["void"] = True
        return out

    try:
        boxA = build_box(cfg, nA, tdir / "workspace", vacant=False)
        k_prepare: dict[str, Any] = {}
        if k_on:
            rc, js, err = bridge_prepare(cfg, boxA, nA, rh, deliverable)
            k_prepare = {"rc": rc, "stderr": err, "result": js}
            (LK).mkdir(parents=True, exist_ok=True)
            (LK / "bridge").mkdir(exist_ok=True)
            (LK / "bridge" / "prepare.json").write_text(json.dumps(k_prepare, ensure_ascii=False, indent=1) + "\n")
            if rc != 0:
                why = f"bridge_prepare_failed rc={rc}: {err[:200]}"
                log(f"[{nA}] {why}")
                if attempt < 2:
                    # 還沒花任何 session 就知道 K 起不來：整條線 void（零成本重跑一次）
                    return void_all(why, [])
                # 第 2 次還是起不來：A、R 照跑（它們有效）；K 記成 void（systematic：分析會列出）
                k_on = False
                k_prepare["unavailable"] = True
                out["K"] = void_cell(cfg, task, nK, "K", LK, prefix=prefix, sample=sample, attempt=attempt, why=why,
                                     extra={"k_on": False, "nested": list(nested), "k_prepare": k_prepare})
        (LA / "workspace_before.sha256").write_text(tree_sha_lines(boxA.app))
        has_contract = (boxA.app / ".vacant" / "contract.json").is_file()
        if not held:
            pool.acquire(1)
            held = True
        try:
            s1 = run_session(cfg, boxA, nA, LA, ledger, n=1, kind="first", text=instr)
        finally:
            pool.release(1)
            held = False
        sA.append(s1)
        save_app_final(boxA.app, LA / "workspace_before.sha256", LA)
        if s1["void"]:
            return void_all(s1["void_reason"], sA)
        # A 的成績：第 1 段結束時的工作區快照（R 的複本也從這份來）
        shutil.rmtree(snap, ignore_errors=True)
        run("cp", "-a", str(boxA.app), str(snap))
        scoreA = score_workspace(cfg, tdir, snap, LA, nA)
        metaA = base_meta(cfg, task, nA, "A", prefix=prefix, sample=sample, attempt=attempt, box=boxA)
        metaA.update({"install_rc": None, "workspace_has_bridge_contract": has_contract,
                      "k_prepare_rc": k_prepare.get("rc"), "nested": list(nested), "k_on": k_on})
        finish_meta(metaA, sA, score=scoreA, score_rc=_rc(LA), workspace=snap, deliverable=deliverable)
        if scoreA is None:
            return void_all("no_score_json", sA)
        out["A"] = metaA
        # (R, K) 兩條巢狀分支：R 在複本上、K 就地；彼此獨立，同時跑
        res: dict[str, Any] = {}
        threads = []
        if r_on:
            def _r() -> None:
                res["R"] = _run_r(cfg, ledger, pool, task, nR, LR, snap, s1, sA, metaA, scoreA, prefix=prefix, sample=sample,
                                  attempt=attempt, instr=instr, deliverable=deliverable)
            threads.append(threading.Thread(target=_r))
        if k_on:
            def _k() -> None:
                res["K"] = _run_k(cfg, ledger, pool, task, nK, LK, boxA, rh, snap, sA, metaA, scoreA, prefix=prefix,
                                  sample=sample, attempt=attempt, instr=instr, deliverable=deliverable, tdir=tdir)
            threads.append(threading.Thread(target=_k))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for a in ("R", "K"):
            if a in res:
                out[a] = res[a]
        branch_void = [a for a in ("R", "K") if res.get(a) and res[a].get("void")]
        if branch_void:
            # A 自己的資料有效（第 1 段沒 void）：不改 A 的 void，另記「整條線 void」讓 driver 重跑一次
            out["void"] = True
            metaA["group_void"] = True
            metaA["group_void_reason"] = "; ".join(f"{a}: {res[a].get('void_reason')}" for a in branch_void)
        if k_on:
            copy_receiver_records(rh, LK / "receiver")
        write_cell(LA, metaA)
        for a in ("R", "K"):
            if out[a] is not None:
                write_cell(cfg.cells / out[a]["cell"], out[a])
        return out
    except Exception as e:  # noqa: BLE001
        (LA / "exception.txt").write_text(traceback.format_exc())
        log(f"[{nA}] harness exception: {type(e).__name__}: {e}")
        return void_all(f"harness_exception: {type(e).__name__}: {str(e)[:200]}", sA)
    finally:
        if held:
            pool.release(1)
        for b in (boxA, boxR):
            if b is not None:
                delete_user(cfg, b.user)
                shutil.rmtree(b.C, ignore_errors=True)
        shutil.rmtree(snap, ignore_errors=True)


def _run_r(cfg: Cfg, ledger: LedgerTail, pool: SlotPool, task: dict, nR: str, LR: Path, snap: Path, s1: dict,
           sA: list[dict], metaA: dict, scoreA: dict | None, *, prefix: str, sample: int, attempt: int, instr: str,
           deliverable: str) -> dict:
    """R（RETRY-NOSUITE）：A 的第 1 段是第 1 次嘗試；逾時或沒有交件才在 A 最後工作區的**複本**上開新 session
    （同一句、沒有任何回饋），總共最多 cfg.r_sessions 段，留最後一段的工作區。"""
    LR.mkdir(parents=True, exist_ok=True)
    tdir = Path(task["dir"])
    sessions = [dict(s1, shared_with_A=True)]
    meta = base_meta(cfg, task, nR, "R", prefix=prefix, sample=sample, attempt=attempt, box=None)
    meta.update({"shared_session1_with": metaA["cell"], "retry_reasons": []})
    again, why = needs_retry(s1, snap, deliverable)
    if not again:
        # R＝A：沒有逾時、有交件，不開新 session；成績與 A 的第 1 段相同（同一份工作區）
        (LR / "score.json").write_text(json.dumps(scoreA) + "\n")
        finish_meta(meta, sessions, score=scoreA, score_rc=None, workspace=snap, deliverable=deliverable)
        meta.update({"retry_needed": False, "score_reused_from_A": True, "user": None})
        return meta
    box: Box | None = None
    try:
        box = build_box(cfg, nR, snap, vacant=False)
        meta["user"] = box.user
        (LR / "workspace_before.sha256").write_text(tree_sha_lines(box.app))
        n = 1
        while again and n < cfg.r_sessions:
            n += 1
            meta["retry_reasons"].append(why)
            with pool.slot(1, priority=True):
                s = run_session(cfg, box, nR, LR, ledger, n=n, kind="retry", text=instr)
            sessions.append(s)
            if s["void"]:
                meta.update({"void": True, "void_reason": s["void_reason"], "sessions": sessions, "n_sessions": len(sessions),
                             "wall_s": round(sum(x.get("wall_s") or 0 for x in sessions), 1), "ended": now()})
                return meta
            again, why = needs_retry(s, box.app, deliverable)
        save_app_final(box.app, LR / "workspace_before.sha256", LR)
        score = score_workspace(cfg, tdir, box.app, LR, nR)
        finish_meta(meta, sessions, score=score, score_rc=_rc(LR), workspace=box.app, deliverable=deliverable)
        meta["retry_needed"] = True
        if score is None:
            meta["void"], meta["void_reason"] = True, "no_score_json"
        return meta
    except Exception as e:  # noqa: BLE001
        (LR / "exception.txt").write_text(traceback.format_exc())
        meta.update({"void": True, "void_reason": f"harness_exception: {type(e).__name__}: {str(e)[:200]}", "sessions": sessions})
        return meta
    finally:
        if box is not None:
            delete_user(cfg, box.user)
            shutil.rmtree(box.C, ignore_errors=True)


def _run_k(cfg: Cfg, ledger: LedgerTail, pool: SlotPool, task: dict, nK: str, LK: Path, boxA: Box, rh: Path, snap: Path,
           sA: list[dict], metaA: dict, scoreA: dict | None, *, prefix: str, sample: int, attempt: int, instr: str,
           deliverable: str, tdir: Path) -> dict:
    """K（CONFORM）：bridge 已在 A 的第 1 段之前 prepare 過（conform、stop_check 關）。每段 session 之後 `judge`；
    accept ⇒ `release --artifact` 並停；否則在 A 的原工作區**就地**開新 session（同一句＋可見檢查的回報），最多 cfg.k_attempts 段。
    沒 accept 過 ＝ 什麼都沒放行（算沒交）。"""
    LK.mkdir(parents=True, exist_ok=True)
    (LK / "bridge").mkdir(exist_ok=True)
    meta = base_meta(cfg, task, nK, "K", prefix=prefix, sample=sample, attempt=attempt, box=boxA)
    sessions = [dict(sA[0], shared_with_A=True)]
    meta.update({"shared_session1_with": metaA["cell"], "k": {"attempts": [], "released": False}})
    kinfo = meta["k"]
    try:
        n = 1
        while True:
            # judge（evaluator 側的失敗不用掉次數：最多再試 2 次；仍不行 ⇒ void）
            res, rc, err = None, None, ""
            for _try in range(3):
                rc, res, err = bridge_judge(cfg, boxA, rh, n)
                (LK / "bridge" / f"judge-{n}.{_try}.json").write_text(
                    json.dumps({"rc": rc, "stderr": err, "result": res}, ensure_ascii=False, indent=1) + "\n")
                if rc != K_EXIT["void"]:
                    break
                time.sleep(5)
            kinfo["attempts"].append({"attempt": n, "rc": rc, "outcome": (res or {}).get("outcome"),
                                      "artifact_sha256": (res or {}).get("artifact_sha256")})
            if rc == K_EXIT["void"] or res is None or rc not in K_EXIT.values():
                meta.update({"void": True, "void_reason": f"bridge_judge_rc={rc}: {err[:160]}", "sessions": sessions})
                return meta
            if rc == K_EXIT["accept"]:
                rrc, rres, rerr = bridge_release(cfg, boxA, rh, res["artifact_sha256"])
                (LK / "bridge" / "release.json").write_text(
                    json.dumps({"rc": rrc, "stderr": rerr, "result": rres}, ensure_ascii=False, indent=1) + "\n")
                kinfo["release_rc"] = rrc
                kinfo["readback_ok"] = (rres or {}).get("readback_ok")
                if rrc != 0 or not (rres or {}).get("released") or (rres or {}).get("readback_ok") is False:
                    meta.update({"void": True, "void_reason": f"bridge_release_rc={rrc}: {rerr[:160]}", "sessions": sessions})
                    return meta
                kinfo["released"] = True
                kinfo["location"] = (rres or {}).get("location")
                break
            if n >= cfg.k_attempts:
                break
            fail = res
            n += 1
            text = k_instruction(instr, fail)
            (LK / f"fix_instruction_{n}.txt").write_text(text)
            with pool.slot(1, priority=True):
                s = run_session(cfg, boxA, nK, LK, ledger, n=n, kind="fix", text=text)
            sessions.append(s)
            if s["void"]:
                meta.update({"void": True, "void_reason": s["void_reason"], "sessions": sessions})
                return meta
        # 計分：只計被放行的成品；沒放行＝沒交
        meta["sessions"] = sessions
        if kinfo["released"]:
            loc = Path(kinfo["location"] or (rh / "released"))
            art = LK / "released_artifact"
            shutil.rmtree(art, ignore_errors=True)
            shutil.copytree(loc, art, ignore=shutil.ignore_patterns(".vacant*"))
            relf, snapf = art / deliverable, snap / deliverable
            same = relf.is_file() and snapf.is_file() and relf.read_bytes() == snapf.read_bytes() and task["bank"].startswith("lcb")
            if same:
                # 放行的檔與 A 第 1 段那一份逐位元相同、而 LCB 計分器只讀 solution.py ⇒ 沿用 A 的成績（同一份檔不重算）
                (LK / "score.json").write_text(json.dumps(scoreA) + "\n")
                score, kinfo["score_reused_from_A"] = scoreA, True
            else:
                score = score_workspace(cfg, tdir, art, LK, nK)
            meta["delivered"] = True
        else:
            score = {"pass": False, "released": False, "note": "nothing released: no accepting judge within the attempt budget"}
            (LK / "score.json").write_text(json.dumps(score) + "\n")
            meta["delivered"] = False
        finish_meta(meta, sessions, score=score, score_rc=None, workspace=None, deliverable=deliverable)
        meta["delivered"] = bool(kinfo["released"])
        save_app_final(boxA.app, LK.parent / metaA["cell"] / "workspace_before.sha256", LK)
        if score is None:
            meta["void"], meta["void_reason"] = True, "no_score_json"
        return meta
    except Exception as e:  # noqa: BLE001
        (LK / "exception.txt").write_text(traceback.format_exc())
        meta.update({"void": True, "void_reason": f"harness_exception: {type(e).__name__}: {str(e)[:200]}", "sessions": sessions})
        return meta


def load_ledger(cfg: Cfg) -> LedgerTail:
    lt = LedgerTail(cfg.ledger_path)
    lt.refresh(force=True)
    return lt


def cfg_from_args(a: argparse.Namespace) -> Cfg:
    c = Cfg()
    for f in ("eval_root", "runs_root", "bin_dir"):
        v = getattr(a, f, None)
        if v:
            setattr(c, f, Path(v))
    for f in ("wheel", "model", "proxy", "upstream", "think", "bridge_py", "bridge_script"):
        v = getattr(a, f, None)
        if v:
            setattr(c, f, v)
    for f in ("agent_timeout", "score_timeout"):
        v = getattr(a, f, None)
        if v:
            setattr(c, f, int(v))
    if getattr(a, "idle_s", None):
        c.idle_s = float(a.idle_s)
    c.install_env = shlex.split(getattr(a, "install_env", "") or os.environ.get("I1001_INSTALL_ENV", ""))
    if getattr(a, "shim_dir", None):
        c.bridge_env = {"PATH": a.shim_dir}
    return c


def add_cfg_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--eval-root")
    ap.add_argument("--runs-root")
    ap.add_argument("--bin-dir")
    ap.add_argument("--wheel")
    ap.add_argument("--model")
    ap.add_argument("--proxy")
    ap.add_argument("--upstream")
    ap.add_argument("--think")
    ap.add_argument("--bridge-py")
    ap.add_argument("--bridge-script")
    ap.add_argument("--shim-dir", help="放 bwrap 墊片的目錄（vm_selfcheck.py 量出需要時才用）")
    ap.add_argument("--agent-timeout")
    ap.add_argument("--score-timeout")
    ap.add_argument("--idle-s")
    ap.add_argument("--install-env", default="", help="只給安裝那一步的環境 'K=V K=V'（本機測試的 proxy／CA）；"
                                                      "也可用環境變數 I1001_INSTALL_ENV（不會出現在 ps 的指令列上）")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="跑一個單位的一條線（手動／冒煙用；批次由 driver_i1001.py 排程）")
    ap.add_argument("group", choices=["a", "c"])
    ap.add_argument("--task", required=True, help="plan 裡那一題的 JSON（含 bank,id,dir,deliverable,k,role）")
    ap.add_argument("--prefix", default="i1")
    ap.add_argument("--nested", default="", help="逗號分隔：R,K")
    ap.add_argument("--attempt", type=int, default=1)
    add_cfg_args(ap)
    a = ap.parse_args(argv)
    cfg = cfg_from_args(a)
    task = json.loads(a.task)
    cfg.cells.mkdir(parents=True, exist_ok=True)
    ledger = load_ledger(cfg)
    pool = SlotPool(4)
    if a.group == "c":
        out = run_c_group(cfg, ledger, pool, task, prefix=a.prefix, attempt=a.attempt)
        print(json.dumps({"cell": out["cell"], "void": out["void"], "void_reason": out["void_reason"]}))
    else:
        nested = tuple(x for x in a.nested.split(",") if x)
        out = run_a_group(cfg, ledger, pool, task, prefix=a.prefix, nested=nested, attempt=a.attempt)
        print(json.dumps({k: ({"cell": v["cell"], "void": v["void"]} if isinstance(v, dict) else v) for k, v in out.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
