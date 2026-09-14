#!/usr/bin/env python3
"""R530 的目錄級沙箱——三個後端，一個介面，而且**是哪一個要落盤**。

這支在架構裡承重什麼（`DECISION_20260913_R530_…_PREREG.md` §三-3）：
R530 的 worker 會在工作區裡跑**它自己寫的 bash**，驗收也要在同一台跑。
`vacant/checks.py` 那顆沙箱是**單一程式碼字串**的沙箱（`python -I` ＋ AST 白名單
＋ literal-only proxy），跑不了一個目錄，對「模型自己寫的任意指令」也不成立。
所以要另外一顆；而「另外一顆」在 Ubuntu 24.04 上不是裝個套件就有的東西
（見下面 S1 的實測），所以這支的第一責任是**把實際拿到的隔離強度講清楚**，
不是假裝拿到了。

## 三個後端（`--backend auto` 依序試，試到能用為止）

| 名字 | 做法 | 網路隔離 | 檔案隔離 |
|---|---|---|---|
| `bwrap` | `bwrap --unshare-all` ＋**最小 rootfs**（只 ro-bind `/usr /bin /sbin /lib /lib64 /etc`）＋ `--bind <ws> <ws>` | **真的有**（net namespace） | **真的有**（只有工作區是 rw，而且 repo／`$HOME` 在裡面**不存在**） |
| `unshare` | `sudo -n unshare -n --` ＋ `setpriv` 降權 ＋ rlimit ＋ cwd 鎖在工作區 | **真的有**（net namespace） | 只有 unix 權限，**不是隔離** |
| `none` | 直接 `subprocess` ＋ rlimit ＋ `killpg` ＋ 乾淨 env | **沒有** | **沒有** |

⚠ **為什麼 bwrap 不用 `--ro-bind / /`**（預註冊 §三-3 的 S1 寫的是那一行）：
`--ro-bind / /` 之下整台機器的檔案系統在沙箱裡**讀得到**，包含
`ops/gain/r530/hidden/`。V/GT 紅線（§五-3 第 1 條）要的是**結構性保證**
「隱藏驗收永遠不在 worker 構得到的地方」，而「讀得到但我們用 DENY 擋指令文字」
不是結構性保證，是擋門。最小 rootfs 之下 repo 根本不在沙箱的檔案系統裡
⇒ 那條洩漏通道**不可表達**（R452 `vacant/suitespec.py` 的同一種紀律）。
代價是 worker 看不到 `git`／`pip` 之外的專案環境——本 run 的工作區本來就是
自給自足的 10–30 KB 目錄，沒有這個需求。

隱藏驗收要跑的時候，runner 用 `ro_binds=` 明示地把**那一次**要用的驗收目錄
ro-bind 進去（`acceptance.py`），跑完就沒有了。
「誰看得到隱藏驗收」因此是一個逐次明示的參數，不是一個預設值。

`none` 不是「沙箱的弱版本」，它**不是沙箱**。留著它的唯一理由是：本機（macOS）
開發與單元測試要跑得起來，而且真跑時「退到 none」必須是一個**看得見的狀態**，
不是一個安靜的預設值。`backend_meta.network_isolated` 是 False 的那一刻，
收官報告就必須帶著 §八-9 那句誠實邊界。

## ⚠ 2026-09-13 在 vacant-dev 上的實測（這一段不准被後來的人當成過時註解刪掉）

預註冊 §三-3 寫的是「`sudo apt install bubblewrap`，套件自帶 AppArmor profile
應可用」。**那個前提是錯的**，逐條：

  · `bubblewrap 0.9.0-1ubuntu0.1` 的 `dpkg -L` 裡**沒有任何 `/etc/apparmor.d/` 檔案**
    ——它只帶 `/usr/lib/sysctl.d/50-bubblewrap.conf`（設 `unprivileged_userns_clone=1`，
    對 Ubuntu 24.04 的限制**無效**，因為擋門是 AppArmor 不是那個 sysctl）。
  · `kernel.apparmor_restrict_unprivileged_userns=1` ⇒ 非特權 `bwrap` 建 userns 時
    會轉進 `unprivileged_userns` profile，接著寫 `/proc/<pid>/uid_map` 被 DENIED
    （`dmesg` 逐字：`apparmor="DENIED" operation="open" … name="proc/…/uid_map"`）
    ⇒ **裸 `bwrap` 在這台機器上起不來**。
  · `sudo bwrap` 起得來（root 建 ns），但同一條 profile 轉換會拿掉 `dac_override`
    ⇒ 綁 `/home/user1/**` 會 `Permission denied`（`/home/user1` 是 `drwxr-x---`）。
    ⇒ 走 `sudo bwrap` 的話**工作區根目錄必須放在世界可穿越的路徑**
    （`/var/tmp/...`），不能放 `~/vacant/r530_work`。

⇒ 要讓 `bwrap` 後端在 vacant-dev 上真的可用，需要**其中一項主機政策改動**：
  (1) 裝一份只放行 `/usr/bin/bwrap` 的 AppArmor profile（Ubuntu 官方建議的做法），或
  (2) 把工作區根改到 `/var/tmp` 並以 `sudo -n bwrap` 執行。
兩者都不是「裝個套件」，所以**由人類或 Fable 決定**，這支不自己決定：
`probe()` 誠實回報每個後端能不能用，`auto` 依序退，退到哪一級寫進 `backend_meta`。

## 共同的收緊（三個後端都套用）

* `RLIMIT_CPU`／`RLIMIT_DATA`／`RLIMIT_AS`（Linux）——形狀逐字沿用
  `vacant/checks.py::_cpu_limits`，只把記憶體上限從 128 MiB 改成 512 MiB
  （Fable 裁決：目錄級任務要跑得動 `python3 -c` 以外的東西）。
* `start_new_session=True` ＋ 逾時 `killpg(SIGKILL)`——逐字沿用 `checks.py`
  的收尾形狀，理由相同：只 kill 直接子行程會留下孤兒。
* 環境變數只留 `PATH`／`HOME`／`TMPDIR`／`LANG`／`LC_ALL`，`HOME` 指向工作區。
* cwd **一律**是該格工作區。

## 誠實邊界（`vacant/checks.py` 的那句，逐字適用，不准刪）

本 run 跑的是自家模型寫的程式碼，威脅模型是「意外」不是「攻擊」。
`bwrap` 後端擋得住意外的觸網與意外的寫出界；它**不是**對抗惡意程式碼的完整
OS 安全邊界。`unshare` 後端只有網路那一半是真的隔離。`none` 後端兩半都沒有。
"""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import platform
import shutil
import signal
import subprocess
import sys
import time

