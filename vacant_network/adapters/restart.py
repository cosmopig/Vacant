"""零設定的重開模式——`vacant do <agent>` 在沒有任務契約時的預設行為（T05／S3，2026-11-17）。

這支在架構裡承重什麼：把 `ops/redo/redo.py` 的 R3 政策做成使用者打得到的一個指令。
R3 是這個 repo 裡第一個在**原生 agent**上量到交付變好的設定（redo1：pi＋gemma-4-12b、34 題×5，
進行中數字見 `ops/redo/`；結論以該批的 `REPORT.md` 為準，這裡不引用數字）。

政策（與 `redo.py` 的 `_policy_stop`／`_policy_deliver` 逐條相同，`tests/test_adapters_restart.py` 對照）：
1. 驗收訊號＝專案在**開始那一刻**就有的測試檔（`*_test.py`／`test_*.py`，`unittest` 跑）。
   跑驗收之前把它們還原成開始時的內容；被改過的記在 `tests_tampered`，也**不寫回專案**。
2. 每一次嘗試：全新的暫存副本＋全新的 agent 行程。嘗試之間不留東西、不給失敗原文。
3. 驗收通過就停、交那一次；最多 `max_attempts` 次、每次 `attempt_timeout_s`、合計 `budget_s`。
   都沒過就交原件測試過最多的那一次（同分取後面那次），給人的訊息明講測試沒有全過。
4. 專案裡沒有測試檔 ⇒ 跑一次、照實交回、明講「沒有可執行的驗收」，不假裝檢查過。

交回：被選中那一次的工作區同步回專案（新增／修改／刪除），**測試檔除外**——跟使用者直接在專案裡跑
agent 的結果同一種形狀，只是多了「選哪一次」。

誠實邊界（改碼請保留）：
- 驗收＝「擋得住專案自己的測試會抓到的錯」，**不等於需求被滿足**。測試寫得弱，這一層就弱。
- 暫存副本**不是沙箱**：agent 以使用者的帳號執行，讀寫得到磁碟上你讀寫得到的一切；這層只保護「交回寫回」
  與「驗收流程」本身，擋不住 agent 在執行期間直接讀寫專案外或其他路徑的檔案，也殺不到自己 `setsid()`
  脫離行程群組的背景子行程。
- 等預算是牆鐘的；重開通常讓 agent 用掉更多模型呼叫（redo1 約兩倍），這一層不省算力。
- `budget_s` 是**整個指令**的牆鐘上限：agent、驗收（所有測試目錄共用同一條期限，不設超額下限）、複製都算在內，
  每次嘗試前預留一次驗收的時間（2026-11-19：只算 agent 時間時，confirm1／confirm1c 各有 1 格第三次嘗試跑到
  外層時限被砍、什麼都沒交回）。
  ⚠ 這點和 `redo.py` 的 R3 不同（R3 只算 agent 牆鐘）：產品比量到的政策略保守，同樣預算下最後一次嘗試可能短一點。
- 快照與驗收一致性：每次 agent 結束並殺完其行程群組後，先拍一次只含一般檔案的私密快照（跳過符號連結、FIFO／socket／
  裝置檔、`COPY_SKIP` 名稱與無法讀取的項目），驗收與寫回皆以**同一份快照**為準（驗收測試的正是實際會寫回的檔案集合），
  避免殘留背景行程在驗收與寫回之間偷改工作區（TOCTOU），也避免 symlink 只在驗收生效卻不寫回。
- 驗收執行隔離邊界：驗收子行程以 `python -I -B` 在工作區外的獨立腳本檔執行（不把 `""` 或 user site 放進 `sys.path`）、
  獨立 session（結束或逾時皆 `killpg` 整組清除）、先載入標準庫再把工作區附在 `sys.path` 尾端、依原測試檔精確路徑載入
  （防止套件目錄或標準庫遮蔽），並透過獨立管線（FD）與單次隨機 nonce 回傳結果（不依賴 stdout 固定標記）。
  ⚠ 但**候選程式碼與 `unittest` 仍在同一個 Python 行程內執行**，故無法防禦惡意候選碼在行程內 monkey-patch
  `unittest` 或執行期狀態（若需要雙行程隔離，請用 `vacant_network.checks.run_python_check`）。
- 寫回安全邊界：寫回前先規劃與驗證所有增／改／刪操作再套用，先刪後增、透過同目錄暫存檔＋`os.replace` 原子置換
  （不原地覆寫硬連結 inode、不把檔案寫進既有目錄）；符號連結、無法讀取的目錄／檔案、或與非空／受保護目錄衝突的路徑
  一律跳過並記於 `changed["skipped"]`，不會寫到專案外面也不會誤刪原檔；若套用途中遇非預期錯誤會回滾，維持原專案不變。
- 容錯邊界：單次嘗試在快照或驗收時發生任何非預期錯誤，該次嘗試一律記為未通過（例如 `acceptance_error`），不中斷整個
  `run()`、也不遺失前面嘗試的成果。
- 這一層不讀 agent 說了什麼；它只看測試。說「做完了」但測試沒過＝沒過。
"""
from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable

from .run import COPY_SKIP, Launch, run_agent, work_root

PATTERNS = ("*_test.py", "test_*.py")
ACC_TIMEOUT_S = 120.0
_CHUNK_SIZE = 65536
_RESULT_KEYS = ("run", "failures", "errors", "skipped", "unexpected_successes")

_UNITTEST_RUNNER = r"""
def _main():
    import importlib.util
    import json
    import os
    import sys
    import traceback
    import unittest

    _os = os
    _json = json
    _sys = sys
    _tb = traceback
    _Loader = unittest.TestLoader
    _Result = unittest.TestResult
    _spec_from_file = importlib.util.spec_from_file_location
    _mod_from_spec = importlib.util.module_from_spec

    raw_cfg = _sys.stdin.read()
    try:
        dn = _os.open(_os.devnull, _os.O_RDONLY)
        try:
            _os.dup2(dn, 0)
        finally:
            _os.close(dn)
    except OSError:
        pass

    cfg = _json.loads(raw_cfg)
    w_fd = int(cfg["w_fd"])
    nonce = str(cfg["nonce"])
    cwd = str(cfg["cwd"])
    tests = cfg["tests"]
    try:
        _os.set_inheritable(w_fd, False)
    except OSError:
        pass

    if cwd not in _sys.path:
        _sys.path.append(cwd)

    out = {
        "run": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "unexpected_successes": 0,
        "load_error": None,
        "first_problem": None,
    }
    for idx, (mod_name, file_path) in enumerate(tests):
        try:
            load_name = mod_name if mod_name not in _sys.modules else f"__vacant_test_{idx}_{mod_name}"
            spec = _spec_from_file(load_name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load test file: {file_path}")
            mod = _mod_from_spec(spec)
            _sys.modules[load_name] = mod
            spec.loader.exec_module(mod)
            suite = _Loader().loadTestsFromModule(mod)
        except BaseException:
            out["load_error"] = _tb.format_exc(limit=3)[-800:]
            break
        res = _Result()
        suite.run(res)
        out["run"] += res.testsRun
        out["failures"] += len(res.failures)
        out["errors"] += len(res.errors)
        out["skipped"] += len(res.skipped)
        out["unexpected_successes"] += len(res.unexpectedSuccesses)
        probs = res.failures + res.errors
        if probs and out["first_problem"] is None:
            out["first_problem"] = (str(probs[0][0]) + "\n" + probs[0][1])[-800:]

    try:
        _sys.stdout.flush()
        _sys.stderr.flush()
    except BaseException:
        pass

    payload = (nonce + "\n" + _json.dumps(out) + "\n").encode("utf-8")
    view = memoryview(payload)
    written = 0
    while written < len(view):
        n = _os.write(w_fd, view[written:])
        if n <= 0:
            break
        written += n
    try:
        _os.close(w_fd)
    except OSError:
        pass
    _os._exit(0)


_main()
"""


def _has_copy_skip(rel: str) -> bool:
    return any(part in COPY_SKIP for part in pathlib.PurePosixPath(rel).parts)


def _matches_prefix(rel: str, prefixes: set[str]) -> bool:
    if not prefixes:
        return False
    if "." in prefixes or rel in prefixes:
        return True
    parts = pathlib.PurePosixPath(rel).parts
    cur = ""
    for part in parts[:-1]:
        cur = f"{cur}/{part}" if cur else part
        if cur in prefixes:
            return True
    return False


def _scan_files(root: pathlib.Path) -> tuple[list[str], set[str]]:
    """掃描 root 底下的所有一般檔案（跳過 COPY_SKIP 的目錄與檔案、symlink 與特殊檔）。
    同時回傳無法列出內容的目錄相對路徑集合。"""
    out: list[str] = []
    unreadable_dirs: set[str] = set()

    def _walk(cur: pathlib.Path, rel_prefix: str) -> None:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            unreadable_dirs.add(rel_prefix or ".")
            return
        for entry in entries:
            name = entry.name
            if name in COPY_SKIP:
                continue
            rel = f"{rel_prefix}/{name}" if rel_prefix else name
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            mode = st.st_mode
            if stat.S_ISLNK(mode):
                continue
            if stat.S_ISDIR(mode):
                _walk(cur / name, rel)
            elif stat.S_ISREG(mode):
                out.append(rel)

    _walk(root, "")
    return sorted(out), unreadable_dirs


def _files(root: pathlib.Path) -> list[str]:
    return _scan_files(root)[0]


def _through_symlink(root: pathlib.Path, rel: str) -> bool:
    """root/rel 的路徑上（含最後一段）有沒有 symlink。root 本身不算。"""
    p = root
    for part in pathlib.PurePosixPath(rel).parts:
        p = p / part
        try:
            if p.is_symlink():
                return True
        except OSError:
            return True
    return False


def _open_reg_readonly(path: pathlib.Path) -> tuple[int, os.stat_result] | None:
    """以 O_NOFOLLOW | O_NONBLOCK 開啟一般檔案，確認不是 symlink／FIFO／目錄。"""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(path), flags)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            os.close(fd)
            return None
        return fd, st
    except OSError:
        os.close(fd)
        return None


