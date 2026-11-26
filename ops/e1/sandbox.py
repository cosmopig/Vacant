"""ops.e1.sandbox — Linux bubblewrap（bwrap）隔離執行層（worker 沙箱與無網路評分沙箱）。

這支在架構裡承重什麼
====================
為 E1′ 提供**真實的行程與檔案系統隔離**，而非僅靠工作目錄路徑慣例：
1. **Worker 沙箱（`build_worker_bwrap_argv`）**：
   - 只讀掛載 `/usr`、`/bin`、`/sbin`、`/lib`、`/lib64`、`/etc`、`~/.piinstall`、解析後的 node 根目錄，
     以及複製並去敏後的 pi 設定目錄（掛在 `/sandbox_cfg`、設 `PI_CODING_AGENT_DIR`）。
   - 可讀寫掛載的只有本回合的工作區副本（`/work`），`/tmp` 與 `HOME`（`/sandbox_home`）皆為 tmpfs。
   - 使用 `--clearenv` 與 `--die-with-parent`、`--unshare-pid`；宿主檔案系統上的鏈規格、隱藏測資、
     評分輸出、別臂工作區、教材目錄、`~/dev/ops`、金鑰皆**未掛載（結構上不可達）**。
   - 共用網路（供連線本機模型端點與文件鏈的來源伺服器；文件鏈另設 `http_proxy` 與 `no_proxy`）。
2. **評分與可見測試沙箱（`build_eval_bwrap_argv`）**：
   - 獨立的 `bwrap`，強制 `--unshare-net`（完全斷網）、`--unshare-pid`、`--die-with-parent`，
     外加 `prlimit` 記憶體上限與逾時強殺整個行程群組；候選工作區只讀掛載，評分結果只由宿主端落盤。

誠實邊界（改碼請保留）
----------------------
- Worker 沙箱因必須呼叫模型端點（與文件來源伺服器）而共用網路，故不阻擋對網路端點的任意存取；
  全機出口封鎖需要額外的網路命名空間或出口代理，不在本模組保證範圍內。
- 去敏複製 `models.json` 時會移除 `openrouter` 等外部 API 金鑰（`sk-` 開頭），僅保留計畫指定的
  本機提供者，確保不會把外部付費金鑰掛進沙箱。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import signal
import subprocess
import threading
import time
import urllib.parse
from typing import Iterable

from . import atomic_write_json

SYSTEM_RO_DIRS: tuple[str, ...] = ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc")
LOG_CAP_BYTES = 16 * 1024 * 1024

_LIVE_PROCS: set[subprocess.Popen] = set()
_LIVE_LOCK = threading.Lock()


def _track_proc(proc: subprocess.Popen, add: bool) -> None:
    with _LIVE_LOCK:
        (_LIVE_PROCS.add if add else _LIVE_PROCS.discard)(proc)


def kill_all_live() -> None:
    """終止所有尚未結束的沙箱行程群組。"""
    with _LIVE_LOCK:
        procs = list(_LIVE_PROCS)
    for proc in procs:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _kill_group(proc: subprocess.Popen) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            continue


def resolve_pi_runtime() -> dict[str, pathlib.Path | None]:
    """解析宿主上的 pi 與 node 實際路徑（追到 readlink -f），供只讀掛進沙箱。"""
    home = pathlib.Path.home()
    piinstall = home / ".piinstall"
    pi_bin = home / ".local" / "bin" / "pi"
    node_bin = home / ".local" / "bin" / "node"

    node_real: pathlib.Path | None = None
    if node_bin.exists():
        node_real = node_bin.resolve()
    else:
        found = shutil.which("node")
        if found:
            node_real = pathlib.Path(found).resolve()

    # 若 node 位在 .../bin/node，掛載其上一層目錄（含 lib/node 等）
    node_root: pathlib.Path | None = None
    if node_real is not None:
        if node_real.parent.name == "bin":
            node_root = node_real.parent.parent
        else:
            node_root = node_real.parent

    return {
        "piinstall": piinstall if piinstall.is_dir() else None,
        "pi_bin": pi_bin if pi_bin.exists() else None,
        "node_bin": node_bin if node_bin.exists() else None,
        "node_real": node_real,
        "node_root": node_root,
    }


def prepare_sanitized_pi_cfg(
    src_cfg_dir: pathlib.Path,
    dst_cfg_dir: pathlib.Path,
    allowed_providers: Iterable[str] | None = None,
) -> list[str]:
    """將 pi 設定目錄複製到本回合專屬私密目錄並去敏，回傳允許提供者的主機名清單（供 no_proxy）。

    安全規則：
    - 只複製 `models.json`（不複製 `extensions/`，避免引用 `~/dev/ops` 或外掛干擾實驗組）。
    - 若指定 `allowed_providers`，只保留這些提供者；否則剔除任何含真實外部 API 金鑰（`sk-` 等）的提供者。
    """
    dst_cfg_dir.mkdir(parents=True, exist_ok=True)
    models_src = src_cfg_dir / "models.json"
    hosts: list[str] = []
    if not models_src.is_file():
        return hosts
    raw = json.loads(models_src.read_text(encoding="utf-8"))
    providers = raw.get("providers") or {}
    allow = set(allowed_providers) if allowed_providers is not None else None
    kept: dict[str, dict] = {}
    for name, cfg in providers.items():
        if allow is not None:
            if name not in allow:
                continue
        else:
            key = str(cfg.get("apiKey") or "")
            if key.startswith("sk-") or name == "openrouter":
                continue
        kept[name] = cfg
        bu = str(cfg.get("baseUrl") or "")
        if bu:
            h = urllib.parse.urlsplit(bu).hostname
            if h and h not in hosts:
                hosts.append(h)

    sanitized = {
        "providers": kept,
    }
    if raw.get("defaultProvider") in kept:
        sanitized["defaultProvider"] = raw["defaultProvider"]
        if raw.get("defaultModel"):
            sanitized["defaultModel"] = raw["defaultModel"]
    elif kept:
        first = next(iter(kept))
        sanitized["defaultProvider"] = first
        models = kept[first].get("models") or []
        if models and isinstance(models[0], dict) and models[0].get("id"):
            sanitized["defaultModel"] = models[0]["id"]

    atomic_write_json(dst_cfg_dir / "models.json", sanitized)
    return hosts


def build_worker_bwrap_argv(
    cmd: list[str],
    *,
    workspace_dir: pathlib.Path,
    pi_cfg_dir: pathlib.Path | None = None,
    extra_ro_binds: list[tuple[pathlib.Path, str]] | None = None,
    http_proxy: str | None = None,
    no_proxy_hosts: Iterable[str] = (),
    extra_env: dict[str, str] | None = None,
    mount_pi: bool = True,
) -> list[str]:
    """組合 worker 的 bubblewrap 指令列。

    除系統唯讀目錄、pi／node 執行期、去敏 pi 設定檔與 `/work` 工作區副本之外，不掛載任何宿主路徑。
    """
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("找不到 bwrap（bubblewrap）；無法建立真實沙箱")

    argv: list[str] = [bwrap, "--die-with-parent", "--unshare-pid", "--clearenv"]

    for sysdir in SYSTEM_RO_DIRS:
        if os.path.exists(sysdir):
            argv += ["--ro-bind", sysdir, sysdir]

    argv += [
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        "--tmpfs", "/sandbox_home",
    ]

    path_parts: list[str] = []
    if mount_pi:
        rt = resolve_pi_runtime()
        if rt["piinstall"] is not None:
            argv += ["--ro-bind", str(rt["piinstall"]), "/opt/piinstall"]
            argv += ["--symlink", "/opt/piinstall/node_modules/.bin/pi", "/opt/bin/pi"]
            path_parts.append("/opt/bin")
        if rt["node_root"] is not None and rt["node_real"] is not None:
            # 若 node 在 /usr 裡就不必重複掛；若在 ~/.local/opt/... 則唯讀掛在 /opt/node
            nroot = str(rt["node_root"])
            if not nroot.startswith("/usr"):
                argv += ["--ro-bind", nroot, "/opt/node"]
                rel_node = rt["node_real"].relative_to(rt["node_root"]).as_posix()
                argv += ["--symlink", f"/opt/node/{rel_node}", "/opt/bin/node"]
                if "/opt/bin" not in path_parts:
                    path_parts.append("/opt/bin")

    if pi_cfg_dir is not None:
        argv += ["--ro-bind", str(pi_cfg_dir.resolve()), "/sandbox_cfg"]

    for host_p, guest_p in extra_ro_binds or ():
        argv += ["--ro-bind", str(host_p.resolve()), guest_p]

    argv += [
        "--bind", str(workspace_dir.resolve()), "/work",
        "--chdir", "/work",
    ]

    path_parts += ["/usr/local/bin", "/usr/bin", "/bin"]
    env: dict[str, str] = {
        "HOME": "/sandbox_home",
        "TMPDIR": "/tmp",
        "PATH": ":".join(path_parts),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PI_SKIP_VERSION_CHECK": "1",
        "PI_OFFLINE": "1",
    }
    if pi_cfg_dir is not None:
        env["PI_CODING_AGENT_DIR"] = "/sandbox_cfg"
    if http_proxy:
        env["http_proxy"] = http_proxy
        env["HTTP_PROXY"] = http_proxy
        np = list(dict.fromkeys(["localhost", "127.0.0.1", *(h for h in no_proxy_hosts if h)]))
        env["no_proxy"] = ",".join(np)
        env["NO_PROXY"] = ",".join(np)
    if extra_env:
        env.update(extra_env)

    for k, v in sorted(env.items()):
        argv += ["--setenv", k, v]

    argv += ["--", *cmd]
    return argv


def build_eval_bwrap_argv(
    cmd: list[str],
    *,
    ro_binds: list[tuple[pathlib.Path, str]] | None = None,
    chdir: str = "/tmp",
    mem_limit_mb: int = 1024,
    cpu_limit_s: int | None = None,
) -> list[str]:
    """組合獨立評分與可見測試的無網路 bubblewrap 指令列（`--unshare-net`＋記憶體限制）。"""
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("找不到 bwrap（bubblewrap）；無法建立無網路評分沙箱")

    argv: list[str] = [
        bwrap,
        "--unshare-net",
        "--unshare-pid",
        "--die-with-parent",
        "--clearenv",
    ]
    for sysdir in SYSTEM_RO_DIRS:
        if os.path.exists(sysdir):
            argv += ["--ro-bind", sysdir, sysdir]

    argv += [
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        "--tmpfs", "/sandbox_home",
    ]
    for host_p, guest_p in ro_binds or ():
        argv += ["--ro-bind", str(host_p.resolve()), guest_p]

    argv += [
        "--chdir", chdir,
        "--setenv", "HOME", "/sandbox_home",
        "--setenv", "TMPDIR", "/tmp",
        "--setenv", "PATH", "/usr/bin:/bin",
        "--setenv", "LANG", "C.UTF-8",
        "--setenv", "LC_ALL", "C.UTF-8",
        "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
        "--setenv", "PYTHONHASHSEED", "0",
        "--setenv", "PYTHONNOUSERSITE", "1",
        "--",
    ]

    prlimit = shutil.which("prlimit")
    if prlimit and (mem_limit_mb > 0 or cpu_limit_s):
        pl = [prlimit]
        if mem_limit_mb > 0:
            pl.append(f"--as={int(mem_limit_mb) * 1024 * 1024}")
        if cpu_limit_s:
            pl.append(f"--cpu={int(cpu_limit_s)}")
        pl.append("--")
        argv += pl

    argv += cmd
    return argv


def run_sandboxed(
    argv: list[str],
    *,
    timeout_s: float,
    stdin_bytes: bytes | None = None,
    log_path: pathlib.Path | None = None,
) -> dict:
    """執行沙箱子行程（獨立行程群組），支援逾時強殺與日誌上限。"""
    t0 = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE if stdin_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if log_path is None else subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as exc:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(f"[sandbox] spawn failed: {exc}\n", encoding="utf-8")
        return {
            "rc": None,
            "wall_s": round(time.monotonic() - t0, 3),
            "timed_out": False,
            "stdout": "",
            "stderr": str(exc),
        }

    _track_proc(proc, True)
    stdout_text = ""
    stderr_text = ""
    try:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            if stdin_bytes is not None and proc.stdin is not None:
                try:
                    proc.stdin.write(stdin_bytes)
                    proc.stdin.close()
                except BrokenPipeError:
                    pass

            def _pump() -> None:
                written = 0
                with open(log_path, "wb") as lf:
                    assert proc.stdout is not None
                    for chunk in iter(lambda: proc.stdout.read(8192), b""):
                        if written < LOG_CAP_BYTES:
                            take = chunk[: LOG_CAP_BYTES - written]
                            lf.write(take)
                            written += len(take)

            th = threading.Thread(target=_pump, daemon=True)
            th.start()
            try:
                proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_group(proc)
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                th.join(timeout=10)
        else:
            try:
                out_b, err_b = proc.communicate(input=stdin_bytes, timeout=timeout_s)
                stdout_text = out_b.decode("utf-8", "replace")
                stderr_text = err_b.decode("utf-8", "replace")
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_group(proc)
                try:
                    out_b, err_b = proc.communicate(timeout=5)
                    stdout_text = out_b.decode("utf-8", "replace")
                    stderr_text = err_b.decode("utf-8", "replace")
                except Exception:
                    pass
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        _track_proc(proc, False)

    return {
        "rc": proc.returncode,
        "wall_s": round(time.monotonic() - t0, 3),
        "timed_out": timed_out,
        "stdout": stdout_text,
        "stderr": stderr_text,
    }
