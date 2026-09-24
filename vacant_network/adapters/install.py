"""install — **加法式、可逆、只動自己那幾條**的安裝器。

這支在架構裡承重什麼（`DECISION_20260919_DEFAULT_ON_INSTALL.md` 的「裝一次就有」＋
2026-09-24 對 `possess.py` 的兩個實測缺陷的修正）：

1. `possess.uninstall` 是**整檔還原**備份 ⇒ 安裝後使用者自己改的設定被安靜地丟掉，
   報告還寫 `ok: True`（vrun-integration 對照 §2.0，實跑重現）。
2. per-run 的 `CLAUDE_CONFIG_DIR`／`CODEX_HOME`／`PI_CODING_AGENT_DIR` 搬家 ⇒ 使用者的
   MCP、登入、外掛那一跑全部不見——包裝後的 agent 已經不是原本那個 agent
   （報告 §05「相容性不能只證明有呼叫到模型」）。

這裡的每一個動作都是**鍵層級**的，並且記在 `$VACANT_HOME/adapters/install.json`：

- `file`：建立一個 Vacant 自己的檔（技能、外掛、extension）。解除安裝時**只有內容仍是
  我們寫的那一份**才刪；被改過就留著並回報。
- `json_hooks`：在 JSON 設定檔的 `hooks.<Event>` 陣列**附加**一筆帶標記的項目。
  解除安裝時只移除帶標記的項目，其他（含安裝後才加的）原封不動。
- `toml_block`：在 TOML 檔尾附加一段有頭尾標記的區塊；寫入前用 `tomllib` 驗過整份檔，
  解除安裝只刪那一段。

第一次動到一個既有檔之前一律先備份（`backups/`，含 sha256），但**還原不用備份**——
備份是給人救急的，不是解除安裝的機制。

## 誠實邊界

1. 這些都是 `$HOME` 底下的普通檔；agent 自己的寫檔工具刪得掉（2026-09-20 實測）。
   `vacant adapters doctor` 會重新量「還在不在」，量到的才算數——裝過不等於在。
2. 管理層（`/etc/claude-code`、`/etc/codex`、`/etc/opencode`）需要 root，這裡不碰。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import shutil
import stat
import tomllib
from typing import Any

from ..atomic import atomic_write_text

MARKER = "vacant-intake"
BLOCK_BEGIN = f"# >>> {MARKER} >>> (managed by `vacant install`; remove with `vacant uninstall`)"
BLOCK_END = f"# <<< {MARKER} <<<"


def state_root() -> pathlib.Path:
    base = os.environ.get("VACANT_HOME")
    root = pathlib.Path(base).expanduser() if base else pathlib.Path.home() / ".vacant"
    return root / "adapters"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_preserving(path: pathlib.Path, text: str) -> None:
    """原子寫入，但**寫穿符號連結、保留原本的權限位元**。

    `os.replace` 直接換掉路徑：`~/.codex/config.toml` 若是指向 dotfiles 的連結，會被換成
    一個普通檔（連結安靜地斷掉）；新檔依 umask 建立，0600 的設定檔（裡面可能有 API key）
    變成 0644（2026-09-24 對抗審查重現）。
    """
    target = pathlib.Path(os.path.realpath(path)) if path.is_symlink() else path
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else None
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, text)
    if mode is not None:
        os.chmod(target, mode)


class Manifest:
    def __init__(self, path: pathlib.Path | None = None):
        self.path = path or (state_root() / "install.json")
        self.data: dict[str, Any] = {"agents": {}}
        if self.path.is_file():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def ops(self, agent: str) -> list[dict[str, Any]]:
        return list((self.data["agents"].get(agent) or {}).get("ops") or [])

    def record(self, agent: str, op: dict[str, Any]) -> None:
        a = self.data["agents"].setdefault(agent, {"ops": [], "installed_at": _now()})
        # 同一個目標只記一次（重複安裝是冪等的）——但**備份與「是不是我們建的」要留第一次的**：
        # 第二次安裝時的「原檔」已經含有我們的掛鉤，拿它當備份，解除安裝就還原不回使用者的位元組。
        key = (op["op"], op["path"], op.get("event"))
        prev = [o for o in a["ops"] if (o["op"], o["path"], o.get("event")) == key]
        if prev:
            op["backup"] = prev[0].get("backup")
            op["created"] = prev[0].get("created")
        a["ops"] = [o for o in a["ops"] if (o["op"], o["path"], o.get("event")) != key]
        a["ops"].append(op)

    def forget(self, agent: str, keep: list[dict[str, Any]] | None = None) -> None:
        """`keep`：撤銷失敗、要留著下次再試的步驟。"""
        if keep:
            self.data["agents"][agent] = {**self.data["agents"].get(agent, {}), "ops": keep}
        else:
            self.data["agents"].pop(agent, None)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.path, json.dumps(self.data, indent=2, ensure_ascii=False) + "\n")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def backup(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    b = path.read_bytes()
    d = state_root() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    dst = d / f"{path.name}.{_sha(b)[:12]}.bak"
    if not dst.exists():
        shutil.copy2(path, dst)
    return str(dst)


# ── op: file ────────────────────────────────────────────────────────

def put_file(m: Manifest, agent: str, path: pathlib.Path, content: str,
             *, mode: int | None = None) -> dict[str, Any]:
    data = content.encode("utf-8")
    existed = path.exists()
    bak = backup(path) if existed else None
    path.parent.mkdir(parents=True, exist_ok=True)
    write_preserving(path, content)
    if mode is not None:
        os.chmod(path, mode)
    op = {"op": "file", "path": str(path), "sha256": _sha(data), "created": not existed,
          "backup": bak}
    m.record(agent, op)
    return op


def undo_file(op: dict[str, Any]) -> str:
    p = pathlib.Path(op["path"])
    if not p.exists():
        return "already gone"
    if _sha(p.read_bytes()) != op["sha256"]:
        return "kept: modified since install"
    bak = pathlib.Path(op["backup"]) if op.get("backup") else None
    if not op.get("created") and bak is not None and bak.is_file():
        shutil.copyfile(bak, p)            # 安裝前就有這個檔（使用者的）⇒ 還原，不是刪掉
        return "original file restored"
    p.unlink()
    # 清掉我們建的空目錄（只往上一層：技能目錄 `…/skills/vacant/`）
    try:
        if p.parent.name in ("vacant",) and not any(p.parent.iterdir()):
            p.parent.rmdir()
    except OSError:
        pass
    return "removed"


# ── op: json_hooks ──────────────────────────────────────────────────

def _load_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def _is_ours(entry: Any) -> bool:
    return MARKER in json.dumps(entry, ensure_ascii=False)


def add_json_hooks(m: Manifest, agent: str, path: pathlib.Path,
                   entries: dict[str, list[dict[str, Any]]],
                   *, root_key: str | None = "hooks") -> dict[str, Any]:
    """`entries = {Event: [entry, ...]}`；每個 entry 的 JSON 裡必須含 `MARKER`。"""
    for ev, lst in entries.items():
        for e in lst:
            if not _is_ours(e):
                raise ValueError(f"hook entry for {ev} lacks the {MARKER} marker")
    existed = path.exists()
    bak = backup(path) if existed else None
    data = _load_json(path)
    hooks = data.setdefault(root_key, {}) if root_key else data
    if not isinstance(hooks, dict):
        raise ValueError(f"{path}: `{root_key}` is not an object")
    for ev, lst in entries.items():
        cur = hooks.setdefault(ev, [])
        if not isinstance(cur, list):
            raise ValueError(f"{path}: hooks.{ev} is not a list")
        cur[:] = [e for e in cur if not _is_ours(e)] + lst
    path.parent.mkdir(parents=True, exist_ok=True)
    write_preserving(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    op = {"op": "json_hooks", "path": str(path), "events": sorted(entries),
          "root_key": root_key, "created": not existed, "backup": bak}
    m.record(agent, op)
    return op


def undo_json_hooks(op: dict[str, Any]) -> str:
    p = pathlib.Path(op["path"])
    if not p.exists():
        return "already gone"
    data = _load_json(p)
    rk = op.get("root_key")
    hooks = data.get(rk, {}) if rk else data
    removed = 0
    if isinstance(hooks, dict):
        for ev in list(hooks):
            lst = hooks[ev]
            if isinstance(lst, list):
                keep = [e for e in lst if not _is_ours(e)]
                removed += len(lst) - len(keep)
                if keep:
                    hooks[ev] = keep
                else:
                    del hooks[ev]
        if rk and not hooks:
            data.pop(rk, None)
    if op.get("created") and not data:
        p.unlink()
        return f"removed {removed} entr(ies); file was ours and is now empty → deleted"
    # 使用者在安裝之後沒動過其他內容 ⇒ 還原**原本的位元組**（排版、鍵順序、結尾換行都一樣）；
    # 動過 ⇒ 只移除我們那幾條，保留他的改動（排版會是 JSON 標準縮排）。
    bak = pathlib.Path(op["backup"]) if op.get("backup") else None
    if bak is not None and bak.is_file():
        try:
            orig = json.loads(bak.read_text(encoding="utf-8") or "{}")
            same = orig == data or (rk is not None and rk not in data
                                    and orig == {**data, rk: {}})
            if same:
                shutil.copyfile(bak, p)
                return f"removed {removed} entr(ies); original bytes restored"
        except ValueError:
            pass
    write_preserving(p, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return f"removed {removed} entr(ies); other content kept"


# ── op: toml_block ──────────────────────────────────────────────────

def strip_block(text: str) -> str:
    """移除我們的區塊。**開頭標記在、結尾標記不在 ⇒ 拒絕**（`ValueError`）：
    一路刪到檔尾會把使用者接在後面的表格一起刪掉，還回報「還原了原本的位元組」。"""
    out, skip = [], False
    for line in text.splitlines(keepends=True):
        if line.startswith(BLOCK_BEGIN.split(" (")[0]):
            skip = True
            continue
        if skip and line.startswith(BLOCK_END):
            skip = False
            continue
        if not skip:
            out.append(line)
    if skip:
        raise ValueError(f"the {MARKER} block's end marker is missing or was edited; "
                         f"refusing to guess where it ends (remove the block by hand)")
    return "".join(out)


def add_toml_block(m: Manifest, agent: str, path: pathlib.Path, block: str,
                   *, prepend: bool = False) -> dict[str, Any]:
    """`prepend=True`：放在檔案最前面（頂層鍵必須在任何 `[table]` 之前，否則會變成
    最後一個表格的鍵、被安靜地忽略——`vrun/possess.py` 記過的 TOML 表格範圍陷阱）。"""
    existed = path.exists()
    bak = backup(path) if existed else None
    base = strip_block(path.read_text(encoding="utf-8")) if existed else ""
    if base and not base.endswith("\n"):
        base += "\n"
    blk = f"{BLOCK_BEGIN}\n{block.rstrip()}\n{BLOCK_END}\n"
    new = (blk + base) if prepend else (base + blk)
    tomllib.loads(new)  # 整份檔要合法；不合法就在寫入前炸
    path.parent.mkdir(parents=True, exist_ok=True)
    write_preserving(path, new)
    op = {"op": "toml_block", "path": str(path), "created": not existed, "backup": bak,
          "prepend": prepend}
    m.record(agent, op)
    return op


def undo_toml_block(op: dict[str, Any]) -> str:
    p = pathlib.Path(op["path"])
    if not p.exists():
        return "already gone"
    new = strip_block(p.read_text(encoding="utf-8"))
    if op.get("created") and not new.strip():
        p.unlink()
        return "block removed; file was ours → deleted"
    bak = pathlib.Path(op["backup"]) if op.get("backup") else None
    if bak is not None and bak.is_file() and bak.read_text(encoding="utf-8").rstrip("\n") \
            == new.rstrip("\n"):
        shutil.copyfile(bak, p)      # 寫穿連結、保留目標的權限
        return "block removed; original bytes restored"
    write_preserving(p, new)
    return "block removed; other content kept"


UNDO = {"file": undo_file, "json_hooks": undo_json_hooks, "toml_block": undo_toml_block,
        "note": lambda op: "nothing to undo"}


def uninstall(m: Manifest, agent: str) -> list[dict[str, str]]:
    """撤銷一個 agent 的全部步驟。**失敗的步驟留在清單裡**，下次 `vacant uninstall`
    再試——忘掉它的話，掛鉤就永遠留在使用者的設定裡、而且沒有東西記得要移除它。"""
    out = []
    failed = []
    for op in reversed(m.ops(agent)):
        try:
            res = UNDO[op["op"]](op)
        except (OSError, ValueError, tomllib.TOMLDecodeError) as e:
            res = f"error: {e}"
            failed.append(op)
        out.append({"op": op["op"], "path": op["path"], "result": res})
    m.forget(agent, keep=list(reversed(failed)))
    return out