def _sha256_file(path: pathlib.Path) -> str | None:
    opened = _open_reg_readonly(path)
    if opened is None:
        return None
    fd, _ = opened
    h = hashlib.sha256()
    try:
        with os.fdopen(fd, "rb") as f:
            while True:
                chunk = f.read(_CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _copy_reg_file(src: pathlib.Path, dst: pathlib.Path, mode: int = 0o600) -> bool:
    opened = _open_reg_readonly(src)
    if opened is None:
        return False
    fd, _ = opened
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(fd, "rb") as src_f:
            fd = -1
            with dst.open("wb") as dst_f:
                while True:
                    chunk = src_f.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst_f.write(chunk)
        os.chmod(dst, mode)
        return True
    except OSError:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            dst.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _rmtree_force(path: pathlib.Path) -> None:
    """清理暫存目錄：先恢復目錄權限（不跟隨 symlink），避免 0o555／0o000 目錄殘留。"""
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or not path.is_dir():
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return
    for dp, dns, fns in os.walk(path, topdown=True, followlinks=False):
        try:
            os.chmod(dp, 0o700)
        except OSError:
            pass
        for name in list(dns) + list(fns):
            p = pathlib.Path(dp) / name
            try:
                if not p.is_symlink():
                    os.chmod(p, 0o700 if p.is_dir() else 0o600)
            except OSError:
                pass
    shutil.rmtree(path, ignore_errors=True)


def _kill_group_and_wait(proc: subprocess.Popen) -> None:
    """殺掉整個獨立 session／行程群組，並短暫等待確認沒有殘留成員。"""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        proc.wait(timeout=2.0)
    except Exception:  # noqa: BLE001
        pass
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        try:
            os.killpg(proc.pid, 0)
        except OSError:
            break
        time.sleep(0.01)


def _read_all_fd(fd: int) -> bytes:
    chunks: list[bytes] = []
    try:
        while True:
            data = os.read(fd, _CHUNK_SIZE)
            if not data:
                break
            chunks.append(data)
    except OSError:
        pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    return b"".join(chunks)


def find_tests(root: pathlib.Path) -> list[str]:
    return [r for r in _files(root) if any(pathlib.PurePath(r.rsplit("/", 1)[-1]).match(p) for p in PATTERNS)]


def _clean_env(home: pathlib.Path) -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1"}


@dataclasses.dataclass
class _Snapshot:
    root: pathlib.Path
    files: dict[str, str]             # rel -> sha256 hex of bytes stored in root/rel
    modes: dict[str, int]             # rel -> original st_mode permission bits (0o777)
    symlinks: set[str]                # rel paths in ws that were symlinks
    unreadable_dirs: set[str]         # rel dirs in ws that could not be listed
    unreadable_files: set[str]        # rel files in ws that could not be read
    special_files: set[str]           # rel non-reg, non-dir, non-symlink paths (FIFO/socket/dev)


def _snapshot_workspace(ws: pathlib.Path, dest: pathlib.Path) -> _Snapshot:
    """將工作區拍成只含一般檔案的私密快照（不跟隨 symlink、跳過特殊檔與 COPY_SKIP）。"""
    dest.mkdir(parents=True, exist_ok=True)
    os.chmod(dest, 0o700)
    files: dict[str, str] = {}
    modes: dict[str, int] = {}
    symlinks: set[str] = set()
    unreadable_dirs: set[str] = set()
    unreadable_files: set[str] = set()
    special_files: set[str] = set()

    def _walk(cur: pathlib.Path, rel_prefix: str) -> None:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            unreadable_dirs.add(rel_prefix or ".")
            return
        for entry in entries:
            name = entry.name
            if name in COPY_SKIP:
                continue
            rel = f"{rel_prefix}/{name}" if rel_prefix else name
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                unreadable_files.add(rel)
                continue
            mode = st.st_mode
            if stat.S_ISLNK(mode):
                symlinks.add(rel)
                continue
            if stat.S_ISDIR(mode):
                _walk(cur / name, rel)
                continue
            if not stat.S_ISREG(mode):
                special_files.add(rel)
                continue
            opened = _open_reg_readonly(cur / name)
            if opened is None:
                unreadable_files.add(rel)
                continue
            fd, st2 = opened
            out_p = dest / rel
            h = hashlib.sha256()
            try:
                out_p.parent.mkdir(parents=True, exist_ok=True)
                with os.fdopen(fd, "rb") as src_f:
                    fd = -1
                    with out_p.open("wb") as dst_f:
                        while True:
                            chunk = src_f.read(_CHUNK_SIZE)
                            if not chunk:
                                break
                            h.update(chunk)
                            dst_f.write(chunk)
                os.chmod(out_p, 0o600)
                files[rel] = h.hexdigest()
                modes[rel] = stat.S_IMODE(st2.st_mode) & 0o777
            except OSError:
                if fd >= 0:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                try:
                    out_p.unlink(missing_ok=True)
                except OSError:
                    pass
                unreadable_files.add(rel)

    _walk(ws, "")
    return _Snapshot(
        root=dest,
        files=files,
        modes=modes,
        symlinks=symlinks,
        unreadable_dirs=unreadable_dirs,
        unreadable_files=unreadable_files,
        special_files=special_files,
    )


def _detect_tampered(snap: _Snapshot, originals: dict[str, bytes]) -> list[str]:
    tampered: list[str] = []
    for rel, want in sorted(originals.items()):
        if rel not in snap.files:
            tampered.append(rel)
            continue
        if snap.files[rel] != hashlib.sha256(want).hexdigest():
            tampered.append(rel)
    return tampered


@dataclasses.dataclass
class _WritePlan:
    added: list[str]
    modified: list[str]
    deleted: list[str]
    skipped: list[str]
    dirs_to_remove: list[str]         # deepest-first relative dir paths safe to rmdir
    before_files: set[str]


def _can_remove_dir(project: pathlib.Path, rel: str, deletes: set[str]) -> list[str] | None:
    """檢查 project/rel 目錄底下是否只包含即將刪除的一般檔案（無 symlink、COPY_SKIP、保護檔、特殊檔或不可讀目錄）。
    安全時回傳由深到淺的相對目錄清單（含 rel 本身），否則回傳 None。"""
    dirs_out: list[str] = []

    def _check(cur: pathlib.Path, cur_rel: str) -> bool:
        try:
            entries = sorted(os.scandir(cur), key=lambda e: e.name)
        except OSError:
            return False
        for entry in entries:
            name = entry.name
            if name in COPY_SKIP:
                return False
            child_rel = f"{cur_rel}/{name}"
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                return False
            mode = st.st_mode
            if stat.S_ISLNK(mode):
                return False
            if stat.S_ISDIR(mode):
                if not _check(cur / name, child_rel):
                    return False
            elif stat.S_ISREG(mode):
                if child_rel not in deletes:
                    return False
            else:
                return False
        dirs_out.append(cur_rel)
        return True

    if not _check(project / rel, rel):
        return None
    return dirs_out


def _plan_write_back(project: pathlib.Path, snap: _Snapshot, protected: set[str]) -> _WritePlan:
    """規劃寫回專案的所有操作（唯讀掃描 project，不做任何變更）。"""
    before_list, proj_unreadable = _scan_files(project)
    before = set(before_list)
    after = set(snap.files)
    ws_unsafe = snap.symlinks | snap.unreadable_dirs | snap.unreadable_files | snap.special_files

    deletes: list[str] = []
    delete_skips: set[str] = set()
    for rel in sorted(before - after - protected):
        if _has_copy_skip(rel):
            continue
        if (_matches_prefix(rel, ws_unsafe)
                or _matches_prefix(rel, proj_unreadable)
                or _through_symlink(project, rel)):
            delete_skips.add(rel)
            continue
        deletes.append(rel)
    delete_set = set(deletes)

    added: list[str] = []
    modified: list[str] = []
    write_skips: set[str] = set()
    dirs_to_remove: list[str] = []
    dirs_seen: set[str] = set()

    for rel in sorted(after - protected):
        if _has_copy_skip(rel):
            continue
        if _through_symlink(project, rel) or _matches_prefix(rel, proj_unreadable):
            write_skips.add(rel)
            continue
        # 檢查每一層父路徑：不能是無法移除的非目錄（例如受保護檔案、特殊檔、或沒被排進刪除的既有檔案）
        parts = pathlib.PurePosixPath(rel).parts
        parent_conflict = False
        cur_p = project
        cur_rel = ""
        for part in parts[:-1]:
            cur_p = cur_p / part
            cur_rel = f"{cur_rel}/{part}" if cur_rel else part
            try:
                st_p = cur_p.lstat()
            except FileNotFoundError:
                break
            except OSError:
                parent_conflict = True
                break
            if stat.S_ISLNK(st_p.st_mode):
                parent_conflict = True
                break
            if not stat.S_ISDIR(st_p.st_mode):
                if not (stat.S_ISREG(st_p.st_mode) and cur_rel in delete_set):
                    parent_conflict = True
                    break
        if parent_conflict:
            write_skips.add(rel)
            continue

        dst = project / rel
        try:
            st_dst = dst.lstat()
        except FileNotFoundError:
            st_dst = None
        except OSError:
            write_skips.add(rel)
            continue

        if st_dst is not None:
            if stat.S_ISLNK(st_dst.st_mode):
                write_skips.add(rel)
                continue
            if stat.S_ISDIR(st_dst.st_mode):
                removable = _can_remove_dir(project, rel, delete_set)
                if removable is None:
                    write_skips.add(rel)
                    continue
                for d_rel in removable:
                    if d_rel not in dirs_seen:
                        dirs_seen.add(d_rel)
                        dirs_to_remove.append(d_rel)
                added.append(rel)
                continue
            if not stat.S_ISREG(st_dst.st_mode):
                write_skips.add(rel)
                continue
            dst_sha = _sha256_file(dst)
            if dst_sha is None:
                write_skips.add(rel)
                continue
            if dst_sha == snap.files[rel]:
                continue
            modified.append(rel)
        else:
            added.append(rel)

    dirs_to_remove.sort(key=lambda r: (-len(pathlib.PurePosixPath(r).parts), r))
    return _WritePlan(
        added=added,
        modified=modified,
        deleted=deletes,
        skipped=sorted(delete_skips | write_skips),
        dirs_to_remove=dirs_to_remove,
        before_files=before,
    )


def _atomic_write_from_file(src: pathlib.Path, dst: pathlib.Path, mode: int | None) -> None:
    """經由同目錄私密暫存檔＋os.replace 原子寫入 dst（不覆寫硬連結 inode，也不寫進既有目錄）。"""
    fd, tmp_name = tempfile.mkstemp(prefix=".vacant-tmp-", dir=str(dst.parent))
    tmp_path = pathlib.Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as dst_f:
            fd = -1
            with src.open("rb") as src_f:
                while True:
                    chunk = src_f.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst_f.write(chunk)
        if mode is not None:
            os.chmod(tmp_path, mode & 0o777)
        if dst.is_symlink():
            raise OSError(f"refusing to replace symlink: {dst}")
        os.replace(tmp_path, dst)
    except BaseException:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _apply_write_plan(project: pathlib.Path, snap: _Snapshot, plan: _WritePlan,
                      backup_dir: pathlib.Path) -> dict[str, list[str]]:
    """套用已驗證的寫回計畫；任何非預期錯誤都會回滾，維持專案不變。"""
    # 套用前驗證所有待寫檔案的快照雜湊仍完整無誤
    for rel in plan.added + plan.modified:
        if _sha256_file(snap.root / rel) != snap.files.get(rel):
            all_planned = sorted(set(plan.skipped) | set(plan.added) | set(plan.modified) | set(plan.deleted))
            return {"added": [], "modified": [], "deleted": [], "skipped": all_planned}

    backup_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    undo: list[Callable[[], None]] = []
    bkp_seq = 0

    def _backup_existing(target: pathlib.Path) -> tuple[pathlib.Path, int]:
        nonlocal bkp_seq
        bkp_seq += 1
        st = target.lstat()
        old_mode = stat.S_IMODE(st.st_mode) & 0o777
        bkp = backup_dir / f"bkp_{bkp_seq}"
        if not _copy_reg_file(target, bkp, mode=0o600):
            raise OSError(f"cannot back up {target}")
        return bkp, old_mode

    try:
        # 1. 先刪除（避免檔案變目錄時的 FileExistsError，也先清空可移除的目錄）
        for rel in plan.deleted:
            target = project / rel
            bkp, old_mode = _backup_existing(target)
            target.unlink()
            undo.append(lambda t=target, b=bkp, m=old_mode: _atomic_write_from_file(b, t, m))

        # 2. 移除即將改為一般檔案的空目錄（由深到淺）
        for rel_dir in plan.dirs_to_remove:
            d = project / rel_dir
            old_mode = stat.S_IMODE(d.lstat().st_mode) & 0o777
            d.rmdir()

            def _restore_dir(p: pathlib.Path = d, m: int = old_mode) -> None:
                p.mkdir(exist_ok=True)
                os.chmod(p, m)

            undo.append(_restore_dir)

        # 3. 寫入新增與修改的檔案（先補齊缺的父目錄並記下回滾動作）
        modified_set = set(plan.modified)
        for rel in sorted(plan.added + plan.modified):
            dst = project / rel
            src = snap.root / rel
            missing_dirs: list[pathlib.Path] = []
            cur = dst.parent
            while cur != project:
                if cur.is_symlink():
                    raise OSError(f"unexpected symlink ancestor: {cur}")
                if cur.exists():
                    break
                missing_dirs.append(cur)
                cur = cur.parent
            for md in reversed(missing_dirs):
                md.mkdir()
                undo.append(lambda p=md: p.rmdir())

            if rel in modified_set:
                bkp, old_mode = _backup_existing(dst)
                _atomic_write_from_file(src, dst, snap.modes.get(rel))
                undo.append(lambda t=dst, b=bkp, m=old_mode: _atomic_write_from_file(b, t, m))
            else:
                _atomic_write_from_file(src, dst, snap.modes.get(rel))
                undo.append(lambda t=dst: t.unlink(missing_ok=True))

        return {
            "added": list(plan.added),
            "modified": list(plan.modified),
            "deleted": list(plan.deleted),
            "skipped": list(plan.skipped),
        }
    except Exception:  # noqa: BLE001
        for fn in reversed(undo):
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass
        all_planned = sorted(set(plan.skipped) | set(plan.added) | set(plan.modified) | set(plan.deleted))
        return {"added": [], "modified": [], "deleted": [], "skipped": all_planned}
    finally:
        _rmtree_force(backup_dir)


def _write_back(project: pathlib.Path, ws: pathlib.Path | _Snapshot, protected: set[str], *,
                _plan: _WritePlan | None = None,
                _backup_root: pathlib.Path | None = None) -> dict[str, list[str]]:
    tmp_dir: pathlib.Path | None = None
    try:
        if isinstance(ws, _Snapshot):
            snap = ws
        else:
            tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="vsnap-"))
            snap = _snapshot_workspace(ws, tmp_dir / "s")
        plan = _plan if _plan is not None else _plan_write_back(project, snap, protected)
        bkp_base = _backup_root if _backup_root is not None else pathlib.Path(tempfile.mkdtemp(prefix="vbkp-"))
        try:
            return _apply_write_plan(project, snap, plan, bkp_base / f"bkp-{secrets.token_hex(6)}")
        finally:
            if _backup_root is None:
                _rmtree_force(bkp_base)
    except Exception:  # noqa: BLE001
        return {"added": [], "modified": [], "deleted": [], "skipped": []}
    finally:
        if tmp_dir is not None:
            _rmtree_force(tmp_dir)


