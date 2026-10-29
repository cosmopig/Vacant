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

## 自動回收（零設定）與用量檢視

- `auto_gc`：零設定自動 gc——**單例鎖（flock，持鎖行程死掉時由 OS 自動釋放）＋頻率限制
  （預設一小時一次）＋時間預算（預設 30 秒，在下一個迴圈邊界停下；已刪的都是簽章鏈不引用的
  blob，中途停下也是安全點）**，全程 fail-open（出錯只記不拋）。工作階段結束／Stop 掛鉤在背景
  離程啟動它（`adapters/hook.py:_spawn_auto_gc`），人也可以手動 `vacant gc --auto`。
- `usage_report`：`vacant usage`——總用量、分區、每專案、物件前 10、可回收估算、上次 gc 結果。
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
# round 72 設計決定（gc↔rescan whack-a-mole）：鏈上活動在此窗口內的專案視為「活躍」，
# gc 保留其「未變動且工作區原檔 bit 相同」的 live 背景 blob（下次修改所需的 before
# 版本；回收它們只買回 I/O、超時與失觀，省不下任何持久磁碟）。預設 7 天。
DEFAULT_ACTIVE_WINDOW_S = 7 * 86400.0

# 2026-10-28 Axis 2（取代 round 72 的「保留活躍專案 before 版本」）：
# store-on-change 之後，版本庫不再重存未改動檔案；自動 gc 另設一個使用量上限，
# 超過時按「工作區冗餘 → 最舊舊版本」的順序回收（讀取端回退工作區＋驗 sha，
# 取不回誠實 UNKNOWN）。`VACANT_TRACE_BUDGET_BYTES` 可覆寫（0＝關）。
#
# round 142（2026-10-28）：512 MiB → 64 MiB。512 MiB 實測為「恰好高於舊式全量
# 複製快照（2G repo 上 542 MB，其中 247 MB 是未變動檔的零價值副本）」⇒ sweep
# 空轉、垃圾永不回收（ASSIGNMENT 主軸 2 人類回報的 564 M 現狀）。64 MiB＝2G
# repo 的 3.2%，實測硬底（活躍索引＋近 50 步 I/O＋已改檔版本）裝得下
# （本專案實測 5.97 MiB，2026-10-28 round 145）；未變動檔副本（同專案 63.18 MiB）
# 由讀端工作區回退兜底，超標時 sweep 優先回收、零損失。
# round 145 另修 `_sweep_to_target` 計數 bug（只數候選不數硬底 ⇒ 69.15 MiB 現狀
# 下 sweep 空轉），見同檔 round 145 註記與 tests/test_retention.py 回歸測試。
DEFAULT_TRACE_BUDGET_BYTES = 64 * 1024 * 1024

# 2026-10-28 Axis 2 最優先（人類點名：~/.vacant 用量沒有上限）：
# `possess/proxyd/wire` 是模型通道的 wire 原始捕獲——每一通模型呼叫一對
# `.req.bin`/`.resp.bin`（原始位元組），隨每通呼叫無上限成長（本機實測
# 4957 個檔案／17.1 MiB，單通回應 ~755 KB）。
# 可究責證據在 `index.jsonl`：一通一行（ts、request/response sha256、狀態、
# 位元組數），`vrun/attest.read_relay_calls` 讀它做「通道是否被中介」的對帳。
# 原始 body 唯一消費者是 wireproxy 同一通內回讀位元組數，**沒有其他讀端**。
# ⇒ 原始 body 設位元組上限（保留最新、刪最舊）；被刪 body 的內容誠實 UNKNOWN，
#   其 sha256/ts/狀態仍在 journal 裡——「這通被中介、內容是 X」的 X 取不回。
DEFAULT_WIRE_BODY_BYTES = 96 * 1024 * 1024
#: index.jsonl 是中介證據（requests_seen／attest 對帳）。8 MiB ≈ 1.7 萬通；
#: 超過時保留最新完整行（一半上限），更早行的證據誠實 UNKNOWN（不是 0、不是 PASS）。
DEFAULT_WIRE_INDEX_BYTES = 8 * 1024 * 1024
#: possess/hooks 每 session 一個事件 jsonl（canary／session_start…，attest 對帳用）。
#: 單檔 2 MiB 上限（與 intake 日誌同口徑）；只保留最新 N 個 session，更早的誠實 UNKNOWN。
DEFAULT_HOOKS_MAX_FILE_BYTES = 2 * 1024 * 1024
DEFAULT_HOOKS_KEEP_SESSIONS = 200

#: 自動 gc 的守門參數（零設定：沒有這些參數也要安全）。
AUTO_GC_MIN_INTERVAL_S = 3600.0   # 頻率限制：同一台機器至多每小時真跑一次
AUTO_GC_BUDGET_S = 30.0           # 時間預算：一次自動 gc 最多佔住多久（超過就停在安全點）
AUTO_GC_LOCK_NAME = "gc.lock"
AUTO_GC_LAST_NAME = "gc_last.json"
AUTO_GC_REPORT_NAME = "gc_report.json"


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