#: 記憶體上限（Fable 裁決：512 MiB）。
DEFAULT_MEMORY_BYTES = 512 * 1024 * 1024
#: 每個測試檔的逾時（Fable 裁決：10 秒）。
DEFAULT_TEST_TIMEOUT_S = 10
#: worker 自己的指令預設逾時（可由模型指定 1–300，見 `openwork_arms`）。
DEFAULT_TOOL_TIMEOUT_S = 120

BACKEND_NAMES = ("bwrap", "unshare", "none")

#: 探針用的目標位址。1.1.1.1:80 選它的理由：不需要 DNS（DNS 在無網路環境下
#: 會以另一種方式失敗，那會讓「擋住了」與「查不到名字」混在一起）。
PROBE_HOST, PROBE_PORT = "1.1.1.1", 80

_PROBE_NET_SRC = (
    "import socket,sys\n"
    f"try:\n    socket.create_connection(({PROBE_HOST!r},{PROBE_PORT}),2).close()\n"
    "    print('NET_REACHED')\n"
    "except Exception as e:\n    print('NET_BLOCKED', type(e).__name__)\n"
)


@dataclasses.dataclass(frozen=True)
class SandboxResult:
    """一次沙箱執行的結果。`timed_out` 與 `rc` 分開記——逾時不是「跑出 124」。"""

    rc: int | None
    stdout: str
    stderr: str
    timed_out: bool
    wall_ms: int
    argv: list[str]

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


def _rlimits(cpu_seconds: int, memory_bytes: int):  # pragma: no cover - 子行程裡跑
    """形狀逐字沿用 `vacant/checks.py::_cpu_limits`（只有數值不同）。"""
    def _apply() -> None:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            resource.setrlimit(resource.RLIMIT_DATA, (memory_bytes, memory_bytes))
            if sys.platform.startswith("linux"):
                resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        except Exception:                                    # noqa: BLE001
            pass
    return _apply