def _restore_test_file(work: pathlib.Path, rel: str, want: bytes) -> None:
    """在驗收副本 work 裡強制還原單一原測試檔（處理路徑上被換成檔案、目錄、symlink 或唯讀權限的情況）。"""
    p = work
    for part in pathlib.PurePosixPath(rel).parts[:-1]:
        p = p / part
        try:
            st = p.lstat()
        except FileNotFoundError:
            p.mkdir(mode=0o700)
            continue
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            p.unlink()
            p.mkdir(mode=0o700)
        else:
            try:
                os.chmod(p, 0o700)
            except OSError:
                pass
    f = work / rel
    try:
        st_f = f.lstat()
    except FileNotFoundError:
        st_f = None
    if st_f is not None:
        if stat.S_ISDIR(st_f.st_mode) and not stat.S_ISLNK(st_f.st_mode):
            _rmtree_force(f)
        else:
            f.unlink()
    f.write_bytes(want)
    os.chmod(f, 0o600)


def _populate_acceptance_work(work: pathlib.Path, originals: dict[str, bytes], snap: _Snapshot,
                              project: pathlib.Path | None, plan: _WritePlan | None) -> None:
    """組裝驗收目錄 work：完全不含 symlink，且與實際會寫回專案的檔案集合一致，最後覆寫原測試檔。"""
    work.mkdir(parents=True, exist_ok=True)
    os.chmod(work, 0o700)
    protected = set(originals)
    if project is not None and plan is not None:
        deleted_set = set(plan.deleted)
        written_set = set(plan.added) | set(plan.modified)
        # 1. 保留專案中未被刪除、未被改寫、且非測試檔的一般檔案（包含因安全原因跳過刪除者）
        for rel in sorted(plan.before_files - deleted_set - written_set - protected):
            _copy_reg_file(project / rel, work / rel, mode=0o600)
        # 2. 放入計畫中真正會寫回的新增／修改檔案（跳過不安全而不會寫回的檔案）
        for rel in sorted(written_set):
            _copy_reg_file(snap.root / rel, work / rel, mode=0o600)
    else:
        for rel in sorted(snap.files):
            if rel not in protected:
                _copy_reg_file(snap.root / rel, work / rel, mode=0o600)
    # 3. 最後以開始時的原始測試檔覆寫
    for rel, want in sorted(originals.items()):
        _restore_test_file(work, rel, want)


