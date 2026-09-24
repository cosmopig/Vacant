"""twin/twinenclose — 把**一位分身那一跑整個**（launcher ＋ pi）關進 enclosure。

## 這支在架構裡承重什麼

裁決 `decisions/DECISION_20260924_TWIN_AGENT_RUN.md` §三 誠實邊界 1 寫的是：
「收住的是模型叫得到的工具，不是 pi 這個行程。pi（node）本身仍是一個有完整
檔案系統與網路權限的 OS 行程。」那是因為展場機 1003 是 Windows。
2026-09-24 人類裁決「**分身迴圈跑在 VM（vacant-dev，Linux）裡**」⇒ 那一層
（`ops/vacantrun/enclosure_20260920/`：bwrap ＋ netns ＋ mount ns ＋ 一扇門）
在這台機器上是**存在的**，這一支把它接上分身那一跑。

```
主機（VM，loop 行程的 worker 執行緒）             enclosure（bwrap --unshare-all）
─────────────────────────────────────             ───────────────────────────────
門：WireProxy --unix <door>/relay.sock ◀─唯一一條路─ 門的內側：127.0.0.1:G → /run/vacant/relay.sock
    path_policy=model、逐通落盤 <door>/wire/        launcher.run（wireproxy 127.0.0.1:X，
    上游＝1003 LM Studio                             upstream=http://127.0.0.1:G/v1）
                                                       └─ twin_agent.sh → pi（只看得到
事件轉送：<run-dir>/lifecycle_part.jsonl                   最小 rootfs＋node＋repo（唯讀）
    → 驗過形狀才 append 進展場 live 檔                     ＋自己的工作區＋自己的 run-dir）
```

### 為什麼 launcher 也要在圍牆裡（不是只圍 pi）

收據上的 `tier` 是 **launcher 行程自己量的**（`attest.probe_enclosure()` 讀
「這個行程有幾張網路介面」）。只把 pi 關進去，launcher 在外面量到的仍是
`ens33` ⇒ 收據照樣是 C，而「pi 被圍起來了」只能寫在一份**沒簽進鏈**的旁註裡。
把整跑關進去，收據上簽的就是量出來的 `enclosure.applied=true`、
`ns_differs_from_outer=true` ⇒ **B 級**（沒有框架掛鉤，所以不是 A；見誠實邊界 3）。

### 門為什麼是另一支 Vacant proxy，不是 byte pipe

launcher 的 wireproxy 與 pi 在**同一個** netns（圍牆裡的 loopback 共用）。
pi 若不走 launcher 的 proxy、直接連門的內側 `127.0.0.1:G`，那一通就**不在收據的
`requests_seen` 裡**。門若是 byte pipe，那一通就完全沒有紀錄。
⇒ 門用 `WireProxy(unix_path=…, path_policy="model")`：它終結 HTTP、逐通落盤、
非模型 path 在開任何連線之前 403。**每一個離開圍牆的位元組都在門的 journal 裡**
（B 級收據那句話本來的意思）。跑完主機側對帳：`door_calls > requests_seen`
⇒ 有一通繞過了 launcher 的 proxy ⇒ `door_unreconciled`，這一跑不算分身做的。

### 為什麼事件要轉送、不直接綁展場 live 檔進去

展場 live 檔是 append-only、接到公開螢幕與錄影的檔。綁進圍牆（可寫）＝圍牆裡
任何行程都能往公開螢幕上寫字。改成：launcher 寫 `<run-dir>/lifecycle_part.jsonl`，
主機側一條執行緒 tail 它，**每一行驗過**（schema、type、task_id、caller 必須
逐字等於主機這邊給的那一份、不准有內容欄位、單行上限）才 append 進 live 檔。
驗不過的行不轉、只計數（`events_rejected`）。

## 誠實邊界（改碼時保留）

1. **`applied=true` 說的是這一跑的 launcher 行程只看得到 loopback**，
   不是「VM 上不存在別的路」。圍牆**外面**（loop 本身、serve_twin）什麼都連得到。
2. **圍牆裡 pi 寫得到自己的工作區與自己的 run-dir**：launcher 要在 run-dir 寫收據，
   而 pi 是 launcher 的子行程、同一個 mount ns。收據鏈的簽章擋得住「事後改收據」
   （主機側跑完就驗章，驗不過就退化），擋不住「run-dir 裡多一個檔」。
3. **B 不是 A。** A 還要框架掛鉤（`framework_hook.canary_fired=true`）與對帳
   `unexplained=0`。分身的 pi 是 `--no-extensions` ＋ 我們自己的三個工具，沒有裝
   Vacant 的 pi 掛鉤 ⇒ `canary_fired=None`（沒量到）⇒ 天花板是 B。不准在展場講 A。
4. **這一層只在 Linux ＋ bwrap 可用的機器上存在**（vacant-dev 靠 2026-09-15 裝的
   `/etc/apparmor.d/bwrap`）。`available()` 每台自己量，量不到就**講出來**，
   呼叫端決定要退回不圍（`enclose=auto`）還是整跑不起（`enclose=on`）。
5. **門的 journal 裡有觀眾特質原文**（鐵律 3 逐字落盤）。它住在
   `<work_root>/doors/<slug>/`（圍牆外、不可寫進圍牆），撤回與閉展時跟 run-dir 一起刪
   （`twinagent.erase_run_artifacts`、`close_exhibition.py`）。
"""
from __future__ import annotations

