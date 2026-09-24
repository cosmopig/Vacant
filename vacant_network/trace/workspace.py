"""workspace — **每一步前後的工作區長什麼樣**：增量索引、差異、內容定址的版本庫。

這支在架構裡承重什麼（`ops/accountability/LOOP.md` §二-1、§二-2）：

追緝要回答「是哪一步把錯的內容寫進去的」。agent 自己回報的寫入（`Write(path)`）只涵蓋
它**宣告**要寫的檔案；殼層指令（`python gen.py > report.md`、`sed -i`、`git checkout`）
改了什麼，agent 平台不會告訴我們。所以每一次工具呼叫前後，Vacant **自己**看一次工作區：

    pre  = scan(ws, cache)           ← 工具呼叫之前
    post = scan(ws, pre)             ← 工具呼叫之後
    diff(pre, post)                  ← 這一步改了哪些檔（新增／修改／刪除）

每個看到的版本都以 sha256 存進版本庫（`objects/`，與 `intake.artifact.Store` 同一格式），
所以任何一步之前或之後的工作區都能**重建**——追緝在重建出來的狀態上重跑檢查
（「這一步之前過、之後不過」），那才是可重驗的證據，不是任何人的意見。

索引是增量的：大小與 mtime 都沒變的檔案沿用上一次的雜湊，只重算有變的。

## 誠實邊界（改碼請保留）

1. **mtime＋大小相同就視為沒變**。在同一個 mtime 刻度內改寫、而且大小不變的檔案看不出來；
   `touch -r` 之類刻意還原 mtime 的寫入也看不出來。要保證逐位元，傳 `full=True`（慢）。
2. 這是 Vacant 在**掛鉤觸發的那一刻**看到的；兩次看之間發生的事（背景行程、使用者自己的編輯、
   agent 繞過掛鉤的寫入）歸不到任何一步——`recorder.py` 把它們記成「沒有紀錄的改動」（究責缺口）。
3. 不跟隨符號連結；連結本身（檔案或目錄）以 `link:<目標>` 記錄。超過 `MAX_BLOB` 的檔案只記雜湊
   不存內容（之後無法重建那一個檔，追緝會標成不可重驗）。
4. 只讀**一般檔案**：FIFO、裝置、socket 不讀（讀 FIFO 會卡住每一次掛鉤——2026-09-24 審查 recorder#0）。
5. 看起來像憑證的檔（`SECRET_PATTERNS`：`.env`、私鑰、`auth.json`…）**只記雜湊、不存內容**
   （`secret:<sha256>`）：改了看得出來，但版本庫裡沒有它（審查 recorder#2）。版本庫本身 0700／0600。
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import stat
from typing import Any


#: 不進索引的目錄名（完整路徑元件比對）。`.git` 的內容由 git 自己追；Vacant 的狀態目錄另外排除。
SKIP_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
                       ".mypy_cache", ".ruff_cache", ".tox", ".cache"})
MAX_BLOB = 8 * 1024 * 1024
MAX_FILES = 50_000
#: 只記雜湊、不存內容的檔（樣式錨定在工作區根，`**/` 開頭＝任何深度）
SECRET_PATTERNS = ("**/.env", "**/.env.*", "**/*.pem", "**/*.key", "**/*.p12", "**/*.pfx",
                   "**/id_rsa*", "**/id_ed25519*", "**/id_ecdsa*", "**/id_dsa*", "**/auth.json",
                   "**/credentials", "**/credentials.*", "**/.netrc", "**/.npmrc", "**/.pypirc",
                   "**/.git-credentials", "**/*secret*.json", "**/.ssh/**", ".env", ".env.*",
                   "auth.json", "credentials", "credentials.*", ".netrc", ".npmrc", ".pypirc")


_SECRET_RX: list = []


def is_secret(rel: str) -> bool:
    if not _SECRET_RX:                       # 編一次（每個檔都重編曾經佔掉冷掃描的三分之一）
        from ..intake.artifact import glob_to_regex
        _SECRET_RX.extend(glob_to_regex(x) for x in SECRET_PATTERNS)
    return any(rx.match(rel) for rx in _SECRET_RX)


class ScanTimeout(Exception):
    """掃描超過期限（掛鉤裡的掃描有上限：掛鉤被 agent 砍掉＝靜默略過）。"""


@dataclasses.dataclass(frozen=True)
class Entry:
    sha256: str          # 內容 sha256；連結是 "link:<目標>"；太大沒存的是 "big:<sha256>"
    size: int
    mtime_ns: int
    exec: bool = False

    def to_json(self) -> list[Any]:
        return [self.sha256, self.size, self.mtime_ns, self.exec]

    @classmethod
    def from_json(cls, v: list[Any]) -> "Entry":
        return cls(str(v[0]), int(v[1]), int(v[2]), bool(v[3]) if len(v) > 3 else False)


Index = dict[str, Entry]


def _sha_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Blobs:
    """內容定址的版本庫：`objects/<前兩碼>/<sha256>`（與 `intake.artifact.Store` 相容）。"""

    def __init__(self, root: pathlib.Path):
        self.root = pathlib.Path(root)

    def path(self, sha: str) -> pathlib.Path:
        return self.root / sha[:2] / sha

    def has(self, sha: str) -> bool:
        return self.path(sha).is_file()

    def put_bytes(self, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        dst = self.path(sha)
        if not dst.is_file():
            for d in (self.root, dst.parent):
                d.mkdir(parents=True, exist_ok=True, mode=0o700)
                try:
                    os.chmod(d, 0o700)
                except OSError:
                    pass
            # 不 fsync：內容定址、讀的時候驗雜湊（`get`），當機留下的壞檔會被當成「重建不了」，
            # 不會被當成內容（fsync 曾經佔掉冷掃描的三分之一）
            tmp = dst.with_name(f"{dst.name}.tmp.{os.getpid()}")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                os.replace(tmp, dst)
            finally:
                if tmp.exists():
                    tmp.unlink()
        return sha

    def put_file(self, p: pathlib.Path, sha: str | None = None) -> str:
        if sha and self.has(sha):
            return sha
        return self.put_bytes(p.read_bytes())

    def get(self, sha: str) -> bytes:
        data = self.path(sha).read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            raise ValueError(f"blob {sha[:12]}… was modified in the store")
        return data


def scan(root: str | os.PathLike, prev: Index | None = None, *,
         skip: set[pathlib.Path] | frozenset[pathlib.Path] = frozenset(),
         blobs: Blobs | None = None, full: bool = False,
         deadline: float | None = None, prev_stored: bool = False) -> Index:
    """掃一次工作區。`prev` 的項目若大小與 mtime 都相同就沿用雜湊（見誠實邊界 1）。
    給 `blobs` ⇒ 每個**新看到的版本**都存進版本庫；沿用的版本也確認在庫裡——除非
    `prev_stored`（`prev` 是帶著同一個版本庫掃出來的：它的每個版本在那時都已經存了；
    逐檔確認曾經佔掉大專案每次掛鉤的三分之一）。`deadline`（`time.monotonic()` 的時刻）
    過了 ⇒ `ScanTimeout`。"""
    import time
    base = pathlib.Path(root).resolve()
    base_s = str(base)
    prev = prev or {}
    out: Index = {}
    skip_r = {os.path.realpath(s) for s in skip}
    # 熱迴圈只用字串路徑（pathlib 的物件開銷曾經佔掉大專案每次掃描的四成）
    for dirpath, dirs, files in os.walk(base_s, followlinks=False):
        if deadline is not None and time.monotonic() > deadline:
            raise ScanTimeout(f"scan passed its deadline after {len(out)} files")
        rel_dir = os.path.relpath(dirpath, base_s)
        prefix = "" if rel_dir == "." else rel_dir.replace(os.sep, "/") + "/"
        keep = []
        for x in sorted(dirs):
            full_x = os.path.join(dirpath, x)
            if x in SKIP_DIRS or os.path.realpath(full_x) in skip_r:
                continue
            if os.path.islink(full_x):
                # 目錄的符號連結：記連結本身，不進去（進去會重複、甚至繞圈）
                try:
                    out[prefix + x] = Entry("link:" + os.readlink(full_x), 0,
                                            os.lstat(full_x).st_mtime_ns)
                except OSError:
                    pass
                continue
            keep.append(x)
        dirs[:] = keep
        for i, name in enumerate(sorted(files)):
            if deadline is not None and i % 256 == 255 and time.monotonic() > deadline:
                # 一個目錄裡就有幾萬個檔：只在目錄之間看時限不夠
                raise ScanTimeout(f"scan passed its deadline after {len(out)} files")
            full_p = os.path.join(dirpath, name)
            rel = prefix + name
            try:
                st = os.lstat(full_p)
                if stat.S_ISLNK(st.st_mode):
                    out[rel] = Entry("link:" + os.readlink(full_p), 0, st.st_mtime_ns)
                    continue
                if not stat.S_ISREG(st.st_mode):
                    continue        # FIFO／裝置／socket：不讀（誠實邊界 4）
                x_bit = bool(st.st_mode & 0o100)
                old = prev.get(rel)
                if not full and old is not None and old.size == st.st_size \
                        and old.mtime_ns == st.st_mtime_ns and old.exec == x_bit:
                    out[rel] = old
                    if blobs is not None and not prev_stored and st.st_size <= MAX_BLOB \
                            and ":" not in old.sha256 and not blobs.has(old.sha256):
                        blobs.put_file(pathlib.Path(full_p), old.sha256)
                    continue
                if is_secret(rel):
                    out[rel] = Entry("secret:" + _sha_file(pathlib.Path(full_p)), st.st_size,
                                     st.st_mtime_ns, x_bit)
                    continue
                if st.st_size > MAX_BLOB:
                    out[rel] = Entry("big:" + _sha_file(pathlib.Path(full_p)), st.st_size,
                                     st.st_mtime_ns, x_bit)
                    continue
                with open(full_p, "rb") as f:
                    data = f.read()
                sha = blobs.put_bytes(data) if blobs is not None \
                    else hashlib.sha256(data).hexdigest()
                out[rel] = Entry(sha, st.st_size, st.st_mtime_ns, x_bit)
            except OSError:
                continue            # 掃描中途被刪掉的檔：這一次就是不在
            if len(out) > MAX_FILES:
                raise ValueError(f"workspace has more than {MAX_FILES} files; "
                                 f"narrow it (trace skips {sorted(SKIP_DIRS)})")
    return out


@dataclasses.dataclass
class Change:
    path: str
    before: str | None       # 之前的內容 sha256（None＝不存在）
    after: str | None        # 之後的內容 sha256（None＝刪除）

    @property
    def kind(self) -> str:
        return "added" if self.before is None else "deleted" if self.after is None else "modified"

    def to_json(self) -> dict[str, Any]:
        return {"path": self.path, "before": self.before, "after": self.after, "kind": self.kind}


def diff(before: Index, after: Index) -> list[Change]:
    out = []
    for path in sorted(set(before) | set(after)):
        a, b = before.get(path), after.get(path)
        sa = a.sha256 if a else None
        sb = b.sha256 if b else None
        if sa != sb or (a and b and a.exec != b.exec):
            out.append(Change(path, sa, sb))
    return out


def index_root(idx: Index) -> str:
    """整個索引的雜湊（路徑＋內容＋可執行位元），與 `vrun.wshash` 的精神相同但包含連結。"""
    rows = sorted([p, e.sha256, e.exec] for p, e in idx.items())
    return hashlib.sha256(json.dumps(rows, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def dump(idx: Index) -> bytes:
    return json.dumps({p: e.to_json() for p, e in sorted(idx.items())},
                      separators=(",", ":"), ensure_ascii=False).encode()


def load(data: bytes | str) -> Index:
    raw = json.loads(data)
    return {str(p): Entry.from_json(v) for p, v in raw.items()}


def materialize(idx: Index, blobs: Blobs, dest: str | os.PathLike) -> list[str]:
    """把一個索引重建成目錄（追緝重跑檢查用）。回傳重建不了的路徑（太大沒存、版本庫缺）。"""
    d = pathlib.Path(dest)
    d.mkdir(parents=True, exist_ok=True)
    missing = []
    for rel, e in sorted(idx.items()):
        out = d / rel
        if ".." in pathlib.PurePosixPath(rel).parts:
            missing.append(rel)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        if e.sha256.startswith("link:"):
            try:
                os.symlink(e.sha256[5:], out)
            except OSError:
                missing.append(rel)
            continue
        if e.sha256.startswith(("big:", "secret:")) or not blobs.has(e.sha256):
            missing.append(rel)
            continue
        out.write_bytes(blobs.get(e.sha256))
        os.chmod(out, 0o755 if e.exec else 0o644)
    return missing