def _clean_env(workspace: pathlib.Path) -> dict[str, str]:
    """乾淨環境。`HOME` ＝ 工作區，`TMPDIR` ＝ `/tmp`。

    ⚠ **`TMPDIR` 刻意不指到工作區底下**。驗收測試會用 `tempfile` 開暫存檔，
      而工作區底下的任何一個新檔案都會改變樹雜湊 ⇒ 「跑一次隱藏驗收」
      就會讓 `ws_end_sha256` 變掉，而 `openwork_arms.run_cell` 對這件事有一條
      硬斷言（隱藏驗收不得動到工作區，§五-3 第 1 條）。
      `bwrap` 後端之下 `/tmp` 是一塊 `--tmpfs`，逐格獨立、跑完就沒了。
    """
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": str(workspace),
        "TMPDIR": "/tmp",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        # worker 寫出來的 .pyc 會進樹雜湊 ⇒ 同一份程式碼在不同格得到不同的樹。
        "PYTHONDONTWRITEBYTECODE": "1",
    }


class Sandbox:
    """一個後端。`run()` 是唯一的執行入口，三個後端的簽章逐字相同。"""

    name = "none"

    def __init__(self, *, memory_bytes: int = DEFAULT_MEMORY_BYTES) -> None:
        self.memory_bytes = memory_bytes
        self._probe: dict | None = None

    # ── 子類別實作 ────────────────────────────────────────────────────
    def _wrap(self, command: str, workspace: pathlib.Path,
              ro_binds: tuple[pathlib.Path, ...] = ()) -> list[str]:
        return ["bash", "-lc", command]

    def available(self) -> tuple[bool, str]:
        """這個後端在這台機器上起不起得來。回 `(ok, 原因)`。"""
        return True, ""

    # ── 共同執行路徑 ──────────────────────────────────────────────────
    def run(self, command: str, *, workspace: str | os.PathLike,
            timeout_s: float = DEFAULT_TOOL_TIMEOUT_S,
            ro_binds: tuple[str | os.PathLike, ...] = ()) -> SandboxResult:
        """跑一條 bash 指令，cwd ＝ `workspace`。

        `ro_binds` ＝ 這一次額外唯讀可見的主機路徑。**只有 `bwrap` 後端真的
        會少掉沒列進來的東西**；另外兩個後端看得到整台機器的檔案系統，
        所以 `ro_binds` 對它們是一個沒有作用的參數——這件事寫在這裡，
        免得有人以為換個後端隔離強度一樣。
        """
        ws = pathlib.Path(workspace).resolve()
        if not ws.is_dir():
            raise FileNotFoundError(f"工作區不存在：{ws}")
        binds = tuple(pathlib.Path(p).resolve() for p in ro_binds)
        argv = self._wrap(command, ws, binds)
        env = _clean_env(ws)
        t0 = time.time()
        proc = None
        try:
            proc = subprocess.Popen(
                argv, cwd=str(ws), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                errors="replace",
                preexec_fn=(_rlimits(int(timeout_s) + 5, self.memory_bytes)
                            if os.name == "posix" else None),
                start_new_session=(os.name == "posix"),
            )
            out, err = proc.communicate(timeout=timeout_s)
            return SandboxResult(proc.returncode, out, err, False,
                                 int((time.time() - t0) * 1000), argv)
        except subprocess.TimeoutExpired:
            if proc is not None:
                _kill_group(proc)
                try:
                    out, err = proc.communicate(timeout=5)
                except Exception:                            # noqa: BLE001
                    out, err = "", ""
            else:                                            # pragma: no cover
                out, err = "", ""
            return SandboxResult(None, out, err, True,
                                 int((time.time() - t0) * 1000), argv)
        except OSError as e:
            # 連沙箱都起不來＝基建故障，不是候選的錯（`checks.CheckInfraError`
            # 的同一條紀律）。呼叫端把它翻成 infra_void。
            raise SandboxInfraError(f"沙箱起不來：{e}（argv={argv[:3]}…）") from e

    # ── 探針（**每個 run 開頭跑一次，結果落盤**）────────────────────────
    def probe(self, workdir: str | os.PathLike, *, force: bool = False) -> dict:
        """實測這個後端到底擋不擋得住網路與寫出界。**不是宣稱，是量的。**

        回一份可落盤的 dict；`network_isolated` 與 `write_confined` 兩個欄位
        是 `backend_meta` 的骨幹——它們為 False 的時候，收官報告必須帶著
        §八-9 的誠實邊界，而不是印一個沙箱的名字就算數。
        """
        if self._probe is not None and not force:
            return self._probe
        ws = pathlib.Path(workdir).resolve()
        ws.mkdir(parents=True, exist_ok=True)
        outside = ws.parent / "_r530_probe_escape.txt"
        if outside.exists():
            outside.unlink()
        ok, why = self.available()
        rec: dict = {
            "backend": self.name,
            "available": ok,
            "unavailable_reason": why or None,
            "platform": platform.platform(),
            "memory_bytes": self.memory_bytes,
            "network_isolated": None,
            "write_confined": None,
            "probe_detail": {},
            "honest_bound": HONEST_BOUND[self.name],
        }
        if not ok:
            self._probe = rec
            return rec
        net = self.run(
            f"{_py()} -c {_shquote(_PROBE_NET_SRC)}", workspace=ws, timeout_s=30)
        rec["probe_detail"]["net"] = {
            "rc": net.rc, "stdout": net.stdout.strip()[:200],
            "stderr": net.stderr.strip()[-200:], "timed_out": net.timed_out}
        rec["network_isolated"] = ("NET_REACHED" not in net.stdout)

        esc = self.run(
            f"{_py()} -c {_shquote(_escape_src(outside))}", workspace=ws, timeout_s=30)
        rec["probe_detail"]["escape"] = {
            "rc": esc.rc, "stdout": esc.stdout.strip()[:200],
            "stderr": esc.stderr.strip()[-200:], "timed_out": esc.timed_out}
        wrote_outside = outside.exists()
        if wrote_outside:
            outside.unlink()

        inside = self.run(
            f"{_py()} -c {_shquote(_inside_src())}", workspace=ws, timeout_s=30)
        rec["probe_detail"]["inside"] = {
            "rc": inside.rc, "stdout": inside.stdout.strip()[:200],
            "stderr": inside.stderr.strip()[-200:], "timed_out": inside.timed_out}
        rec["write_works_inside"] = ("WROTE_INSIDE" in inside.stdout)
        rec["write_confined"] = (not wrote_outside) and rec["write_works_inside"]
        for junk in ("r530_probe_inside.txt",):
            p = ws / junk
            if p.exists():
                p.unlink()

        # 第三條、也是 V/GT 最在意的一條：repo（裡面有 `hidden/`）在沙箱裡
        # **存不存在**。存在就代表隱藏驗收的隔離是靠 DENY 擋門而不是結構。
        repo = pathlib.Path(__file__).resolve().parents[3]
        vis = self.run(f"{_py()} -c {_shquote(_visible_src(repo))}",
                       workspace=ws, timeout_s=30)
        rec["probe_detail"]["repo_visible"] = {
            "rc": vis.rc, "stdout": vis.stdout.strip()[:200],
            "path": str(repo)}
        rec["repo_hidden_from_sandbox"] = ("REPO_VISIBLE" not in vis.stdout)
        self._probe = rec
        return rec