import json
import os
import pathlib
import platform
import shutil
import signal
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
REPO = TWIN.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

#: enclosure 本體（2026-09-20 量過、有負控制的那一支；**呼叫它，不複製它**）。
ENC_SH = REPO / "ops" / "vacantrun" / "enclosure_20260920" / "bin" / "enc.sh"
#: 圍牆裡看到的門（`enc.sh` 把門的目錄 `--ro-bind` 到 `/run/vacant`）。
INNER_DOOR_SOCK = "/run/vacant/relay.sock"
#: launcher 在圍牆裡寫的事件檔（主機側轉送進展場 live 檔）。
EVENTS_PART = "lifecycle_part.jsonl"
#: inner 模式的參數檔。
PARAMS_NAME = "_enclosed_params.json"
#: 轉送事件時單行上限（lifecycle 事件實測 < 1 KiB；超過就是有人往裡面塞東西）。
MAX_EVENT_LINE = 8192
#: 事件裡**不准出現**的 key（lifecycle 誠實邊界 3：不帶內容）。
CONTENT_KEYS = frozenset({"body", "request", "response", "messages", "text",
                          "content", "traits", "card", "card_text"})

_AVAIL: dict[str, Any] = {}


def door_dir_for(work_root: pathlib.Path, slug: str) -> pathlib.Path:
    """門的目錄（socket、policy.json、門的 journal）。**圍牆外**、不在 ws／run-dir 裡。"""
    return pathlib.Path(work_root) / "doors" / slug


def node_dir(pi_bin: str | None) -> pathlib.Path | None:
    """pi 所在的 node 安裝根（`<root>/bin/pi` → `<root>`），唯讀綁進圍牆用。"""
    exe = shutil.which(pi_bin or "pi")
    if not exe:
        return None
    # ⚠ **不要 resolve()**：`<root>/bin/pi` 是指向 `lib/node_modules/.../dist/cli.js`
    #   的符號連結，解開之後的「上上層」是套件目錄不是 node 根。
    root = pathlib.Path(os.path.abspath(exe)).parent.parent
    return root if (root / "bin" / "node").exists() else None


def _python() -> str:
    """圍牆裡跑 launcher 的 python。**要在 /usr 底下**（最小 rootfs 只有 /usr）。"""
    for c in (os.environ.get("VACANT_TWIN_ENC_PY"), "/usr/bin/python3"):
        if c and pathlib.Path(c).is_file() and str(pathlib.Path(c)).startswith("/usr/"):
            return c
    return "/usr/bin/python3"


