"""retention — **磁碟空間與資料留存治理**：清掉過程留下的巨量工作區副本與孤立物件，**不動任何簽章鏈**。

這支在架構裡承重什麼：
Vacant 的三個核心路徑都會在磁碟上留下與專案等大的副本：
1. **追緝版本庫（`$VACANT_HOME/trace/objects/`）**：第一次掃描工作區時，`workspace.scan` 會把專案裡每一個
   ≤ 8 MB 的檔案都複製進 `trace/objects/`（即使 agent 從頭到尾沒改過它），之後每一步又存下 `input_blob`、
   `output_blob` 與完整／差異索引。
2. **收件隔離區（`$VACANT_HOME/quarantine/`）**：每次 `vacant check`（含掛鉤在 Stop 的檢查）與 `vacant submit`
   都會把繳付物再凍結一份進 `quarantine/objects/`；被退回或中間檢查產生的候選物件從不回收。
3. **一次性工作區（`~/.vacant-work/<task>/<run>/ws*`）與 `vacant run` 暫存（`_frozen_ws`／`_origin_ws`）**：
   每次重試都完整複製整個專案，結束後留在原地。
4. **掛鉤追加日誌（`$VACANT_HOME/intake/hooks/*.jsonl`、`*.log`）**：只增不減。

## 為什麼清理不會弄壞簽章鏈（究責紅線）

`Recorder`（`chain.ndjson`）、`Ledger`（`ledger.ndjson`）與 `vrun`（`receipts_*.ndjson`）簽在鏈上的都是
**內容的 SHA-256 摘要**（`pre_index`、`post_index`、`input_blob`、`output_blob`、`artifact_sha256`、
`workspace_tree_sha256`），而不是把檔案位元組塞進簽章鏈本身：
- `Recorder.verify()` 與 `Recorder.verify_since()` 只驗 `chain.ndjson` 與 `head.json`，完全不讀 `objects/`。
- 未被任何步驟改動過、且目前仍在工作區原位（SHA-256 經重算吻合）的檔案，`Trace.file_text` 與
  `workspace.materialize` 可直接從工作區讀取並核對雜湊，無須在 `trace/objects/` 留一份重複副本。
- 收件帳本只保留最新接受／放行／待審與最近 N 次決策的候選物件，其餘中間 `check` 或舊退回的隔離物件
  可直接回收，帳本簽章鏈照常通過。

## 誠實邊界

1. 被清掉的**舊步驟中間版本**（超過 `keep_recent_steps` 且工作區原檔後來又被改寫過的版本）無法再用
   `materialize` 重建出當時的檔案內容；那一步的簽章、寫入清單（路徑＋前後 sha256）仍在 `chain.ndjson`。
   若之後對已被清掉中間版本的古老步驟跑 `blame`，`Trace` 會誠實標記該狀態 `unreadable`（`UNOBSERVED`），
   絕不會把過錯栽給別的步驟。
2. 預設保留最新回合與最近 `keep_recent_steps`（預設 50 步）的全部索引與修改版本，因此當下與近期的
   `zerostop`、`evidence`、`blame`、`delivery.md` 行為 100% 不變。
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import pathlib
import shutil
import sys
import time
from typing import Any

from .atomic import atomic_write_text
from .intake.statepaths import state_dir, work_dir
from .trace import workspace as W

DEFAULT_KEEP_STEPS = 50
DEFAULT_KEEP_DECISIONS = 2
DEFAULT_KEEP_RUNS = 3
DEFAULT_KEEP_SET_ASIDE = 3
DEFAULT_MAX_LOG_BYTES = 2 * 1024 * 1024  # 2 MB


def _file_size(p: pathlib.Path) -> int:
    try:
        return p.lstat().st_size if not p.is_symlink() else 0
    except OSError:
        return 0


def _tree_size(p: pathlib.Path) -> int:
    if not p.exists():
        return 0
    if p.is_file() or p.is_symlink():
        return _file_size(p)
    total = 0
    for root, _dirs, files in os.walk(p, followlinks=False):
        for f in files:
            try:
                st = os.lstat(os.path.join(root, f))
                total += st.st_size
            except OSError:
                pass
    return total


def _remove_path(p: pathlib.Path, *, dry_run: bool) -> tuple[int, int]:
    """回傳 `(釋放位元組數, 刪除檔案數)`。"""
    if not p.exists() and not p.is_symlink():
        return 0, 0
    if p.is_file() or p.is_symlink():
        sz = _file_size(p)
        if not dry_run:
            with contextlib.suppress(OSError):
                p.unlink(missing_ok=True)
        return sz, 1
    sz, count = 0, 0
    for root, _dirs, files in os.walk(p, followlinks=False):
        for f in files:
            count += 1
            with contextlib.suppress(OSError):
                sz += os.lstat(os.path.join(root, f)).st_size
    if not dry_run:
        for q in (p, *p.rglob("*")):
            if not q.is_symlink():
                with contextlib.suppress(OSError):
                    q.chmod(0o700)
        shutil.rmtree(p, ignore_errors=True)
    return sz, max(1, count)


def _index_base_sha(blobs: W.Blobs, idx_sha: str | None) -> str | None:
    """若 `idx_sha` 是差異索引，回傳它指向的關鍵幀 `base` sha256。"""
    if not idx_sha or ":" in idx_sha or not blobs.has(idx_sha):
        return None
    try:
        raw = json.loads(blobs.get(idx_sha))
        if isinstance(raw, dict) and "" in raw and isinstance(raw[""], dict):
            base = raw[""].get("base")
            return str(base) if isinstance(base, str) else None
    except (OSError, ValueError):
        return None
    return None


def _load_project_index(blobs: W.Blobs, idx_sha: str | None) -> W.Index:
    if not idx_sha or ":" in idx_sha or not blobs.has(idx_sha):
        return {}
    try:
        raw = json.loads(blobs.get(idx_sha))
        if not isinstance(raw, dict):
            return {}
        if "" not in raw:
            return {str(k): W.Entry.from_json(v) for k, v in raw.items()}
        meta = raw[""]
        base_sha = meta.get("base")
        if not isinstance(base_sha, str) or not blobs.has(base_sha):
            return {}
        base_raw = json.loads(blobs.get(base_sha))
        if not isinstance(base_raw, dict) or "" in base_raw:
            return {}
        out = {str(k): W.Entry.from_json(v) for k, v in base_raw.items()}
        for d in meta.get("del") or []:
            out.pop(str(d), None)
        for k, v in raw.items():
            if k != "":
                out[str(k)] = W.Entry.from_json(v)
        return out
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def compact_trace(
    root: pathlib.Path | None = None,
    *,
    keep_recent_steps: int = DEFAULT_KEEP_STEPS,
    prune_redundant_workspace_blobs: bool = True,
    max_age_days: float | None = None,
    keep_set_aside: int = DEFAULT_KEEP_SET_ASIDE,
    dry_run: bool = False,
) -> dict[str, Any]:
    """清理 `$VACANT_HOME/trace/` 下多餘的物件與過期的擱置鏈，不動 `chain.ndjson` 與 `head.json`。"""
    sroot = pathlib.Path(root).resolve() if root is not None else state_dir()
    troot = sroot / "trace"
    obj_root = troot / "objects"
    proj_root = troot / "projects"
    if not troot.is_dir():
        return {"bytes_freed": 0, "files_removed": 0, "projects_scanned": 0}

    blobs = W.Blobs(obj_root)
    keep_shas: set[str] = set()
    # 已被工作區原位檔案涵蓋、且從未在任何步驟被改寫的純重複檔案 sha256
    redundant_candidates: set[str] = set()
    must_keep_file_shas: set[str] = set()
    projects_scanned = 0
    bytes_freed = 0
    files_removed = 0
    now = time.time()

    def _keep_index(sha: str | None) -> None:
        if not sha or ":" in sha:
            return
        keep_shas.add(sha)
        base = _index_base_sha(blobs, sha)
        if base:
            keep_shas.add(base)

    if proj_root.is_dir():
        for pdir in sorted(x for x in proj_root.iterdir() if x.is_dir()):
            projects_scanned += 1
            # 1) 清理過多的 chain.set-aside.*.ndjson
            set_asides = sorted(pdir.glob("chain.set-aside.*.ndjson"),
                                key=lambda p: p.stat().st_mtime if p.exists() else 0)
            drop_asides = set_asides[:-keep_set_aside] if keep_set_aside > 0 else set_asides
            if max_age_days is not None:
                cutoff = now - max_age_days * 86400.0
                for sa in set_asides:
                    with contextlib.suppress(OSError):
                        if sa not in drop_asides and sa.stat().st_mtime < cutoff:
                            drop_asides.append(sa)
            for sa in drop_asides:
                b, c = _remove_path(sa, dry_run=dry_run)
                bytes_freed += b
                files_removed += c
                stamp = sa.name.removeprefix("chain.set-aside.").removesuffix(".ndjson")
                for aux in (pdir / f"head.set-aside.{stamp}.json",
                            pdir / f"chain.set-aside.{stamp}.why.txt"):
                    b2, c2 = _remove_path(aux, dry_run=dry_run)
                    bytes_freed += b2
                    files_removed += c2

            ws_path: pathlib.Path | None = None
            with contextlib.suppress(OSError, ValueError):
                pmeta = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
                if isinstance(pmeta, dict) and pmeta.get("workspace"):
                    cand_ws = pathlib.Path(str(pmeta["workspace"]))
                    if cand_ws.is_dir():
                        ws_path = cand_ws

            # 2) state.json 裡的現用索引一定要留（下一步增量掃描靠它們）
            active_indices: set[str] = set()
            with contextlib.suppress(OSError, ValueError):
                st = json.loads((pdir / "state.json").read_text(encoding="utf-8"))
                if isinstance(st, dict):
                    if ws_path is None and st.get("workspace"):
                        cand_ws = pathlib.Path(str(st["workspace"]))
                        if cand_ws.is_dir():
                            ws_path = cand_ws
                    for k in ("last_index", "index_key"):
                        v = st.get(k)
                        if isinstance(v, str) and v:
                            _keep_index(v)
                            active_indices.add(v)
                    for pend_map in (st.get("pending"), st.get("open")):
                        for pend in (pend_map or {}).values():
                            if isinstance(pend, dict):
                                for k in ("pre_index", "bound_index"):
                                    v = pend.get(k)
                                    if isinstance(v, str) and v:
                                        _keep_index(v)
                                        active_indices.add(v)
                                ib = pend.get("input_blob")
                                if isinstance(ib, str) and ib:
                                    keep_shas.add(ib)

            chain_file = pdir / "chain.ndjson"
            if not chain_file.is_file():
                continue

            events: list[dict[str, Any]] = []
            with contextlib.suppress(OSError):
                for ln in chain_file.read_text(encoding="utf-8", errors="replace").splitlines():
                    if not ln.strip():
                        continue
                    with contextlib.suppress(ValueError):
                        row = json.loads(ln)
                        if isinstance(row, dict):
                            events.append({"seq": row.get("seq", 0), "type": row.get("type"),
                                           **(row.get("payload") or {})})

            # 找出初始索引、最後一則使用者提示的起點、以及所有曾被改動過的檔案版本
            initial_idx: str | None = None
            last_user_seq = -1
            step_events: list[dict[str, Any]] = []
            modified_paths: set[str] = set()

            for e in events:
                t = e.get("type")
                if t == "trace_genesis" and ws_path is None and e.get("workspace"):
                    cand_ws = pathlib.Path(str(e["workspace"]))
                    if cand_ws.is_dir():
                        ws_path = cand_ws
                elif t == "transcript":
                    for k in ("blob", "sha256", "transcript_blob"):
                        v = e.get(k)
                        if isinstance(v, str) and v and ":" not in v:
                            keep_shas.add(v)
                elif t == "prompt":
                    tb = e.get("text_blob")
                    if isinstance(tb, str) and tb:
                        keep_shas.add(tb)
                    if str(e.get("source") or "user") in ("user", "vacant do"):
                        last_user_seq = max(last_user_seq, int(e.get("seq") or 0))
                elif t == "step":
                    step_events.append(e)
                    if initial_idx is None and isinstance(e.get("pre_index"), str):
                        initial_idx = e["pre_index"]
                    for w in e.get("writes") or []:
                        if isinstance(w, dict) and w.get("path"):
                            modified_paths.add(str(w["path"]))
                    wb = e.get("writes_blob")
                    if isinstance(wb, str) and blobs.has(wb):
                        keep_shas.add(wb)
                        with contextlib.suppress(OSError, ValueError):
                            for w in json.loads(blobs.get(wb)):
                                if isinstance(w, dict) and w.get("path"):
                                    modified_paths.add(str(w["path"]))
                elif t == "unrecorded_change":
                    if initial_idx is None and isinstance(e.get("before_index"), str):
                        initial_idx = e["before_index"]
                    _keep_index(e.get("before_index"))
                    _keep_index(e.get("after_index"))
                    for ch in e.get("changes") or []:
                        if isinstance(ch, dict):
                            if ch.get("path"):
                                modified_paths.add(str(ch["path"]))
                            for k in ("before", "after"):
                                v = ch.get(k)
                                if isinstance(v, str) and ":" not in v:
                                    keep_shas.add(v)
                                    must_keep_file_shas.add(v)
                    cb = e.get("changes_blob")
                    if isinstance(cb, str) and blobs.has(cb):
                        keep_shas.add(cb)
                        with contextlib.suppress(OSError, ValueError):
                            for ch in json.loads(blobs.get(cb)):
                                if isinstance(ch, dict):
                                    if ch.get("path"):
                                        modified_paths.add(str(ch["path"]))
                                    for k in ("before", "after"):
                                        v = ch.get(k)
                                        if isinstance(v, str) and ":" not in v:
                                            keep_shas.add(v)
                                            must_keep_file_shas.add(v)
                elif t == "coverage" and isinstance(e.get("baseline"), dict):
                    bidx = e["baseline"].get("index")
                    if isinstance(bidx, str):
                        if initial_idx is None:
                            initial_idx = bidx
                        _keep_index(bidx)
                        active_indices.add(bidx)
                elif t == "session_closed" and isinstance(e.get("final_index"), str):
                    if initial_idx is None:
                        initial_idx = e["final_index"]
                    _keep_index(e["final_index"])
                    active_indices.add(e["final_index"])

            if initial_idx:
                _keep_index(initial_idx)
                active_indices.add(initial_idx)

            # 保留最近 keep_recent_steps 步 ＋ 目前這個要求（last_user_seq 之後）的所有步驟
            recent_steps = step_events[-keep_recent_steps:] if keep_recent_steps > 0 else []
            kept_steps = {id(s): s for s in recent_steps}
            for s in step_events:
                if int(s.get("seq") or 0) > last_user_seq:
                    kept_steps[id(s)] = s

            for s in kept_steps.values():
                for k in ("input_blob", "output_blob", "writes_blob", "reads_blob", "payload_blob"):
                    v = s.get(k)
                    if isinstance(v, str) and v:
                        keep_shas.add(v)
                for k in ("pre_index", "post_index"):
                    v = s.get(k)
                    if isinstance(v, str) and v:
                        _keep_index(v)
                        active_indices.add(v)
                reads = list(s.get("reads") or [])
                rb = s.get("reads_blob")
                if isinstance(rb, str) and blobs.has(rb):
                    with contextlib.suppress(OSError, ValueError):
                        reads = json.loads(blobs.get(rb))
                for r in reads:
                    if isinstance(r, dict) and isinstance(r.get("blob"), str) and r["blob"]:
                        keep_shas.add(r["blob"])
                writes = list(s.get("writes") or [])
                wb = s.get("writes_blob")
                if isinstance(wb, str) and blobs.has(wb):
                    with contextlib.suppress(OSError, ValueError):
                        writes = json.loads(blobs.get(wb))
                for w in writes:
                    if isinstance(w, dict):
                        for k in ("before", "after"):
                            v = w.get(k)
                            if isinstance(v, str) and ":" not in v:
                                keep_shas.add(v)
                                must_keep_file_shas.add(v)

            # 索引裡出現的檔案內容：
            # 若檔案曾被改動過、或工作區已不在／內容已變 ⇒ 留在版本庫；
            # 若檔案從頭到尾未被任何步驟改動，且目前工作區原檔大小與 sha256 完全相同 ⇒
            # 工作區本身就是這份內容，版本庫裡的重複副本可安全回收。
            seen_idx_entries: dict[tuple[str, str], bool] = {}
            for idx_sha in list(active_indices):
                idx = _load_project_index(blobs, idx_sha)
                for rel, entry in idx.items():
                    fsha = entry.sha256
                    if ":" in fsha:
                        continue
                    if rel in modified_paths or not prune_redundant_workspace_blobs or ws_path is None:
                        keep_shas.add(fsha)
                        must_keep_file_shas.add(fsha)
                        continue
                    cache_key = (rel, fsha)
                    if cache_key not in seen_idx_entries:
                        live_ok = False
                        src = ws_path / rel
                        with contextlib.suppress(OSError):
                            st_live = src.lstat()
                            if not os.path.islink(src) and st_live.st_size == entry.size:
                                if st_live.st_mtime_ns == entry.mtime_ns or W._sha_file(src) == fsha:
                                    live_ok = True
                        seen_idx_entries[cache_key] = live_ok
                    if seen_idx_entries[cache_key]:
                        redundant_candidates.add(fsha)
                    else:
                        keep_shas.add(fsha)
                        must_keep_file_shas.add(fsha)
            if not dry_run and prune_redundant_workspace_blobs and (pdir / "state.json").is_file():
                with contextlib.suppress(OSError, ValueError):
                    st_cur = json.loads((pdir / "state.json").read_text(encoding="utf-8"))
                    if isinstance(st_cur, dict) and not st_cur.get("compacted"):
                        st_cur["compacted"] = True
                        atomic_write_text(pdir / "state.json", json.dumps(st_cur, ensure_ascii=False))

    # 任何在別處被標記必須保留的 sha，不可當成重複副本刪掉
    keep_shas |= must_keep_file_shas
    cutoff_ts = (now - max_age_days * 86400.0) if max_age_days is not None else None

    if obj_root.is_dir():
        for sub in sorted(obj_root.iterdir()):
            if not sub.is_dir():
                continue
            for blob_file in sorted(sub.iterdir()):
                sha = blob_file.name
                if sha in keep_shas:
                    continue
                if cutoff_ts is not None and sha not in redundant_candidates:
                    with contextlib.suppress(OSError):
                        if blob_file.stat().st_mtime >= cutoff_ts:
                            continue
                b, c = _remove_path(blob_file, dry_run=dry_run)
                bytes_freed += b
                files_removed += c
            if not dry_run:
                with contextlib.suppress(OSError):
                    if not any(sub.iterdir()):
                        sub.rmdir()

    return {
        "bytes_freed": bytes_freed,
        "files_removed": files_removed,
        "projects_scanned": projects_scanned,
        "kept_blobs": len(keep_shas),
    }


def compact_quarantine(
    root: pathlib.Path | None = None,
    *,
    keep_latest_per_task: int = DEFAULT_KEEP_DECISIONS,
    max_age_days: float | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """清理 `$VACANT_HOME/quarantine/` 裡未被帳本最新裁決／放行引用的候選清單與隔離物件。"""
    sroot = pathlib.Path(root).resolve() if root is not None else state_dir()
    store_roots = [p for p in (sroot / "intake" / "store", sroot / "quarantine") if p.is_dir()]
    if not store_roots:
        return {"bytes_freed": 0, "files_removed": 0, "candidates_kept": 0}

    ledger_files: list[pathlib.Path] = []
    ldir = sroot / "intake" / "ledger"
    if ldir.is_dir():
        ledger_files.extend(sorted(ldir.glob("*.ndjson")))
    tasks_dir = sroot / "intake" / "tasks"
    if tasks_dir.is_dir():
        for tdir in sorted(x for x in tasks_dir.iterdir() if x.is_dir()):
            lf = tdir / "ledger.ndjson"
            if lf.is_file():
                ledger_files.append(lf)

    keep_artifacts: set[str] = set()
    for ledger_file in ledger_files:
        decisions: list[str] = []
        with contextlib.suppress(OSError):
            for ln in ledger_file.read_text(encoding="utf-8", errors="replace").splitlines():
                if not ln.strip():
                    continue
                with contextlib.suppress(ValueError):
                    row = json.loads(ln)
                    p = (row.get("payload") or {}) if isinstance(row, dict) else {}
                    t = row.get("type") if isinstance(row, dict) else None
                    asha = p.get("artifact_sha256")
                    if not isinstance(asha, str) or not asha:
                        continue
                    if t in ("release", "released", "approval", "approval_recorded"):
                        keep_artifacts.add(asha)
                    elif t == "decision":
                        decisions.append(asha)
                        if p.get("outcome") in ("accept", "hold", "escalate"):
                            keep_artifacts.add(asha)
        if keep_latest_per_task > 0:
            for asha in decisions[-keep_latest_per_task:]:
                keep_artifacts.add(asha)

    now = time.time()
    cutoff_ts = (now - max_age_days * 86400.0) if max_age_days is not None else None
    bytes_freed = 0
    files_removed = 0
    kept_manifests = 0
    keep_objects: set[str] = set()

    for qroot in store_roots:
        cand_dir = qroot / "candidates"
        obj_dir = qroot / "objects"
        if cand_dir.is_dir():
            for mf in sorted(cand_dir.glob("*.json")):
                asha = mf.stem
                keep_this = asha in keep_artifacts
                if not keep_this and cutoff_ts is not None:
                    with contextlib.suppress(OSError):
                        if mf.stat().st_mtime >= cutoff_ts:
                            keep_this = True
                if keep_this:
                    kept_manifests += 1
                    with contextlib.suppress(OSError, ValueError):
                        data = json.loads(mf.read_text(encoding="utf-8"))
                        for fentry in data.get("files") or []:
                            if isinstance(fentry, dict) and isinstance(fentry.get("sha256"), str):
                                keep_objects.add(fentry["sha256"])
                else:
                    b, c = _remove_path(mf, dry_run=dry_run)
                    bytes_freed += b
                    files_removed += c

        if obj_dir.is_dir():
            for sub in sorted(obj_dir.iterdir()):
                if not sub.is_dir():
                    continue
                for obj_file in sorted(sub.iterdir()):
                    if obj_file.name in keep_objects:
                        continue
                    if cutoff_ts is not None:
                        with contextlib.suppress(OSError):
                            if obj_file.stat().st_mtime >= cutoff_ts:
                                continue
                    b, c = _remove_path(obj_file, dry_run=dry_run)
                    bytes_freed += b
                    files_removed += c
                if not dry_run:
                    with contextlib.suppress(OSError):
                        if not any(sub.iterdir()):
                            sub.rmdir()

    return {
        "bytes_freed": bytes_freed,
        "files_removed": files_removed,
        "candidates_kept": kept_manifests,
        "objects_kept": len(keep_objects),
    }


def compact_work(
    wroot: pathlib.Path | None = None,
    *,
    keep_runs_per_task: int = DEFAULT_KEEP_RUNS,
    max_age_days: float | None = None,
    strip_workspaces_only: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """清理 `~/.vacant-work/`（`vacant do` 的隔離工作區副本）。

    - 同一次執行若重試產生了 `ws`、`ws2`、`ws3`，中間被淘汰的 `ws`、`ws2` 副本直接回收，只留最後一個。
    - 每個 task 超過 `keep_runs_per_task` 的舊執行：移除佔空間的 `ws*` 工作區副本（`strip_workspaces_only=True`
      時保留輕量的 `a*/agent_stdout.log`；`False` 時連同舊 run 目錄一併移除）。
    """
    base = pathlib.Path(wroot).resolve() if wroot is not None else work_dir()
    if not base.is_dir():
        return {"bytes_freed": 0, "files_removed": 0, "runs_scanned": 0}

    now = time.time()
    cutoff_ts = (now - max_age_days * 86400.0) if max_age_days is not None else None
    bytes_freed = 0
    files_removed = 0
    runs_scanned = 0

    for task_d in sorted(x for x in base.iterdir() if x.is_dir()):
        runs = sorted(
            (x for x in task_d.iterdir() if x.is_dir()),
            key=lambda p: (p.stat().st_mtime if p.exists() else 0, p.name),
        )
        runs_scanned += len(runs)
        # 1) 每一跑內部：若有 ws, ws2, ws3，中間失敗的舊工作區只留最後一個
        for rdir in runs:
            ws_dirs = sorted(
                (x for x in rdir.iterdir() if x.is_dir() and (x.name == "ws" or x.name.startswith("ws"))),
                key=lambda p: int(p.name[2:] or "1") if p.name[2:].isdigit() or p.name == "ws" else 0,
            )
            for old_ws in ws_dirs[:-1]:
                b, c = _remove_path(old_ws, dry_run=dry_run)
                bytes_freed += b
                files_removed += c

        # 2) 超過保留數量的舊 run
        keep_n = max(0, keep_runs_per_task)
        old_runs = runs[:-keep_n] if keep_n > 0 else list(runs)
        if cutoff_ts is not None:
            for rdir in runs:
                with contextlib.suppress(OSError):
                    if rdir not in old_runs and rdir.stat().st_mtime < cutoff_ts:
                        old_runs.append(rdir)
        for rdir in old_runs:
            if strip_workspaces_only:
                for ws_d in sorted(x for x in rdir.iterdir() if x.is_dir() and x.name.startswith("ws")):
                    b, c = _remove_path(ws_d, dry_run=dry_run)
                    bytes_freed += b
                    files_removed += c
            else:
                b, c = _remove_path(rdir, dry_run=dry_run)
                bytes_freed += b
                files_removed += c
        if not dry_run:
            with contextlib.suppress(OSError):
                if not any(task_d.iterdir()):
                    task_d.rmdir()

    return {
        "bytes_freed": bytes_freed,
        "files_removed": files_removed,
        "runs_scanned": runs_scanned,
    }


def compact_logs(
    root: pathlib.Path | None = None,
    *,
    max_log_bytes: int = DEFAULT_MAX_LOG_BYTES,
    dry_run: bool = False,
) -> dict[str, Any]:
    """截斷過大的掛鉤追加日誌（保留最新一半的完整行），避免 `events.jsonl`／`errors.jsonl` 無限膨脹。"""
    sroot = pathlib.Path(root).resolve() if root is not None else state_dir()
    hdir = sroot / "intake" / "hooks"
    if not hdir.is_dir() or max_log_bytes <= 0:
        return {"bytes_freed": 0, "logs_compacted": 0}

    bytes_freed = 0
    logs_compacted = 0
    keep_bytes = max(4096, max_log_bytes // 2)
    for name in ("events.jsonl", "errors.jsonl", "submit.log", "finalize.log"):
        p = hdir / name
        if not p.is_file() or p.is_symlink():
            continue
        try:
            sz = p.stat().st_size
            if sz <= max_log_bytes:
                continue
            logs_compacted += 1
            if not dry_run:
                raw = p.read_bytes()[-keep_bytes:]
                nl = raw.find(b"\n")
                if nl >= 0 and nl + 1 < len(raw):
                    raw = raw[nl + 1:]
                atomic_write_text(p, raw.decode("utf-8", errors="replace"))
                new_sz = p.stat().st_size
                bytes_freed += max(0, sz - new_sz)
            else:
                bytes_freed += max(0, sz - keep_bytes)
        except OSError:
            continue
    return {"bytes_freed": bytes_freed, "logs_compacted": logs_compacted}


def compact_vrun_dir(
    run_dir: pathlib.Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """清理 `vacant run` 留下的 `_frozen_ws`、`_origin_ws` 與 `wire_RUN-ON` 原始請求包，
    **保留 `receipts_*.ndjson`、`attestation.json`、`result.json`**，使 `verify_run_receipts` 100% 維持通過。"""
    base = pathlib.Path(run_dir).resolve()
    if not base.is_dir():
        return {"bytes_freed": 0, "files_removed": 0}

    bytes_freed = 0
    files_removed = 0
    targets = [base] + [x for x in base.rglob("*") if x.is_dir()]
    seen: set[pathlib.Path] = set()
    for d in targets:
        if any(p in seen for p in (d, *d.parents)):
            continue
        has_receipts = bool(list(d.glob("receipts_*.ndjson"))) or (d / "result.json").is_file()
        if not has_receipts:
            continue
        for heavy in ("_frozen_ws", "_origin_ws", "wire_RUN-ON"):
            hp = d / heavy
            if hp.exists():
                seen.add(hp)
                b, c = _remove_path(hp, dry_run=dry_run)
                bytes_freed += b
                files_removed += c
        for retry_ws in sorted(d.glob("_attempt_*_ws")):
            seen.add(retry_ws)
            b, c = _remove_path(retry_ws, dry_run=dry_run)
            bytes_freed += b
            files_removed += c
    return {"bytes_freed": bytes_freed, "files_removed": files_removed}


def verify_trace_chains(root: pathlib.Path | None = None) -> tuple[int, bool, list[str]]:
    """驗證 trace 版本庫下所有專案的簽章鏈（Recorder.verify）。回傳 (驗證專案數, 是否全數通過, 錯誤訊息列表)。"""
    base = (root or state_dir()) / "trace"
    pdir = base / "projects"
    if not pdir.is_dir():
        return 0, True, []
    from .trace.recorder import Recorder
    count = 0
    errors = []
    for p in sorted(pdir.iterdir()):
        if not p.is_dir() or not (p / "chain.ndjson").is_file():
            continue
        count += 1
        try:
            rec = Recorder(p, root=base)
            rec.dir = p
            rec.chain_path = p / "chain.ndjson"
            rec.state_path = p / "state.json"
            v = rec.verify()
            if isinstance(v, tuple):
                ok, reason = v
            else:
                ok, reason = v.get("ok"), v.get("reason")
            if not ok:
                errors.append(f"{p.name}: {reason}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p.name}: {e}")
    return count, len(errors) == 0, errors


def gc_all(
    *,
    root: pathlib.Path | None = None,
    work_root: pathlib.Path | None = None,
    vrun_dirs: list[pathlib.Path] | None = None,
    keep_recent_steps: int = DEFAULT_KEEP_STEPS,
    keep_latest_per_task: int = DEFAULT_KEEP_DECISIONS,
    keep_runs_per_task: int = DEFAULT_KEEP_RUNS,
    max_age_days: float | None = None,
    older_than_hours: float | None = None,
    max_log_bytes: int = DEFAULT_MAX_LOG_BYTES,
    aggressive: bool = False,
    dry_run: bool = False,
    verify: bool = False,
) -> dict[str, Any]:
    """一次清理所有 Vacant 狀態目錄的冗餘資料，回傳結構化報告。"""
    if older_than_hours is not None and max_age_days is None:
        max_age_days = older_than_hours / 24.0

    if aggressive:
        keep_recent_steps = min(keep_recent_steps, 10)
        keep_latest_per_task = min(keep_latest_per_task, 1)
        keep_runs_per_task = 0

    tr = compact_trace(
        root,
        keep_recent_steps=keep_recent_steps,
        prune_redundant_workspace_blobs=True,
        max_age_days=max_age_days,
        dry_run=dry_run,
    )
    qr = compact_quarantine(
        root,
        keep_latest_per_task=keep_latest_per_task,
        max_age_days=max_age_days,
        dry_run=dry_run,
    )
    wk = compact_work(
        work_root,
        keep_runs_per_task=keep_runs_per_task,
        max_age_days=max_age_days,
        strip_workspaces_only=not aggressive,
        dry_run=dry_run,
    )
    lg = compact_logs(root, max_log_bytes=max_log_bytes, dry_run=dry_run)
    vr = {"bytes_freed": 0, "files_removed": 0}
    for vd in vrun_dirs or []:
        res = compact_vrun_dir(vd, dry_run=dry_run)
        vr["bytes_freed"] += res["bytes_freed"]
        vr["files_removed"] += res["files_removed"]

    total_bytes = (tr["bytes_freed"] + qr["bytes_freed"] + wk["bytes_freed"]
                   + lg["bytes_freed"] + vr["bytes_freed"])
    total_files = (tr["files_removed"] + qr["files_removed"] + wk["files_removed"]
                   + lg["logs_compacted"] + vr["files_removed"])

    rep: dict[str, Any] = {
        "dry_run": dry_run,
        "aggressive": aggressive,
        "bytes_freed": total_bytes,
        "mb_freed": round(total_bytes / (1024 * 1024), 3),
        "files_removed": total_files,
        "trace": tr,
        "quarantine": qr,
        "work": wk,
        "logs": lg,
        "vrun": vr,
    }
    if verify:
        v_count, v_ok, v_errs = verify_trace_chains(root)
        rep["verified_projects"] = v_count
        rep["verify_ok"] = v_ok
        rep["verify_errors"] = v_errs
    return rep


def _human_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.2f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="vacant gc",
        description="清理 Vacant 留下的工作區副本、未改動檔案副本、舊隔離物件與過大日誌（保留所有簽章鏈可驗）",
    )
    ap.add_argument("--state-dir", type=pathlib.Path, default=None,
                    help="Vacant 狀態根目錄（預設 $VACANT_HOME 或 ~/.vacant）")
    ap.add_argument("--work-dir", type=pathlib.Path, default=None,
                    help="vacant do 工作區根目錄（預設 $VACANT_WORK 或 ~/.vacant-work）")
    ap.add_argument("--vrun-dir", type=pathlib.Path, action="append", default=[],
                    help="額外清理的 vacant run 輸出目錄（可重複；移除 _frozen_ws/_origin_ws/wire_RUN-ON）")
    ap.add_argument("--keep-steps", type=int, default=DEFAULT_KEEP_STEPS,
                    help=f"每個專案保留完整步驟版本的最近步數（預設 {DEFAULT_KEEP_STEPS}）")
    ap.add_argument("--keep-runs", type=int, default=DEFAULT_KEEP_RUNS,
                    help=f"每個任務保留 ~/.vacant-work 的最近執行數（預設 {DEFAULT_KEEP_RUNS}）")
    ap.add_argument("--max-age-days", type=float, default=None,
                    help="只清理早於 N 天的非必要物件（預設立即清理冗餘副本）")
    ap.add_argument("--older-than-hours", type=float, default=None,
                    help="只清理超過指定小時數的非必要物件（例如 0.5 代表 30 分鐘前）")
    ap.add_argument("--verify", action="store_true",
                    help="清理後自動對保留之專案執行 Recorder.verify() 驗簽，確保簽章鏈 100%% 完好")
    ap.add_argument("--aggressive", action="store_true",
                    help="積極模式：只留最近 10 步、1 份候選、清空所有 ~/.vacant-work 舊目錄")
    ap.add_argument("--dry-run", action="store_true",
                    help="只計算可釋放空間，不實際刪除任何檔案")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    return ap


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw[:1] in (["gc"], ["clean"]):
        raw = raw[1:]
    args = build_parser().parse_args(raw)
    rep = gc_all(
        root=args.state_dir,
        work_root=args.work_dir,
        vrun_dirs=args.vrun_dir,
        keep_recent_steps=args.keep_steps,
        keep_runs_per_task=args.keep_runs,
        max_age_days=args.max_age_days,
        older_than_hours=args.older_than_hours,
        aggressive=args.aggressive,
        dry_run=args.dry_run,
        verify=args.verify,
    )
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if rep.get("verify_ok", True) else 1
    mode_tag = "（預覽 --dry-run，未刪除）" if rep["dry_run"] else "✓ 已清理"
    print(f"{mode_tag} 釋放空間：{_human_bytes(rep['bytes_freed'])}（共處理 {rep['files_removed']} 個檔案／項目）")
    print(f"  · trace 版本庫   : 釋放 {_human_bytes(rep['trace']['bytes_freed'])} "
          f"（掃描 {rep['trace']['projects_scanned']} 個專案，保留 {rep['trace']['kept_blobs']} 個必要物件）")
    print(f"  · quarantine 隔離: 釋放 {_human_bytes(rep['quarantine']['bytes_freed'])} "
          f"（保留 {rep['quarantine']['candidates_kept']} 份候選清單）")
    print(f"  · vacant-work    : 釋放 {_human_bytes(rep['work']['bytes_freed'])} "
          f"（掃描 {rep['work']['runs_scanned']} 次執行）")
    print(f"  · hooks 日誌     : 釋放 {_human_bytes(rep['logs']['bytes_freed'])} "
          f"（截斷 {rep['logs']['logs_compacted']} 個日誌）")
    if args.vrun_dir:
        print(f"  · vrun 目錄      : 釋放 {_human_bytes(rep['vrun']['bytes_freed'])}")
    if args.verify:
        v_ok_tag = "全數通過 ✓" if rep.get("verify_ok") else "驗證失敗 ✗"
        print(f"  · 鏈驗章 (--verify): {rep.get('verified_projects', 0)} 個專案簽章鏈 {v_ok_tag}")
        if rep.get("verify_errors"):
            for err in rep["verify_errors"]:
                print(f"    - {err}")
    print("  （簽章鏈 chain.ndjson / ledger.ndjson / receipts_*.ndjson 完整保留，離線驗章不變）")
    return 0 if rep.get("verify_ok", True) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