class SandboxInfraError(RuntimeError):
    """沙箱本身起不來（不是被跑的東西的錯）。呼叫端翻成 `infra_void`。"""


def _kill_group(proc: subprocess.Popen) -> None:
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
        except Exception:                                    # noqa: BLE001
            pass
    try:
        proc.kill()
    except Exception:                                        # noqa: BLE001
        pass


def _py() -> str:
    return "python3" if shutil.which("python3") else sys.executable


def _abs(name: str) -> str:
    """絕對路徑。`sudo env -i` 之後 `PATH` 是我們自己給的，但 `sudo` 自己的
    `secure_path` 在解析第一個 argv 時仍然管用——把每一段都寫成絕對路徑
    可以讓「到底跑了哪一支 binary」在 `SandboxResult.argv` 裡看得見。"""
    return shutil.which(name) or f"/usr/bin/{name}"


def _shquote(s: str) -> str:
    import shlex
    return shlex.quote(s)


def _escape_src(outside: pathlib.Path) -> str:
    return (
        "import sys\n"
        f"p = {str(outside)!r}\n"
        "try:\n"
        "    open(p, 'w').write('escaped')\n"
        "    print('ESCAPED')\n"
        "except Exception as e:\n"
        "    print('ESCAPE_BLOCKED', type(e).__name__)\n"
    )