def available(*, force: bool = False) -> tuple[bool, str]:
    """這台機器上圍牆**真的起得來**嗎（跑一次 `enc.sh /bin/true`，不是看檔案在不在）。"""
    if _AVAIL and not force:
        return _AVAIL["ok"], _AVAIL["why"]
    ok, why = False, ""
    if platform.system() != "Linux":
        why = f"不是 Linux（{platform.system()}）⇒ 沒有 netns／mount ns"
    elif not shutil.which("bwrap"):
        why = "bwrap 不在 PATH 上"
    elif not ENC_SH.is_file():
        why = f"找不到 {ENC_SH}"
    else:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="twin_encprobe_"))
        try:
            r = subprocess.run(["bash", str(ENC_SH), "/bin/true"],
                               env={"PATH": "/usr/bin:/bin", "ENC_WS": str(tmp)},
                               capture_output=True, text=True, timeout=30)
            ok = r.returncode == 0
            why = "ok" if ok else f"enc.sh rc={r.returncode}：{(r.stderr or '').strip()[:300]}"
        except Exception as e:                           # noqa: BLE001
            why = f"enc.sh 起不來：{type(e).__name__}: {e}"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    _AVAIL.update(ok=ok, why=why)
    return ok, why


# ---------------------------------------------------------------------------
# 事件轉送（主機側）
# ---------------------------------------------------------------------------

def check_event_line(line: str, *, task_id: str, caller: dict) -> dict | None:
    """一行圍牆裡寫出來的事件 → 可以轉送的 dict，或 `None`（不轉）。"""
    from vacant_network.vrun import lifecycle
    if len(line.encode("utf-8")) > MAX_EVENT_LINE:
        return None
    try:
        e = json.loads(line)
    except (ValueError, TypeError):
        return None
    if not isinstance(e, dict):
        return None
    if e.get("schema") != lifecycle.SCHEMA or e.get("type") not in lifecycle.TYPES:
        return None
    if e.get("task_id") != task_id:
        return None
    if CONTENT_KEYS & set(e):
        return None
    if e.get("type") == "run_started" and e.get("caller") != caller:
        return None
    if e.get("type") != "run_started" and "caller" in e:
        return None
    return e