def _sweep_to_target(
    obj_root: pathlib.Path,
    keep_shas: set[str],
    redundant_live: set[str],
    target_bytes: int,
    *,
    dry_run: bool,
    budget: _Budget | None = None,
) -> dict[str, Any]:
    """把版本庫壓到 `target_bytes` 以下（2026-10-28 Axis 2）。

    優先序：先回收「与工作區冗餘」的 blob（工作區仍有 bit 相同原檔、讀取端回退取得，
    內容零損失），再按最舊優先回收其餘非必須保留的舊版本（內容轉為 UNKNOWN：
    `file_text` 回 None、`materialize` 列進 missing；不崩、不假 PASS）。鏈、事件體、
    近期步驟索引、writes 前後版本（keep_shas 且不在 redundant_live）＝硬底（hard floor），
    此機制不動。

    2026-10-28 round 145 修正：判斷「是否已達標」必須以**整個版本庫**
    （候選＋硬底）計，而非只看候選——否則「硬底 5.97 MiB＋冗餘 63.18 MiB＝69.15 MiB
    ＞ 64 MiB 預算」時，候選單獨 63.18 MiB＜預算 ⇒ sweep 空轉、預算形同虛設
    （真實 `~/.vacant` 實測）。若硬底本身超過預算，本機制誠實回報
    `target_reached=False` 並附上 `hard_keep_bytes`（能刪的已全刪）；不假達標。
    """
    cands: list[tuple[int, int, int, pathlib.Path]] = []
    total = 0          # 整個版本庫（含硬底）的位元組數
    hard_keep = 0      # 硬底位元組（本機制不可回收）
    if obj_root.is_dir():
        for sub in sorted(obj_root.iterdir()):
            if not sub.is_dir():
                continue
            for bf in sorted(sub.iterdir()):
                sha = bf.name
                try:
                    sz = bf.stat().st_size
                except OSError:
                    continue
                total += sz
                if sha in keep_shas and sha not in redundant_live:
                    hard_keep += sz
                    continue
                # 0＝工作區冗餘（先回收，零損失）；1＝其餘舊版本（後回收，內容轉 UNKNOWN）
                cands.append((0 if (sha in keep_shas) else 1, sz, bf.stat().st_mtime_ns, bf))
    cands.sort(key=lambda t: (t[0], t[2]))
    freed = 0
    removed = 0
    aborted = False
    remaining = total
    for rank, size, _mts, bf in cands:
        if remaining <= target_bytes:
            break
        if budget is not None and budget.expired():
            aborted = True
            break
        b, c = _remove_path(bf, dry_run=dry_run)
        remaining -= b
        freed += b
        removed += c
    if not dry_run and obj_root.is_dir():
        for sub in sorted(obj_root.iterdir()):
            with contextlib.suppress(OSError):
                if sub.is_dir() and not any(sub.iterdir()):
                    sub.rmdir()
    return {"target_bytes": target_bytes, "bytes_freed": freed, "files_removed": removed,
            "bytes_remaining": remaining, "target_reached": remaining <= target_bytes,
            "hard_keep_bytes": hard_keep, "aborted": aborted}


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


class _Budget:
    """一次 gc 的時間預算。`expired()` 為真時各 `compact_*` 在下一個迴圈邊界停下；
    已刪的檔案都停在安全點（簽章鏈引用的 blob 永不刪），所以中途停下也是合法的。"""

    def __init__(self, deadline: float | None):
        self.deadline = deadline

    def expired(self) -> bool:
        return self.deadline is not None and time.time() >= self.deadline