def _inside_src() -> str:
    return (
        "open('r530_probe_inside.txt','w').write('ok')\n"
        "print('WROTE_INSIDE')\n"
    )


def _visible_src(repo: pathlib.Path) -> str:
    return (
        "import os\n"
        f"p = {str(repo)!r}\n"
        "print('REPO_VISIBLE' if os.path.isdir(p) else 'REPO_ABSENT')\n"
    )


# ══ 後端 ═══════════════════════════════════════════════════════════════
HONEST_BOUND = {
    "bwrap": ("mount ＋ net namespace 隔離；只有工作區可寫。這是應用層加固，"
              "不是對抗惡意程式碼的完整 OS 安全邊界（vacant/checks.py 的同一句）。"),
    "unshare": ("只有網路是真的隔離（net namespace）；檔案端只有 unix 權限與 "
                "cwd 慣例，**擋門不是隔離**（預註冊 §三-3 S2 逐字）。"),
    "none": ("**不是沙箱**：沒有網路隔離、沒有檔案隔離，只有 rlimit／逾時／"
             "killpg／乾淨環境變數。觸網與寫出界只靠 DENY 擋門攔，"
             "而擋門建立在指令文字比對上。"),
}


class NoneSandbox(Sandbox):
    """rlimit ＋ 逾時 ＋ killpg ＋ 乾淨 env。**沒有隔離**，名字就這樣寫。"""

    name = "none"


class BwrapSandbox(Sandbox):
    """`bubblewrap`。唯一兩半隔離都是真的那一個。

    `use_sudo=True` 時走 `sudo -n bwrap`：Ubuntu 24.04 的 AppArmor 擋掉非特權
    userns（見模組 docstring 的實測），root 建 ns 之後以 `--uid/--gid` 降回
    呼叫者的 uid。代價是**工作區根必須世界可穿越**（confined bwrap 沒有
    `dac_override`），所以 `~`（`drwxr-x---`）底下的工作區在這個模式下綁不起來。
    """

    name = "bwrap"

    def __init__(self, *, memory_bytes: int = DEFAULT_MEMORY_BYTES,
                 use_sudo: bool = False) -> None:
        super().__init__(memory_bytes=memory_bytes)
        self.use_sudo = use_sudo

    #: 最小 rootfs：沙箱裡看得到的主機目錄就這些，**全部唯讀**。
    #: 沒有 `/home`、沒有 `/var`、沒有 repo ⇒ `ops/gain/r530/hidden/` 在沙箱的
    #: 檔案系統裡**不存在**，而不是「存在但我們不准它讀」。
    SYSTEM_RO = ("/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/etc")

    def _wrap(self, command: str, workspace: pathlib.Path,
              ro_binds: tuple[pathlib.Path, ...] = ()) -> list[str]:
        pre = ["sudo", "-n"] if self.use_sudo else []
        uid_gid = (["--uid", str(os.getuid()), "--gid", str(os.getgid())]
                   if self.use_sudo else [])
        sysro: list[str] = []
        for d in self.SYSTEM_RO:
            # `-try` 版本：`/lib64` 在某些發行版是不存在的符號連結，
            # 缺一個系統目錄不該讓沙箱整個起不來。
            sysro += ["--ro-bind-try", d, d]
        extra: list[str] = []
        for p in ro_binds:
            extra += ["--ro-bind", str(p), str(p)]
        return pre + [
            "bwrap",
            "--unshare-all", "--die-with-parent", "--new-session",
            *sysro,
            "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
            "--bind", str(workspace), str(workspace),
            *extra,
            "--chdir", str(workspace),
            *uid_gid,
            "--", "bash", "-lc", command,
        ]

    def available(self) -> tuple[bool, str]:
        if not shutil.which("bwrap"):
            return False, "bwrap 不在 PATH 上"
        if self.use_sudo and not shutil.which("sudo"):
            return False, "use_sudo 但 sudo 不在 PATH 上"
        try:
            r = subprocess.run(
                self._wrap("true", pathlib.Path(".").resolve()),
                capture_output=True, text=True, timeout=30)
        except Exception as e:                               # noqa: BLE001
            return False, f"bwrap 起不來：{type(e).__name__}: {e}"
        if r.returncode != 0:
            return False, f"bwrap rc={r.returncode}：{(r.stderr or '').strip()[:300]}"
        return True, ""