def _parse_runner_output(raw: bytes, nonce: str) -> tuple[dict[str, Any] | None, str | None]:
    """嚴格驗證並解析 runner 經獨立管線送回的結果；任何格式異常皆回失敗。"""
    if not raw:
        return None, "runner_no_output"
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return None, "runner_bad_output"
    lines = [ln for ln in text.splitlines() if ln]
    if len(lines) != 2 or not hmac.compare_digest(lines[0], nonce):
        return None, "runner_bad_output"
    try:
        data = json.loads(lines[1])
    except (ValueError, TypeError):
        return None, "runner_bad_output"
    if not isinstance(data, dict):
        return None, "runner_bad_output"
    for k in _RESULT_KEYS:
        v = data.get(k)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            return None, "runner_bad_output"
    le = data.get("load_error")
    fp = data.get("first_problem")
    if le is not None and not isinstance(le, str):
        return None, "runner_bad_output"
    if fp is not None and not isinstance(fp, str):
        return None, "runner_bad_output"
    return data, None


def acceptance(originals: dict[str, bytes], ws: pathlib.Path, timeout_s: float = ACC_TIMEOUT_S, *,
               _snapshot: _Snapshot | None = None,
               _project: pathlib.Path | None = None,
               _plan: _WritePlan | None = None) -> dict:
    """在工作區快照的**潔淨副本**裡、把開始時的測試檔還原之後跑它們。驗收自己壞掉＝沒過（不是通過）。"""
    tests = sorted(originals)
    base: dict[str, Any] = {"accept": False, "tests": tests, "passed": None, "run": None,
                            "tests_tampered": [], "status": None, "first_problem": None}
    if not tests:
        return {**base, "status": "no_tests"}
    deadline = time.monotonic() + max(0.0, timeout_s)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vrun-"))
    os.chmod(tmp, 0o700)
    try:
        snap = _snapshot if _snapshot is not None else _snapshot_workspace(ws, tmp / "snap")
        base["tests_tampered"] = _detect_tampered(snap, originals)
        if deadline - time.monotonic() <= 0:
            return {**base, "status": "timeout"}
        work = tmp / "w"
        _populate_acceptance_work(work, originals, snap, _project, _plan)
        home = tmp / "h"
        home.mkdir(mode=0o700)
        runner_dir = tmp / "r"
        runner_dir.mkdir(mode=0o700)
        runner_script = runner_dir / "runner.py"
        runner_script.write_text(_UNITTEST_RUNNER, encoding="utf-8")
        os.chmod(runner_script, 0o600)

        by_dir: dict[str, list[tuple[str, pathlib.Path]]] = {}
        for rel in tests:
            d, _, name = rel.rpartition("/")
            by_dir.setdefault(d, []).append((name[:-3], (work / rel).resolve()))

        agg = {k: 0 for k in _RESULT_KEYS}
        first: str | None = None
        for idx, (d, mod_entries) in enumerate(sorted(by_dir.items())):
            left = deadline - time.monotonic()
            if left <= 0:
                return {**base, "status": "timeout"}
            run_cwd = (work / d if d else work).resolve()
            nonce = secrets.token_hex(16)
            r_fd, w_fd = os.pipe()
            out_log = runner_dir / f"out_{idx}.log"
            err_log = runner_dir / f"err_{idx}.log"
            cfg_file = runner_dir / f"cfg_{idx}.json"
            cfg_data = json.dumps({
                "w_fd": w_fd,
                "nonce": nonce,
                "cwd": str(run_cwd),
                "tests": [[m, str(p)] for m, p in mod_entries],
            }).encode("utf-8")
            cfg_file.write_bytes(cfg_data)
            os.chmod(cfg_file, 0o600)

            proc: subprocess.Popen | None = None
            timed_out = False
            raw_res = b""
            rc: int | None = None
            try:
                with cfg_file.open("rb") as cfg_in, out_log.open("wb") as out_f, err_log.open("wb") as err_f:
                    try:
                        cfg_file.unlink(missing_ok=True)
                    except OSError:
                        pass
                    proc = subprocess.Popen(
                        [sys.executable, "-I", "-B", str(runner_script)],
                        cwd=str(run_cwd),
                        env=_clean_env(home),
                        stdin=cfg_in,
                        stdout=out_f,
                        stderr=err_f,
                        pass_fds=(w_fd,),
                        start_new_session=True,
                    )
                os.close(w_fd)
                w_fd = -1
                wait_left = deadline - time.monotonic()
                if wait_left <= 0:
                    timed_out = True
                else:
                    try:
                        rc = proc.wait(timeout=wait_left)
                    except subprocess.TimeoutExpired:
                        timed_out = True
            finally:
                if w_fd >= 0:
                    try:
                        os.close(w_fd)
                    except OSError:
                        pass
                if proc is not None:
                    _kill_group_and_wait(proc)
                raw_res = _read_all_fd(r_fd)

            if timed_out:
                return {**base, "status": "timeout"}
            if rc != 0:
                out_tail = ""
                try:
                    out_tail = (out_log.read_bytes() + b"\n" + err_log.read_bytes()).decode("utf-8", "replace")[-800:]
                except OSError:
                    pass
                return {**base, "status": "runner_no_output" if not raw_res else "runner_bad_output",
                        "first_problem": out_tail or None}
            r, err_status = _parse_runner_output(raw_res, nonce)
            if err_status is not None or r is None:
                out_tail = ""
                try:
                    out_tail = out_log.read_bytes().decode("utf-8", "replace")[-800:]
                except OSError:
                    pass
                return {**base, "status": err_status or "runner_bad_output", "first_problem": out_tail or None}
            if r["load_error"]:
                return {**base, "status": "load_error", "first_problem": r["load_error"], "run": agg["run"]}
            for k in _RESULT_KEYS:
                agg[k] += r[k]
            first = first or r["first_problem"]

        bad = agg["failures"] + agg["errors"] + agg["unexpected_successes"]
        return {**base, "status": "ok", "run": agg["run"], "passed": agg["run"] - bad - agg["skipped"],
                "accept": agg["run"] > 0 and bad == 0 and agg["skipped"] == 0, "first_problem": first}
    except Exception as e:  # noqa: BLE001 — 單次驗收任何非預期錯誤皆安全判為未通過
        return {**base, "status": "acceptance_error", "first_problem": f"{type(e).__name__}: {e}"[-800:]}
    finally:
        _rmtree_force(tmp)