def _atomic_write_json(path: pathlib.Path, obj: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def compact_trace(
    root: pathlib.Path | None = None,
    *,
    keep_recent_steps: int = DEFAULT_KEEP_STEPS,
    prune_redundant_workspace_blobs: bool = True,
    max_age_days: float | None = None,
    keep_set_aside: int = DEFAULT_KEEP_SET_ASIDE,
    dry_run: bool = False,
    budget: _Budget | None = None,
    active_window_s: float | None = DEFAULT_ACTIVE_WINDOW_S,
    target_bytes: int | None = None,
) -> dict[str, Any]:
    """清理 `$VACANT_HOME/trace/` 下多餘的物件與過期的擱置鏈，不動 `chain.ndjson` 與 `head.json`。

    `target_bytes`（2026-10-28 Axis 2）：常規回收後若版本庫仍大於此位元組數，再按
    「工作區冗餘 → 最舊舊版本」的順序回收（見 `_sweep_to_target`）：讀取端回退
    「工作區＋驗 sha」，取不回誠實回 UNKNOWN；必須保留的 blob 從不動。

    round 72 設計決定（gc↔rescan whack-a-mole）：鏈上活動在 `active_window_s` 內（預設
    7 天）的**活躍專案**，其「未變動且工作區原檔 bit 相同」的 live 背景 blob 正是那些
    檔案下次被修改時所需的 before 版本，對它回收只買回 I/O、超時與失觀（下一次掃描
    如數重存），故予以保留；**非活躍專案**（超出窗口）照舊回收。`active_window_s=None`
    表示無活躍窗口（全部照舊回收）；`0.0` 等於「無任何專案活躍」。"""
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
    # 2026-10-28 Axis 2：「工作區仍有 bit 相同原檔」的 blob（含活躍專案的）——
    # 常規回收保留（取代 round 72 的 whack-a-mole 理由），但超出 target_bytes 時可安全回收
    redundant_live: set[str] = set()
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
            if budget is not None and budget.expired():
                break
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

            # round 72：活躍邊界（以鏈上活動的磁碟時間為準；與本檔其他 max_age 判斷同用 mtime）
            project_active = False
            if active_window_s is not None:
                last_activity = 0.0
                for _name in ("chain.ndjson", "state.json", "head.json"):
                    with contextlib.suppress(OSError):
                        last_activity = max(last_activity, (pdir / _name).stat().st_mtime)
                project_active = last_activity > 0 and (now - last_activity) < active_window_s

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
                        redundant_live.add(fsha)
                        if project_active:
                            # 活躍專案：保留（下次修改所需的 before 版本；回收＝whack-a-mole）
                            keep_shas.add(fsha)
                            must_keep_file_shas.add(fsha)
                        else:
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

    aborted = False
    if obj_root.is_dir():
        for sub in sorted(obj_root.iterdir()):
            if budget is not None and budget.expired():
                aborted = True
                break
            if not sub.is_dir():
                continue
            for blob_file in sorted(sub.iterdir()):
                if budget is not None and budget.expired():
                    aborted = True
                    break
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

    target: dict[str, Any] | None = None
    if target_bytes is not None and target_bytes >= 0:
        target = _sweep_to_target(obj_root, keep_shas, redundant_live, int(target_bytes),
                                  dry_run=dry_run, budget=budget)
        if target["aborted"]:
            aborted = True

    rep = {
        "bytes_freed": bytes_freed + (target["bytes_freed"] if target else 0),
        "files_removed": files_removed + (target["files_removed"] if target else 0),
        "projects_scanned": projects_scanned,
        "kept_blobs": len(keep_shas),
        "aborted": aborted,
    }
    if target is not None:
        rep["target"] = target
    return rep


def compact_quarantine(
    root: pathlib.Path | None = None,
    *,
    keep_latest_per_task: int = DEFAULT_KEEP_DECISIONS,
    max_age_days: float | None = None,
    dry_run: bool = False,
    budget: _Budget | None = None,
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
        if budget is not None and budget.expired():
            break
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
                if budget is not None and budget.expired():
                    break
                if not sub.is_dir():
                    continue
                for obj_file in sorted(sub.iterdir()):
                    if budget is not None and budget.expired():
                        break
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
    budget: _Budget | None = None,
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
        if budget is not None and budget.expired():
            break
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
            if budget is not None and budget.expired():
                break
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
    budget: _Budget | None = None,
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
        if budget is not None and budget.expired():
            break
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
    budget: _Budget | None = None,
    target_bytes: int | None = None,
) -> dict[str, Any]:
    """一次清理所有 Vacant 狀態目錄的冗餘資料，回傳結構化報告。

    `target_bytes`：把 trace 版本庫壓到此位元組數以下（2026-10-28 Axis 2；見
    `compact_trace`）；None＝常規保守回收。"""
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
        budget=budget,
        target_bytes=target_bytes,
    )
    qr = compact_quarantine(
        root,
        keep_latest_per_task=keep_latest_per_task,
        max_age_days=max_age_days,
        dry_run=dry_run,
        budget=budget,
    )
    wk = compact_work(
        work_root,
        keep_runs_per_task=keep_runs_per_task,
        max_age_days=max_age_days,
        strip_workspaces_only=not aggressive,
        dry_run=dry_run,
        budget=budget,
    )
    lg = compact_logs(root, max_log_bytes=max_log_bytes, dry_run=dry_run)
    # 4b) 模型通道 wire 捕獲＋session hook 事件（2026-10-28 Axis 2 最優先）
    wire = compact_wire(root, budget=budget)
    hooks = compact_session_hooks(root, dry_run=dry_run)
    vr = {"bytes_freed": 0, "files_removed": 0}
    for vd in vrun_dirs or []:
        if budget is not None and budget.expired():
            break
        res = compact_vrun_dir(vd, dry_run=dry_run, budget=budget)
        vr["bytes_freed"] += res["bytes_freed"]
        vr["files_removed"] += res["files_removed"]

    total_bytes = (tr["bytes_freed"] + qr["bytes_freed"] + wk["bytes_freed"]
                   + lg["bytes_freed"]
                   + wire["body_bytes_freed"] + wire["index_bytes_freed"]
                   + hooks["bytes_freed"] + vr["bytes_freed"])
    total_files = (tr["files_removed"] + qr["files_removed"] + wk["files_removed"]
                   + lg["logs_compacted"]
                   + wire["body_files_removed"] + hooks["files_removed"]
                   + vr["files_removed"])

    aborted = any(r.get("aborted") for r in (tr, qr, wk, lg)) or (
        budget is not None and budget.expired())
    rep: dict[str, Any] = {
        "dry_run": dry_run,
        "aggressive": aggressive,
        "aborted": aborted,
        "bytes_freed": total_bytes,
        "mb_freed": round(total_bytes / (1024 * 1024), 3),
        "files_removed": total_files,
        "trace": tr,
        "quarantine": qr,
        "work": wk,
        "logs": lg,
        "wire": wire,
        "session_hooks": hooks,
        "vrun": vr,
    }
    if verify:
        v_count, v_ok, v_errs = verify_trace_chains(root)
        rep["verified_projects"] = v_count
        rep["verify_ok"] = v_ok
        rep["verify_errors"] = v_errs
    return rep