class UnshareSandbox(Sandbox):
    """`sudo -n unshare -n` ＋ `setpriv` 降權。**只有網路那一半是真的。**

    預註冊 §三-3 的 S2。它比 `none` 強的只有一件事：net namespace 是核心層級的
    隔離，不是指令文字比對。檔案端一格都沒多。
    """

    name = "unshare"

    def __init__(self, *, memory_bytes: int = DEFAULT_MEMORY_BYTES,
                 reuid: int | None = None, regid: int | None = None) -> None:
        super().__init__(memory_bytes=memory_bytes)
        # ⚠ **預設是「降權回呼叫者自己」＝檔案端一格都沒多。**
        #   更強的配置是給一個**專用的無特權 uid**（例如 `nobody`）：
        #   `/home/<user>` 是 `drwxr-x---` ⇒ 那個 uid 讀不到 repo、讀不到
        #   `ops/gain/r530/hidden/`、讀不到 `~/.cline-keys` ⇒ 隱藏驗收的隔離
        #   就從「DENY 擋門」升級成「unix 權限」。代價是工作區根要搬到
        #   世界可穿越而且那個 uid 寫得進去的地方（`/var/tmp/...`），
        #   而那是一次**主機層級的決定**（建目錄、chown）——
        #   所以這支只把參數留出來（`run_r530 --sandbox-uid/--sandbox-gid`），
        #   **不自己決定**。實際用了哪一個逐格落盤在 `backend_meta`。
        self.reuid = os.getuid() if reuid is None else reuid
        self.regid = os.getgid() if regid is None else regid

    def _wrap(self, command: str, workspace: pathlib.Path,
              ro_binds: tuple[pathlib.Path, ...] = ()) -> list[str]:
        # ⚠ `ro_binds` 在這個後端**沒有作用**：整台機器的檔案系統本來就看得到。
        #   不假裝有作用，也不因此拒收參數——換後端的人要從
        #   `backend_meta.honest_bound` 讀到這件事，不是從一個例外。
        #
        # ⚠ **環境變數必須明示地穿過 `sudo`**（2026-09-13 在 vacant-dev 實測）：
        #   `sudo` 預設 `env_reset`，於是 `subprocess(env=…)` 給的乾淨環境
        #   **一個都到不了裡面**——實測 stderr 噴 `/root/.bash_profile:
        #   Permission denied`，代表 `HOME` 是 root 的而不是工作區的。
        #   那不只是噪音：`HOME`／`TMPDIR` 決定驗收測試的暫存檔寫到哪，
        #   而暫存檔寫進工作區會改變樹雜湊。所以這裡用 `env -i` 重建。
        env = _clean_env(workspace)
        return [
            "sudo", "-n", _abs("env"), "-i",
            *[f"{k}={v}" for k, v in sorted(env.items())],
            _abs("unshare"), "--net", "--",
            _abs("setpriv"), f"--reuid={self.reuid}", f"--regid={self.regid}",
            "--clear-groups", "--",
            _abs("bash"), "-lc", command,
        ]

    def available(self) -> tuple[bool, str]:
        for tool in ("sudo", "unshare", "setpriv"):
            if not shutil.which(tool):
                return False, f"{tool} 不在 PATH 上"
        try:
            r = subprocess.run(self._wrap("true", pathlib.Path(".").resolve()),
                               capture_output=True, text=True, timeout=30)
        except Exception as e:                               # noqa: BLE001
            return False, f"unshare 起不來：{type(e).__name__}: {e}"
        if r.returncode != 0:
            return False, (f"unshare rc={r.returncode}："
                           f"{(r.stderr or '').strip()[:300]}")
        return True, ""


