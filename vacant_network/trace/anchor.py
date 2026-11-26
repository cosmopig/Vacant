"""anchor — **外部鏈頭錨定（`vacant trace anchor`）**：把已驗章的鏈頭寫成 JSON 並可選提交到 git。

這支在架構裡承重什麼（2026-11-26 紀錄強化 4）：

單機簽章鏈最大的剩餘弱點之一是「整條鏈被截短、重寫或整份換掉」——沒有外部錨點時，
持有同帳號私鑰的人可以從任意位置截短再重簽。過去實驗腳本另外手算鏈頭與 harness
檔案雜湊再推上 git；這裡把它做成標準產品指令：

    vacant trace anchor [--output FILE] [--file EXTRA ...] [--git REPO]
    vacant trace anchor --check FILE [--check-files]

- 寫出前先對目前專案鏈跑 `Recorder.verify()`（fail-closed：不對壞鏈或空鏈產出錨點）。
- 寫出 JSON（`schema: "vacant-trace-anchor/1"`）：`project_key`、`chain_length`、`last_seq`、
  `head_hash`、`genesis_hash`、`signer`、`timestamp`、`ts_ms`、`chain_sha256`、`sealed_volumes`、
  與選配的 `extra_files`（每個額外檔案的 sha256 與位元組數）。
- `--git <repo>` 在指定 git 倉庫內只暫存並提交該錨點檔（`shell=False`，不碰倉庫內其他變動，
  亦不自動 push）。
- `--check <file>` 驗證目前專案鏈本身驗章通過、簽章者與創世相符、且仍**延伸**自該錨點
  （`current_seq >= anchor_seq` 且第 `anchor_seq` 筆的雜湊逐字等於 `head_hash`）。

## 誠實邊界（改碼請保留）

1. **本機錨點檔或本機 git 倉庫無法防止同機控制者一併改寫**。真正的防竄改需要把該 git 倉庫
   推往外部遠端、唯附加儲存或公開透明度日誌（`--git` 只做本機 commit，不自動 push）。
2. 錨定只證明「目前鏈**延伸**自當時已驗章的鏈頭」（可偵測截短、重寫或換簽章者）；
   不證明錨定之前沒有遺漏任何未經掛鉤的步驟（那取決於掛鉤覆蓋率與金鑰隔離）。
3. `extra_files` 的雜湊記錄錨定當下的檔案內容；`--check` 預設只驗鏈延伸（額外檔案狀態記於
   結果供查），加上 `--check-files` 才對額外檔案的後續變動 fail-closed。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import time
from typing import Any, Sequence

from ..atomic import atomic_write_text
from .recorder import Recorder

ANCHOR_SCHEMA = "vacant-trace-anchor/1"


class AnchorError(RuntimeError):
    """錨點建立、寫入、git 提交或解析失敗（fail-closed）。"""


def _sha256_file(p: pathlib.Path) -> tuple[str, int]:
    h = hashlib.sha256()
    total = 0
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            total += len(chunk)
    return h.hexdigest(), total


def create_anchor(
    rec: Recorder,
    *,
    extra_files: Sequence[str | os.PathLike[str]] = (),
    trust: Any = None,
) -> dict[str, Any]:
    """對目前專案已驗章的簽章鏈建立外部錨點字典（不寫檔）。壞鏈或空鏈一律拋 `AnchorError`。"""
    ok, why = rec.verify(trust)
    if not ok:
        raise AnchorError(f"cannot anchor trace chain that does not verify ({why})")
    book, _torn, _head = rec._consistent_snapshot()
    if not book.entries:
        raise AnchorError("trace chain is empty")
    genesis = book.entries[0]
    last = book.entries[-1]
    signer = str((genesis.payload or {}).get("signer") or "")
    ts_ms = int(time.time() * 1000)
    ts_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts_ms / 1000.0))

    chain_sha: str | None = None
    if rec.chain_path.is_file():
        chain_sha, _ = _sha256_file(rec.chain_path)

    sealed: list[dict[str, Any]] = []
    for vp in rec._sealed_volume_paths():
        vsha, vsz = _sha256_file(vp)
        sealed.append({"name": vp.name, "sha256": vsha, "bytes": vsz})

    extras: dict[str, dict[str, Any]] = {}
    for raw in extra_files:
        p = pathlib.Path(raw)
        resolved = p.resolve() if p.is_absolute() else (pathlib.Path.cwd() / p).resolve()
        if not resolved.is_file():
            raise AnchorError(f"extra file not found or not a regular file: {raw}")
        fsha, fsz = _sha256_file(resolved)
        try:
            key = resolved.relative_to(rec.workspace).as_posix()
        except ValueError:
            key = str(raw)
        extras[key] = {"path": str(resolved), "sha256": fsha, "bytes": fsz}

    return {
        "schema": ANCHOR_SCHEMA,
        "project_key": rec.dir.name,
        "workspace": str(rec.workspace),
        "chain_length": len(book.entries),
        "last_seq": last.seq,
        "head_hash": last.hash(),
        "genesis_hash": genesis.hash(),
        "signer": signer,
        "timestamp": ts_iso,
        "ts_ms": ts_ms,
        "chain_sha256": chain_sha,
        "sealed_volumes": sealed,
        "extra_files": extras,
    }


def _run_git(repo: pathlib.Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _is_under(child: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def write_anchor(
    anchor: dict[str, Any],
    output: pathlib.Path | None = None,
    *,
    git_repo: pathlib.Path | None = None,
) -> dict[str, Any]:
    """將錨點 JSON 寫入磁碟，並於指定 `--git <repo>` 時於該倉庫提交該錨點檔（不 push）。"""
    text = json.dumps(anchor, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    written_paths: list[str] = []

    if output is not None:
        out_p = pathlib.Path(output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(out_p, text)
        written_paths.append(str(out_p.resolve()))

    git_info: dict[str, Any] | None = None
    if git_repo is not None:
        repo = pathlib.Path(git_repo).resolve()
        if not repo.is_dir():
            raise AnchorError(f"git repo directory does not exist: {repo}")
        chk = _run_git(repo, ["rev-parse", "--is-inside-work-tree"])
        if chk.returncode != 0 or chk.stdout.strip() != "true":
            raise AnchorError(f"not a git repository: {repo}")

        if output is not None and _is_under(pathlib.Path(output), repo):
            target = pathlib.Path(output).resolve()
        elif output is not None:
            target = repo / "anchors" / pathlib.Path(output).name
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(target, text)
            written_paths.append(str(target.resolve()))
        else:
            target = repo / "anchors" / f"{anchor['project_key']}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(target, text)
            written_paths.append(str(target.resolve()))

        rel = target.resolve().relative_to(repo).as_posix()
        add = _run_git(repo, ["add", "--", rel])
        if add.returncode != 0:
            raise AnchorError(f"git add failed: {add.stderr.strip() or add.stdout.strip()}")

        diff = _run_git(repo, ["diff", "--cached", "--quiet", "--", rel])
        if diff.returncode == 0:
            head = _run_git(repo, ["rev-parse", "HEAD"])
            git_info = {
                "repo": str(repo),
                "path": rel,
                "committed": False,
                "commit": head.stdout.strip() if head.returncode == 0 else None,
                "note": "anchor file unchanged from HEAD",
            }
        else:
            msg = (f"vacant trace anchor: {anchor['project_key']} "
                   f"seq={anchor['last_seq']} head={str(anchor['head_hash'])[:12]}")
            com = _run_git(repo, ["commit", "-m", msg, "--", rel])
            if com.returncode != 0:
                raise AnchorError(f"git commit failed: {com.stderr.strip() or com.stdout.strip()}")
            head = _run_git(repo, ["rev-parse", "HEAD"])
            git_info = {
                "repo": str(repo),
                "path": rel,
                "committed": True,
                "commit": head.stdout.strip() if head.returncode == 0 else None,
            }

    return {"written": written_paths, "git": git_info}


def check_anchor(
    rec: Recorder,
    anchor_path: pathlib.Path,
    *,
    trust: Any = None,
    check_files: bool = False,
) -> dict[str, Any]:
    """驗證目前專案的簽章鏈是否仍然完整且**延伸**自 `anchor_path` 所記之鏈頭。"""
    p = pathlib.Path(anchor_path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AnchorError(f"could not read anchor file {p}: {exc}") from exc
    if not isinstance(raw, dict):
        raise AnchorError(f"anchor file {p} must contain a JSON object")

    a_proj = raw.get("project_key")
    a_seq = raw.get("last_seq")
    if a_seq is None:
        a_seq = raw.get("chain_length")
    a_head = raw.get("head_hash")
    a_signer = raw.get("signer")
    a_genesis = raw.get("genesis_hash")
    if not isinstance(a_proj, str) or not a_proj:
        raise AnchorError("anchor missing project_key")
    if isinstance(a_seq, bool) or not isinstance(a_seq, int) or a_seq < 1:
        raise AnchorError("anchor has invalid last_seq / chain_length")
    if not isinstance(a_head, str) or not a_head:
        raise AnchorError("anchor missing head_hash")

    base_out: dict[str, Any] = {
        "ok": False,
        "project_key": rec.dir.name,
        "anchor_project_key": a_proj,
        "anchor_seq": a_seq,
        "anchor_head_hash": a_head,
        "current_seq": None,
        "extended_by": None,
        "extra_files": {},
        "reason": "",
    }

    if a_proj != rec.dir.name:
        base_out["reason"] = (f"anchor project_key {a_proj!r} does not match "
                              f"current workspace project_key {rec.dir.name!r}")
        return base_out

    ok, why = rec.verify(trust)
    if not ok:
        base_out["reason"] = f"current trace chain does not verify ({why})"
        return base_out

    book, _torn, _head = rec._consistent_snapshot()
    if not book.entries:
        base_out["reason"] = "current trace chain is empty"
        return base_out

    genesis = book.entries[0]
    last = book.entries[-1]
    base_out["current_seq"] = last.seq
    base_out["current_head_hash"] = last.hash()

    cur_signer = str((genesis.payload or {}).get("signer") or "")
    if isinstance(a_signer, str) and a_signer and cur_signer != a_signer:
        base_out["reason"] = (f"trace signer mismatch (anchor={a_signer[:16]}…, "
                              f"current={cur_signer[:16]}…)")
        return base_out
    if isinstance(a_genesis, str) and a_genesis and genesis.hash() != a_genesis:
        base_out["reason"] = "trace genesis_hash does not match anchor (chain was replaced)"
        return base_out

    if last.seq < a_seq:
        base_out["reason"] = (f"trace chain ends at seq {last.seq}, shorter than anchored "
                              f"seq {a_seq} (truncated or replaced)")
        return base_out

    at = next((e for e in book.entries if e.seq == a_seq), None)
    if at is None:
        base_out["reason"] = f"anchored seq {a_seq} is missing from the current chain"
        return base_out
    if at.hash() != a_head:
        base_out["reason"] = (f"entry at seq {a_seq} hash {at.hash()[:16]}… does not match "
                              f"anchored head_hash {a_head[:16]}… (rewritten or forked)")
        return base_out

    # 額外檔案雜湊對照
    ef_status: dict[str, dict[str, Any]] = {}
    ef_failures: list[str] = []
    raw_extras = raw.get("extra_files")
    if isinstance(raw_extras, dict):
        for k, meta in sorted(raw_extras.items()):
            if not isinstance(meta, dict):
                continue
            fpath = pathlib.Path(str(meta.get("path") or (rec.workspace / k)))
            want_sha = str(meta.get("sha256") or "")
            if not fpath.is_file():
                ef_status[k] = {"status": "missing", "path": str(fpath), "expected_sha256": want_sha}
                ef_failures.append(f"{k}: missing")
                continue
            got_sha, _ = _sha256_file(fpath)
            if got_sha != want_sha:
                ef_status[k] = {"status": "changed", "path": str(fpath),
                                "expected_sha256": want_sha, "actual_sha256": got_sha}
                ef_failures.append(f"{k}: sha256 mismatch")
            else:
                ef_status[k] = {"status": "ok", "path": str(fpath), "sha256": got_sha}
    base_out["extra_files"] = ef_status
    base_out["extended_by"] = last.seq - a_seq

    if check_files and ef_failures:
        base_out["reason"] = "extra files changed since anchor: " + "; ".join(ef_failures)
        return base_out

    base_out["ok"] = True
    base_out["reason"] = (f"chain extends anchor at seq {a_seq} (head {a_head[:12]}…, "
                          f"now at seq {last.seq}, +{last.seq - a_seq} entries)")
    return base_out