def _resolve_auto_budget() -> int | None:
    """自動 gc 的版本庫上限：`VACANT_TRACE_BUDGET_BYTES` 覆寫（0＝關），
    否則 64 MiB 預設（round 142 由 512 MiB 下修；Axis 2）。"""
    env = os.environ.get("VACANT_TRACE_BUDGET_BYTES")
    if env is not None:
        try:
            v = int(env)
            return None if v <= 0 else v
        except ValueError:
            return DEFAULT_TRACE_BUDGET_BYTES
    return DEFAULT_TRACE_BUDGET_BYTES


def _resolve_wire_body_budget() -> int:
    """`VACANT_WIRE_BODY_BYTES` 覆寫（0＝關），否則 96 MiB 預設（Axis 2 最優先）。"""
    env = os.environ.get("VACANT_WIRE_BODY_BYTES")
    if env is not None:
        try:
            v = int(env)
            return max(0, v)
        except ValueError:
            return DEFAULT_WIRE_BODY_BYTES
    return DEFAULT_WIRE_BODY_BYTES


def _resolve_wire_index_budget() -> int:
    """`VACANT_WIRE_INDEX_BYTES` 覆寫（0＝關），否則 8 MiB 預設（Axis 2 最優先）。"""
    env = os.environ.get("VACANT_WIRE_INDEX_BYTES")
    if env is not None:
        try:
            v = int(env)
            return max(0, v)
        except ValueError:
            return DEFAULT_WIRE_INDEX_BYTES
    return DEFAULT_WIRE_INDEX_BYTES


