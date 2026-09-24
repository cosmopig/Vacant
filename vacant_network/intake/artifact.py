"""artifact — **隔離區**：把候選成果凍結成內容定址的物件，之後只認雜湊。

這支在架構裡承重什麼（報告 §06「上傳到隔離區不等於公開」、§04「收件模式」）：

agent 的工作區是 agent 的。它交出來的東西先被**複製**進隔離區，每個檔案以 sha256
命名存放；驗證跑在隔離區**重新攤開的一份拷貝**上；放行時從隔離區拿**同一批位元組**
送到目的端，並且再算一次雜湊。所以：

- 驗證之後 agent 再改工作區，影響不到已凍結的候選版本（舊版 `publish.py` 驗完雜湊
  再從原路徑 `copyfile` 一次，中間那段 TOCTOU 在這裡不存在）。
- 「批准 A 之後換成 B」會在放行時被抓到：B 的雜湊不是被批准的那個。

`artifact_sha256` 只取決於 (路徑, 內容, 可執行位元)，與任務、時間、機器無關
⇒ 同一份成果不論從哪個 agent、哪條路徑交進來，都是同一個雜湊。

## 誠實邊界

1. 隔離區跟 agent 同一個 OS 帳號時，agent **寫得到**它。這裡做的是**竄改可偵測**：
   `materialize()` 與放行都逐檔重算，對不上就拒絕。要竄改不可能，收件端換帳號或換機器。
2. 符號連結與特殊檔**不複製**（一個指向工作區外的連結會把別的東西帶出去），
   列在 `skipped` 裡——被跳過的檔案不存在於候選成果中，驗證器看不到它們。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
from typing import Any

from ..atomic import atomic_write_bytes
from ..canonical import canonical_bytes

ARTIFACT_SCHEMA = "vacant-artifact/1"

#: 永遠不收進候選成果的目錄（版本控制與 Vacant 自己的狀態）。
ALWAYS_SKIP_DIRS = frozenset({".git", ".hg", ".svn", "__pycache__"})

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 500 * 1024 * 1024
MAX_FILES = 20000


class ArtifactError(RuntimeError):
    pass


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """`**` 跨目錄、`*`／`?` 不跨 `/`；不依賴 3.13 的 full_match。

    ⚠ **樣式錨定在成果的根目錄**，這點**不同於 gitignore**：`.env` 只配根目錄的 `.env`，
    任何深度要寫 `**/.env`（gitignore 裡沒有斜線的樣式會配任何深度）。開頭的 `/`
    等於錨定，所以 `/secrets.json` ＝ `secrets.json`（不會變成永遠配不到）。
    """
    pat = pattern.strip()
    while pat.startswith("./") or pat.startswith("/"):
        pat = pat[2:] if pat.startswith("./") else pat[1:]
    if pat in ("", "."):
        pat = "**"
    i, out = 0, []
    while i < len(pat):
        c = pat[i]
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    body = "".join(out)
    # 目錄樣式 `docs/` ⇒ 底下全部
    if pat.endswith("/"):
        body += ".*"
    return re.compile("^" + body + "$")


def matches(rel: str, patterns: list[str]) -> bool:
    return any(glob_to_regex(p).match(rel) for p in patterns)


def _sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def artifact_digest(files: list[dict[str, Any]]) -> str:
    rows = sorted([f["path"], f["sha256"], bool(f.get("exec"))] for f in files)
    return hashlib.sha256(canonical_bytes({"files": rows})).hexdigest()


def collect(workspace: str | pathlib.Path, include: list[str],
            exclude: list[str]) -> tuple[list[tuple[str, pathlib.Path]], list[dict[str, str]]]:
    """依 include／exclude 從工作區挑出檔案。回 `(選中的, 跳過的)`。不跟隨符號連結。"""
    ws = pathlib.Path(workspace).resolve()
    chosen: list[tuple[str, pathlib.Path]] = []
    skipped: list[dict[str, str]] = []
    for root, dirs, files in os.walk(ws, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in ALWAYS_SKIP_DIRS)
        rroot = pathlib.Path(root)
        # 目錄本身是符號連結 ⇒ os.walk 不會進去，但要記下來
        for d in list(dirs):
            dp = rroot / d
            if dp.is_symlink():
                rel = dp.relative_to(ws).as_posix()
                if matches(rel, include) or matches(rel + "/x", include):
                    skipped.append({"path": rel, "reason": "symlink (not followed)"})
                dirs.remove(d)
        for name in sorted(files):
            p = rroot / name
            rel = p.relative_to(ws).as_posix()
            if not matches(rel, include) or matches(rel, exclude):
                continue
            st = p.lstat()
            if stat.S_ISLNK(st.st_mode):
                skipped.append({"path": rel, "reason": "symlink (not followed)"})
                continue
            if not stat.S_ISREG(st.st_mode):
                skipped.append({"path": rel, "reason": "not a regular file"})
                continue
            chosen.append((rel, p))
    return chosen, skipped


class Store:
    """內容定址的物件庫＋候選成果清單。"""

    def __init__(self, root: str | pathlib.Path):
        self.root = pathlib.Path(root)
        self.objects = self.root / "objects"
        self.candidates = self.root / "candidates"

    def object_path(self, sha: str) -> pathlib.Path:
        return self.objects / sha[:2] / sha

    def put_file(self, src: pathlib.Path) -> tuple[str, int]:
        self.objects.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        dst = self.object_path(sha)
        if not dst.exists() or _sha256_file(dst) != sha:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                os.chmod(dst, 0o600)
            atomic_write_bytes(dst, data)
            os.chmod(dst, 0o444)
        return sha, len(data)

    def put_bytes(self, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        dst = self.object_path(sha)
        if not dst.exists() or _sha256_file(dst) != sha:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                os.chmod(dst, 0o600)
            atomic_write_bytes(dst, data)
            os.chmod(dst, 0o444)
        return sha

    def freeze(self, workspace: str | pathlib.Path, *, include: list[str],
               exclude: list[str], task_id: str, source: str) -> dict[str, Any]:
        """工作區 → 候選成果。回 manifest（也寫進 `candidates/<artifact_sha256>.json`）。"""
        chosen, skipped = collect(workspace, include, exclude)
        if len(chosen) > MAX_FILES:
            raise ArtifactError(f"deliverable has {len(chosen)} files (limit {MAX_FILES})")
        files: list[dict[str, Any]] = []
        total = 0
        for rel, p in chosen:
            size = p.stat().st_size
            if size > MAX_FILE_BYTES:
                raise ArtifactError(f"{rel} is {size} bytes (limit {MAX_FILE_BYTES})")
            total += size
            if total > MAX_TOTAL_BYTES:
                raise ArtifactError(f"deliverable exceeds {MAX_TOTAL_BYTES} bytes")
            sha, n = self.put_file(p)
            files.append({"path": rel, "sha256": sha, "size": n,
                          "exec": bool(p.stat().st_mode & stat.S_IXUSR)})
        return self._write_manifest(files, skipped, task_id=task_id, source=source)

    def freeze_blobs(self, blobs: dict[str, bytes], *, task_id: str, source: str,
                     include: list[str], exclude: list[str]) -> dict[str, Any]:
        """HTTP 收件用：路徑→位元組。路徑逃逸（`..`、絕對路徑）直接拒絕。"""
        files: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        total = 0
        norms = [safe_relpath(r) for r in blobs]
        probs = path_problems(norms)
        if probs:
            # 成果本身的問題（重複路徑、檔案與目錄同名）⇒ 由呼叫端記成 reject，不是 void
            raise ArtifactError("submission paths: " + "; ".join(probs[:5]))
        for rel, data in sorted(blobs.items()):
            norm = safe_relpath(rel)
            if norm is None:
                raise ArtifactError(f"refusing unsafe path {rel!r}")
            if not matches(norm, include) or matches(norm, exclude):
                skipped.append({"path": norm, "reason": "outside deliverable.include"})
                continue
            if len(data) > MAX_FILE_BYTES:
                raise ArtifactError(f"{norm} is {len(data)} bytes (limit {MAX_FILE_BYTES})")
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise ArtifactError(f"submission exceeds {MAX_TOTAL_BYTES} bytes")
            sha = self.put_bytes(data)
            files.append({"path": norm, "sha256": sha, "size": len(data), "exec": False})
        return self._write_manifest(files, skipped, task_id=task_id, source=source)

    def _write_manifest(self, files: list[dict[str, Any]], skipped: list[dict[str, str]],
                        *, task_id: str, source: str) -> dict[str, Any]:
        digest = artifact_digest(files)
        manifest = {"schema": ARTIFACT_SCHEMA, "artifact_sha256": digest,
                    "task_id": task_id, "source": source,
                    "files": sorted(files, key=lambda f: f["path"]), "skipped": skipped}
        self.candidates.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(self.candidates / f"{digest}.json",
                           json.dumps(manifest, ensure_ascii=False, indent=2).encode())
        return manifest

    def load_manifest(self, artifact_sha256: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-f]{64}", str(artifact_sha256)):
            raise ArtifactError("not an artifact sha256")
        p = self.candidates / f"{artifact_sha256}.json"
        if not p.is_file():
            raise ArtifactError(f"no candidate {artifact_sha256[:12]}… in the quarantine")
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            raise ArtifactError(f"candidate manifest is not JSON: {e}") from e
        if artifact_digest(m.get("files", [])) != artifact_sha256:
            raise ArtifactError("candidate manifest does not hash to its own name "
                                "(the quarantine was modified)")
        probs = path_problems([f.get("path") for f in m.get("files", [])])
        if probs:
            raise ArtifactError("candidate manifest has unsafe paths: " + "; ".join(probs[:5]))
        return m

    def integrity_problems(self, manifest: dict[str, Any]) -> list[str]:
        probs = path_problems([f.get("path") for f in manifest.get("files", [])])
        if artifact_digest(manifest.get("files", [])) != manifest.get("artifact_sha256"):
            probs.append("manifest digest mismatch")
        for f in manifest.get("files", []):
            if not re.fullmatch(r"[0-9a-f]{64}", str(f.get("sha256"))):
                probs.append(f"{f.get('path')}: not a sha256")
                continue
            op = self.object_path(f["sha256"])
            if not op.is_file():
                probs.append(f"{f['path']}: object missing")
            elif _sha256_file(op) != f["sha256"]:
                probs.append(f"{f['path']}: object was modified in the quarantine")
        return probs

    def materialize(self, manifest: dict[str, Any], dest: str | pathlib.Path) -> pathlib.Path:
        """把候選成果攤成一個新目錄（驗證用、發布用）。逐檔重算雜湊。"""
        probs = self.integrity_problems(manifest)
        if probs:
            raise ArtifactError("quarantine integrity: " + "; ".join(probs))
        d = pathlib.Path(dest)
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        root = d.resolve()
        for f in manifest["files"]:
            out = d / f["path"]
            if root not in out.resolve().parents:        # 第二道：path_problems 之外再確認一次
                raise ArtifactError(f"{f['path']}: escapes the target directory")
            out.parent.mkdir(parents=True, exist_ok=True)
            data = self.object_path(f["sha256"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != f["sha256"]:
                raise ArtifactError(f"{f['path']}: object changed while materializing")
            out.write_bytes(data)
            os.chmod(out, 0o755 if f.get("exec") else 0o644)
        return d


def path_problems(paths: list[Any]) -> list[str]:
    """一批成果路徑能不能安全地攤成一棵樹：每個都是正規化的相對路徑、不重複、
    沒有「一個是檔案、另一個把它當目錄」。清單是從隔離區讀回來的（可能被改過），
    所以攤開之前一定要過這一關。"""
    probs: list[str] = []
    seen: set[str] = set()
    for p in paths:
        norm = safe_relpath(p) if isinstance(p, str) else None
        if norm is None or norm != p:
            probs.append(f"{p!r} is not a normalized relative path")
            continue
        if norm in seen:
            probs.append(f"{norm!r} appears twice")
        seen.add(norm)
    for p in seen:
        parts = p.split("/")
        for i in range(1, len(parts)):
            if "/".join(parts[:i]) in seen:
                probs.append(f"{'/'.join(parts[:i])!r} is both a file and a directory")
                break
    return probs


def safe_relpath(rel: str) -> str | None:
    """HTTP 或其他外部來源給的路徑：只收相對、不含 `..`、不含 NUL。"""
    if not rel or "\x00" in rel or rel.startswith(("/", "\\")) or ":" in rel.split("/")[0]:
        return None
    parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(parts)