class EventForwarder(threading.Thread):
    """tail `<run-dir>/lifecycle_part.jsonl` → 驗過才 append 進展場 live 檔。"""

    def __init__(self, src: pathlib.Path, dst: pathlib.Path | None, *,
                 task_id: str, caller: dict, poll_s: float = 0.25) -> None:
        super().__init__(daemon=True, name="twin-enc-events")
        self.src, self.dst = src, dst
        self.task_id, self.caller = task_id, caller
        self.poll_s = poll_s
        self.forwarded = 0
        self.rejected = 0
        self._pos = 0
        self._buf = b""
        self._halt = threading.Event()

    def _pump(self) -> None:
        if not self.src.is_file():
            return
        try:
            with self.src.open("rb") as f:
                f.seek(self._pos)
                chunk = f.read()
                self._pos = f.tell()
        except OSError:
            return
        self._buf += chunk
        while b"\n" in self._buf:
            raw, self._buf = self._buf.split(b"\n", 1)
            if not raw.strip():
                continue
            e = check_event_line(raw.decode("utf-8", "replace"),
                                 task_id=self.task_id, caller=self.caller)
            if e is None:
                self.rejected += 1
                continue
            if self.dst is None:
                self.forwarded += 1
                continue
            try:
                self.dst.parent.mkdir(parents=True, exist_ok=True)
                # 一次 write、O_APPEND：與其他分身的轉送執行緒並行也不會交錯成半行
                fd = os.open(self.dst, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
                try:
                    os.write(fd, (json.dumps(e, ensure_ascii=False) + "\n").encode("utf-8"))
                finally:
                    os.close(fd)
                self.forwarded += 1
            except OSError:
                # lifecycle 誠實邊界 2：寫不進事件檔不准改變一跑的結果
                self.rejected += 1

    def run(self) -> None:
        while not self._halt.is_set():
            self._pump()
            self._halt.wait(self.poll_s)
        self._pump()

    def finish(self) -> None:
        self._halt.set()
        self.join(timeout=10)


# ---------------------------------------------------------------------------
# 主機側：起門、起圍牆、轉送事件、對帳
# ---------------------------------------------------------------------------

def run_enclosed(*, argv: list[str], workspace: pathlib.Path, run_dir: pathlib.Path,
                 door_dir: pathlib.Path, task_id: str, timeout_s: float,
                 events_path: pathlib.Path | None, events_caller: dict,
                 endpoint: str, model: str, pi_bin: str | None = None) -> dict:
    """跑一位分身，**整跑在圍牆裡**。回 launcher 的 summary（多一塊 `twin_enclosure`）。

    起不來（門起不來、bwrap 失敗、summary 沒落盤）⇒ `SystemExit`／`RuntimeError`，
    呼叫端（`twinagent.run_one`）照既有規則走退化（例外類名進 `degrade_kind`）。
    """
    from vacant_network.vrun import envmap
    from vacant_network.vrun.wireproxy import WireProxy

    workspace, run_dir = pathlib.Path(workspace), pathlib.Path(run_dir)
    door_dir = pathlib.Path(door_dir)
    # 🔴 repo 整份是**唯讀綁進圍牆**的（launcher／擴充要讀得到）。run 產物若住在 repo
    #    底下（`twin_loop.sh` 的預設庫就在 `ops/exhibit/twin/store/`），別的分身的工作區、
    #    wire log、檔案庫、sqlite 就全部在圍牆裡**讀得到**——圍牆等於沒圍檔案系統那一半。
    #    fail-closed：VM 上 `VACANT_TWIN_DB` 一定要放在 checkout 外面（START.md「VM 跑法」）。
    repo_r = REPO.resolve()
    for label, p in (("workspace", workspace), ("run_dir", run_dir), ("door_dir", door_dir)):
        rp = p.resolve()
        if rp == repo_r or repo_r in rp.parents:
            raise RuntimeError(
                f"{label}={p} 在 repo（{REPO}）底下，而 repo 是整份唯讀綁進圍牆的 ⇒ "
                "別的分身的 run 產物在圍牆裡讀得到。把 VACANT_TWIN_DB／VACANT_TWIN_AGENTRUNS "
                "放到 checkout 外面。停。")
    if door_dir.exists():
        shutil.rmtree(door_dir)
    door_dir.mkdir(parents=True)
    ndir = node_dir(pi_bin)
    if ndir is None:
        raise RuntimeError(f"找不到 pi（{pi_bin or 'pi'}）⇒ 圍牆裡沒有 agent 可跑")
    (run_dir / "home").mkdir(parents=True, exist_ok=True)

    door = WireProxy(wire_dir=door_dir / "wire",
                     upstreams={"openai": endpoint, "anthropic": envmap.SINK_UPSTREAM},
                     keys={}, sentinel="", mode="tee",
                     unix_path=str(door_dir / "relay.sock"), path_policy="model")
    door.start()
    part = run_dir / EVENTS_PART
    fwd = EventForwarder(part, events_path, task_id=task_id, caller=events_caller)
    fwd.start()
    params = {"argv": argv, "workspace": str(workspace), "run_dir": str(run_dir),
              "task_id": task_id, "timeout_s": timeout_s,
              "events_path": str(part), "events_caller": events_caller}
    (run_dir / PARAMS_NAME).write_text(json.dumps(params, ensure_ascii=False),
                                       encoding="utf-8")
    pi_path = str(ndir / "bin" / "pi")
    setenv = " ".join(f"{k}={v}" for k, v in {
        "PYTHONPATH": str(REPO), "PYTHONUNBUFFERED": "1",
        "HOME": str(run_dir / "home"),
        "VACANT_AGENT_MODEL": model, "VACANT_TWIN_PI": pi_path,
        "VACANT_ATTEST": "warn",
    }.items())
    # ⚠ 環境**從零給**：loop 行程的環境裡有雲端 token 與真上游位址。
    #   bwrap 不 --clearenv 的話那些會原樣進圍牆（pi 的 /proc/self/environ 讀得到）。
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
           "ENC_WS": str(workspace), "ENC_RW": str(run_dir),
           "ENC_RO": f"{REPO}:{ndir}", "ENC_DOOR": str(door_dir),
           "ENC_PY": _python(), "ENC_PATH": f"{ndir}/bin:/usr/bin:/bin",
           "ENC_SETENV": setenv}
    cmd = ["bash", str(ENC_SH), _python(), "-m", "ops.exhibit.twin.twinenclose",
           "--inner", str(run_dir / PARAMS_NAME)]
    t0 = time.time()
    enc_rc: int | None = None
    timed_out = False
    try:
        with (run_dir / "enclosure_stderr.log").open("wb") as errf:
            proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                                    stdout=errf, stderr=errf,
                                    start_new_session=True)
            try:
                enc_rc = proc.wait(timeout=float(timeout_s) + 120.0)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
                enc_rc = proc.wait(timeout=30)
    finally:
        fwd.finish()
        door.stop()
    summ_p = run_dir / "run_RUN-ON.json"
    if not summ_p.is_file():
        raise RuntimeError(f"圍牆裡的 launcher 沒有落 summary（enc rc={enc_rc}"
                           f"{'，外層逾時' if timed_out else ''}）")
    summary = json.loads(summ_p.read_text("utf-8"))
    door_stats = dict(door.stats)
    seen = summary.get("requests_seen")
    door_calls = int(door_stats.get("requests_seen") or 0)
    summary["twin_enclosure"] = {
        "enc_rc": enc_rc, "outer_timed_out": timed_out,
        "wall_s": round(time.time() - t0, 3),
        "door_calls": door_calls,
        "door_refused_path": int(door_stats.get("refused_path") or 0),
        "door_blocked": int(door_stats.get("blocked") or 0),
        # 門看到的比 launcher 的 proxy 多 ⇒ 有一通繞過了收據那一層（見檔頭）
        "door_excess": (door_calls - seen) if isinstance(seen, int) else None,
        "events_forwarded": fwd.forwarded, "events_rejected": fwd.rejected,
    }
    return summary