def compact_wire(
    root: pathlib.Path | None = None,
    *,
    max_body_bytes: int | None = None,
    max_index_bytes: int | None = None,
    dry_run: bool = False,
    budget: _Budget | None = None,
) -> dict[str, Any]:
    """收緊模型通道 wire 原始捕獲（`possess/proxyd/wire`；2026-10-28 Axis 2 最優先）。

    - `.req.bin`／`.resp.bin`：每一通模型呼叫的原始位元組，無上限成長。保留最新、
      刪最舊，直到合計 ≤ `max_body_bytes`。唯一讀端是 wireproxy 同一通內的位元組數
      自驗；**可究責證據在 index.jsonl（每通 sha256/ts/狀態），本函式不刪它**。
      被刪 body 的內容誠實 UNKNOWN（journal 的 sha256 仍在）。
    - `index.jsonl`：中介日誌（`vrun/attest.read_relay_calls`／requests_seen 對帳）。
      超過 `max_index_bytes` 時保留最新完整行（一半上限、至少 4 KB）原子重寫；
      更早行的證據誠實 UNKNOWN。常駐 proxy 每通以 `open("a")` 追記，gc 重寫與它
      競爭時最多丟少量行（fail-open：證據缺失＝UNKNOWN，不損毀、不會偽成 PASS）。
    - 任何 OSError 跳過不拋（fail-open）。
    """
    if max_body_bytes is None:
        max_body_bytes = _resolve_wire_body_budget()
    if max_index_bytes is None:
        max_index_bytes = _resolve_wire_index_budget()
    sroot = pathlib.Path(root).resolve() if root is not None else state_dir()
    wdir = sroot / "possess" / "proxyd" / "wire"
    rep: dict[str, Any] = {
        "wire_dir": str(wdir),
        "body_bytes_before": 0, "body_files_before": 0,
        "body_bytes_freed": 0, "body_files_removed": 0,
        "index_bytes_before": 0, "index_lines_before": 0,
        "index_bytes_freed": 0, "index_lines_dropped": 0,
    }
    if not wdir.is_dir():
        return rep
    # ── 原始 body：位元組上限，保留最新 ──
    bodies: list[tuple[float, int, pathlib.Path]] = []
    total = 0
    for f in wdir.iterdir():
        if f.name == "index.jsonl" or not f.is_file() or f.is_symlink():
            continue
        try:
            st = f.lstat()
        except OSError:
            continue
        bodies.append((st.st_mtime, st.st_size, f))
        total += st.st_size
    rep["body_bytes_before"] = total
    rep["body_files_before"] = len(bodies)
    if max_body_bytes > 0 and total > max_body_bytes:
        bodies.sort(key=lambda t: t[0])  # 最舊在前
        for _mt, sz, f in bodies:
            if total <= max_body_bytes or (budget is not None and budget.expired()):
                break
            if not dry_run:
                with contextlib.suppress(OSError):
                    f.unlink(missing_ok=True)
            total -= sz
            rep["body_bytes_freed"] += sz
            rep["body_files_removed"] += 1
    # ── index.jsonl：保留最新完整行 ──
    ip = wdir / "index.jsonl"
    try:
        isz = ip.lstat().st_size if ip.is_file() else 0
    except OSError:
        isz = 0
    rep["index_bytes_before"] = isz
    if max_index_bytes > 0 and isz > max_index_bytes:
        keep_bytes = max(4096, max_index_bytes // 2)
        try:
            raw = ip.read_bytes()
        except OSError:
            raw = b""
        tail = raw[-keep_bytes:]
        nl = tail.find(b"\n")
        if 0 <= nl < len(tail) - 1:
            tail = tail[nl + 1:]
        if not dry_run and tail != raw:
            try:
                atomic_write_text(ip, tail.decode("utf-8", errors="replace"))
            except OSError:
                tail = raw  # 重寫失敗＝不動原檔（fail-open）
        freed = max(0, len(raw) - len(tail))
        if freed > 0:
            rep["index_bytes_freed"] = freed
            rep["index_lines_before"] = raw.count(b"\n")
            rep["index_lines_dropped"] = max(0, raw.count(b"\n") - tail.count(b"\n"))
    return rep


def compact_session_hooks(
    root: pathlib.Path | None = None,
    *,
    max_file_bytes: int = DEFAULT_HOOKS_MAX_FILE_BYTES,
    keep_sessions: int = DEFAULT_HOOKS_KEEP_SESSIONS,
    dry_run: bool = False,
) -> dict[str, Any]:
    """收緊 `possess/hooks` 的 per-session 事件 jsonl（2026-10-28 Axis 2 最優先）。

    每個 agent session 一個 `pi_<uuid>.jsonl`（canary／session_start…），
    `vrun/attest.read_hook_events` 依 run_id 讀**當下 session** 的事件做對帳。
    單檔超 `max_file_bytes` 保留最新完整行；session 數超 `keep_sessions` 保留最新。
    被刪 session 的事件誠實 UNKNOWN（不是 0、不是 PASS）。fail-open。
    """
    sroot = pathlib.Path(root).resolve() if root is not None else state_dir()
    hdir = sroot / "possess" / "hooks"
    rep: dict[str, Any] = {
        "hooks_dir": str(hdir),
        "bytes_before": 0, "files_before": 0,
        "bytes_freed": 0, "files_removed": 0, "files_truncated": 0,
    }
    if not hdir.is_dir():
        return rep
    files: list[tuple[float, int, pathlib.Path]] = []
    total = 0
    for f in hdir.iterdir():
        if not f.is_file() or f.is_symlink() or not f.name.endswith(".jsonl"):
            continue
        try:
            st = f.lstat()
        except OSError:
            continue
        files.append((st.st_mtime, st.st_size, f))
        total += st.st_size
    rep["bytes_before"] = total
    rep["files_before"] = len(files)
    # 單檔上限：保留最新完整行
    for _mt, sz, f in files:
        if sz <= max_file_bytes:
            continue
        keep_bytes = max(4096, max_file_bytes // 2)
        try:
            raw = f.read_bytes()
        except OSError:
            continue
        tail = raw[-keep_bytes:]
        nl = tail.find(b"\n")
        if 0 <= nl < len(tail) - 1:
            tail = tail[nl + 1:]
        if tail == raw:
            continue
        if not dry_run:
            try:
                atomic_write_text(f, tail.decode("utf-8", errors="replace"))
            except OSError:
                continue
        rep["bytes_freed"] += max(0, len(raw) - len(tail))
        rep["files_truncated"] += 1
    # session 數上限：保留最新 keep_sessions 個
    files.sort(key=lambda t: (t[0], -t[1]))  # 最新在前，同 mtime 則較小的先處理（避免刪除大檔案）
    for _mt, sz, f in files[keep_sessions:]:
        if not dry_run:
            with contextlib.suppress(OSError):
                f.unlink(missing_ok=True)
        rep["bytes_freed"] += sz
        rep["files_removed"] += 1
    return rep


def auto_gc(
    root: pathlib.Path | None = None,
    work_root: pathlib.Path | None = None,
    *,
    min_interval_s: float = AUTO_GC_MIN_INTERVAL_S,
    budget_s: float = AUTO_GC_BUDGET_S,
    force: bool = False,
    dry_run: bool = False,
    target_bytes: int | None = None,
) -> dict[str, Any]:
    """零設定自動 gc：單例鎖（flock）＋頻率限制＋時間預算，全程 fail-open。

    - **單例**：`$VACANT_HOME/gc.lock` 用 `fcntl.flock` 非阻塞取鎖；持鎖行程死掉時 OS 自動
      釋放，不會留死鎖。拿不到鎖 → `skipped_locked`。
    - **頻率**：`$VACANT_HOME/gc_last.json` 記上次真跑的 ts；未到間隔 → `skipped_rate_limited`
      （`force=True` 跳過）。
    - **預算**：`gc_all(budget=_Budget(now+budget_s))`，各迴圈在邊界檢查並停下。
    - **fail-open**：任何例外 → `status="error"`＋錯誤訊息，不拋不阻（掛鉤路徑永遠放行）。
    - **dry_run**：只估算不刪除、不取鎖不計頻（供人檢視）。

    回傳結構：`{"status": "ok"|"skipped_rate_limited"|"skipped_locked"|"error", "ok": bool, ...}`。
    """
    sroot = pathlib.Path(root).resolve() if root is not None else state_dir()
    wroot = pathlib.Path(work_root).resolve() if work_root is not None else work_dir()
    rep: dict[str, Any] = {"status": "error", "ok": False, "state_dir": str(sroot)}
    try:
        if target_bytes is None:
            target_bytes = _resolve_auto_budget()
        if dry_run:
            rep.update(gc_all(root=sroot, work_root=wroot, dry_run=True, target_bytes=target_bytes))
            rep["status"] = "dry_run"
            rep["ok"] = True
            return rep

        sroot.mkdir(parents=True, exist_ok=True)
        lock_path = sroot / AUTO_GC_LOCK_NAME
        last_path = sroot / AUTO_GC_LAST_NAME
        report_path = sroot / AUTO_GC_REPORT_NAME

        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            import fcntl
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                rep["status"] = "skipped_locked"
                rep["reason"] = "another gc is running (lock held)"
                return rep
            if not force:
                try:
                    last = json.loads(last_path.read_text(encoding="utf-8"))
                    if time.time() - float(last.get("ts", 0)) < min_interval_s:
                        rep["status"] = "skipped_rate_limited"
                        rep["reason"] = f"last gc {int(time.time() - float(last['ts']))}s ago < {int(min_interval_s)}s"
                        rep["last"] = last
                        return rep
                except (OSError, ValueError, KeyError):
                    pass  # 沒有上次記錄或讀不到 → 照跑

            t0 = time.time()
            budget = _Budget(t0 + budget_s)
            body = gc_all(root=sroot, work_root=wroot, dry_run=dry_run, budget=budget,
                          target_bytes=target_bytes)
            elapsed = time.time() - t0
            body.update({
                "status": "ok",
                "ok": True,
                "elapsed_s": round(elapsed, 3),
                "budget_s": budget_s,
                "auto": True,
            })
            if aborted := body.get("aborted"):
                body["status"] = "ok_partial"
            # 寫回頻與報告（原子寫）
            summary = {"ts": t0, "elapsed_s": body["elapsed_s"], "bytes_freed": body["bytes_freed"],
                       "files_removed": body["files_removed"], "status": body["status"]}
            with contextlib.suppress(OSError):
                _atomic_write_json(last_path, summary)
            with contextlib.suppress(OSError):
                _atomic_write_json(report_path, body)
            return body
        finally:
            with contextlib.suppress(OSError):
                import fcntl
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
    except Exception as e:  # noqa: BLE001 — fail-open：出錯只記不拋
        rep["status"] = "error"
        rep["error"] = f"{type(e).__name__}: {e}"[:300]
        with contextlib.suppress(OSError):
            _atomic_write_json(sroot / AUTO_GC_REPORT_NAME, rep)
        return rep


def usage_report(
    root: pathlib.Path | None = None,
    work_root: pathlib.Path | None = None,
    *,
    with_estimate: bool = True,
) -> dict[str, Any]:
    """`vacant usage`：總用量、分區、每專案、物件前 10、可回收估算、上次 gc 結果。

    估算走 `gc_all(dry_run=True)`：只計算不刪除、不取鎖不計頻，失敗不阻（回 `error` 欄位）。
    """
    sroot = pathlib.Path(root).resolve() if root is not None else state_dir()
    wroot = pathlib.Path(work_root).resolve() if work_root is not None else work_dir()
    out: dict[str, Any] = {
        "state_dir": str(sroot),
        "work_dir": str(wroot),
        "totals": {},
        "areas": {},
        "objects": {},
        "projects": [],
    }
    try:
        out["totals"]["state_dir"] = _tree_size(sroot)
        out["totals"]["work_dir"] = _tree_size(wroot)
        for name, sub in (
            ("trace_objects", sroot / "trace" / "objects"),
            ("trace_projects", sroot / "trace" / "projects"),
            ("intake", sroot / "intake"),
            ("quarantine", sroot / "quarantine"),
            ("possess", sroot / "possess"),
            ("possess_wire", sroot / "possess" / "proxyd" / "wire"),
            ("possess_hooks", sroot / "possess" / "hooks"),
            ("adapters", sroot / "adapters"),
        ):
            out["areas"][name] = _tree_size(sub)
        # 物件前 10
        obj_root = sroot / "trace" / "objects"
        if obj_root.is_dir():
            tops: list[tuple[int, str]] = []
            n_obj = 0
            b_obj = 0
            for sub in obj_root.iterdir():
                if not sub.is_dir():
                    continue
                for f in sub.iterdir():
                    try:
                        sz = f.stat().st_size
                    except OSError:
                        sz = 0
                    n_obj += 1
                    b_obj += sz
                    tops.append((sz, f.name))
            tops.sort(reverse=True)
            out["objects"] = {
                "count": n_obj,
                "bytes": b_obj,
                "top": [{"sha256": name, "bytes": sz} for sz, name in tops[:10]],
            }
        # 2026-10-28 Axis 2：使用量上限（自動 gc 的收縮目標）
        _budget = _resolve_auto_budget()
        out["budget"] = {
            "trace_objects_bytes": (out.get("objects") or {}).get("bytes", 0),
            "budget_bytes": _budget,
            "within_budget": (_budget is None)
            or ((out.get("objects") or {}).get("bytes", 0) <= _budget),
            "override_env": "VACANT_TRACE_BUDGET_BYTES",
        }
        # 2026-10-28 Axis 2 最優先：模型通道 wire 捕獲上限
        out["budget"]["wire"] = {
            "wire_bytes": out["areas"].get("possess_wire", 0),
            "hooks_bytes": out["areas"].get("possess_hooks", 0),
            "wire_body_budget_bytes": _resolve_wire_body_budget(),
            "wire_index_budget_bytes": _resolve_wire_index_budget(),
            "override_env": ["VACANT_WIRE_BODY_BYTES", "VACANT_WIRE_INDEX_BYTES"],
        }
        # 每專案
        pdir = sroot / "trace" / "projects"
        if pdir.is_dir():
            projs = []
            for p in sorted(pdir.iterdir()):
                if not p.is_dir():
                    continue
                info: dict[str, Any] = {"project": p.name, "bytes": _tree_size(p)}
                with contextlib.suppress(OSError, ValueError):
                    meta = json.loads((p / "project.json").read_text(encoding="utf-8"))
                    if isinstance(meta, dict) and meta.get("workspace"):
                        info["workspace"] = str(meta["workspace"])
                chain_f = p / "chain.ndjson"
                if chain_f.is_file():
                    with contextlib.suppress(OSError):
                        info["chain_events"] = sum(
                            1 for ln in chain_f.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip())
                try:
                    mts = [q.stat().st_mtime for q in (p, chain_f)] if chain_f.is_file() else [p.stat().st_mtime]
                    info["last_activity"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(max(mts)))
                except OSError:
                    pass
                projs.append(info)
            projs.sort(key=lambda r: r["bytes"], reverse=True)
            out["projects"] = projs
        # 上次 gc
        with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
            out["last_gc"] = json.loads((sroot / AUTO_GC_REPORT_NAME).read_text(encoding="utf-8"))
        with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
            out["last_gc_meta"] = json.loads((sroot / AUTO_GC_LAST_NAME).read_text(encoding="utf-8"))
        # 可回收估算（dry-run；不取鎖不計頻）
        if with_estimate:
            try:
                est = gc_all(root=sroot, work_root=wroot, dry_run=True)
                out["reclaimable_estimate"] = {"bytes": est["bytes_freed"], "files": est["files_removed"]}
            except Exception as e:  # noqa: BLE001 — 估算失敗不阻
                out["reclaimable_estimate"] = {"error": f"{type(e).__name__}: {e}"[:200]}
    except Exception as e:  # noqa: BLE001 — fail-open
        out["error"] = f"{type(e).__name__}: {e}"[:300]
    return out


def usage_main(argv: list[str] | None = None) -> int:
    """`vacant usage` CLI：預設人類可讀，`--json` 結構化。"""
    raw = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="vacant usage", description="Vacant 磁碟用量檢視")
    ap.add_argument("--state-dir", type=pathlib.Path, default=None)
    ap.add_argument("--work-dir", type=pathlib.Path, default=None)
    ap.add_argument("--no-estimate", action="store_true", help="不算可回收估算（快一點）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(raw)
    rep = usage_report(args.state_dir, args.work_dir, with_estimate=not args.no_estimate)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    h = _human_bytes
    tot = rep.get("totals", {})
    print(f"Vacant 磁碟用量（{rep['state_dir']}）")
    print("  （數字是 apparent size＝st_size 加總（du -sb 同義）；du -sh 數的是已分配 block，兩者可能不同）")
    if "state_dir" in tot:
        print(f"  狀態目錄總計  : {h(tot['state_dir'])}")
    for name, b in rep.get("areas", {}).items():
        print(f"  · {name:<16}: {h(b)}")
    if "work_dir" in tot:
        print(f"  工作區目錄    : {h(tot['work_dir'])}（{rep['work_dir']}）")
    ob = rep.get("objects", {})
    if ob:
        print(f"  trace 物件    : {ob['count']:,} 個、{h(ob['bytes'])}")
        for t in ob.get("top", [])[:5]:
            print(f"    {h(t['bytes']):>10}  {t['sha256'][:16]}…")
    bu = rep.get("budget", {})
    if bu and bu.get("budget_bytes") is not None:
        state = "✓ 在上限內" if bu.get("within_budget") else "⚠ 超上限（vacant gc --auto 會收縮）"
        print(f"  使用量上限    : {h(bu['budget_bytes'])}（trace 物件 {h(bu.get('trace_objects_bytes', 0))}）{state}")
    for pj in rep.get("projects", [])[:10]:
        extra = f"  （{pj['chain_events']} 步）" if pj.get("chain_events") is not None else ""
        print(f"  專案 {pj['project']}: {h(pj['bytes'])}{extra}  {pj.get('last_activity', '')}")
    est = rep.get("reclaimable_estimate")
    if isinstance(est, dict) and "bytes" in est:
        print(f"  可回收（估算）: {h(est['bytes'])}（{est['files']} 個檔案；vacant gc --dry-run 可預覽）")
    if isinstance(est, dict) and "error" in est:
        print(f"  可回收（估算）: 失敗：{est['error']}")
    meta = rep.get("last_gc_meta")
    if isinstance(meta, dict) and meta.get("ts"):
        print(f"  上次自動 gc   : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(meta['ts']))}"
              f"  釋放 {h(meta.get('bytes_freed', 0))}（{meta.get('status')}）")
    if rep.get("error"):
        print(f"  （部分統計失敗：{rep['error']}）")
    return 0


def _human_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.2f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def _parse_size(s: str) -> int:
    """`--target-bytes` 的值：整數位元組，或帶 K/M/G 後綴（如 `256M`、`1G`）。"""
    s = s.strip().upper()
    mult = 1
    if s and s[-1] in "KMG":
        mult = {"K": 1024, "M": 1024 * 1024, "G": 1024 * 1024 * 1024}[s[-1]]
        s = s[:-1]
    try:
        v = int(s, 10)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expecting bytes or K/M/G suffix, got {s!r}")
    if v < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return v * mult


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
    ap.add_argument("--target-bytes", type=_parse_size, default=None, metavar="N",
                    help="把 trace 版本庫壓到 N 位元組以下（如 256M／1G）：先回收與工作區"
                         "冗餘的 blob，再最舊優先回收舊版本；讀取端取不回誠實 UNKNOWN，"
                         "簽章鏈與必須保留物件不動（2026-10-28 Axis 2）")
    ap.add_argument("--older-than-hours", type=float, default=None,
                    help="只清理超過指定小時數的非必要物件（例如 0.5 代表 30 分鐘前）")
    ap.add_argument("--verify", action="store_true",
                    help="清理後自動對保留之專案執行 Recorder.verify() 驗簽，確保簽章鏈 100%% 完好")
    ap.add_argument("--aggressive", action="store_true",
                    help="積極模式：只留最近 10 步、1 份候選、清空所有 ~/.vacant-work 舊目錄")
    ap.add_argument("--auto", action="store_true",
                    help="零設定自動 gc：單例鎖＋頻率限制（預設 1h）＋時間預算（預設 30s），fail-open")
    ap.add_argument("--force", action="store_true",
                    help="跳過頻率限制（仍受單例鎖保護）")
    ap.add_argument("--min-interval-s", type=float, default=AUTO_GC_MIN_INTERVAL_S,
                    help=f"--auto 的頻率限制秒數（預設 {int(AUTO_GC_MIN_INTERVAL_S)}）")
    ap.add_argument("--budget-s", type=float, default=AUTO_GC_BUDGET_S,
                    help=f"--auto 的時間預算秒數（預設 {int(AUTO_GC_BUDGET_S)}）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只計算可釋放空間，不實際刪除任何檔案")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    return ap


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw[:1] in (["gc"], ["clean"]):
        raw = raw[1:]
    if raw[:1] == ["usage"]:
        return usage_main(raw[1:])
    args = build_parser().parse_args(raw)
    if args.auto:
        rep = auto_gc(
            args.state_dir,
            args.work_dir,
            min_interval_s=args.min_interval_s,
            budget_s=args.budget_s,
            force=args.force,
            dry_run=args.dry_run,
            target_bytes=args.target_bytes,
        )
        if args.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            st = rep["status"]
            if st in ("ok", "ok_partial"):
                tail = f"（時間預算內未完成，停在安全點）" if st == "ok_partial" else ""
                print(f"自動 gc {tail}: 釋放 {_human_bytes(rep['bytes_freed'])}"
                      f"（{rep['files_removed']} 個檔案，{rep.get('elapsed_s', '?')}s）")
                print("  （簽章鏈完整保留；vacant usage 看用量）")
            elif st == "dry_run":
                print(f"自動 gc 預覽（--dry-run，未刪除）: 可釋放 {_human_bytes(rep['bytes_freed'])}"
                      f"（{rep['files_removed']} 個檔案）")
            elif st == "skipped_rate_limited":
                print(f"自動 gc 跳過：{rep.get('reason', 'rate limit')}（--force 可強制）")
            elif st == "skipped_locked":
                print("自動 gc 跳過：另一支 gc 正在執行")
            else:
                print(f"自動 gc 失敗（fail-open，未影響任何資料）: {rep.get('error', st)}")
        return 0 if rep.get("ok") else 1
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
        target_bytes=args.target_bytes,
    )
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if rep.get("verify_ok", True) else 1
    mode_tag = "（預覽 --dry-run，未刪除）" if rep["dry_run"] else "✓ 已清理"
    print(f"{mode_tag} 釋放空間：{_human_bytes(rep['bytes_freed'])}（共處理 {rep['files_removed']} 個檔案／項目）")
    tinfo = rep["trace"].get("target")
    if tinfo is not None:
        tag = "✓ 已達標" if tinfo["target_reached"] and not tinfo["aborted"] else "（預算內未達標）"
        print(f"  · trace 版本庫   : 釋放 {_human_bytes(rep['trace']['bytes_freed'])} "
              f"（掃描 {rep['trace']['projects_scanned']} 個專案，保留 {rep['trace']['kept_blobs']} 個必要物件）")
        print(f"    └ 目標 {tinfo['target_bytes'] / (1024 * 1024):.0f} MiB {tag}: 現餘 "
              f"{_human_bytes(tinfo['bytes_remaining'])}")
    else:
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