def deliver_index(accs: list[dict]) -> int:
    """交哪一次：第一個驗收通過的；都沒過就交原件測試過最多的（同分取最後一次）。＝redo.py `_policy_deliver`。"""
    for i, a in enumerate(accs):
        if a["accept"]:
            return i
    return max(range(len(accs)), key=lambda i: (accs[i]["passed"] or 0, i))


def run(project: pathlib.Path, build: Callable[[str, pathlib.Path], Launch], prompt: str, *,
        max_attempts: int = 3, attempt_timeout_s: float = 600.0, budget_s: float = 1800.0,
        min_attempt_s: float = 60.0, log: Callable[[str], None] | None = None) -> dict:
    project = project.resolve()
    say = log or (lambda m: None)
    originals = {rel: (project / rel).read_bytes() for rel in find_tests(project)}
    protected = set(originals)
    if not originals:
        max_attempts = 1
        attempt_timeout_s = budget_s
    run_dir = work_root() / f"restart-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{secrets.token_hex(3)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    attempts: list[dict] = []
    snaps: list[_Snapshot | None] = []
    spent = 0.0
    t0 = time.monotonic()
    reserve = min(ACC_TIMEOUT_S, budget_s / 10) if originals else 0.0   # 每次嘗試後留給驗收的時間
    while len(attempts) < max_attempts:
        remaining = budget_s - (time.monotonic() - t0) - reserve
        if attempts and remaining < min_attempt_s:
            break
        remaining = max(remaining, min(0.1, budget_s))
        k = len(attempts) + 1
        attempt_dir = run_dir / f"attempt_{k}"
        ws = attempt_dir / "w"
        shutil.copytree(project, ws, symlinks=True, ignore=shutil.ignore_patterns(*COPY_SKIP))
        launch = build(prompt, ws)
        say(f"attempt {k} of {max_attempts} (up to {min(attempt_timeout_s, remaining):.0f}s)")
        try:
            r = run_agent(launch, workspace=ws, timeout_s=min(attempt_timeout_s, remaining),
                          log_dir=attempt_dir / "logs")
        finally:
            if launch.cleanup:
                launch.cleanup()
        spent += r["wall_ms"] / 1000.0

        snap: _Snapshot | None = None
        plan: _WritePlan | None = None
        try:
            snap_dir = attempt_dir / f"snap-{secrets.token_hex(8)}"
            snap = _snapshot_workspace(ws, snap_dir)
            plan = _plan_write_back(project, snap, protected)
            if originals:
                acc_t = max(0.0, min(ACC_TIMEOUT_S, budget_s - (time.monotonic() - t0)))
                acc = acceptance(originals, ws, acc_t, _snapshot=snap, _project=project, _plan=plan)
            else:
                acc = {"accept": None, "passed": None, "status": "no_tests",
                       "tests_tampered": [], "run": None}
        except Exception as e:  # noqa: BLE001 — 單次評估失敗安全判為未通過，不影響其他嘗試
            acc = {"accept": False if originals else None, "passed": None, "run": None,
                   "status": "acceptance_error", "tests_tampered": [],
                   "first_problem": f"{type(e).__name__}: {e}"[-800:]}

        attempts.append({"attempt": k, "accept": acc["accept"], "passed": acc["passed"], "run": acc["run"],
                         "status": acc["status"], "tests_tampered": acc["tests_tampered"],
                         "rc": r["rc"], "timed_out": r["timed_out"], "wall_s": round(r["wall_ms"] / 1000.0, 1),
                         "spawn_error": r["spawn_error"], "workspace": str(ws)})
        snaps.append(snap)
        say(f"attempt {k}: " + ("no tests to run" if not originals else
                                f"tests {'PASS' if acc['accept'] else 'FAIL'} ({acc['passed']}/{acc['run']})"))
        if not originals or acc["accept"]:
            break
    d = deliver_index([{"accept": bool(a["accept"]), "passed": a["passed"]} for a in attempts])
    if snaps[d] is not None:
        changed = _write_back(project, snaps[d], protected, _backup_root=run_dir)
    else:
        changed = {"added": [], "modified": [], "deleted": [], "skipped": []}
    res = {"mode": "restart", "project": str(project), "tests": sorted(originals), "max_attempts": max_attempts,
           "accepted": None if not originals else bool(attempts[d]["accept"]),
           "delivered_attempt": d + 1, "attempts": attempts, "changed": changed,
           "agent_wall_s": round(spent, 1), "total_wall_s": round(time.monotonic() - t0, 1),
           "run_dir": str(run_dir)}
    (run_dir / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def summary(res: dict) -> str:
    n = len(res["attempts"])
    ch = res["changed"]
    files = f"{len(ch['added'])} added, {len(ch['modified'])} modified, {len(ch['deleted'])} deleted"
    if res["accepted"] is None:
        head = (f"[vacant] ran once; no executable acceptance (no *_test.py / test_*.py in the project), "
                f"so nothing was checked. {files}.")
    elif res["accepted"]:
        head = (f"[vacant] the project's tests pass on attempt {res['delivered_attempt']} "
                f"(up to {res.get('max_attempts', n)} allowed); delivered that attempt. {files}.")
    else:
        a = res["attempts"][res["delivered_attempt"] - 1]
        head = (f"[vacant] not all tests pass after {n} attempt(s); delivered attempt "
                f"{res['delivered_attempt']} ({a['passed'] or 0}/{a['run'] or 0} tests). {files}.")
    if ch.get("skipped"):
        head += (f"\n  not written back ({len(ch['skipped'])}): unsafe path (symlink, conflict, or unreadable) "
                 f"({', '.join(ch['skipped'][:5])}{' …' if len(ch['skipped']) > 5 else ''}); see the attempt workspace.")
    tam = sorted({t for a in res["attempts"] for t in a["tests_tampered"]})
    if tam:
        head += f"\n  the agent edited test files ({', '.join(tam)}); checked against the originals, not written back."
    return head + f"\n  attempts and logs: {res['run_dir']}"