_BACKENDS = {
    "bwrap": BwrapSandbox,
    "unshare": UnshareSandbox,
    "none": NoneSandbox,
}


def make_sandbox(name: str = "auto", *, workdir: str | os.PathLike,
                 memory_bytes: int = DEFAULT_MEMORY_BYTES,
                 use_sudo_bwrap: bool = False,
                 sandbox_uid: int | None = None,
                 sandbox_gid: int | None = None) -> tuple[Sandbox, dict]:
    """建一個沙箱，回 `(sandbox, backend_meta)`。

    `name="auto"` ⇒ 依 `BACKEND_NAMES` 的順序試，**第一個 `available()` 為真的**
    就用它，並把試過的每一個與失敗原因一起寫進 `backend_meta.tried`。
    「為什麼退到這一級」必須留在證據裡，否則收官只會看到一個後端名字。

    明示指定名字而該後端起不來 ⇒ `SystemExit`。指定了就是要那一個，
    靜靜換一個比較弱的沙箱是最糟的失敗方式。
    """
    tried: list[dict] = []
    if name not in ("auto", *BACKEND_NAMES):
        raise SystemExit(f"unknown backend {name!r}（可用 auto／{list(BACKEND_NAMES)}）")
    order = BACKEND_NAMES if name == "auto" else (name,)
    chosen: Sandbox | None = None
    for bname in order:
        kwargs = {"memory_bytes": memory_bytes}
        if bname == "bwrap":
            kwargs["use_sudo"] = use_sudo_bwrap
        if bname == "unshare":
            kwargs["reuid"] = sandbox_uid
            kwargs["regid"] = sandbox_gid
        sb = _BACKENDS[bname](**kwargs)
        ok, why = sb.available()
        tried.append({"backend": bname, "available": ok, "reason": why or None})
        if ok:
            chosen = sb
            break
    if chosen is None:
        raise SystemExit(
            "沒有任何沙箱後端可用："
            + json.dumps(tried, ensure_ascii=False)
            + "——量不到不是通過。停。")
    meta = dict(chosen.probe(workdir))
    meta["requested"] = name
    meta["tried"] = tried
    meta["use_sudo_bwrap"] = bool(use_sudo_bwrap)
    # 預註冊 §三-6 C7 指名的是 `backend_meta.sandbox`；本支原本叫 `backend`。
    # 兩個名字都落盤，理由同 `rows.jsonl` 的 `workspace_*` 別名。
    meta["sandbox"] = meta["backend"]
    meta["sandbox_uid"] = getattr(chosen, "reuid", None)
    meta["sandbox_gid"] = getattr(chosen, "regid", None)
    return chosen, meta


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="R530 沙箱探針（零模型呼叫）")
    ap.add_argument("--backend", default="auto",
                    choices=["auto", *BACKEND_NAMES])
    ap.add_argument("--workdir", default=None,
                    help="探針用的暫存工作區（預設在 TMPDIR 開一個）")
    ap.add_argument("--sudo-bwrap", action="store_true",
                    help="bwrap 走 sudo -n（Ubuntu 24.04 AppArmor 擋非特權 userns 時唯一可行）")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    import tempfile
    tmp = None
    wd = args.workdir
    if wd is None:
        tmp = tempfile.TemporaryDirectory(prefix="r530probe.")
        wd = tmp.name
    try:
        _sb, meta = make_sandbox(args.backend, workdir=wd,
                                 use_sudo_bwrap=args.sudo_bwrap)
    except SystemExit as e:
        print(str(e))
        return 2
    text = json.dumps(meta, ensure_ascii=False, indent=2)
    print(text)
    if args.json:
        p = pathlib.Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
    if tmp is not None:
        tmp.cleanup()
    # 探針本身「跑完了」就回 0——**擋不擋得住是資料不是退出碼**。
    # 用退出碼表達隔離強度會讓「這台機器只有 none」變成一個看起來像壞掉的東西，
    # 於是有人會去「修」它；隔離強度該進 backend_meta 讓判準去讀。
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