# ---------------------------------------------------------------------------
# 圍牆裡：門的內側 ＋ launcher.run
# ---------------------------------------------------------------------------

class _Pipe(socketserver.BaseRequestHandler):
    """127.0.0.1:G → 門（路徑型 unix socket）。byte pipe：HTTP 在門的主機側才被終結。"""

    def handle(self) -> None:           # pragma: no cover - 只在圍牆裡跑
        try:
            up = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            up.connect(INNER_DOOR_SOCK)
        except OSError:
            return
        down = self.request

        def pipe(a, b):
            try:
                while True:
                    d = a.recv(65536)
                    if not d:
                        break
                    b.sendall(d)
            except OSError:
                pass
            finally:
                try:
                    b.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
        t = threading.Thread(target=pipe, args=(down, up), daemon=True)
        t.start()
        pipe(up, down)
        t.join(timeout=30)
        up.close()


class _Srv(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def inner_main(params_path: str) -> int:    # pragma: no cover - 只在圍牆裡跑
    p = json.loads(pathlib.Path(params_path).read_text("utf-8"))
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(INNER_DOOR_SOCK)
        s.close()
    except OSError as e:
        print(f"門連不上 {INNER_DOOR_SOCK}：{e}", file=sys.stderr)
        return 3
    srv = _Srv(("127.0.0.1", 0), _Pipe)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["VACANT_RUN_UPSTREAM_OPENAI"] = f"http://127.0.0.1:{srv.server_address[1]}/v1"
    from vacant_network.vrun import launcher
    launcher.run(p["argv"], workspace=pathlib.Path(p["workspace"]),
                 run_dir=pathlib.Path(p["run_dir"]), suite_dir=None,
                 vacant_on=True, allow_no_suite=True, task_id=p["task_id"],
                 timeout_s=p["timeout_s"], capture_agent_stdout=True,
                 events_path=p["events_path"], events_caller=p["events_caller"])
    srv.shutdown()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="分身那一跑的 enclosure（圍牆）")
    ap.add_argument("--inner", default=None, help="（圍牆裡用）參數檔")
    ap.add_argument("--probe", action="store_true", help="只量這台起不起得來圍牆")
    a = ap.parse_args(argv)
    if a.inner:
        return inner_main(a.inner)
    ok, why = available(force=True)
    print(json.dumps({"enclosure_available": ok, "why": why,
                      "enc_sh": str(ENC_SH)}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
