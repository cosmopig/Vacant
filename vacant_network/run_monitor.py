"""run_monitor — 統一監測平台：批次夜跑＋信任生態＋LM Studio 機群＋Hermes 日誌。

（本檔不對應既定規劃文件編號；定位是操作面板，把 16/17 號文件裡分散在四處的
「看資料」動作收進同一頁，並提供最小操作旗標。四個資料來源，每個都可獨立開關，
開關持久化在 `<runs_root>/monitor_config.json`——關掉的來源完全不輪詢上游。）

  1. **runs** — 批次實驗（X1/X3 夜跑）：讀 `RunLedger` 落盤紀錄算進度/outcome
     分布；暫停/恢復/終止/跳過寫 `control.json`（batch.RunControl 格式），由
     `x1.run_x1(control=...)` 在呼叫模型前輪詢。
  2. **eco** — 信任生態（12 §5 的居民生態）：roster/scoreboard/trust 開關/wipe。
     ⚠️ Ecosystem 建構子在 root 不存在時會**憑空生出預設居民**——本檔絕不在
     讀取路徑上建構不存在的生態（exists=False 就回報，不創建）；建構既有生態
     時名冊一律「從磁碟發現」，杜絕預設名冊補生居民的副作用。roster 的信用分
     採 standing(vid, substrate=None) 的**跨 substrate 概覽口徑**（registry.py
     明文「僅供概覽」——監測就是概覽；正式數字以 ledger/research.py 為準）。
     本機 root 不存在時可讀 hermes 拉回的**遠端鏡像**（唯讀快照，操作一律拒絕）。
  3. **lmstudio** — LM Studio hub（`/_mon/api/overview`）的伺服器端代理（避免
     瀏覽器 CORS）；hub 掛了誠實回報錯誤，不假裝有資料。
  4. **hermes** — 向 Hermes 所在機器收日誌：`ssh -o BatchMode=yes`（**金鑰認證
     限定**，出現 password 提示＝失敗——17 號 P0-4 紀律），逐檔 tail 回來存進
     `<runs_root>/hermes_logs/`。沒裝金鑰時面板顯示失敗原因與一行修法，不掛死。
     另可 `tar` 鏡像整個遠端生態根回 `<runs_root>/eco_mirror/` 餵 eco 面板。

遠端看盤（B-5）：預設只綁 127.0.0.1。要開放繫結必須同時設 token（操作鈕
終止/wipe/trust 不能無認證暴露；GET 讀取不擋）。零程式替代：`tailscale serve`。

⚠️ 誠實邊界：本檔只是觀測與操作旗標，不是信任來源；生態的可信性來自 ledger
簽章鏈，批次的真相來自 RunLedger/trace JSONL。面板與磁碟不符時，以磁碟為準。

紀律：純 stdlib（http.server / json / subprocess / urllib），無外部依賴、無框架、
無 CDN。前端輪詢（2.5s）——批次/生態的變化是秒～分鐘級，輪詢已夠即時。
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
import shlex
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .batch import RunControl, RunLedger

_OUTCOMES = ("pass", "fail", "infra_void", "skipped_by_operator")

SOURCES = ("runs", "eco", "lmstudio", "hermes")

# Hermes 機器上 vacant MCP server 的兩份 trace。相對路徑＝遠端 $HOME 底下
# （ssh 指令在家目錄執行）——**不要放 /tmp**：Ubuntu 重開機會清空，證據蒸發。
DEFAULT_HERMES_PATHS = ("vacant_traces/vac_app.jsonl", "vacant_traces/vac_wire.jsonl")

_SSH_KEY_HINT = (
    "ssh 需要金鑰認證（BatchMode 拒絕互動式密碼——P0-4 紀律）。修法（一次性，"
    "在本機 PowerShell）：ssh-keygen -t ed25519（若還沒有金鑰）；然後 "
    "type $env:USERPROFILE\\.ssh\\id_ed25519.pub | ssh <host> \"cat >> ~/.ssh/authorized_keys\""
    "（這一步會要你輸入一次密碼，之後就不用了）。"
)


def _is_safe_run_id(run_id: str) -> bool:
    """擋路徑穿越：run_id 只能是 runs_root 底下的單層目錄名，或 "." 代表 runs_root 自己。"""
    if run_id == ".":
        return True
    if not run_id or run_id == "..":
        return False
    p = Path(run_id)
    return not p.is_absolute() and ".." not in p.parts and len(p.parts) == 1


def _run_dir(runs_root: Path, run_id: str) -> Path:
    return Path(runs_root) if run_id == "." else Path(runs_root) / run_id


# --- runs 來源（批次實驗）------------------------------------------------------

def _planned_total(run_dir: Path) -> int | None:
    """容錯讀 run 目錄的 manifest.json 取計畫總數（沒有＝誠實回 None，不猜）。

    鍵名 planned_total 是暫定格式（x1_pilot 會寫）；RECORD_SPEC（17 號 P0-1）
    定案後以其 manifest 規格為準，本函式只做容錯讀取、不擁有格式。"""
    p = run_dir / "manifest.json"
    if not p.exists():
        return None
    try:
        v = json.loads(p.read_text(encoding="utf-8")).get("planned_total")
        return int(v) if v is not None else None
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return None


def summarize_run(runs_root: Path, run_id: str) -> dict[str, Any]:
    """單一 run 目錄的即時摘要：只讀 ledger.jsonl；總數只信 manifest、不猜測。"""
    d = _run_dir(runs_root, run_id)
    ledger = RunLedger(d / "ledger.jsonl")
    records = ledger.records()

    by_outcome: dict[str, int] = dict.fromkeys(_OUTCOMES, 0)
    by_family: dict[str, dict[str, int]] = {}
    by_worker: dict[str, dict[str, int]] = {}  # 臂（policy）×seed 分解——X1 三臂配對跑時看的就是這個
    last_ts_ms = 0
    _BUCKET_MS = 300_000  # sparkline 分桶寬：5 分鐘
    spark_buckets: dict[int, list[int]] = {}  # bucket index → [done, pass]
    for r in records:
        outcome = str(r.get("outcome", "?"))
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        fam = str(r.get("family", "?"))
        fs = by_family.setdefault(fam, {"pass": 0, "fail": 0, "other": 0})
        wk = f"{r.get('worker', '?')}·{r.get('seed', '?')}"
        ws = by_worker.setdefault(wk, {"pass": 0, "fail": 0, "other": 0})
        for bucket in (fs, ws):
            if outcome == "pass":
                bucket["pass"] += 1
            elif outcome == "fail":
                bucket["fail"] += 1
            else:
                bucket["other"] += 1
        ts = r.get("ts_ms") or 0
        if ts > last_ts_ms:
            last_ts_ms = ts
        if ts:
            b = spark_buckets.setdefault(int(ts) // _BUCKET_MS, [0, 0])
            b[0] += 1
            if outcome == "pass":
                b[1] += 1

    # sparkline：5 分鐘一桶的完成吞吐，只留最後 ≤36 桶（3 小時窗），中間空桶補零
    # （停滯在圖上＝掉到 0 的平線）。ledger 無 infra_void（run_x1 的 resume 設計），
    # 這是「完成吞吐」曲線；void 率另列數字，不混進來。<2 個非空桶畫不出線 → None。
    spark = None
    if len(spark_buckets) >= 2:
        last_b = max(spark_buckets)
        first_b = max(min(spark_buckets), last_b - 35)
        spark = {
            "bucket_s": 300,
            "t0_ms": first_b * _BUCKET_MS,
            "buckets": [spark_buckets.get(i, [0, 0])
                        for i in range(first_b, last_b + 1)],
        }

    # 速率：取最近 ≤20 筆有時戳的完成格算吞吐；ETA 只在 manifest 有計畫總數時給
    stamps = sorted(int(r["ts_ms"]) for r in records if r.get("ts_ms"))
    recent = stamps[-20:]
    rate_per_min = None
    if len(recent) >= 2 and recent[-1] > recent[0]:
        rate_per_min = round((len(recent) - 1) / ((recent[-1] - recent[0]) / 60000), 2)
    planned = _planned_total(d)
    eta_min = None
    if planned and rate_per_min and planned > len(records):
        eta_min = int((planned - len(records)) / rate_per_min)

    lanes = sorted(p.name for p in d.glob("*.trace.jsonl")) if d.exists() else []
    control = RunControl(d / "control.json")
    return {
        "run_id": run_id,
        "path": str(d),
        "first_ts_ms": stamps[0] if stamps else None,  # 簡易檢視算「執行時長」用
        "total_done": len(records),
        "by_outcome": by_outcome,
        "by_family": by_family,
        "by_worker": by_worker,
        "lanes": lanes,
        "corrupt_lines": ledger.corrupt_lines,
        "last_activity_ms": last_ts_ms,
        "control_state": control.state(),
        "planned_total": planned,
        "rate_per_min": rate_per_min,
        "eta_min": eta_min,
        "spark": spark,
    }


def scan_runs(runs_root: Path) -> list[dict[str, Any]]:
    """列出 runs_root 下每個看起來像 run 的目錄（含 ledger.jsonl）的摘要。"""
    runs_root = Path(runs_root)
    if not runs_root.exists():
        return []
    run_ids = sorted(
        d.name for d in runs_root.iterdir()
        if d.is_dir() and (d / "ledger.jsonl").exists()
    )
    if (runs_root / "ledger.jsonl").exists():
        run_ids.append(".")  # runs_root 自己就是單一 run 的情況
    return [summarize_run(runs_root, rid) for rid in run_ids]


def tail_records(runs_root: Path, run_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """最近 N 筆完成紀錄（按 ts_ms 排序；用於面板的日誌檢視）。"""
    d = _run_dir(runs_root, run_id)
    records = RunLedger(d / "ledger.jsonl").records()
    records.sort(key=lambda r: r.get("ts_ms") or 0)
    return records[-limit:]


# --- GitHub 歸檔 runs（上游 cosmopig/Vacant 的 runs/，直接從 git ref 讀）---------
#
# 為什麼讀 git ref 而不是讀工作樹：工作樹在哪個分支、有沒有沒提交的改動都會讓
# 「面板上的數字」跟「GitHub 上的資料」悄悄分岔；`git cat-file <sha>:<path>` 讀到的
# 一定是那個 commit 的位元組，面板同時顯示 commit sha ＋ `git ls-remote` 查到的
# 遠端 sha，兩者相等＝這份資料就是 GitHub main 現在的樣子（誠實語意：截至上次
# 檢查時刻）。歸檔 run 是靜態證據，刻意不併進即時 run 清單：不判停滯、不推播。
#
# 索引紀律沿用 runs/INDEX.json 自己的定義（ops/gain/build_runs_index.py）：
# 只列 kind ∈ {real_run, aborted}；analysis（衍生物）、smoke（不進統計）等照它
# 的定義不列，但數量照實回報。數字只抄 runner 自己寫的 summary.json，讀不到就
# 回 None（面板顯示「—」），不從 rows 重算、不猜。

_GH_LISTED_KINDS = ("real_run", "aborted")


def _gh_arm_stats(entry: dict[str, Any], summary: dict[str, Any] | None
                  ) -> tuple[str, list[dict[str, Any]]]:
    """把一個 run 的逐臂統計攤平成 [{arm, planned, done, delivered, void}]。

    delivered＝正確交付（accepted ∧ meets_demand；gain_run 的 accepted_and_meets_demand、
    R530 版面的 deliv——ops/gain/power_paired.py 同一條定義）。回 (layout, arms)。"""
    by_rows = entry.get("n_rows_by_arm") or {}
    arms_raw = (summary or {}).get("arms")
    stats = (summary or {}).get("arms_stats")
    out: list[dict[str, Any]] = []

    def _int(v: Any) -> int | None:
        if isinstance(v, bool) or v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    if isinstance(arms_raw, dict) and arms_raw:
        for arm, a in arms_raw.items():
            if not isinstance(a, dict):
                continue
            void = _int(a.get("infra_void"))
            done = _int(a.get("processed"))
            if done is None and arm in by_rows and void is not None:
                done = int(by_rows[arm]) + void  # rows 不含 void 列（gain_run 設計）
            out.append({"arm": arm, "planned": _int(a.get("tasks")), "done": done,
                        "delivered": _int(a.get("accepted_and_meets_demand")),
                        "void": void})
        return "gain_arms", out
    if isinstance(stats, dict) and stats:
        for arm, a in stats.items():
            if not isinstance(a, dict):
                continue
            out.append({"arm": arm, "planned": None, "done": _int(a.get("processed")),
                        "delivered": _int(a.get("deliv")),
                        "void": _int(a.get("infra_void"))})
        return "gain_arms_stats", out
    for arm, n in sorted(by_rows.items()):
        out.append({"arm": arm, "planned": None, "done": _int(n),
                    "delivered": None, "void": None})
    return "index_only", out


def _gh_run_row(entry: dict[str, Any], summary: dict[str, Any] | None) -> dict[str, Any]:
    layout, arms = _gh_arm_stats(entry, summary)

    def _sum(key: str) -> int | None:
        vals = [a[key] for a in arms]
        return sum(vals) if vals and all(v is not None for v in vals) else None

    bank = entry.get("bank") or {}
    return {
        "run_id": entry.get("name"),
        "kind": entry.get("kind"),
        "subkind": entry.get("subkind"),
        "date": entry.get("date"),
        "seed": entry.get("seed"),
        "bank": bank.get("family"),
        "bank_version": bank.get("version"),
        "layout": layout,
        "arms": arms,
        "total_done": _sum("done"),
        "total_delivered": _sum("delivered"),
        "infra_void": entry.get("infra_void"),
        "terminal": entry.get("terminal"),
        "complete": entry.get("complete"),
        "headline": entry.get("headline"),
        "verdict_decisions": entry.get("verdict_decisions") or [],
        "n_decision_refs": len(entry.get("decision_refs") or []),
    }


class GitHubRuns:
    """GitHub 上游 runs/ 的唯讀視圖：從本機 git 的 `<remote>/<branch>` ref 讀
    runs/INDEX.json ＋ 各 run 的 summary.json，並用 `git ls-remote` 對照遠端。

    同步（`git fetch`）在背景做、不擋請求；唯讀實例不 fetch（不寫 .git），只做
    ls-remote 比對——它會誠實顯示「本機落後遠端」。git_run：測試注入點，簽名
    (args, input_bytes) -> CompletedProcess。"""

    _REMOTE_CHECK_S = 120.0

    def __init__(self, repo_dir: Path | str | None, *, remote: str = "origin",
                 branch: str = "main", runs_subdir: str = "runs",
                 fetch_every_s: float = 600.0,
                 git_run: Callable[[list[str], bytes | None],
                                   subprocess.CompletedProcess] | None = None) -> None:
        self.repo_dir = Path(repo_dir) if repo_dir else None
        self.remote = remote
        self.branch = branch
        self.ref = f"refs/remotes/{remote}/{branch}"
        self.runs_subdir = runs_subdir.strip("/")
        self.fetch_every_s = fetch_every_s
        self._git_run = git_run or self._default_git_run
        self._lock = threading.Lock()
        self._busy = threading.Lock()  # 背景 fetch／ls-remote 同時只跑一個
        self._cache_sha: str | None = None
        self._cache_rows: list[dict[str, Any]] = []
        self._cache_meta: dict[str, Any] = {}
        self._remote_sha: str | None = None
        self._remote_checked_ms: int | None = None
        self._remote_err: str | None = None
        self._last_fetch_ms: int | None = None
        self._fetch_err: str | None = None
        self._read_err: str | None = None
        self._url: str | None = None

    @property
    def configured(self) -> bool:
        return self.repo_dir is not None

    def _default_git_run(self, args: list[str], input_bytes: bytes | None
                         ) -> subprocess.CompletedProcess:
        import os
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # 公開 repo；要密碼就失敗，不卡住
        kw: dict[str, Any] = {"input": input_bytes} if input_bytes is not None \
            else {"stdin": subprocess.DEVNULL}
        return subprocess.run(["git", "-C", str(self.repo_dir), *args],
                              capture_output=True, timeout=120, env=env, **kw)

    # -- 讀 git 物件 ---------------------------------------------------------------
    def _local_sha(self) -> str | None:
        p = self._git_run(["rev-parse", "--verify", "--quiet", self.ref + "^{commit}"], None)
        sha = p.stdout.decode("ascii", "replace").strip() if p.returncode == 0 else ""
        return sha or None

    def _read_many(self, sha: str, paths: list[str]) -> dict[str, bytes | None]:
        """一次 `git cat-file --batch` 讀多個檔（Windows 上逐檔開行程太慢）。"""
        if not paths:
            return {}
        req = "".join(f"{sha}:{p}\n" for p in paths).encode("utf-8")
        p = self._git_run(["cat-file", "--batch"], req)
        if p.returncode != 0:
            raise RuntimeError(_clean_stderr(p.stderr) or "git cat-file 失敗")
        buf, pos, out = p.stdout, 0, {}
        for path in paths:
            nl = buf.index(b"\n", pos)
            header = buf[pos:nl].split()
            pos = nl + 1
            if len(header) >= 2 and header[-1] == b"missing":
                out[path] = None
                continue
            size = int(header[2])
            out[path] = buf[pos:pos + size] if header[1] == b"blob" else None
            pos += size + 1  # 內容後面跟一個換行
        return out

    def _rebuild(self, sha: str) -> None:
        base = self.runs_subdir
        idx_raw = self._read_many(sha, [f"{base}/INDEX.json"]).get(f"{base}/INDEX.json")
        if idx_raw is None:
            raise RuntimeError(f"{self.ref} 裡沒有 {base}/INDEX.json")
        index = json.loads(idx_raw.decode("utf-8"))
        entries = [e for e in index.get("runs") or [] if isinstance(e, dict)]
        listed = [e for e in entries if e.get("kind") in _GH_LISTED_KINDS]
        want = [f"{base}/{e['name']}/summary.json" for e in listed
                if any(f.get("name") == "summary.json" for f in e.get("files") or [])]
        blobs = self._read_many(sha, want)
        rows = []
        for e in listed:
            raw = blobs.get(f"{base}/{e['name']}/summary.json")
            summary = None
            if raw is not None:
                try:
                    summary = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    summary = None  # 壞檔＝讀不到，數字回 None，不吞成 0
            rows.append(_gh_run_row(e, summary if isinstance(summary, dict) else None))
        rows.sort(key=lambda r: (r.get("date") or "", r.get("run_id") or ""), reverse=True)
        by_kind: dict[str, int] = {}
        for e in entries:
            by_kind[str(e.get("kind"))] = by_kind.get(str(e.get("kind")), 0) + 1
        self._cache_rows = rows
        self._cache_meta = {
            "index_entries": len(entries),
            "listed": len(rows),
            "by_kind": by_kind,
            "listed_kinds": list(_GH_LISTED_KINDS),
            "generated_by": index.get("generated_by"),
        }
        self._cache_sha = sha

    def runs(self) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        with self._lock:
            try:
                sha = self._local_sha()
                if sha is None:
                    self._read_err = f"找不到 {self.ref}（還沒 fetch 過？）"
                    return []
                if sha != self._cache_sha:
                    self._rebuild(sha)
                self._read_err = None
            except Exception as e:  # git 不在、ref 壞、INDEX 解析失敗：照實回報
                self._read_err = f"{type(e).__name__}: {e}"
            return list(self._cache_rows)

    # -- 跟遠端對照 ----------------------------------------------------------------
    def remote_url(self) -> str | None:
        if self._url is None:
            p = self._git_run(["remote", "get-url", self.remote], None)
            self._url = p.stdout.decode("utf-8", "replace").strip() if p.returncode == 0 else ""
        return self._url or None

    def check_remote(self) -> None:
        p = self._git_run(["ls-remote", self.remote, f"refs/heads/{self.branch}"], None)
        self._remote_checked_ms = int(time.time() * 1000)
        if p.returncode != 0:
            self._remote_err = _clean_stderr(p.stderr) or f"ls-remote exit {p.returncode}"
            return
        first = p.stdout.decode("ascii", "replace").split()
        self._remote_sha = first[0] if first else None
        self._remote_err = None if first else f"遠端沒有 {self.branch} 分支"

    def fetch(self) -> dict[str, Any]:
        p = self._git_run(["fetch", "--quiet", self.remote, self.branch], None)
        self._last_fetch_ms = int(time.time() * 1000)
        self._fetch_err = None if p.returncode == 0 else (
            _clean_stderr(p.stderr) or f"git fetch exit {p.returncode}")
        self.check_remote()
        return {"ok": self._fetch_err is None, "error": self._fetch_err}

    def _bg(self, allow_fetch: bool) -> None:
        if not self._busy.acquire(blocking=False):
            return
        try:
            now = time.time() * 1000
            due_fetch = (allow_fetch and self.fetch_every_s > 0
                         and (self._last_fetch_ms is None
                              or now - self._last_fetch_ms > self.fetch_every_s * 1000))
            if due_fetch:
                self.fetch()
            elif (self._remote_checked_ms is None
                  or now - self._remote_checked_ms > self._REMOTE_CHECK_S * 1000):
                self.check_remote()
        except Exception as e:
            self._remote_err = f"{type(e).__name__}: {e}"
        finally:
            self._busy.release()

    def kick(self, allow_fetch: bool) -> None:
        """到期就在背景 fetch／ls-remote；請求執行緒立刻返回。"""
        if self.configured:
            threading.Thread(target=self._bg, args=(allow_fetch,), daemon=True).start()

    def status(self) -> dict[str, Any]:
        if not self.configured:
            return {"configured": False}
        self.runs()  # 確保 local sha／快取是新的
        local = self._cache_sha
        remote = self._remote_sha
        return {
            "configured": True,
            "repo": str(self.repo_dir),
            "remote": self.remote,
            "branch": self.branch,
            "url": self.remote_url(),
            "local_sha": local,
            "remote_sha": remote,
            # None＝還沒查到遠端（不知道），不是「不一致」
            "in_sync": (local == remote) if (local and remote) else None,
            "remote_checked_ms": self._remote_checked_ms,
            "remote_error": self._remote_err,
            "last_fetch_ms": self._last_fetch_ms,
            "fetch_error": self._fetch_err,
            "read_error": self._read_err,
            **self._cache_meta,
        }


# --- trace 增量統計（infra_void 只在 trace、不在 ledger——run_x1 的 resume 設計）--

class TraceStats:
    """逐 lane 增量讀 *.trace.jsonl：void/總數、最後活動時戳、最近 N 筆精簡記錄。

    為什麼需要它：`run_x1` 的 infra_void **不寫 ledger**（瞬斷格子要在 resume 重試，
    不留永久洞），只落 trace——所以 09 §3.5 的「排除率 <5%」門檻只能從 trace 算。
    trace 每行含完整 prompt/answer（大），故用 offset 增量讀：每輪只讀新增位元組，
    剖析後**只留小欄位**（ts/task/family/outcome/policy/seed），prompt/answer 即棄。
    檔案被截短（重鑄 run）→ 該檔計數歸零重讀。server 重啟＝從頭掃一次（可接受）。
    """

    _RECENT_N = 30

    def __init__(self) -> None:
        # path → {"offset": int, "void": int, "total": int, "corrupt": int,
        #          "last_ts": int, "recent": list[dict]}
        self._files: dict[Path, dict[str, Any]] = {}

    def _update_file(self, path: Path) -> None:
        st = self._files.setdefault(
            path, {"offset": 0, "void": 0, "total": 0, "corrupt": 0,
                   "last_ts": 0, "recent": []})
        try:
            size = path.stat().st_size
        except OSError:
            return
        if size < st["offset"]:  # 截短＝重鑄：這個檔的貢獻歸零重讀
            st.update(offset=0, void=0, total=0, corrupt=0, last_ts=0, recent=[])
        if size == st["offset"]:
            return
        with path.open("rb") as f:
            f.seek(st["offset"])
            chunk = f.read()
        # 只吃到最後一個換行為止——半行（正在寫入中）留給下一輪
        nl = chunk.rfind(b"\n")
        if nl < 0:
            return
        st["offset"] += nl + 1
        for raw in chunk[:nl].split(b"\n"):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                st["corrupt"] += 1
                continue
            st["total"] += 1
            if rec.get("outcome") == "infra_void":
                st["void"] += 1
            ts = int(rec.get("ts_ms") or 0)
            if ts > st["last_ts"]:
                st["last_ts"] = ts
            st["recent"].append({k: rec.get(k) for k in
                                 ("ts_ms", "task", "family", "outcome",
                                  "policy", "seed", "infra_error")})
            del rec  # prompt/answer 隨整筆丟棄，不進駐記憶體
        st["recent"] = st["recent"][-self._RECENT_N:]

    def for_run(self, run_dir: Path) -> dict[str, Any]:
        """彙整一個 run 目錄下所有 lane 的 trace 統計（增量更新後回傳）。"""
        paths = sorted(run_dir.glob("*.trace.jsonl")) if run_dir.exists() else []
        void = total = corrupt = 0
        last_ts = 0
        recent: list[dict[str, Any]] = []
        for p in paths:
            self._update_file(p)
            st = self._files[p]
            void += st["void"]
            total += st["total"]
            corrupt += st["corrupt"]
            last_ts = max(last_ts, st["last_ts"])
            recent.extend(st["recent"])
        recent.sort(key=lambda r: r.get("ts_ms") or 0)
        return {
            "trace_void": void,
            "trace_total": total,
            "trace_corrupt": corrupt,
            # 09 §3.5 排除率口徑：void ÷ 全部嘗試（trace 含 pass/fail/void/skip 全記錄）
            "void_rate": round(void / total, 4) if total else None,
            "trace_last_ts_ms": last_ts,
            "recent": recent[-self._RECENT_N:],
        }


def _enrich(summary: dict[str, Any], trace: dict[str, Any],
            stall_min: float, now_ms: int,
            late_min: float | None = None) -> dict[str, Any]:
    """把 trace 統計＋停滯/完成判定併進 run 摘要（純函式，可測）。

    stalled 的誠實語意：「超過門檻沒有新進度的觀察」，不是「行程死了的推論」——
    面板顯示「無新進度 Xm」讓人自己判斷。已達 planned_total 的 run 標 finished，
    不再報停滯；從沒有任何活動的空 run 也不報（沒開始不等於卡住）。

    late 是停滯前的琥珀色中間態（Healthchecks 的 up→late→down 階梯）：超過
    late_min（預設取 stall_min 的一半）但還沒到 stall_min。與 stalled 互斥；
    同樣只是觀察，通知端刻意不理它（record/notify/page 分級——late 只上版面）。"""
    out = dict(summary)
    out.update(trace)
    last = max(out.get("last_activity_ms") or 0, trace.get("trace_last_ts_ms") or 0)
    idle_s = max(0, (now_ms - last) // 1000) if last else None
    planned = out.get("planned_total")
    finished = bool(planned and out.get("total_done", 0) >= planned)
    has_activity = bool(out.get("total_done", 0) or trace.get("trace_total", 0))
    out["idle_s"] = idle_s
    out["finished"] = finished
    out["stalled"] = bool(
        has_activity and not finished
        and idle_s is not None and idle_s > stall_min * 60)
    if late_min is None:
        late_min = stall_min / 2
    out["late"] = bool(
        has_activity and not finished and not out["stalled"]
        and idle_s is not None and idle_s > late_min * 60)
    return out


# --- 來源開關（feature：能調用所有資料、可以開關；磁碟即真相）------------------

class SourceToggles:
    """四個資料來源的開關，持久化在 runs_root/monitor_config.json。

    讀壞了當全開（跟 RunControl 同一容錯哲學：面板端的壞檔不該讓平台掛掉）。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, bool]:
        state = dict.fromkeys(SOURCES, True)
        if not self.path.exists():
            return state
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for k, v in (raw.get("sources") or {}).items():
                if k in state:
                    state[k] = bool(v)
        except (json.JSONDecodeError, OSError, ValueError):
            pass
        return state

    def all(self) -> dict[str, bool]:
        return self._read()

    def enabled(self, source: str) -> bool:
        return self._read().get(source, True)

    def set(self, source: str, enabled: bool) -> None:
        state = self._read()
        state[source] = bool(enabled)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"sources": state}, ensure_ascii=False), encoding="utf-8")


# --- eco 來源（信任生態 B）------------------------------------------------------

class EcoView:
    """既有生態的唯讀視圖＋兩個操作（trust 開關、wipe）。

    絕不在 root 不存在時建構 Ecosystem（那會生出居民）；建構時名冊從磁碟發現。
    eco 物件快取 _TTL 秒後重建，讓跨行程寫入（MCP server 的 delegate）反映到
    episodes/chain；chain_ok 在重建時算一次（每次輪詢全鏈重驗會隨 episode 數
    變貴——面板口徑，正式驗證用 `vacant verify`）。

    鏡像模式（B-4）：本機 root 不存在、但 mirror_dir 有 hermes 收取回來的遠端
    生態複本時，改讀鏡像並標 mirror=True；鏡像**唯讀**——trust/wipe 對複本
    操作是謊（遠端不會變），一律拒絕並指路去 VM 上操作。本機 root 存在時
    一律優先本機、忽略鏡像。"""

    _TTL = 10.0

    def __init__(self, root: Path | None, mirror_dir: Path | None = None) -> None:
        self.root = Path(root) if root else None
        self.mirror_dir = Path(mirror_dir) if mirror_dir else None
        self._hist_cache: tuple[tuple[int, int], dict[str, Any]] | None = None
        self._eco = None
        self._built_at = 0.0
        self._built_root: Path | None = None
        self._chain_ok: dict[str, bool] = {}

    # -- 磁碟發現（不經 Ecosystem，零副作用）--------------------------------------
    @staticmethod
    def _discover_names(root: Path) -> list[str]:
        rdir = root / "residents"
        if not rdir.is_dir():
            return []
        return sorted(
            p.name for p in rdir.iterdir()
            if (p / "trust" / "vacant_id").exists()
        )

    @staticmethod
    def _trust_on(root: Path) -> bool | None:
        p = root / "state.json"
        if not p.exists():
            return True  # 與 Ecosystem._load_trust_state 同預設
        try:
            return bool(json.loads(p.read_text(encoding="utf-8")).get("trust_on", True))
        except (json.JSONDecodeError, OSError, ValueError):
            return None

    def _local_exists(self) -> bool:
        return self.root is not None and bool(self._discover_names(self.root))

    def _mirror_exists(self) -> bool:
        return self.mirror_dir is not None and bool(self._discover_names(self.mirror_dir))

    def _serving(self) -> tuple[Path, bool] | None:
        """回 (生效的 root, 是否鏡像)；兩邊都沒有＝None。本機優先。"""
        if self._local_exists():
            return (self.root, False)  # type: ignore[return-value]
        if self._mirror_exists():
            return (self.mirror_dir, True)  # type: ignore[return-value]
        return None

    class _NullBrain:
        """監測面永不生成：真被呼叫到＝有讀取路徑觸發了模型呼叫，直接炸出來。"""

        name = "monitor(no-brain)"

        def generate(self, prompt: str) -> str:
            raise RuntimeError("run_monitor 不做生成——讀取路徑不該呼叫腦")

    def _build(self, root: Path):
        from .ecosystem import DEFAULT_ROSTER, Ecosystem

        names = self._discover_names(root)
        if not names:
            return None
        roster = {n: DEFAULT_ROSTER.get(n, "?") for n in names}
        return Ecosystem(root, self._NullBrain(), roster=roster)

    def _eco_cached(self, root: Path):
        now = time.monotonic()
        stale = (self._eco is None or self._built_root != root
                 or (now - self._built_at) > self._TTL)
        if stale:
            self._eco = self._build(root)
            self._built_at = now
            self._built_root = root
            # chain_ok 每次重建算一次（A-3）：輪詢讀快取值，不逐請求全鏈重驗
            self._chain_ok = {}
            if self._eco is not None:
                for r in self._eco.residents.values():
                    self._chain_ok[r.name] = r.body.logbook.verify_chain(
                        r.body.public_identity())
        return self._eco

    def invalidate(self) -> None:
        self._eco = None

    # -- 對外 --------------------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        if self.root is None:
            return {"configured": False}
        serving = self._serving()
        if serving is None:
            return {"configured": True, "exists": False, "root": str(self.root),
                    "mirror_available": False}
        root, is_mirror = serving

        from .ecosystem import INSUFFICIENT_DATA_N

        eco = self._eco_cached(root)
        assert eco is not None
        roster = []
        for r in eco.residents.values():
            score, obs = eco.registry.standing(r.vacant_id)  # 概覽口徑（跨 substrate）
            flags = []
            if obs < INSUFFICIENT_DATA_N:
                flags.append("INSUFFICIENT_DATA")
            if r.deliveries <= eco.probation_m:
                flags.append("PROBATION")
            roster.append({
                "name": r.name, "vacant_id": r.vacant_id[-12:], "tier": r.tier,
                "credit": round(score, 3), "n_obs": round(obs, 1),
                "deliveries": r.deliveries, "flags": flags,
                "episodes": len(r.stream.episodes()),
                "chain_ok": self._chain_ok.get(r.name, False),
            })
        hist = self._credit_history(root)
        # 自我核對：重放終值 vs registry 現值不符 → 列名不掩蓋（誠實紀律）
        hist["replay_mismatch"] = sorted(
            r["name"] for r in roster
            if hist["series"].get(r["name"])
            and abs(hist["series"][r["name"]][-1][1] - r["credit"]) > 0.005)
        out = {
            "configured": True, "exists": True, "root": str(root),
            "mirror": is_mirror,
            "trust_on": self._trust_on(root),
            "roster": roster,
            "scoreboard": eco.scoreboard(),
            "events": self._ledger_tail(root, 20),
            "credit_history": hist,
        }
        if is_mirror:
            marker = root / ".mirrored_at"
            try:
                out["mirrored_at_ms"] = int(marker.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                out["mirrored_at_ms"] = None
        return out

    @staticmethod
    def _ledger_tail(root: Path, n: int) -> list[dict[str, Any]]:
        p = root / "ledger" / "events.jsonl"
        if not p.exists():
            return []
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        out = []
        for ln in lines[-n:]:
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue  # 壞行不擋面板；鏈驗才是真相層
        return out

    def _credit_history(self, root: Path) -> dict[str, Any]:
        """信用重放（純讀 ledger，不建 registry）：每 agent 的 credit 時間序列。

        可行等價性：ecosystem 互審的五維分數就是 verdict 全 1.0/0.0（五維同值），
        REVIEW 事件又記錄了實際採計權重（同源降權後）——五維 Beta 同步等值更新
        等價於單一 Beta：α += w·s、β += w·(1−s)，credit = α/(α+β)，初始 Beta(1,1)
        = 0.5。SLASH 目前只記帳不扣分（reputation 牙齒是 W2+ 後推項），故重放
        只需 REVIEW 與 WIPE（重置 Beta），SLASH/WIPE 另出標記給圖上畫紅點。

        口徑差異要誠實：registry.standing 是跨 substrate 平均，重放把所有 REVIEW
        併進單一 Beta——單 substrate 下兩者相等；若未來多 substrate 造成偏差，
        由呼叫端拿重放終值對 roster 現值核對（replay_mismatch）標出來，不掩蓋。
        """
        p = root / "ledger" / "events.jsonl"
        if not p.exists():
            return {"series": {}, "marks": [], "n_events": 0}
        st = p.stat()
        key = (int(st.st_mtime_ns), int(st.st_size))
        if self._hist_cache and self._hist_cache[0] == key:
            return self._hist_cache[1]
        ab: dict[str, list[float]] = {}          # name -> [α, β]
        series: dict[str, list[list[float]]] = {}  # name -> [[ts_ms, credit], ...]
        marks: list[dict[str, Any]] = []
        n_events = 0
        t0: int | None = None
        t1: int | None = None
        for ln in p.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                ev = json.loads(ln)
            except ValueError:
                continue  # 壞行不擋圖；鏈驗才是真相層
            n_events += 1
            et, ts = ev.get("type"), ev.get("ts_ms")
            tgt = ev.get("target")
            if ts:
                t0 = ts if t0 is None else min(t0, ts)
                t1 = ts if t1 is None else max(t1, ts)
            if not ts or not tgt:
                continue
            if et == "REVIEW":
                a_b = ab.setdefault(tgt, [1.0, 1.0])
                w = float(ev.get("weight") or 0.0)
                s = 1.0 if ev.get("verdict") == "PASS" else 0.0
                a_b[0] += w * s
                a_b[1] += w * (1.0 - s)
                series.setdefault(tgt, []).append(
                    [ts, round(a_b[0] / (a_b[0] + a_b[1]), 4)])
            elif et == "WIPE":
                ab[tgt] = [1.0, 1.0]
                series.setdefault(tgt, []).append([ts, 0.5])
                marks.append({"ts_ms": ts, "type": "WIPE", "target": tgt})
            elif et == "SLASH":
                marks.append({"ts_ms": ts, "type": "SLASH", "target": tgt,
                              "task_id": ev.get("task_id"),
                              "reason": (ev.get("reason") or "")[:80]})
        out = {"series": series, "marks": marks, "n_events": n_events,
               "t0_ms": t0, "t1_ms": t1}
        self._hist_cache = (key, out)
        return out

    def _refuse_if_mirror(self) -> dict[str, Any] | None:
        serving = self._serving()
        if serving is not None and serving[1]:
            return {"ok": False,
                    "error": "目前顯示的是遠端鏡像（唯讀）——對複本操作不會改變遠端；"
                             "請到 VM 上用 vacant toggle / vacant resident wipe 操作"}
        return None

    def toggle_trust(self, on: bool) -> dict[str, Any]:
        """鏡像 cmd_eco_toggle：直接寫 state.json，不必建生態。"""
        assert self.root is not None
        refused = self._refuse_if_mirror()
        if refused:
            return refused
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "state.json").write_text(
            json.dumps({"trust_on": bool(on)}), encoding="utf-8")
        self.invalidate()
        return {"ok": True, "trust_on": bool(on)}

    def wipe(self, name: str) -> dict[str, Any]:
        refused = self._refuse_if_mirror()
        if refused:
            return refused
        serving = self._serving()
        if serving is None:
            return {"ok": False, "error": "生態不存在"}
        eco = self._eco_cached(serving[0])
        if eco is None or name not in eco.residents:
            known = ", ".join(eco.residents) if eco else "（生態不存在）"
            return {"ok": False, "error": f"找不到居民：{name}（居民：{known}）"}
        res = eco.wipe(name)
        self.invalidate()
        return {"ok": True, **res}


# --- lmstudio 來源（機群 hub 代理 C）--------------------------------------------

def _percentile(sorted_vals: list[float], p: float) -> float:
    idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * p))
    return sorted_vals[idx]


class LMStudioProxy:
    """伺服器端代理一至多個 hub 的 /_mon/api/*；快取避免每輪輪詢都打上游。

    每個 hub 一張卡：overview（成功快取 3s／失敗 15s——斷線 hub 若照成功節奏
    重試，每 3 秒就有一發 GET 吃滿 timeout 拖慢整個面板）＋ extras（15s 快取）：
      - probe：最近 ≤200 筆 chat 完成的 per-machine median/p95 延遲與 tok/s
        （「平均延遲」會被思考模式長呼叫拉爆——P1-0 機時重估要的就是這組分布）
      - errors：最近錯誤請求（only_errors）
      - events：模型載入/卸載事件（解釋延遲斷崖：JIT 載入的那 45 秒）
    """

    _TTL_OK = 3.0
    _TTL_ERR = 15.0
    _TTL_EXTRA = 15.0

    def __init__(self, urls: str | list[str] | tuple[str, ...],
                 http_get: Callable[[str], bytes] | None = None) -> None:
        if isinstance(urls, str):
            urls = [u.strip() for u in urls.split(",") if u.strip()]
        self.urls = [u.rstrip("/") for u in (urls or [])]
        self._http_get = http_get or self._default_get
        self._ov_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._ex_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    @staticmethod
    def _default_get(url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.read()

    def _hub_overview(self, url: str) -> dict[str, Any]:
        now = time.monotonic()
        cached = self._ov_cache.get(url)
        if cached:
            ttl = self._TTL_OK if cached[1].get("ok") else self._TTL_ERR
            if now - cached[0] < ttl:
                return cached[1]
        try:
            raw = self._http_get(f"{url}/_mon/api/overview?window_hours=24")
            payload: dict[str, Any] = {"ok": True, "url": url, "overview": json.loads(raw)}
        except Exception as e:  # hub 掛了/網路斷：誠實回報，不假裝有資料
            payload = {"ok": False, "url": url, "error": f"{type(e).__name__}: {e}"}
        self._ov_cache[url] = (now, payload)
        return payload

    def _hub_extras(self, url: str) -> dict[str, Any]:
        now = time.monotonic()
        cached = self._ex_cache.get(url)
        if cached and now - cached[0] < self._TTL_EXTRA:
            return cached[1]
        extras: dict[str, Any] = {}
        try:
            rows = json.loads(self._http_get(f"{url}/_mon/api/logs?limit=200"))
            rows = rows if isinstance(rows, list) else []
            extras["probe"] = self._probe(rows)
            # 原始請求列（壓縮欄位）：給前端畫「請求量×延遲」時間軸——
            # 之前只煮成中位數就丟掉，延遲斷崖跟 JIT 載入的因果只能用文字講
            extras["reqlog"] = [
                {"ts": r["ts"], "m": str(r.get("machine") or "?"),
                 "lat": r.get("latency_ms"),
                 "ok": r.get("status_code") == 200,
                 "chat": "chat" in str(r.get("path") or "")}
                for r in rows if r.get("ts")]
        except Exception:
            extras["probe"] = {}
            extras["reqlog"] = []
        try:
            errs = json.loads(self._http_get(f"{url}/_mon/api/logs?limit=5&only_errors=true"))
            extras["errors"] = [
                {"ts": r.get("ts"), "machine": r.get("machine"), "model": r.get("model"),
                 "status": r.get("status_code"), "path": r.get("path"),
                 "error": (r.get("error") or "")[:120]}
                for r in (errs if isinstance(errs, list) else [])]
        except Exception:
            extras["errors"] = []
        try:
            ev = json.loads(self._http_get(f"{url}/api/events?limit=24"))
            extras["events"] = (ev.get("events") if isinstance(ev, dict) else ev) or []
        except Exception:
            extras["events"] = []  # 舊版 hub 沒有 /api/events：容忍
        self._ex_cache[url] = (now, extras)
        return extras

    @staticmethod
    def _probe(rows: list[dict]) -> dict[str, Any]:
        """per-machine chat 完成的延遲分布與吞吐（中位數口徑，抗長呼叫離群）。"""
        by_m: dict[str, dict[str, list[float]]] = {}
        for r in rows:
            if "chat" not in str(r.get("path") or ""):
                continue
            if r.get("status_code") != 200 or not r.get("latency_ms"):
                continue
            m = str(r.get("machine") or "?")
            s = by_m.setdefault(m, {"lat": [], "toks": []})
            lat = float(r["latency_ms"])
            s["lat"].append(lat)
            ct = r.get("completion_tokens")
            if ct and lat > 0:
                s["toks"].append(float(ct) / (lat / 1000))
        out = {}
        for m, s in by_m.items():
            lat = sorted(s["lat"])
            toks = sorted(s["toks"])
            out[m] = {
                "n": len(lat),
                "med_ms": round(_percentile(lat, 0.5)),
                "p95_ms": round(_percentile(lat, 0.95)),
                "med_tok_s": round(_percentile(toks, 0.5), 1) if toks else None,
            }
        return out

    def overview(self) -> dict[str, Any]:
        if not self.urls:
            return {"configured": False}
        hubs = []
        for url in self.urls:
            hub = dict(self._hub_overview(url))
            if hub.get("ok"):
                hub.update(self._hub_extras(url))
            hubs.append(hub)
        return {"configured": True, "hubs": hubs}


# --- hermes 來源（遠端日誌收取）--------------------------------------------------

def _ssh_exe() -> str:
    """Windows 上鎖定內建 OpenSSH 絕對路徑。

    監測台若由某些啟動器帶起（PATH 裡 Git 的 mingw ssh 排前面），mingw ssh 在
    無 tty 的 subprocess 下會掛死到 timeout——實測過的坑，別靠 PATH 碰運氣。"""
    import os
    if os.name == "nt":
        cand = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/OpenSSH/ssh.exe"
        if cand.exists():
            return str(cand)
    return "ssh"


def _default_ssh_run(host: str, command: str) -> subprocess.CompletedProcess:
    """BatchMode 限定：沒金鑰＝立刻失敗（不會卡在 password 提示）——P0-4 紀律。"""
    return subprocess.run(
        [_ssh_exe(), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
         "-o", "ConnectTimeout=6", host, command],
        capture_output=True, timeout=25, stdin=subprocess.DEVNULL,
    )


# ssh 客戶端的例行噪音（資訊性警告）——錯誤顯示前濾掉，別讓它蓋住真正的錯誤
_SSH_NOISE = (
    "post-quantum key exchange",
    "store now, decrypt later",
    "The server may need to be upgraded",
    "Warning: Permanently added",
)


def _clean_stderr(raw: bytes | None) -> str:
    lines = (raw or b"").decode("utf-8", errors="replace").splitlines()
    keep = [ln for ln in lines
            if ln.strip() and not any(n in ln for n in _SSH_NOISE)
            and not ln.startswith("** ")]
    return "\n".join(keep).strip()


class HermesLogs:
    """向 Hermes 所在機器逐檔 tail 日誌；成功存進 save_dir，失敗誠實回報。

    另提供 mirror_eco（B-4）：`ssh tar` 把遠端生態根整包拉回 mirror_dir，
    給 EcoView 的鏡像模式讀——鏡像是複本快照，不是即時，面板會標收取時間。"""

    def __init__(
        self,
        ssh_host: str,
        paths: tuple[str, ...],
        save_dir: Path,
        ssh_run: Callable[[str, str], subprocess.CompletedProcess] | None = None,
        eco_remote_root: str = "",
        mirror_dir: Path | None = None,
    ) -> None:
        self.ssh_host = ssh_host or ""
        self.paths = tuple(paths) or DEFAULT_HERMES_PATHS
        self.save_dir = Path(save_dir)
        self._ssh_run = ssh_run or _default_ssh_run
        self.eco_remote_root = eco_remote_root or ""
        self.mirror_dir = Path(mirror_dir) if mirror_dir else None
        self.last: dict[str, Any] | None = None  # 上次收取結果（記憶體）
        self.last_mirror: dict[str, Any] | None = None

    def config(self) -> dict[str, Any]:
        return {
            "configured": bool(self.ssh_host),
            "host": self.ssh_host,
            "paths": list(self.paths),
            "save_dir": str(self.save_dir),
            "eco_remote_root": self.eco_remote_root,
            "last": self.last,
            "last_mirror": self.last_mirror,
        }

    _MIRROR_LOCK = threading.Lock()  # 行程內互斥：管家自動鏡像 vs 上線補收 vs 手動鈕

    def mirror_eco(self) -> dict[str, Any]:
        """把遠端生態根 tar 回 mirror_dir（先清舊鏡像再解，快照語意）。"""
        import io
        import shutil
        import tarfile

        if not self.ssh_host:
            return {"ok": False, "error": "未設定 --hermes-ssh"}
        if not self.eco_remote_root or self.mirror_dir is None:
            return {"ok": False, "error": "未設定 --hermes-eco-root"}
        try:
            proc = self._ssh_run(
                self.ssh_host, f"tar -C {shlex.quote(self.eco_remote_root)} -cf - .")
        except Exception as e:
            out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            self.last_mirror = out
            return out
        if proc.returncode != 0 or not proc.stdout:
            err = _clean_stderr(proc.stderr)
            out = {"ok": False, "error": err or f"ssh exit {proc.returncode}"}
            low = err.lower()
            if "permission denied" in low or "password" in low:
                out["hint"] = _SSH_KEY_HINT.replace("<host>", self.ssh_host)
            self.last_mirror = out
            return out
        try:
            with self._MIRROR_LOCK:
                if self.mirror_dir.exists():
                    shutil.rmtree(self.mirror_dir)
                self.mirror_dir.mkdir(parents=True, exist_ok=True)
                with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tf:
                    # filter="data"（3.12 內建）擋路徑穿越/絕對路徑/裝置檔
                    tf.extractall(self.mirror_dir, filter="data")
                    n_files = len(tf.getnames())
                (self.mirror_dir / ".mirrored_at").write_text(
                    str(int(time.time() * 1000)), encoding="utf-8")
        except (tarfile.TarError, OSError) as e:
            out = {"ok": False, "error": f"解包失敗：{type(e).__name__}: {e}"}
            self.last_mirror = out
            return out
        out = {"ok": True, "files": n_files, "bytes": len(proc.stdout),
               "mirror_dir": str(self.mirror_dir),
               "fetched_at_ms": int(time.time() * 1000)}
        self.last_mirror = out
        return out

    def _fetch_one(self, path: str) -> dict[str, Any]:
        """單檔增量收取：本機 full_<name> 的大小＝已收 offset，只拉遠端新增段。

        遠端重鑄（重開機/輪替 → 遠端變小）：本機舊史改名歸檔、從頭重拉——
        歷史永不覆蓋。每次收取後對完整副本簽 sha256 記進 index.jsonl。"""
        base = Path(path).name
        full = self.save_dir / f"full_{base}"
        entry: dict[str, Any] = {"path": path}
        data = b""
        for _round in range(2):  # 第二輪只在偵測到遠端重鑄時發生
            offset = full.stat().st_size if full.exists() else 0
            q = shlex.quote(path)
            cmd = (f'sz=$(wc -c < {q} 2>/dev/null || echo -1); echo "SIZE:$sz"; '
                   f'tail -c +{offset + 1} {q} 2>/dev/null')
            proc = self._ssh_run(self.ssh_host, cmd)
            if proc.returncode != 0:
                entry.update(ok=False,
                             error=_clean_stderr(proc.stderr) or f"ssh exit {proc.returncode}")
                return entry
            stdout = proc.stdout or b""
            nl = stdout.find(b"\n")
            header = stdout[:nl].decode("ascii", "replace") if nl >= 0 else ""
            if not header.startswith("SIZE:"):
                entry.update(ok=False, error=f"非預期輸出：{header[:60]!r}")
                return entry
            try:
                remote_size = int(header[5:].strip())
            except ValueError:
                remote_size = -1
            data = stdout[nl + 1:]
            if remote_size < 0:
                entry.update(ok=False, error="遠端檔案不存在（可能還沒被寫入）")
                return entry
            if remote_size < offset:
                self.save_dir.mkdir(parents=True, exist_ok=True)
                stamp = time.strftime("%Y%m%d-%H%M%S")
                full.rename(self.save_dir / f"archive_{stamp}_{base}")
                continue  # 重鑄：歸檔舊史，從頭重拉
            break
        self.save_dir.mkdir(parents=True, exist_ok=True)
        if data:
            with full.open("ab") as f:
                f.write(data)
        raw = full.read_bytes() if full.exists() else b""
        sha = hashlib.sha256(raw).hexdigest() if raw else None
        with (self.save_dir / "index.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts_ms": int(time.time() * 1000), "path": path,
                                "new_bytes": len(data), "total_bytes": len(raw),
                                "sha256": sha}, ensure_ascii=False) + "\n")
        entry.update(ok=True, new_bytes=len(data), total_bytes=len(raw),
                     saved_to=str(full), sha256=sha,
                     tail=raw[-3000:].decode("utf-8", errors="replace"))
        return entry

    def fetch(self) -> dict[str, Any]:
        if not self.ssh_host:
            return {"ok": False, "error": "未設定 --hermes-ssh（例：zongon@100.118.96.3）"}
        results = []
        auth_failed = False
        for path in self.paths:
            try:
                entry = self._fetch_one(path)
            except Exception as e:  # subprocess timeout / ssh 不存在等
                entry = {"path": path, "ok": False, "error": f"{type(e).__name__}: {e}"}
            if not entry.get("ok"):
                low = (entry.get("error") or "").lower()
                if "permission denied" in low or "password" in low:
                    auth_failed = True
            results.append(entry)
        out: dict[str, Any] = {
            "ok": any(r.get("ok") for r in results),
            "host": self.ssh_host,
            "fetched_at_ms": int(time.time() * 1000),
            "results": results,
        }
        if auth_failed:
            out["hint"] = _SSH_KEY_HINT.replace("<host>", self.ssh_host)
        self.last = out
        return out

    def app_records(self, limit: int = 20) -> list[dict[str, Any]]:
        """本機 full app trace 的結構化尾巴（給面板渲染「模型 I/O 記錄」）。"""
        target = None
        for p in self.paths:
            if "app" in Path(p).name:
                target = self.save_dir / f"full_{Path(p).name}"
                break
        if target is None or not target.exists():
            return []
        out = []
        for ln in target.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            out.append({
                "t": r.get("t"), "kind": r.get("kind") or r.get("tool") or "?",
                "brain": r.get("brain"), "latency_s": r.get("latency_s"),
                "prompt": (r.get("prompt") or "")[:2000],
                "answer": (r.get("answer") or "")[:2000],
                "error": r.get("error"), "verified": r.get("verified"),
                "human": _humanize_trace(r),
            })
        return out[-limit:]


# --- hermes 即時串流（ssh tail -F 直播＋斷線退避重連＋上線自動補收）---------------

_LIVE_READY = "VACANT_LIVE_READY"
_TAIL_HEADER = re.compile(r"^==> (.+) <==$")


def _default_live_popen(host: str, command: str) -> subprocess.Popen:
    """常駐 ssh：BatchMode（沒金鑰立刻失敗）＋ keepalive（半死連線最終 EOF）。"""
    return subprocess.Popen(
        [_ssh_exe(), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
         "-o", "ConnectTimeout=6", "-o", "ServerAliveInterval=10",
         "-o", "ServerAliveCountMax=3", host, command],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)


def _humanize_trace(rec: dict[str, Any]) -> str | None:
    """trace 行 → 一句人話（繁中）。認不出的型別回 None（面板保留原文）。

    這層只是「翻譯」，不是資料來源——原始 JSON 一字不動地留在 raw 與收取檔，
    要對帳永遠以原始紀錄為準。"""
    # wire 格式：{"dir": "hermes->vacant", "msg": {...jsonrpc...}}
    msg = rec.get("msg")
    if isinstance(msg, dict):
        d = str(rec.get("dir") or "")
        who = ("Hermes → vacant" if d.startswith("hermes")
               else "vacant → Hermes" if d else "")
        m = msg.get("method")
        if m == "ping":
            return f"{who}：確認在線（ping）"
        if m == "initialize":
            return f"{who}：建立連線（initialize 握手）"
        if m == "notifications/initialized":
            return f"{who}：連線就緒"
        if m == "tools/list":
            return f"{who}：詢問有哪些工具可用"
        if m == "tools/call":
            name = (msg.get("params") or {}).get("name") or "?"
            return f"{who}：呼叫工具「{name}」"
        if isinstance(m, str):
            return f"{who}：{m}"
        if "result" in msg:
            r = msg.get("result")
            if isinstance(r, dict) and isinstance(r.get("tools"), list):
                return f"{who}：回覆工具清單（{len(r['tools'])} 個工具）"
            if r == {}:
                return f"{who}：回覆 OK"
            return f"{who}：回覆結果"
        if "error" in msg:
            err = msg.get("error")
            detail = (err.get("message") or "")[:60] if isinstance(err, dict) else ""
            return f"{who}：回覆錯誤{('——' + detail) if detail else ''}"
        return None
    # app 格式：{"kind": "generate", "brain": ..., "latency_s": ..., ...}
    kind = rec.get("kind") or rec.get("tool")
    if kind:
        parts = [f"模型呼叫「{kind}」"]
        if rec.get("brain"):
            parts.append(f"用 {rec['brain']}")
        if rec.get("latency_s") is not None:
            parts.append(f"耗時 {rec['latency_s']}s")
        if rec.get("caller"):
            parts.append(f"來源 {rec['caller']}")
        s = "，".join(parts)
        if rec.get("error"):
            s += "——出錯了"
        elif rec.get("verified") is True:
            s += "——已驗證通過"
        return s
    return None


def _live_summarize(rec: dict[str, Any]) -> dict[str, Any]:
    """app/wire trace 行的白名單摘要（面板即時列表用；全文仍在 raw/收取檔）。"""
    out: dict[str, Any] = {}
    for k in ("t", "ts_ms", "kind", "tool", "brain", "caller", "latency_s",
              "verified", "error", "dir", "method"):
        if rec.get(k) is not None:
            out[k] = rec[k]
    for k in ("prompt", "answer", "text", "body"):
        v = rec.get(k)
        if isinstance(v, str) and v:
            out[k] = v[:2000]
    human = _humanize_trace(rec)
    if human:
        out["human"] = human
    return out


class HermesLive(threading.Thread):
    """對 Hermes 機器保持一條 `ssh tail -F` 常駐串流——監測台的「直播」升級。

    - 遠端指令先 `echo VACANT_LIVE_READY` 再 `tail -n 0 -F`：連上必有第一行，
      connecting→online 的狀態轉換不靠猜。
    - VM 離線／連線死掉：EOF → 退避重連（5→60s 封頂），面板誠實標「離線·重試中」
      ——不裝在線、不掛死。
    - 離線→在線轉換：自動觸發 HermesLogs.fetch()（增量補收斷線期間的歷史）與
      mirror_eco()——VM 一開機，資料自己接上，實驗自動走下去，人不用在場。
    - tail -F 對還不存在的檔案會等它出現（stderr 已靜音）：VM 在線但 trace
      未生成時，狀態仍誠實顯示 online（連線是真的，只是還沒有流量）。
    """

    BACKOFF = (5.0, 10.0, 20.0, 40.0, 60.0)

    def __init__(self, hermes: HermesLogs, stop_ev: threading.Event, *,
                 popen: Callable[[str, str], Any] | None = None,
                 ring_size: int = 200, catchup: bool = True) -> None:
        super().__init__(daemon=True, name="vacant-mon-hermes-live")
        self._hermes = hermes
        self._stop_ev = stop_ev
        self._popen = popen or _default_live_popen
        self._catchup_on = catchup
        self._ring: collections.deque[dict[str, Any]] = collections.deque(maxlen=ring_size)
        self._lock = threading.Lock()
        self._proc: Any = None
        self._cur_file = "?"
        self._seq = 0
        self.status = "starting"          # starting|connecting|online|offline|stopped
        self.last_error = ""
        self.connected_at_ms: int | None = None
        self.last_line_ms: int | None = None
        self.retry_in_s: float | None = None
        self.fails = 0
        self.catchups = 0

    # -- 對外 --------------------------------------------------------------

    def snapshot(self, limit: int = 30) -> dict[str, Any]:
        with self._lock:
            return {
                "running": True, "status": self.status, "error": self.last_error,
                "connected_at_ms": self.connected_at_ms,
                "last_line_ms": self.last_line_ms,
                "retry_in_s": self.retry_in_s, "fails": self.fails,
                "catchups": self.catchups,
                "entries": list(self._ring)[-max(0, limit):],
            }

    def close(self) -> None:
        """shutdown 用：殺掉常駐 ssh，讓阻塞中的 readline 立刻 EOF。"""
        proc = self._proc
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass

    @classmethod
    def backoff_delay(cls, fails: int) -> float:
        return cls.BACKOFF[min(max(fails, 1), len(cls.BACKOFF)) - 1]

    # -- 主迴圈 ------------------------------------------------------------

    def run(self) -> None:
        files = " ".join(shlex.quote(p) for p in self._hermes.paths)
        cmd = f"echo {_LIVE_READY}; exec tail -n 0 -F {files} 2>/dev/null"
        while not self._stop_ev.is_set():
            with self._lock:
                self.status, self.retry_in_s = "connecting", None
            err_lines: list[bytes] = []
            try:
                proc = self._popen(self._hermes.ssh_host, cmd)
                self._proc = proc
                if proc.stderr is not None:
                    threading.Thread(target=self._drain, args=(proc.stderr, err_lines),
                                     daemon=True).start()
                self._read_stream(proc.stdout)
                try:
                    proc.kill()
                except Exception:
                    pass
            except Exception as e:
                err_lines.append(f"{type(e).__name__}: {e}".encode())
            finally:
                self._proc = None
            if self._stop_ev.is_set():
                break
            err = _clean_stderr(b"\n".join(err_lines))
            with self._lock:
                self.status = "offline"
                self.last_error = err or "連線中斷（EOF）"
                self.fails += 1
                self.retry_in_s = self.backoff_delay(self.fails)
            if self._stop_ev.wait(self.retry_in_s):
                break
        with self._lock:
            self.status = "stopped"

    @staticmethod
    def _drain(stream: Any, sink: list[bytes]) -> None:
        try:
            for ln in iter(stream.readline, b""):
                if len(sink) < 50:
                    sink.append(ln.rstrip())
        except Exception:
            pass

    def _read_stream(self, stdout: Any) -> None:
        got_first = False
        for raw in iter(stdout.readline, b""):
            if self._stop_ev.is_set():
                return
            text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not got_first:
                got_first = True
                self._on_online()
                if _LIVE_READY in text:
                    continue  # hello 行本身不進 ring
            self._ingest(text)

    def _on_online(self) -> None:
        with self._lock:
            self.status = "online"
            self.last_error = ""
            self.connected_at_ms = int(time.time() * 1000)
            self.fails = 0
            self.retry_in_s = None
        if self._catchup_on:
            threading.Thread(target=self._catchup, daemon=True,
                             name="vacant-mon-hermes-catchup").start()

    def _catchup(self) -> None:
        """上線補收：斷線期間的歷史用既有增量收取拉齊；失手不影響直播。"""
        try:
            self._hermes.fetch()
        except Exception:
            pass
        if self._hermes.eco_remote_root and self._hermes.mirror_dir is not None:
            try:
                self._hermes.mirror_eco()
            except Exception:
                pass
        with self._lock:
            self.catchups += 1

    def _ingest(self, text: str) -> None:
        m = _TAIL_HEADER.match(text)
        if m:
            self._cur_file = Path(m.group(1)).name
            return
        if not text.strip():
            return
        self._seq += 1
        entry: dict[str, Any] = {
            "seq": self._seq, "ts_ms": int(time.time() * 1000),
            "file": self._cur_file, "raw": text[:4000],
        }
        try:
            rec = json.loads(text)
        except ValueError:
            rec = None
        if isinstance(rec, dict):
            entry["rec"] = _live_summarize(rec)
        with self._lock:
            self._ring.append(entry)
            self.last_line_ms = entry["ts_ms"]


# --- 閘道側記錄對帳（B4：獨立第三方記錄，防自家漏筆）-----------------------------

def _default_pull_get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read()


def pull_gateway_records(
    runs_root: Path, run_id: str, url: str,
    http_get: Callable[[str], bytes] | None = None, pad_s: int = 120,
) -> dict[str, Any]:
    """把 hub 監測站在該 run 時間窗內的完整請求記錄拉存進 run 目錄。

    時間窗由 run 自己的 ledger/trace 時戳界定（±pad_s）。存檔格式＝hub 的
    原樣回應＋meta（來源/窗口/筆數）——外部格式不改寫；RECORD_SPEC（P0-1）
    定案後由 `vacant record pack` 收編。"""
    d = _run_dir(Path(runs_root), run_id)
    stamps = [int(r["ts_ms"]) for r in RunLedger(d / "ledger.jsonl").records()
              if r.get("ts_ms")]
    trace = TraceStats().for_run(d)
    if trace.get("trace_last_ts_ms"):
        stamps.append(trace["trace_last_ts_ms"])
    if not stamps:
        return {"ok": False, "error": "run 沒有任何時間戳，無法界定時間窗"}
    since = min(stamps) // 1000 - pad_s
    until = max(stamps) // 1000 + pad_s
    get = http_get or _default_pull_get
    base_api = (f"{url.rstrip('/')}/api/requests?since={since}&until={until}"
                f"&include_bodies=true&limit=1000")  # hub 上限 1000/頁 → after_id 分頁
    rows: list = []
    after_id = None
    api = base_api
    for _page in range(50):  # 護欄：最多 5 萬筆
        api = base_api + (f"&after_id={after_id}" if after_id is not None else "")
        try:
            data = json.loads(get(api))
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}", "url": api}
        page = data.get("rows") if isinstance(data, dict) else data
        page = page if isinstance(page, list) else []
        rows.extend(page)
        if len(page) < 1000:
            break
        ids = [r.get("id") for r in page if isinstance(r, dict) and r.get("id") is not None]
        if not ids:
            break  # 沒有 id 可分頁：只能拿到第一頁，誠實停（meta 會記筆數）
        after_id = max(ids)
    out_path = d / "gateway_records.json"
    out_path.write_text(json.dumps({
        "meta": {"source_url": base_api, "since": since, "until": until,
                 "fetched_at_ms": int(time.time() * 1000), "count": len(rows)},
        "rows": rows,
    }, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "count": len(rows), "saved_to": str(out_path),
            "window": [since, until]}


# --- 管家執行緒（L3 自動收取 ＋ B3 狀態變化推播）---------------------------------

def _default_notify_post(url: str, text: str) -> None:
    req = urllib.request.Request(
        url, data=text.encode("utf-8"),
        headers={"Content-Type": "text/plain; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(req, timeout=6):
        pass


class _Housekeeper(threading.Thread):
    """背景管家：定期自動收取 hermes logs；run 狀態變化（停滯/void 超標/完成）
    推播到 notify_url（如 ntfy.sh/<topic>）。只在狀態**轉變**時推一次，不轟炸。"""

    def __init__(self, ctx: "_Ctx", stop_ev: threading.Event, *,
                 hermes_auto_s: float, notify_url: str,
                 notify_post: Callable[[str, str], None], tick_s: float) -> None:
        super().__init__(daemon=True, name="vacant-mon-housekeeper")
        self._ctx = ctx
        self._stop = stop_ev
        self._auto_s = hermes_auto_s
        self._notify_url = notify_url
        self._post = notify_post
        self._tick = tick_s
        self._state: dict[str, dict[str, bool]] = {}
        self._last_fetch = 0.0

    def run(self) -> None:
        while not self._stop.wait(self._tick):
            now = time.monotonic()
            try:
                if (self._auto_s > 0 and self._ctx.hermes.ssh_host
                        and self._ctx.toggles.enabled("hermes")
                        and now - self._last_fetch >= self._auto_s):
                    self._last_fetch = now
                    self._ctx.hermes.fetch()
            except Exception:
                pass  # 管家失手不影響服務；下一輪再試
            try:
                if self._notify_url and self._ctx.toggles.enabled("runs"):
                    self._check_runs()
            except Exception:
                pass

    def _check_runs(self) -> None:
        for s in scan_runs(self._ctx.runs_root):
            e = _enrich(s, self._ctx.trace_stats.for_run(
                _run_dir(self._ctx.runs_root, s["run_id"])),
                self._ctx.stall_min, int(time.time() * 1000))
            st = self._state.setdefault(e["run_id"], {})
            msgs = []
            if e["stalled"] and not st.get("stalled"):
                msgs.append(f"⚠ {e['run_id']} 無新進度 {(e['idle_s'] or 0) // 60} 分鐘")
            st["stalled"] = bool(e["stalled"])
            hot = bool((e.get("void_rate") or 0) > 0.05)
            if hot and not st.get("void"):
                msgs.append(f"⚠ {e['run_id']} infra_void 率 "
                            f"{(e.get('void_rate') or 0) * 100:.1f}%（>5% 門檻）")
            st["void"] = hot
            if e["finished"] and not st.get("finished"):
                msgs.append(f"✅ {e['run_id']} 完成 {e['total_done']}/{e.get('planned_total')}")
            st["finished"] = bool(e["finished"])
            for m in msgs:
                try:
                    self._post(self._notify_url, m)
                except Exception:
                    pass  # 推播失敗不重試（下次狀態轉變再推）；面板才是主要通道


# --- 內嵌單頁（無框架/無 CDN）----------------------------------------------------

_PAGE = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0e0f13">
<link rel="manifest" href="/manifest.json">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<title>Vacant — 監測台</title>
<style>
  /* ---- tokens：既有 8 色不動；衍生 token 收編原硬編碼（#12151c/#0c0e13/#20242f） ---- */
  /* 2026-08 重設計：near-black 分層（bg < panel < tile）＋ glow 語彙。
     深色系卡片比容器「淺一階」做層次（業界深色慣例）；亮色 token 組另行翻面 */
  :root { color-scheme: dark; --bg:#0e0f13; --panel:#14161d; --ink:#e6e8ee;
          --muted:#9aa1b0; --line:#262b36; --ok:#3ecf8e; --warn:#f0b429; --bad:#ff5470;
          --accent:#6ea8fe;
          --tile:#1a1e29; --inset:#0b0d12; --hover:#232937;
          --faint:#5c6375;  /* 第三層文字：說明句、軸標，比 --muted 再退一階 */
          --violet:#a78bfa;
          --glow-accent:0 0 12px rgba(110,168,254,.30);
          --glow-ok:0 0 10px rgba(62,207,142,.32);
          --glow-bad:0 0 10px rgba(255,84,112,.32);
          --line-soft:rgba(255,255,255,.05);
          --accent-soft:rgba(110,168,254,.12); --ok-soft:rgba(62,207,142,.12);
          --warn-soft:rgba(240,180,41,.12); --bad-soft:rgba(255,84,112,.14);
          --ok-ring:rgba(62,207,142,.4); --bad-ring:rgba(255,84,112,.4);
          --grid-dot:rgba(255,255,255,.035);
          --shadow-float:0 8px 24px rgba(0,0,0,.45), 0 2px 6px rgba(0,0,0,.35);
          /* 圖表軸線／刻度（亮色模式要翻黑，故收 token；SVG 屬性吃 var() 已實測） */
          --ax-soft:rgba(255,255,255,.055); --ax:rgba(255,255,255,.12);
          --ax-mid:rgba(255,255,255,.2); --ax-strong:rgba(255,255,255,.3);
          --ser2:#c792ea; --ser3:#ff9e64;  /* 圖表第 2/3 序列色（機器分色） */
          --sb-thumb:#2a303c; --topbar-bg:rgba(14,15,19,.88); }
  * { box-sizing: border-box; scrollbar-width:thin; scrollbar-color:var(--sb-thumb) var(--inset); }
  html { scroll-behavior:smooth; }
  body { margin:0; padding:0 0 0 64px;
         font:14px/1.55 system-ui,-apple-system,"Segoe UI","Noto Sans TC","Microsoft JhengHei",sans-serif;
         font-variant-numeric:tabular-nums;  /* 等寬數字：2.5s 輪詢只換值不換版 */
         background:var(--bg) radial-gradient(var(--grid-dot) 1px, transparent 1px);
         background-size:22px 22px; color:var(--ink); }
  a { color:inherit; text-decoration:none; }
  ::selection { background:rgba(110,168,254,.28); }
  ::-webkit-scrollbar { width:8px; height:8px; }
  ::-webkit-scrollbar-track { background:var(--inset); }
  ::-webkit-scrollbar-thumb { background:var(--sb-thumb); border-radius:4px; }
  :focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
  .rail, .kpi-lbl, .seg, .svp-tab, .chev, .mnav { user-select:none; }
  /* 斷線超過 10s：內容降飽和標示「這是快照」，topbar 保持清晰承載警示 */
  body.stale .main section.src, body.stale .kpis { filter:saturate(.55); opacity:.8; }
  svg.ic { width:16px; height:16px; flex:none; }
  .main { max-width:1400px; margin:0 auto; padding:0 20px 48px; }
  /* ---- 左側 icon 側欄（scroll-spy 錨點） ---- */
  .rail { position:fixed; top:0; left:0; bottom:0; width:64px; z-index:40;
          display:flex; flex-direction:column; align-items:center; gap:6px;
          padding:12px 0; background:var(--tile); border-right:1px solid var(--line); }
  .rail-logo { width:40px; height:40px; border-radius:12px; display:flex; align-items:center;
               justify-content:center; margin-bottom:10px; cursor:pointer;
               background:linear-gradient(135deg,var(--accent),var(--violet));
               color:#0b0c10; font-weight:800; font-size:16px; font-family:inherit;
               transition:box-shadow .2s ease, transform .15s ease; }
  .rail-logo:hover { box-shadow:0 0 14px -2px rgba(122,165,255,.6); }
  .rail-logo:active { transform:scale(.95); }
  /* 滑動指示塊：跟著目前分區移動的發光方塊（scroll-spy 驅動） */
  .rail-ind { position:absolute; top:0; left:12px; width:40px; height:40px; border-radius:12px;
              background:var(--accent-soft);
              box-shadow:0 0 0 1px rgba(110,168,254,.4), 0 0 16px -2px rgba(110,168,254,.55);
              transition:transform .3s cubic-bezier(.23,1,.32,1), opacity .2s ease;
              opacity:0; pointer-events:none; z-index:0; }
  .rail-ind.on { opacity:1; }
  .rail-item { width:40px; height:40px; border-radius:12px; display:flex; align-items:center;
               justify-content:center; color:var(--muted); position:relative; z-index:1;
               transition:color .2s ease; }
  .rail-item svg { width:20px; height:20px; }
  .rail-item:hover { background:var(--hover); color:var(--ink); }
  .rail-item.active { color:var(--accent); }
  .rail-item.active:hover { background:transparent; }
  /* ---- 頂欄（sticky） ---- */
  .topbar { position:sticky; top:0; z-index:30; display:flex; align-items:center; gap:10px;
            flex-wrap:wrap; padding:14px 2px 12px; margin-bottom:16px;
            background:var(--topbar-bg); backdrop-filter:blur(8px);
            border-bottom:1px solid var(--line-soft); }
  h1 { font-size:18px; font-weight:700; margin:0; letter-spacing:.01em; }
  .dot { width:9px; height:9px; border-radius:50%; background:var(--muted); flex:none; }
  .dot.ok { background:var(--ok); } .dot.warn { background:var(--warn); }
  .dot.bad { background:var(--bad); }
  .dot.pulse.ok { animation:ring-ok 2.4s ease-out infinite; }
  .dot.pulse.bad { animation:ring-bad 1.6s ease-out infinite; }
  @keyframes ring-ok { 0%{box-shadow:0 0 0 0 var(--ok-ring)} 70%,100%{box-shadow:0 0 0 8px transparent} }
  @keyframes ring-bad { 0%{box-shadow:0 0 0 0 var(--bad-ring)} 70%,100%{box-shadow:0 0 0 8px transparent} }
  /* 診斷句移進頂欄（mockup 版式）：h1 旁一句系統現況，取代獨立 hero 行 */
  .sys-phrase { font-size:13px; color:var(--muted); min-width:0; overflow:hidden;
                text-overflow:ellipsis; white-space:nowrap; }
  #status { color:var(--muted); font-size:12px; margin-left:auto; }
  .srcbar { display:flex; gap:6px; flex-wrap:wrap; }
  .srcbar label { position:relative; display:flex; gap:6px; align-items:center; cursor:pointer;
                  font-size:12px; color:var(--muted); padding:4px 10px; border:1px solid var(--line);
                  border-radius:999px; background:var(--tile); }
  .srcbar label.on { color:var(--ink); border-color:var(--accent); background:var(--accent-soft); }
  /* checkbox 用 sr-only 定位而非 display:none：保留鍵盤聚焦，ring 畫在 label 上 */
  .srcbar input { position:absolute; width:1px; height:1px; opacity:0; margin:0; pointer-events:none; }
  .srcbar label:has(input:focus-visible) { outline:2px solid var(--accent); outline-offset:2px; }
  .mnav { display:none; gap:6px; overflow-x:auto; padding:8px 0 2px; width:100%; order:5; }
  .mnav a { flex:none; font-size:12px; color:var(--muted); border:1px solid var(--line);
            border-radius:999px; padding:5px 12px; background:var(--tile); }
  .mnav a.active { color:var(--accent); border-color:var(--accent); background:var(--accent-soft); }
  /* 唯讀公開模式：只藏「會發 POST 的操作件」（.op-only）；導航／篩選／展開照常可用。
     後端 do_POST 對 readonly 一律 403，這裡只是不誘導。 */
  body.readonly .op-only { display:none !important; }
  body.readonly .ro-badge { display:inline-block; background:var(--warn); color:#000;
    font-size:11px; font-weight:700; border-radius:6px; padding:1px 8px; }
  .ro-badge { display:none; }
  /* ---- KPI 統計卡列：三段式解剖 label → 大數字 → 走勢（業界 KPI 卡收斂型） ---- */
  .kpis { display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin-bottom:18px; }
  .kpi { background:var(--panel); border:1px solid var(--line); border-radius:14px;
         padding:13px 14px; min-width:0; display:flex; flex-direction:column; gap:2px; }
  .kpi-lbl { display:flex; align-items:center; gap:7px; font-size:12px; color:var(--muted);
             margin-bottom:6px; min-height:20px; }
  .kpi-ico { display:inline-flex; align-items:center; color:var(--muted); flex:none; }
  .kpi-ico svg.ic { width:15px; height:15px; }
  .kpi-ico.accent { color:var(--accent); }
  .kpi-ico.ok { color:var(--ok); }
  .kpi-ico.warn { color:var(--warn); }
  .kpi-ico.bad { color:var(--bad); }
  .kpi-tag { margin-left:auto; font-size:10.5px; color:var(--muted); border:1px solid var(--line);
             border-radius:999px; padding:1px 7px; background:var(--tile); }
  .kpi-num { font-size:27px; font-weight:700; line-height:1.15; letter-spacing:-.01em;
             font-variant-numeric:tabular-nums; }
  .kpi-num small { font-size:12px; font-weight:500; color:var(--muted); }
  /* 有異常的 KPI 整卡染警示（mockup .kpi.alert）：其餘卡保持安靜 */
  .kpi.alert { box-shadow:inset 0 0 0 1px rgba(240,180,41,.4); }
  .kpi.alert .kpi-num { color:var(--warn); }
  /* KPI 內迷你走勢：現值旁答「在變好還是變壞」；無資料＝空著不佔位 */
  .kpi-spark { margin-top:auto; padding-top:7px; }
  .kpi-spark svg { display:block; width:100%; height:26px; }
  /* 深色系折線配柔光暈（glow）；亮色由 body.light 關掉 */
  #k-active-spark polyline { filter:drop-shadow(0 0 2.5px rgba(110,168,254,.55)); }
  #k-pass-spark polyline { filter:drop-shadow(0 0 2.5px rgba(62,207,142,.5)); }
  body.light .kpi-spark polyline { filter:none; }
  /* app trace 耗時橫條：同批最大值定刻度，離群慢呼叫免讀數字 */
  .latbar { display:block; height:4px; background:var(--inset); border-radius:2px; margin-top:5px; }
  .latbar i { display:block; height:100%; border-radius:2px; min-width:2px; }
  /* ---- 區塊 ---- */
  section.src { background:var(--panel); border:1px solid var(--line); border-radius:16px;
                padding:24px; margin-bottom:24px; scroll-margin-top:70px; }
  /* 區塊標題列：標題＋灰階提示句＋右推的操作區（mockup 版面） */
  section.src > header { display:flex; align-items:baseline; gap:12px;
                         flex-wrap:wrap; margin-bottom:16px; }
  section.src > header .hint { font-size:12px; color:var(--faint); }
  section.src > header .actions { margin-left:auto; display:flex; gap:8px;
                                  align-items:center; flex-wrap:wrap; }
  /* demo 主場差異化：信任生態掛 accent 頂緣光帶＋標題染色——視線先落這裡，
     其餘不動（日常看盤 runs 仍是工作主角，不搶它的資訊密度） */
  #sec-eco { position:relative; border-color:rgba(110,168,254,.30); }
  #sec-eco::before { content:''; position:absolute; top:-1px; left:16px; right:16px; height:2px;
                     border-radius:2px; pointer-events:none;
                     background:linear-gradient(90deg, transparent, var(--accent) 30%,
                       var(--accent) 70%, transparent); opacity:.65; }
  #sec-eco h2 { color:var(--accent); }
  section.src.off { opacity:.45; }
  section.src h2 { font-size:17px; font-weight:700; letter-spacing:0;
                   color:var(--ink); margin:0; display:flex; gap:8px;
                   align-items:center; }
  section.src h2 svg { width:16px; height:16px; color:var(--muted); }
  /* ---- runs filter 工具列（靜態，不在 #runs 重繪邊界內＝搜尋框不丟 focus） ---- */
  .toolbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
  .toolbar[hidden] { display:none; }
  .search { flex:1; min-width:180px; display:flex; align-items:center; gap:8px;
            background:var(--inset); border:1px solid var(--line); border-radius:10px;
            padding:0 12px; color:var(--muted); }
  .search:focus-within { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent); }
  .search svg { width:14px; height:14px; }
  .search input { flex:1; background:none; border:0; outline:0; color:var(--ink);
                  font-size:13px; font-family:inherit; padding:8px 0; min-width:0; }
  .segs { display:flex; gap:3px; background:var(--tile); border:1px solid var(--line);
          border-radius:10px; padding:3px; max-width:100%; overflow-x:auto; }
  .seg { border:0; background:none; color:var(--muted); font-size:12px; padding:5px 10px;
         border-radius:8px; cursor:pointer; white-space:nowrap; }
  .seg:hover { color:var(--ink); border-color:transparent; }
  .seg.active { background:var(--hover); color:var(--ink); }
  .sv-sel { background:var(--inset); color:var(--ink); border:1px solid var(--line);
            border-radius:10px; padding:7px 10px; font-size:12px; font-family:inherit; }
  /* 已套用篩選 chips（可逐一卸除）＋零結果空態 */
  #sv-chips { display:flex; gap:6px; flex-wrap:wrap; margin:-4px 0 10px; }
  .fchip { display:inline-flex; gap:6px; align-items:center; font-size:11.5px;
           color:var(--ink); background:var(--accent-soft); border:1px solid var(--accent);
           border-radius:999px; padding:2px 10px; cursor:pointer; user-select:none; }
  .fchip b { color:var(--accent); font-weight:700; }
  .fchip.clear { background:var(--tile); border-color:var(--line); color:var(--muted); }
  /* 已完成摺疊列（表格版：一列 colspan，內容包在 .dh） */
  #sv-donehdr { cursor:pointer; user-select:none; }
  #sv-donehdr td { padding:10px 12px 4px; border-bottom:0; }
  #sv-donehdr .dh { display:flex; align-items:center; gap:8px;
                    color:var(--muted); font-size:12px; }
  #sv-donehdr:hover .dh { color:var(--ink); }
  #sv-donehdr .chev2 { transition:transform .15s; }
  #sv-list.dc .sv-row.fin { display:none; }
  .sv-phrase.warn { color:var(--warn); }
  /* 停滯「知悉」triage：列上快速鈕＋鍵盤游標列 */
  .sv-ack { font-size:11px; padding:2px 10px; border-radius:999px; background:var(--bad-soft);
            border:1px solid var(--bad); color:var(--bad); transition:background .15s ease; }
  .sv-ack:hover { background:rgba(255,84,112,.28); border-color:var(--bad); }
  .sv-row.kbd { outline:2px solid var(--accent); outline-offset:-2px; border-radius:8px; }
  .kbdhint { font-size:10px; color:var(--muted); border:1px solid var(--line);
             border-radius:4px; padding:0 5px; }
  /* 亮色模式：整組 token 翻面。狀態色換深化版（原亮色系在白底對比不足），
     文字/非文字對比維持 AA；圖表軸線走 --ax 系 token 一起翻黑 */
  body.light { color-scheme:light;
    --bg:#eef0f4; --panel:#ffffff; --tile:#f4f5f8; --inset:#e9ebf1; --hover:#e4e7ee;
    --ink:#1b2130; --muted:#5c6575; --line:#d8dce5; --line-soft:rgba(16,24,40,.08);
    --ok:#0e7a4e; --warn:#8a6400; --bad:#c2244a; --accent:#2e63d8;
    --ok-soft:rgba(14,122,78,.11); --warn-soft:rgba(138,100,0,.12);
    --bad-soft:rgba(194,36,74,.10); --accent-soft:rgba(46,99,216,.10);
    --ok-ring:rgba(14,122,78,.35); --bad-ring:rgba(194,36,74,.35);
    --grid-dot:rgba(16,24,40,.05);
    --shadow-float:0 8px 24px rgba(23,32,54,.16), 0 2px 6px rgba(23,32,54,.10);
    --faint:#7a8496;
    --ax-soft:rgba(16,24,40,.07); --ax:rgba(16,24,40,.15);
    --ax-mid:rgba(16,24,40,.30); --ax-strong:rgba(16,24,40,.42);
    --ser2:#8f49c9; --ser3:#b3551d;
    /* 亮色系沒有 glow 語彙（白底彩暈顯髒），全部關掉 */
    --glow-accent:none; --glow-ok:none; --glow-bad:none;
    --sb-thumb:#c2c8d4; --topbar-bg:rgba(238,240,244,.88); }
  body.light .ro-badge { color:#fff; }  /* warn 變深棕，黑字會糊掉 */
  .rail-night { margin-top:auto; background:none; border:0; padding:0; cursor:pointer; }
  .rail-night:hover { border:0; }
  body.light .rail-night { color:var(--warn); }
  .ic-sun { display:none; }
  body.light .ic-moon { display:none; }
  body.light .ic-sun { display:inline; }
  #sv-toast { position:fixed; bottom:18px; left:50%; transform:translateX(-50%);
              background:var(--tile); border:1px solid var(--line); border-radius:8px;
              padding:8px 16px; font-size:12.5px; z-index:80; box-shadow:var(--shadow-float);
              opacity:0; transition:opacity .25s; pointer-events:none; }
  #sv-toast.on { opacity:1; }
  .chip { font-size:11px; color:var(--muted); background:var(--inset);
          border:1px solid var(--line-soft); border-radius:6px; padding:1px 7px;
          font-family:ui-monospace,Consolas,monospace; }
  .chev { color:var(--muted); }
  /* ---- 卡片與共用元件 ---- */
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:12px; }
  .card { background:var(--tile); border:1px solid var(--line); border-radius:12px; padding:12px; }
  .card.stall { border-color:var(--bad); box-shadow:0 0 0 1px var(--bad); }
  .voidhot { color:var(--bad); font-weight:700; }
  .tasklist { margin-top:8px; font:11.5px/1.5 ui-monospace,Consolas,monospace;
              max-height:220px; overflow:auto; border-top:1px solid var(--line); }
  .tasklist div { display:flex; gap:8px; align-items:center; padding:2px 0;
                  border-bottom:1px solid var(--line-soft); }
  .tasklist .o-pass { color:var(--ok); } .tasklist .o-fail { color:var(--warn); }
  .tasklist .o-infra_void { color:var(--bad); }
  .tasklist button { padding:1px 8px; font-size:11px; margin-left:auto; }
  .card h3 { font-size:13.5px; margin:0 0 8px; display:flex; justify-content:space-between;
             align-items:center; font-family:ui-monospace,Consolas,monospace; gap:8px; }
  .pill { font-size:11px; padding:2px 9px; border-radius:999px; border:1px solid var(--line);
          color:var(--muted); background:var(--panel); white-space:nowrap; }
  .pill.running,.pill.on,.pill.ok { color:var(--ok); border-color:transparent; background:var(--ok-soft); }
  .pill.paused,.pill.warn { color:var(--warn); border-color:transparent; background:var(--warn-soft); }
  .pill.stop_after_current,.pill.off,.pill.bad { color:var(--bad); border-color:transparent; background:var(--bad-soft); }
  .counts { display:flex; gap:10px; flex-wrap:wrap; font-size:12px; color:var(--muted);
            margin-bottom:8px; align-items:center; }
  .counts b { color:var(--ink); font-variant-numeric:tabular-nums; }
  .meta { font-size:11px; color:var(--muted); margin:6px 0; }
  .btns { display:flex; gap:8px; flex-wrap:wrap; margin-top:6px; }
  button { display:inline-flex; align-items:center; gap:6px; background:var(--hover);
           color:var(--ink); border:1px solid var(--line); border-radius:8px;
           padding:6px 12px; cursor:pointer; font-size:12px; font-family:inherit;
           transition:border-color .15s ease, background .15s ease, transform .1s ease; }
  button:hover { border-color:var(--accent); }
  button:active { transform:scale(.97); }
  button:disabled { opacity:.45; pointer-events:none; }
  button svg { width:13px; height:13px; }
  /* 危險操作視覺分級：按下前就告知，confirm 只是最後防線 */
  .btn-danger { color:var(--bad); }
  .btn-danger:hover { border-color:var(--bad); background:var(--bad-soft); }
  .skip { display:flex; gap:6px; margin-top:8px; }
  .skip input { flex:1; background:var(--inset); border:1px solid var(--line); border-radius:8px;
                color:var(--ink); padding:6px 10px; font-size:12px; font-family:inherit; }
  pre.log { background:var(--inset); border:1px solid var(--line); border-radius:10px;
            padding:10px; font:11.5px/1.45 ui-monospace,Consolas,monospace;
            max-height:260px; overflow:auto; white-space:pre-wrap; word-break:break-all; }
  ul.ev { list-style:none; margin:8px 0 0; padding:0; max-height:200px; overflow:auto;
          font:12px/1.6 ui-monospace,Consolas,monospace; }
  ul.ev li { border-bottom:1px solid var(--line-soft); padding:3px 0; }
  .empty { color:var(--muted); padding:22px; text-align:center; font-size:12.5px; }
  /* ---- GitHub 歸檔 runs ---- */
  .gh-sync { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:6px; }
  .gh-sync a, .gh-tbl a { color:var(--accent); text-decoration:none; }
  .gh-sync a:hover, .gh-tbl a:hover { text-decoration:underline; }
  .gh-kinds { font-size:11.5px; color:var(--muted); margin:2px 0 10px; }
  .gh-tools { display:flex; gap:8px; align-items:center; margin-bottom:8px; }
  .gh-tools input { flex:1; max-width:320px; background:var(--inset); border:1px solid var(--line);
                    border-radius:8px; color:var(--ink); padding:6px 10px; font-size:12px; font-family:inherit; }
  .gh-tbl { width:100%; border-collapse:collapse; font-size:12.5px; }
  .gh-tbl th { font-size:11.5px; color:var(--muted); font-weight:600; text-align:left;
               padding:6px 8px; border-bottom:1px solid var(--line); white-space:nowrap; }
  .gh-tbl td { padding:6px 8px; border-bottom:1px solid var(--line-soft); vertical-align:top; }
  .gh-tbl td.r, .gh-tbl th.r { text-align:right; }
  .gh-tbl .nm { font-family:ui-monospace,Consolas,monospace; font-weight:600; word-break:break-all; }
  .gh-tbl .num { font-family:ui-monospace,Consolas,monospace; font-variant-numeric:tabular-nums; }
  .gh-arms { display:flex; gap:4px; flex-wrap:wrap; }
  .gh-hl { color:var(--muted); font-size:11.5px; max-width:360px; }
  @media (max-width:900px){ .gh-tbl th:nth-child(4), .gh-tbl td:nth-child(4),
    .gh-tbl th:nth-child(8), .gh-tbl td:nth-child(8) { display:none; } }
  .note { color:var(--warn); font-size:12px; margin-top:6px; }
  /* ---- 信任生態：信用視覺化（demo 主場） ---- */
  .esec { font-size:11px; letter-spacing:.05em; text-transform:uppercase;
          color:var(--muted); margin:14px 0 6px; }
  .eco-legend { display:flex; gap:12px; flex-wrap:wrap; font-size:11.5px;
                color:var(--muted); margin:2px 0 6px; }
  .eco-legend .lg { display:flex; align-items:center; gap:5px; }
  .eco-legend .sw { width:14px; height:3px; border-radius:2px; }
  .cchart { position:relative; background:var(--inset); border:1px solid var(--line-soft);
            border-radius:10px; padding:6px 4px 2px; }
  .cchart svg { display:block; width:100%; }
  .cchart text { font-size:10px; fill:var(--muted); }
  .cchart .tip { position:absolute; top:8px; transform:translateX(-50%); pointer-events:none;
                 background:var(--panel); border:1px solid var(--line); border-radius:8px;
                 padding:5px 9px; font-size:11px; white-space:nowrap; line-height:1.5;
                 box-shadow:var(--shadow-float); z-index:5; }
  /* 名冊列：對齊的信用偏移條（0.5 基準置中）＝六個 agent 一眼可比 */
  .roster { display:flex; flex-direction:column; gap:5px; margin-top:4px; }
  .rrow { display:grid; grid-template-columns:148px minmax(120px,1fr) 46px auto; gap:10px;
          align-items:center; background:var(--tile); border:1px solid var(--line);
          border-radius:10px; padding:7px 12px; font-size:12px; }
  .rrow .rr-nm { display:flex; align-items:center; gap:7px; overflow:hidden;
                 white-space:nowrap; font-family:ui-monospace,Consolas,monospace; }
  .rrow .rr-nm i { width:8px; height:8px; border-radius:50%; flex:none; }
  .rrow .rr-nm small { color:var(--muted); }
  .cbar { position:relative; height:14px; background:var(--inset); border-radius:4px; }
  .cbar .base { position:absolute; left:50%; top:-2px; bottom:-2px; width:1px;
                background:var(--ax-strong); }
  .cbar .fl { position:absolute; top:2px; bottom:2px; border-radius:3px;
              transition:width .5s ease; min-width:2px;
              box-shadow:var(--fl-glow, none); }
  body.light .cbar .fl { box-shadow:none; }
  .rrow .rr-val { text-align:right; font-variant-numeric:tabular-nums; }
  .rrow .rr-meta { display:flex; gap:6px; align-items:center; flex-wrap:wrap;
                   color:var(--muted); font-size:11px; justify-content:flex-end; }
  /* 交付卡：一卡＝一次交付的 ROUTE→REVIEW→AUDIT→DELIVERED 流水 */
  .dcards { display:flex; flex-direction:column; gap:5px; }
  .dcard { display:flex; gap:8px; align-items:center; flex-wrap:wrap; font-size:12px;
           background:var(--tile); border:1px solid var(--line); border-radius:10px;
           padding:7px 12px; }
  .dcard .dc-when { color:var(--muted); font-size:11px; width:74px; flex:none; }
  .dcard .stg { display:flex; align-items:center; gap:4px; font-size:11px;
                padding:2px 8px; border-radius:999px; background:var(--inset);
                border:1px solid var(--line-soft); color:var(--muted); }
  .dcard .stg b { color:var(--ink); font-weight:600; }
  .dcard .stg.ok { color:var(--ok); border-color:transparent; background:var(--ok-soft); }
  .dcard .stg.warn { color:var(--warn); border-color:transparent; background:var(--warn-soft); }
  .dcard .stg.bad { color:var(--bad); border-color:transparent; background:var(--bad-soft); }
  .dcard .arr { color:var(--muted); opacity:.6; font-size:10px; }
  /* scoreboard on/off 配對長條 */
  .sb-pair { display:flex; flex-direction:column; gap:4px; margin-top:8px; max-width:520px; }
  .sb-pair .sbrow { display:grid; grid-template-columns:30px 1fr 92px; gap:8px;
                    align-items:center; font-size:11.5px; color:var(--muted); }
  .sb-pair .trk { height:11px; background:var(--inset); border-radius:4px; overflow:hidden; }
  .sb-pair .fl { height:100%; border-radius:4px; background:var(--accent); width:0;
                 transition:width .6s ease; }
  .sb-pair .fl.off { background:#5a6275; }
  .sb-pair .pc { text-align:right; font-variant-numeric:tabular-nums; }
  .mx { overflow-x:auto; margin-top:8px; }
  .mx table { border-collapse:collapse; font:11.5px/1.5 ui-monospace,Consolas,monospace; }
  .mx th, .mx td { border:1px solid var(--line); padding:3px 9px; text-align:left; }
  .mx th { color:var(--muted); font-weight:600; }
  .mx th:first-child, .mx td:first-child { position:sticky; left:0; background:var(--panel); }
  .mx .on { color:var(--ok); }
  .tiles { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; margin:8px 0; }
  .tile { background:var(--inset); border:1px solid var(--line-soft); border-radius:8px;
          padding:6px 8px; min-width:0; }
  .tile b { display:block; font-size:15px; font-variant-numeric:tabular-nums;
            overflow:hidden; text-overflow:ellipsis; }
  .tile span { font-size:10.5px; color:var(--muted); }
  .livedot { display:inline-block; width:6px; height:6px; border-radius:50%;
             background:var(--ok); margin-right:5px; vertical-align:1px;
             animation:ring-ok 2.4s ease-out infinite; }
  /* ---- 批次執行區的主從式元件（診斷句 hero＋人話列＋側面板） ---- */
  .sv-diag { display:flex; align-items:center; gap:12px; margin:6px 0 16px; }
  .sv-diag .dot { width:12px; height:12px; }
  .sv-diag-t { font-size:21px; font-weight:650; letter-spacing:-.01em; }
  .sv-main { display:flex; gap:16px; align-items:flex-start; }
  .sv-list { flex:1; min-width:0; }
  /* run 列＝表格列（第八輪改版）：狀態走 pill，形狀＋顏色雙通道仍由 pill 文字承擔 */
  .sv-row.pre { opacity:0; }
  .sv-row { transition:opacity .2s cubic-bezier(.23,1,.32,1), background .15s ease; }
  .sv-row .c-st { display:flex; align-items:center; gap:8px; }
  .sv-ico { width:14px; height:14px; flex:none; }
  .dot.pulse-soft, .sv-ico.pulse-soft { animation:vbreathe 2.4s ease-in-out infinite; }
  @keyframes vbreathe { 0%,100% { opacity:1; } 50% { opacity:.45; } }
  /* ---- run 詳情：置中彈窗（modal）——所有寬度統一，點背景／Esc 關閉 ---- */
  /* visibility 進 transition：收合動畫結束才隱藏（同時把看不見的終止鈕踢出 Tab 序） */
  .modal { position:fixed; inset:0; z-index:70; display:flex;
           align-items:center; justify-content:center; padding:16px;
           opacity:0; visibility:hidden; pointer-events:none;
           transition:opacity .22s ease, visibility .22s; }
  .modal.open { opacity:1; visibility:visible; pointer-events:auto; }
  .svp { width:min(560px, 100%); max-height:min(82vh, calc(100vh - 32px)); overflow:auto;
         background:var(--panel); border:1px solid var(--line);
         border-radius:16px; padding:18px 20px; box-shadow:var(--shadow-float);
         transform:translateY(10px) scale(.98);
         transition:transform .22s cubic-bezier(.23,1,.32,1); }
  .modal.open .svp { transform:none; }
  .svp.wide { width:min(760px, 100%); }
  #io-hint { font-size:12px; color:var(--faint); }
  .svp-head { display:flex; align-items:center; gap:8px; margin-bottom:12px; flex-wrap:wrap; }
  .svp-close { margin-left:auto; color:var(--muted); cursor:pointer; background:none;
               border:0; padding:4px; }
  .svp-close:hover { color:var(--ink); border:0; }
  .tiles.two { grid-template-columns:1fr 1fr; }
  .tile small { font-size:10px; color:var(--muted); }  /* 文字不用 alpha 淡化（對比紀律） */
  .svp-tabs { display:flex; gap:4px; font-size:11.5px; margin:12px 0 6px; }
  .svp-tab { color:var(--muted); padding:3px 10px; border-radius:6px; cursor:pointer;
             background:none; border:0; font-family:inherit; font-size:11.5px; }
  .svp-tab:hover { color:var(--ink); border:0; }
  .svp-tab.on { color:var(--ink); background:var(--hover); }
  .svp-chart { position:relative; }
  /* 心跳條：與趨勢圖同資料的離散檢視（每格 title 提示；hover 抬亮） */
  .svp-hb { margin-top:8px; }
  .svp-hb .hb-track { display:flex; gap:2px; height:14px; }
  .svp-hb i { flex:1; min-width:2px; border-radius:2px; background:var(--inset); }
  .svp-hb i.ok { background:var(--ok); opacity:.8; }
  .svp-hb i.mix { background:var(--warn); opacity:.85; }
  .svp-hb i.bad { background:var(--bad); opacity:.85; }
  .svp-hb i:hover { opacity:1; }
  .svp-hb .hb-cap { display:flex; justify-content:space-between;
                    font-size:10px; color:var(--muted); margin-top:3px; }
  .svp-chart svg { display:block; width:100%; height:110px; }
  .svp-chart text { font-size:10.5px; fill:var(--muted); }
  .svp-tip { position:absolute; top:2px; transform:translateX(-50%);
             background:var(--tile); border:1px solid var(--line); border-radius:6px;
             padding:2px 8px; font-size:11px; color:var(--ink);
             pointer-events:none; white-space:nowrap; box-shadow:var(--shadow-float); }
  #svp-line { transition:stroke-dashoffset .5s ease-out .1s; }
  #svp-band { transition:opacity .3s ease .4s; }
  .svp-sec { font-size:11px; color:var(--muted); margin:12px 0 6px; }
  .hbar { display:flex; align-items:center; gap:8px; margin-bottom:6px; font-size:11.5px; }
  .hbar .nm { font-family:ui-monospace,Consolas,monospace; width:126px; overflow:hidden;
              text-overflow:ellipsis; white-space:nowrap; flex:none; }
  .hbar .trk { flex:1; height:11px; background:var(--inset); border-radius:4px; overflow:hidden; }
  .hbar .fl { height:100%; border-radius:4px; background:var(--ok); width:0;
              transition:width .4s ease-out; }
  .hbar .fl.warn { background:var(--warn); }
  .hbar .pc { width:38px; text-align:right; font-variant-numeric:tabular-nums; flex:none; }
  .svp .tasklist { max-height:150px; border-top:0; background:var(--inset);
                   border-radius:8px; padding:4px 10px; }
  .svp .btns { margin-top:12px; }
  /* modal 遮罩：所有寬度常駐（原本只有手機 sheet 用） */
  #sv-backdrop { position:fixed; inset:0; z-index:60; background:rgba(5,6,9,.55);
                 opacity:0; pointer-events:none; transition:opacity .2s ease; }
  #sv-backdrop.on { opacity:1; pointer-events:auto; }
  /* ---- mockup 版面元件（2026-08-28 第八輪：對內版整體改版） ---- */
  /* 內容卡：區塊內的次級容器，比 panel 淺一階（深色系靠分層不靠邊框） */
  .ccard { background:var(--tile); border-radius:14px; padding:16px; min-width:0; }
  .ccard h3 { font-size:14px; font-weight:600; margin:0 0 2px; }
  .ccard .cap { font-size:12px; color:var(--faint); margin-bottom:12px; }
  /* ccard 裡的次級列（rrow/dcard 原本吃 tile）：退回 panel 底保住層次 */
  .ccard .rrow, .ccard .dcard { background:var(--panel); border-color:var(--line-soft); }
  .ccard .cchart { border-color:transparent; }
  /* runs 表格：掃讀密度高於卡片流；數值右對齊＋等寬 */
  .rtbl { width:100%; border-collapse:collapse; font-size:14px; }
  .rtbl th { font-size:12px; color:var(--muted); font-weight:600; text-align:left;
             padding:8px 12px; border-bottom:1px solid var(--line); white-space:nowrap; }
  .rtbl th.r, .rtbl td.r { text-align:right; }
  .rtbl td { padding:10px 12px; border-bottom:1px solid var(--line-soft); }
  .rtbl tbody tr { cursor:pointer; transition:background .15s ease; }
  .rtbl tbody tr:hover td { background:rgba(110,168,254,.05); }
  .rtbl tbody tr.sel td { background:var(--accent-soft); }
  .rtbl tbody tr.kbd { outline:2px solid var(--accent); outline-offset:-2px; }
  .rtbl tbody tr.gone { display:none; }
  .rtbl .nm { font-family:ui-monospace,Consolas,monospace; font-weight:600;
              max-width:220px; overflow:hidden; text-overflow:ellipsis;
              white-space:nowrap; display:block; }
  .rtbl .num { font-family:ui-monospace,Consolas,monospace;
               font-variant-numeric:tabular-nums; }
  /* 進度條（表格內，取代原 sv-bar 全寬條） */
  .pbar { height:6px; border-radius:3px; background:var(--inset); overflow:hidden;
          min-width:90px; display:flex; }
  .pbar i { display:block; height:100%; transition:width .45s cubic-bezier(.23,1,.32,1); }
  .pbar i.p1 { border-radius:3px 0 0 3px; }
  /* 心跳條（表格內迷你版，沿用 svBuckets 資料） */
  .hbm { display:inline-flex; gap:2px; align-items:flex-end; height:16px; }
  .hbm i { width:3px; border-radius:1px; background:var(--inset); }
  .hbm i.ok { background:var(--ok); opacity:.85; }
  .hbm i.mix { background:var(--warn); opacity:.85; }
  .hbm i.bad { background:var(--bad); opacity:.85; }
  /* 信任生態兩欄：名冊 | 交付流水 */
  .eco-grid { display:grid; grid-template-columns:7fr 5fr; gap:16px; margin-top:14px; }
  /* 名冊列（mockup）：0.5 置中發散條，右綠=上升、左紅=下降（方向色，非身分色） */
  .eroster { display:flex; flex-direction:column; }
  /* 第四欄固定寬：每列是獨立 grid，auto 欄會因 chips 有無而寬度不一 → 長條欄位互相對不齊 */
  .erow { display:grid; grid-template-columns:140px minmax(120px,1fr) 56px 148px;
          gap:12px; align-items:center; padding:8px 0;
          border-bottom:1px solid var(--line-soft); font-size:12px; }
  .erow:last-child { border-bottom:0; }
  .e-nm { font-family:ui-monospace,Consolas,monospace; font-weight:600;
          overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .e-nm small { color:var(--muted); font-weight:400; }
  .dbar { position:relative; height:14px; background:var(--inset); border-radius:7px; }
  .dbar::before { content:''; position:absolute; left:50%; top:-3px; bottom:-3px;
                  width:1px; background:var(--ax-strong); }
  .dbar i { position:absolute; top:2px; bottom:2px; border-radius:5px; min-width:0;
            transition:width .5s ease; }
  .dbar i.pos { left:50%; background:linear-gradient(90deg, rgba(62,207,142,.45), var(--ok));
                box-shadow:var(--glow-ok); }
  .dbar i.neg { right:50%; background:linear-gradient(270deg, rgba(255,84,112,.45), var(--bad));
                box-shadow:var(--glow-bad); }
  .e-sc { text-align:right; font-family:ui-monospace,Consolas,monospace;
          font-variant-numeric:tabular-nums; font-weight:700; }
  .e-sc.pos { color:var(--ok); } .e-sc.neg { color:var(--bad); } .e-sc.mid { color:var(--muted); }
  .e-meta { display:flex; gap:6px; align-items:center; justify-content:flex-end; flex-wrap:wrap; }
  .eaxis { display:grid; grid-template-columns:140px minmax(120px,1fr) 56px 148px; gap:12px;
           margin-top:4px; }
  .eaxis .ticks { grid-column:2; display:flex; justify-content:space-between;
                  font:10px ui-monospace,Consolas,monospace; color:var(--faint); }
  .eaxis .ticks .mid { color:var(--muted); }
  /* LM Studio 機器卡（4 格統計） */
  .machines { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:12px; }
  .mc header { display:flex; align-items:center; gap:8px; margin-bottom:12px; }
  .mc .nm { font-weight:700; font-size:17px; font-family:ui-monospace,Consolas,monospace; }
  .mc header .st { margin-left:auto; display:flex; gap:6px; }
  .mc .st4 { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }
  .mc .st4 .v { font-size:20px; font-weight:700; font-family:ui-monospace,Consolas,monospace;
                font-variant-numeric:tabular-nums; overflow:hidden; text-overflow:ellipsis; }
  .mc .st4 .v.bad { color:var(--bad); }
  .mc .st4 .k { font-size:11px; color:var(--faint); }
  .hermes-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:start; }
  @media (max-width:900px){
    .eco-grid, .machines, .hermes-grid { grid-template-columns:1fr; }
  }
  /* ---- terminal 風滾動視窗（老師 8/14：最近錯誤仿 terminal 增加科技感） ---- */
  .term { background:var(--inset); border:1px solid var(--line); border-radius:12px;
          overflow:hidden; }
  .term .tbar { display:flex; align-items:center; gap:6px; background:var(--panel);
                padding:7px 12px; border-bottom:1px solid var(--line); }
  .term .tbar i { width:10px; height:10px; border-radius:50%; flex:none; }
  .term .tbar i:nth-child(1) { background:var(--bad); }
  .term .tbar i:nth-child(2) { background:var(--warn); }
  .term .tbar i:nth-child(3) { background:var(--ok); }
  .term .tbar .ttl { font:11px/1 ui-monospace,Consolas,monospace; color:var(--muted);
                     margin-left:8px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .term .tbody { font:12px/1.7 ui-monospace,Consolas,monospace; padding:10px 14px;
                 max-height:200px; overflow-y:auto; }
  .term .ln { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .term .t { color:var(--muted); opacity:.75; }
  .term .lv-e { color:var(--bad); font-weight:700; }
  .term .lv-w { color:var(--warn); }
  .term .src { color:var(--accent); }
  .term .cursor { display:inline-block; width:7px; height:13px; background:var(--ok);
                  vertical-align:-2px; animation:tblink 1s steps(1) infinite; }
  @keyframes tblink { 50% { opacity:0; } }
  /* ---- LM Studio gateway 分頁：兩個 gateway 摺成 tabs，不再上下重複整組卡片 ---- */
  .gw-tabs { display:flex; gap:6px; margin-top:10px; }
  .gw-tab { font:12px ui-monospace,Consolas,monospace; color:var(--muted);
            border:1px solid var(--line); border-radius:999px; padding:4px 14px;
            background:var(--tile); cursor:pointer; }
  .gw-tab:hover { color:var(--ink); border-color:var(--accent); }
  .gw-tab.on { color:var(--accent); border-color:var(--accent); background:var(--accent-soft); }
  /* ---- 對外公開模式（7779）：老師 8/14 裁定——只留「任務執行狀況＋信任生態」，
     LM Studio／Hermes 等底層技術區塊只在內部看；再加一句話結論 hero 與故事化說明。
     全走 CSS（readonly class 由 /api/mode 非同步掛上，CSS 才不會有時序競態） ---- */
  body.readonly #sec-github, body.readonly .rail-item[data-sec="sec-github"],
  body.readonly .mnav a[data-sec="sec-github"],
  body.readonly #sec-lmstudio, body.readonly #sec-hermes,
  body.readonly .rail-item[data-sec="sec-lmstudio"],
  body.readonly .rail-item[data-sec="sec-hermes"],
  body.readonly .mnav a[data-sec="sec-lmstudio"],
  body.readonly .mnav a[data-sec="sec-hermes"],
  body.readonly .kpi.k-internal, body.readonly #runs-hint { display:none !important; }
  body.readonly .kpis { grid-template-columns:repeat(4,1fr); }
  body.readonly .kpi-num { font-size:32px; }  /* 展場站距 1–2m，數字放大一級 */
  .pub-hero { display:none; }
  body.readonly .pub-hero { display:block; margin:10px 0 22px; }
  .pub-hero h2 { margin:0 0 8px; font-size:29px; font-weight:800; line-height:1.35;
                 letter-spacing:.01em; }
  .pub-hero h2 .up { color:var(--ok); } .pub-hero h2 .down { color:var(--bad); }
  .pub-hero p { margin:0; font-size:14.5px; color:var(--muted); max-width:56em; }
  /* 對外統整卡：完成任務／donut 通過率／被攔下（mockup_external 三卡） */
  .pub-stats { display:none; }
  body.readonly .pub-stats { display:grid; grid-template-columns:repeat(3,1fr);
                             gap:16px; margin:4px 0 20px; }
  .pcard { background:var(--tile); border-radius:14px; padding:20px; min-width:0; }
  .pcard .lbl { font-size:13px; color:var(--muted); }
  .pcard .val { font-size:34px; font-weight:800; font-variant-numeric:tabular-nums;
                margin:4px 0; line-height:1.2; }
  .pcard .val small { font-size:16px; color:var(--muted); font-weight:600; }
  .pcard .val.bad { color:var(--bad); }
  .pcard .cap { font-size:12px; color:var(--faint); line-height:1.6; }
  .pcard.ring { display:flex; gap:18px; align-items:center; }
  .ringviz { position:relative; width:104px; height:104px; flex:none; }
  .ringviz svg { width:104px; height:104px; transform:rotate(-90deg); display:block; }
  .ringviz circle { fill:none; stroke-width:11; stroke-linecap:round; }
  .ringviz .track { stroke:var(--inset); }
  .ringviz .arc { stroke:var(--ok); filter:drop-shadow(0 0 6px rgba(62,207,142,.5));
                  transition:stroke-dasharray .6s ease; }
  .ringviz .ctr { position:absolute; inset:0; display:grid; place-items:center;
                  font-size:22px; font-weight:800; font-variant-numeric:tabular-nums; }
  @media (max-width:900px){ body.readonly .pub-stats { grid-template-columns:1fr; } }
  /* 攔截卡 ↔ 信任生態的視覺連結：卡可點（捲動+閃紅），紅色與左偏信任條同色系 */
  .pcard.link { cursor:pointer; transition:border-color .15s ease, box-shadow .15s ease;
                border:1px solid transparent; }
  .pcard.link:hover { border-color:var(--bad); box-shadow:0 0 12px -4px var(--bad); }
  .erow.flash { animation:eflash 1.2s ease 2; }
  @keyframes eflash { 0%,100% { background:transparent; } 40% { background:var(--bad-soft); } }
  .pub-story { display:none; }
  body.readonly .pub-story { display:block; font-size:13px; color:var(--muted);
                             margin:-4px 0 12px; max-width:56em; line-height:1.7; }
  body.readonly .pub-story b { color:var(--ink); }
  /* ---- 信用分數機制小動畫（對外限定）：交付→審查→信用升降，9s 雙相位循環。
     顏色全走 tokens（綠=上升、紅=下降）＝動畫本身就是發散圖的圖例。
     reduced-motion 時全域 animation:none，base 樣式即為靜態可讀的圖解。 ---- */
  .pub-mech { display:none; }
  body.readonly .pub-mech { display:block; background:var(--tile); border-radius:14px;
                            padding:16px 20px 14px; margin:0 0 16px; }
  .m-stage { display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
  .m-node { display:flex; flex-direction:column; align-items:center; gap:7px; }
  .m-cap { font-size:11px; color:var(--faint); white-space:nowrap; }
  .m-arrow { color:var(--muted); font-size:17px; opacity:.55; }
  .m-agentbox { position:relative; display:flex; align-items:center; gap:6px; height:34px; }
  .m-avatar { width:34px; height:34px; border-radius:50%; background:var(--accent-soft);
              color:var(--accent); display:flex; align-items:center; justify-content:center; }
  .m-avatar svg { width:17px; height:17px; }
  .m-pkg { color:var(--muted); display:flex; animation:mpkg 9s infinite; }
  .m-pkg svg { width:15px; height:15px; }
  @keyframes mpkg { 0%,2% { transform:none; opacity:1; }
    7% { transform:translateX(16px); opacity:.1; } 11% { transform:none; opacity:1; }
    50%,52% { transform:none; opacity:1; }
    57% { transform:translateX(16px); opacity:.1; } 61% { transform:none; opacity:1; }
    100% { transform:none; opacity:1; } }
  .m-revs { display:flex; gap:6px; height:34px; align-items:center; }
  .m-revs i { width:13px; height:13px; border-radius:50%; background:var(--inset);
              border:1px solid var(--line); }
  .m-revs i:nth-child(1) { animation:mrv1 9s infinite; }
  .m-revs i:nth-child(2) { animation:mrv2 9s infinite; }
  .m-revs i:nth-child(3) { animation:mrv3 9s infinite; }
  @keyframes mrv1 { 0%,10% { background:var(--inset); box-shadow:none; }
    14%,42% { background:var(--ok); box-shadow:var(--glow-ok); }
    47%,60% { background:var(--inset); box-shadow:none; }
    64%,92% { background:var(--bad); box-shadow:var(--glow-bad); }
    97%,100% { background:var(--inset); box-shadow:none; } }
  @keyframes mrv2 { 0%,13% { background:var(--inset); box-shadow:none; }
    17%,42% { background:var(--ok); box-shadow:var(--glow-ok); }
    47%,63% { background:var(--inset); box-shadow:none; }
    67%,92% { background:var(--bad); box-shadow:var(--glow-bad); }
    97%,100% { background:var(--inset); box-shadow:none; } }
  @keyframes mrv3 { 0%,16% { background:var(--inset); box-shadow:none; }
    20%,42% { background:var(--ok); box-shadow:var(--glow-ok); }
    47%,66% { background:var(--inset); box-shadow:none; }
    70%,92% { background:var(--bad); box-shadow:var(--glow-bad); }
    97%,100% { background:var(--inset); box-shadow:none; } }
  .m-cred { position:relative; width:104px; height:13px; background:var(--inset);
            border-radius:7px; }
  .m-cred::before { content:''; position:absolute; left:50%; top:-3px; bottom:-3px;
                    width:1px; background:var(--ax-strong); }
  .m-cred i { position:absolute; top:2px; bottom:2px; width:42px; }
  .m-cred .fg { left:50%; border-radius:0 5px 5px 0; transform:scaleX(.6);
                transform-origin:left; animation:mfg 9s infinite;
                background:linear-gradient(90deg, rgba(62,207,142,.45), var(--ok));
                box-shadow:var(--glow-ok); }
  .m-cred .fb { right:50%; border-radius:5px 0 0 5px; transform:scaleX(.6);
                transform-origin:right; animation:mfb 9s infinite;
                background:linear-gradient(270deg, rgba(255,84,112,.45), var(--bad));
                box-shadow:var(--glow-bad); }
  @keyframes mfg { 0%,16% { transform:scaleX(0); } 26%,42% { transform:scaleX(1); }
                   48%,100% { transform:scaleX(0); } }
  @keyframes mfb { 0%,66% { transform:scaleX(0); } 76%,92% { transform:scaleX(1); }
                   97%,100% { transform:scaleX(0); } }
  .m-scenes { display:flex; gap:20px; flex-wrap:wrap; margin-top:12px; font-size:12px; }
  .m-sc { opacity:1; }  /* base 兩句並列常駐（reduced-motion 靜態版）；動畫只做亮/暗 */
  .sc-good { color:var(--ok); animation:mscg 9s infinite; }
  .sc-bad { color:var(--bad); animation:mscb 9s infinite; }
  @keyframes mscg { 0%,4% { opacity:.35; } 10%,44% { opacity:1; } 50%,100% { opacity:.35; } }
  @keyframes mscb { 0%,54% { opacity:.35; } 60%,94% { opacity:1; } 99%,100% { opacity:.35; } }
  .m-caption { margin:10px 0 0; font-size:12.5px; color:var(--muted); line-height:1.7;
               border-top:1px solid var(--line-soft); padding-top:10px; max-width:56em; }
  /* ---- 發散圖讀法註解（對外限定）：貼著資料的標籤，欄位對齊 .erow ---- */
  .pub-ecap { display:none; }
  body.readonly .pub-ecap { display:grid; gap:12px; margin-top:2px;
                            grid-template-columns:140px minmax(120px,1fr) 56px 148px; }
  .pub-ecap .lr { grid-column:2; display:flex; justify-content:space-between;
                  gap:8px; font-size:11px; }
  .pub-ecap .l { color:var(--bad); } .pub-ecap .r { color:var(--ok); }
  .pub-ecap .m { color:var(--muted); }
  /* 對外的「最近交付」換 terminal 皮（科技感）：純 CSS 換裝，不動 render 邏輯 */
  body.readonly .dcards { background:var(--inset); border:1px solid var(--line);
                          border-radius:12px; padding:8px 14px; gap:0; }
  body.readonly .dcard { background:none; border:0; border-radius:0; padding:6px 0;
                         border-bottom:1px solid var(--line-soft);
                         font-family:ui-monospace,Consolas,monospace; }
  body.readonly .dcard:last-child { border-bottom:0; }
  /* ---- 響應式：<=1240 KPI 3 欄；<=980 收側欄、開手機導航；<=560 窄幅堆疊 ---- */
  @media (max-width:1240px){ .kpis { grid-template-columns:repeat(3,1fr); } }
  @media (max-width:980px){
    body { padding-left:0; }
    .rail { display:none; }
    .mnav { display:flex; }
    section.src { scroll-margin-top:118px; }  /* 頂欄含手機導航變高，錨點多讓一些 */
  }
  /* ---- 手機（<=640）：對外展示優先的響應式收斂 ---- */
  @media (max-width:640px){
    .main { padding:0 12px 40px; }
    section.src { padding:16px; border-radius:14px; margin-bottom:14px; }
    section.src > header { gap:8px; }
    section.src h2 { font-size:15px; }
    .pub-hero p { font-size:13px; }
    body.readonly .kpi-num { font-size:26px; }
    .pcard { padding:16px; }
    .pcard .val { font-size:28px; }
    .pcard.ring { gap:14px; }
    .ringviz, .ringviz svg { width:88px; height:88px; }
    .ringviz .ctr { font-size:18px; }
    /* runs 表格手機收四欄：藏心跳(3)/void(6)/最近活動(7)，保 run/狀態/進度/通過率 */
    .rtbl th:nth-child(3), .rtbl td:nth-child(3),
    .rtbl th:nth-child(6), .rtbl td:nth-child(6),
    .rtbl th:nth-child(7), .rtbl td:nth-child(7) { display:none; }
    .rtbl { font-size:13px; }
    .rtbl th, .rtbl td { padding:8px 8px; }
    .rtbl .nm { max-width:110px; }
    .pbar { min-width:56px; }
    .sv-list { overflow-x:auto; }  /* 最後保險：真擠不下就欄內捲，不撐爆頁面 */
    .term .tbody { font-size:11px; }
    .gw-tabs { flex-wrap:wrap; }
    .eco-grid, .machines, .hermes-grid { gap:12px; }
    .ccard { padding:12px; }
    .m-stage { gap:10px; }
    .m-caption { font-size:12px; }
  }
  @media (max-width:560px){
    .kpis, body.readonly .kpis { grid-template-columns:repeat(2,1fr); gap:8px; }
    .pub-hero h2 { font-size:21px; }
    .sv-diag-t { font-size:18px; }
    /* 名冊列窄幅改堆疊：固定欄寬 grid 在手機會撐出整頁橫向捲動 */
    .erow { grid-template-columns:1fr auto;
            grid-template-areas:"nm val" "bar bar" "meta meta"; gap:6px 10px; }
    .erow .e-nm { grid-area:nm; } .erow .e-sc { grid-area:val; }
    .erow .dbar { grid-area:bar; } .erow .e-meta { grid-area:meta; justify-content:flex-start; }
    .eaxis, body.readonly .pub-ecap { display:none; }
  }
  /* 手機觸控命中區補到 ≥36px（WCAG 2.5.8 之上），視覺尺寸不變 */
  @media (pointer:coarse){
    .seg { padding:10px 12px; }
    .svp-tab { padding:9px 12px; }
    .svp-close { padding:10px; margin:-6px -6px -6px auto; }
    .mnav a { padding:9px 14px; }
    .sv-ack { padding:9px 14px; }       /* 停滯知悉是主要 triage 動作，20px 高按不到 */
    .btns button { padding:9px 14px; }  /* trust/wipe/鏡像等操作鈕一併加大 */
  }
  /* 彈窗手機微調：滿寬留邊、底部讓 safe-area */
  @media (max-width:720px){
    .svp { padding-bottom:calc(18px + env(safe-area-inset-bottom)); }
  }
  @media (prefers-reduced-motion:reduce){ * { animation:none !important; transition:none !important; } }
</style></head>
<body>
<aside class="rail">
  <span class="rail-ind" id="rail-ind"></span>
  <a class="rail-logo" href="#" id="rail-top" title="回到頂端">V</a>
  <a class="rail-item" href="#sec-runs" data-sec="sec-runs" title="批次執行"><svg><use href="#i-runs"/></svg></a>
  <a class="rail-item" href="#sec-github" data-sec="sec-github" title="GitHub 歸檔 runs"><svg><use href="#i-git"/></svg></a>
  <a class="rail-item" href="#sec-eco" data-sec="sec-eco" title="信任生態"><svg><use href="#i-eco"/></svg></a>
  <a class="rail-item" href="#sec-lmstudio" data-sec="sec-lmstudio" title="LM Studio 機群"><svg><use href="#i-lm"/></svg></a>
  <a class="rail-item" href="#sec-hermes" data-sec="sec-hermes" title="Hermes 日誌"><svg><use href="#i-hermes"/></svg></a>
  <button class="rail-item rail-night" id="rail-night" title="亮色模式"><svg><use href="#i-moon" class="ic-moon"/><use href="#i-sun" class="ic-sun"/></svg></button>
</aside>
<div class="main">
<header class="topbar">
  <span class="dot" id="health"></span>
  <h1>Vacant 監測台</h1>
  <span class="sys-phrase" id="sv-dtext">連線中…</span>
  <div id="status">連線中…</div>
  <span class="ro-badge">唯讀公開檢視</span>
  <div class="srcbar" id="srcbar"></div>
  <nav class="mnav">
    <a href="#sec-runs" data-sec="sec-runs">批次執行</a>
    <a href="#sec-github" data-sec="sec-github">GitHub</a>
    <a href="#sec-eco" data-sec="sec-eco">信任生態</a>
    <a href="#sec-lmstudio" data-sec="sec-lmstudio">LM Studio</a>
    <a href="#sec-hermes" data-sec="sec-hermes">Hermes</a>
  </nav>
</header>
<!-- 對外 hero：一句話結論置頂（僅 readonly 顯示；科學傳播原則——先給結論再給數字） -->
<div class="pub-hero">
  <h2>6 個 AI agent 互相審核、彼此交付——<br>
      誠實的 agent <span class="up">信任上升</span>，搗亂的 <span class="down">信任下降</span>。</h2>
  <p>沒有人工介入：任務由系統派發，成果由其他 agent 審核，信用分數全靠帳本（ledger）累積。
     你現在看到的是即時資料。</p>
</div>
<div class="kpis">
  <div class="kpi"><div class="kpi-lbl"><span class="kpi-ico accent" id="k-active-ico"><svg class="ic"><use href="#i-runs"/></svg></span>進行中 runs<span class="kpi-tag" id="k-active-tag" hidden></span></div>
    <div class="kpi-num" id="k-active-num">–</div>
    <div class="kpi-spark" id="k-active-spark" title="全 runs 合計吞吐 · 近 3 小時（5 分鐘/桶）"></div></div>
  <div class="kpi" id="kpi-stall"><div class="kpi-lbl"><span class="kpi-ico" id="k-stall-ico"><svg class="ic"><use href="#i-warn"/></svg></span>停滯<span class="kpi-tag" id="k-stall-tag" hidden></span></div>
    <div class="kpi-num" id="k-stall-num">–</div></div>
  <div class="kpi"><div class="kpi-lbl"><span class="kpi-ico" id="k-pass-ico"><svg class="ic"><use href="#i-check"/></svg></span>通過率<span class="kpi-tag">累計</span></div>
    <div class="kpi-num" id="k-pass-num">–</div>
    <div class="kpi-spark" id="k-pass-spark" title="逐桶通過率 · 近 3 小時（5 分鐘/桶）"></div></div>
  <div class="kpi" title="跨所有 run 累計（trace 口徑）：模型回空/耗盡而作廢的比率"><div class="kpi-lbl"><span class="kpi-ico" id="k-void-ico"><svg class="ic"><use href="#i-skip"/></svg></span>void 率<span class="kpi-tag">trace</span></div>
    <div class="kpi-num" id="k-void-num">–</div></div>
  <div class="kpi k-internal"><div class="kpi-lbl"><span class="kpi-ico" id="k-lm-ico"><svg class="ic"><use href="#i-lm"/></svg></span>LM Studio 在線<span class="kpi-tag">24h</span></div>
    <div class="kpi-num" id="k-lm-num">–</div></div>
  <div class="kpi k-internal"><div class="kpi-lbl"><span class="kpi-ico" id="k-hermes-ico"><svg class="ic"><use href="#i-hermes"/></svg></span>Hermes 串流<span class="kpi-tag" id="k-hermes-tag" hidden></span></div>
    <div class="kpi-num" id="k-hermes-num">–</div></div>
</div>
<section class="src" id="sec-runs">
  <header><h2><svg class="ic"><use href="#i-runs"/></svg><span id="ttl-runs">批次執行</span></h2>
    <span class="hint" id="runs-hint">X1/X3 夜跑</span></header>
  <p class="pub-story" id="ps-story">系統把任務自動派給 agent 執行——這裡是每一批任務的即時進度與通過情況。</p>
  <!-- 對外統整卡（mockup_external 三卡；數字由 renderKPIs 接真實 run 資料） -->
  <div class="pub-stats">
    <div class="pcard"><div class="lbl">自動派發任務</div>
      <div class="val"><span id="ps-done">–</span> <small>件</small></div>
      <div class="cap">全部由 agent 自主執行，無人工介入</div></div>
    <div class="pcard ring">
      <div class="ringviz"><svg viewBox="0 0 120 120" aria-hidden="true">
        <circle class="track" cx="60" cy="60" r="52"/>
        <circle class="arc" id="ps-arc" cx="60" cy="60" r="52" stroke-dasharray="0 326.7"/></svg>
        <div class="ctr" id="ps-rate">–</div></div>
      <div><div class="lbl">審查通過率</div>
        <div class="cap">成果要通過審查<br>才算交付成功</div></div></div>
    <div class="pcard link" onclick="pubGoEco()" role="button" tabindex="0"
         onkeydown="if(event.key==='Enter')pubGoEco()">
      <div class="lbl">被攔下的交付</div>
      <div class="val bad"><span id="ps-fail">–</span> <small>件</small></div>
      <div class="cap">審查未過就退回——多來自低信任 agent，點我看下方信任生態 ↓</div></div>
  </div>
  <div class="toolbar" id="run-toolbar" hidden>
    <label class="search"><svg><use href="#i-search"/></svg><input id="run-q" placeholder="搜尋 run_id / 臂" aria-label="搜尋 run_id 或臂"><span class="kbdhint" title="按 / 聚焦搜尋">/</span></label>
    <div class="segs" id="sv-segs">
      <button class="seg active" data-st="all">全部 <span id="svc-all"></span></button>
      <button class="seg" data-st="running">執行中 <span id="svc-running"></span></button>
      <button class="seg" data-st="stalled">停滯 <span id="svc-stalled"></span></button>
      <button class="seg" data-st="paused">暫停 <span id="svc-paused"></span></button>
      <button class="seg" data-st="done">完成 <span id="svc-done"></span></button>
    </div>
    <select id="sv-sort" class="sv-sel" title="排序" aria-label="排序">
      <option value="sev">嚴重優先</option>
      <option value="recent">最近活動</option>
      <option value="prog">進度</option>
      <option value="pass">通過率</option>
      <option value="void">void 率</option>
      <option value="name">名稱</option>
    </select>
  </div>
  <div id="sv-chips" hidden></div>
  <div class="sv-main">
    <div class="sv-list" id="sv-list">
      <div class="empty" id="sv-off" hidden>來源已關閉</div>
      <table class="rtbl" id="sv-tbl" hidden>
        <thead><tr>
          <th>run</th><th>狀態</th><th>心跳</th><th style="width:20%">進度</th>
          <th class="r">通過率</th><th class="r">void</th><th class="r">最近活動</th>
        </tr></thead>
        <tbody id="sv-tbody"></tbody>
      </table>
      <div class="empty" id="sv-loading">載入中…</div>
    </div>
    <div id="sv-panel" class="modal" aria-hidden="true"><div class="svp" id="svp-body"></div></div>
  </div></section>
<section class="src" id="sec-github">
  <header><h2><svg class="ic"><use href="#i-git"/></svg>GitHub 歸檔 runs</h2>
    <span class="hint" id="gh-hint"></span>
    <div class="actions" id="gh-actions"></div></header>
  <div id="gh-sync"><div class="empty">載入中…</div></div>
  <div id="gh-body"></div></section>
<section class="src" id="sec-eco">
  <header><h2><svg class="ic"><use href="#i-eco"/></svg>信任生態</h2>
    <span class="hint" id="eco-hint"></span>
    <div class="actions" id="eco-actions"></div></header>
  <p class="pub-story">每個 agent 都從中性的 <b>0.5</b> 出發：把事情做好，信任往右長；交出爛成果被審核抓到，
    信任往左掉。<b>系統沒被告知誰是搗亂者——是信任分數自己把他們找出來的。</b></p>
  <!-- 機制小動畫（對外限定，純 CSS 循環）：交付 → 審查 → 信用升降 -->
  <div class="pub-mech" aria-label="信用分數如何變化：agent 交付成果，其他 agent 審查，信用分數隨結果升降">
    <div class="m-stage">
      <div class="m-node">
        <span class="m-agentbox">
          <span class="m-avatar"><svg class="ic"><use href="#i-eco"/></svg></span>
          <span class="m-pkg"><svg class="ic"><use href="#i-runs"/></svg></span>
        </span>
        <span class="m-cap">agent 交付成果</span>
      </div>
      <span class="m-arrow">→</span>
      <div class="m-node">
        <span class="m-revs"><i></i><i></i><i></i></span>
        <span class="m-cap">其他 agent 審查</span>
      </div>
      <span class="m-arrow">→</span>
      <div class="m-node">
        <span class="m-cred"><i class="fb"></i><i class="fg"></i></span>
        <span class="m-cap">信用分數升降</span>
      </div>
    </div>
    <div class="m-scenes">
      <span class="m-sc sc-good">✓ 好好交付 → 審查通過 → 信用往右長</span>
      <span class="m-sc sc-bad">✕ 交出爛成果 → 被抓包退回 → 信用往左掉</span>
    </div>
    <p class="m-caption">信用分數就像外送平台的星等——每一筆交付都由其他 agent 評分：
      好評累積，星等越高、越常被派單；一直出包被退，星等就掉，單子也不會再來。</p>
  </div>
  <div id="eco"><div class="empty">載入中…</div></div></section>
<section class="src" id="sec-lmstudio">
  <header><h2><svg class="ic"><use href="#i-lm"/></svg>LM Studio 機群</h2>
    <span class="hint" id="lm-hint"></span>
    <div class="actions" id="lm-actions"></div></header>
  <div id="lmstudio"><div class="empty">載入中…</div></div></section>
<section class="src" id="sec-hermes">
  <header><h2><svg class="ic"><use href="#i-hermes"/></svg>Hermes 日誌收取</h2>
    <span class="hint" id="hermes-hint"></span>
    <div class="actions" id="hermes-actions"></div></header>
  <div id="hermes"></div><div id="hermes-live"></div></section>
</div>
<div id="sv-backdrop"></div>
<!-- 模型 I/O 記錄：獨立彈窗（入口鈕在 Hermes 收取狀態卡） -->
<div id="io-modal" class="modal" aria-hidden="true"><div class="svp wide">
  <div class="svp-head"><b>模型 I/O 記錄</b><span class="hint" id="io-hint"></span>
    <button class="svp-close" onclick="ioClose()" title="關閉" aria-label="關閉"><svg class="ic"><use href="#i-x"/></svg></button></div>
  <div id="io-list"><div class="empty">（尚無記錄——先按「收取 logs」）</div></div>
</div></div>
<div id="sv-toast" role="status"></div>
<svg style="display:none" aria-hidden="true"><defs>
  <symbol id="i-logo" viewBox="0 0 24 24" fill="currentColor" stroke="none">
    <rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="8" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/></symbol>
  <symbol id="i-runs" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 12.5l9 5 9-5"/><path d="M3 16.5l9 5 9-5"/></symbol>
  <symbol id="i-git" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="8" r="2"/><path d="M6 7v10"/><path d="M18 10c0 4-6 3-11.2 7.6"/></symbol>
  <symbol id="i-eco" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z"/><path d="M9 12l2 2 4-4"/></symbol>
  <symbol id="i-lm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <rect x="7" y="7" width="10" height="10" rx="2"/><path d="M9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4"/></symbol>
  <symbol id="i-hermes" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="1.6"/><path d="M8.2 8.2a5.4 5.4 0 0 0 0 7.6M15.8 8.2a5.4 5.4 0 0 1 0 7.6M5.4 5.4a9.4 9.4 0 0 0 0 13.2M18.6 5.4a9.4 9.4 0 0 1 0 13.2"/></symbol>
  <symbol id="i-search" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="11" cy="11" r="7"/><path d="M20 20l-3.8-3.8"/></symbol>
  <symbol id="i-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M5 13l4 4L19 7"/></symbol>
  <symbol id="i-pause" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
    <path d="M9 5v14M15 5v14"/></symbol>
  <symbol id="i-play" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M8 5l11 7-11 7V5z"/></symbol>
  <symbol id="i-stop" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round">
    <rect x="6" y="6" width="12" height="12" rx="2"/></symbol>
  <symbol id="i-skip" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M5 5l9 7-9 7V5z"/><path d="M19 5v14"/></symbol>
  <symbol id="i-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M6 9l6 6 6-6"/></symbol>
  <symbol id="i-download" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 3v10M8 9l4 4 4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></symbol>
  <symbol id="i-mirror" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M20 11a8 8 0 0 0-14.9-3M4 13a8 8 0 0 0 14.9 3"/><path d="M4 5v4h4M20 19v-4h-4"/></symbol>
  <symbol id="i-warn" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 3.5L21.5 20h-19L12 3.5z"/><path d="M12 10v4.5M12 17.6v.01"/></symbol>
  <symbol id="i-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
    <path d="M6 6l12 12M18 6L6 18"/></symbol>
  <symbol id="i-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/></symbol>
  <symbol id="i-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="4"/>
    <path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M19.1 4.9l-1.8 1.8M6.7 17.3l-1.8 1.8"/></symbol>
</defs></svg>
<script>
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function post(url, body, _retried){
  const headers = {'Content-Type':'application/json'};
  const tok = localStorage.getItem('vacant_mon_token');
  if(tok) headers['X-Vacant-Token'] = tok;
  const r = await fetch(url, {method:'POST', headers, body: JSON.stringify(body||{})});
  if(r.status === 401 && !_retried){
    const t = prompt('這台監測台設定了操作 token，請輸入：');
    if(t){ localStorage.setItem('vacant_mon_token', t); return post(url, body, true); }
  }
  let j = null; try { j = await r.json(); } catch(_){}
  if(!r.ok || (j && j.ok === false)) alert('操作失敗：' + (j && j.error ? j.error : r.status));
  refresh();
  return j;
}

// ---------- 來源開關 ----------
let SRC = {runs:true, eco:true, lmstudio:true, hermes:true};
/* 唯讀公開模式偵測（一次）：藏操作件；徽章是兩個 topbar 裡的靜態 .ro-badge */
fetch('/api/mode').then(r=>r.json()).then(m=>{
  if(m && m.readonly){
    document.body.classList.add('readonly');
    // 對外用語：老師 8/14 裁定的區塊名是「任務執行狀況」（內部保留批次術語）
    const t = document.getElementById('ttl-runs');
    if(t) t.textContent = '任務執行狀況';
    if(cache.runs) renderKPIs();  // readonly class 掛上後補畫統整卡（避免首輪資料先到的競態）
  }
}).catch(()=>{});
function renderSrcBar(){
  $('#srcbar').innerHTML = Object.entries(SRC).map(([k,v]) =>
    `<label class="op-only ${v?'on':''}"><input type="checkbox" ${v?'checked':''}
       onchange="post('/api/sources',{source:'${k}',enabled:this.checked})"><span>${k}</span></label>`
  ).join('');
  for(const k of Object.keys(SRC))
    document.getElementById('sec-'+k).classList.toggle('off', !SRC[k]);
}

// ---------- 側欄／手機導航 scroll-spy（含滑動發光指示塊） ----------
const SECS = ['sec-runs','sec-eco','sec-lmstudio','sec-hermes'];
function moveRailInd(){
  const ind = document.getElementById('rail-ind');
  const act = document.querySelector('.rail-item.active');
  if(!ind) return;
  if(!act){ ind.classList.remove('on'); return; }
  ind.classList.add('on');
  ind.style.transform = 'translateY(' + act.offsetTop + 'px)';
}
function setActiveSec(id){
  document.querySelectorAll('[data-sec]').forEach(a =>
    a.classList.toggle('active', a.dataset.sec === id));
  moveRailInd();
}
function spy(){
  let cur = SECS[0];
  for(const id of SECS){
    const el = document.getElementById(id);
    if(el && el.getBoundingClientRect().top < 150) cur = id;
  }
  setActiveSec(cur);
}
// 點側欄：指示塊立刻滑過去（不等平滑捲動抵達），到站後 spy 會再確認
document.querySelector('.rail').addEventListener('click', e => {
  const item = e.target.closest('.rail-item');
  if(item) setActiveSec(item.dataset.sec);
});
document.getElementById('rail-top').addEventListener('click', e => {
  e.preventDefault();
  scrollTo({top: 0, behavior: 'smooth'});
});
let spyPending = false;
addEventListener('scroll', () => {
  if(spyPending) return;
  spyPending = true;
  requestAnimationFrame(() => { spyPending = false; spy(); });
}, {passive:true});
spy();

// ---------- runs ----------
// 名字/ID 一律走 data-* 屬性再由 handler 讀 dataset（不內插進 JS 字串——
// 內插字串遇單引號會壞；HTML 屬性上下文配 esc() 才是對的跳脫層）
function runCtl(el, cmd){
  if(cmd==='stop' && !confirm('終止？（下一題開始前收工，已完成不受影響）')) return;
  post('/api/runs/'+encodeURIComponent(el.dataset.rid)+'/control', {cmd});
}
function runSkip(el){
  const input = el.previousElementSibling;
  if(!input.value) return;
  post('/api/runs/'+encodeURIComponent(el.dataset.rid)+'/control',
       {cmd:'skip', task_id: input.value});
  input.value = '';
}
// 各來源最新快取（KPI 與 filter 重繪都吃這裡，不重新 fetch）
// 注意：不能叫 last——renderHermes 內有同名區域 const，會踩 TDZ
const cache = {runs:null, eco:null, lm:null, hermes:null, live:null, gh:null};

// 狀態的單一真相：row icon／pill／sparkline 同色（stalled 蓋過一切；finished 靜音）
// late＝停滯前的琥珀中間態；暫停/收尾是刻意閒置，不算遲滯（觀察歸觀察、意圖歸意圖）
const lateOf = r => !!(r.late && !r.stalled && !r.finished && r.control_state === 'running');
function statusOf(r){
  if(r.stalled) return r.acked ? {k:'warn', icon:'i-warn'} : {k:'bad', icon:'i-warn'};
  if(r.finished) return {k:'', icon:'i-check'};
  if(r.control_state==='paused' || r.control_state==='stop_after_current')
    return {k:'warn', icon:'i-pause'};
  if(lateOf(r)) return {k:'warn', icon:'i-warn'};
  return {k:'ok', icon:'i-play'};
}
// ---------- KPI 卡（各來源 render 後都會呼叫；缺料顯示 –，不顯示假 0） ----------
// KPI 迷你走勢：跨 run 以「絕對 5 分鐘桶」合併（各 run 的 spark t0 皆桶對齊）
function kpiSparks(rows){
  const merged = new Map();  // 絕對桶 index → [done, pass]
  (rows || []).forEach(r => {
    const sp = r.spark;
    if(!sp) return;
    const b0 = Math.floor(sp.t0_ms / 300000);
    sp.buckets.forEach((b, i) => {
      const m = merged.get(b0 + i) || [0, 0];
      m[0] += b[0]; m[1] += b[1];
      merged.set(b0 + i, m);
    });
  });
  if(merged.size < 2){ kpiSpark('k-active-spark', null); kpiSpark('k-pass-spark', null); return; }
  const keys = [...merged.keys()].sort((a, b) => a - b);
  const last = keys[keys.length - 1], first = Math.max(keys[0], last - 35);
  const B = [];
  for(let k = first; k <= last; k++) B.push(merged.get(k) || [0, 0]);
  kpiSpark('k-active-spark', B.map(b => b[0]), 'var(--accent)', true);
  kpiSpark('k-pass-spark', B.map(b => b[0] ? Math.round(100 * b[1] / b[0]) : null), 'var(--ok)', false);
}
function kpiSpark(id, vals, col, area){
  const host = document.getElementById(id);
  if(!host) return;
  const key = JSON.stringify(vals || null);
  if(host.dataset.j === key) return;
  host.dataset.j = key;
  if(!vals || vals.filter(v => v != null).length < 2){ host.innerHTML = ''; return; }
  const W = 132, H = 26, n = vals.length;
  const mx = Math.max.apply(null, vals.filter(v => v != null).concat([1]));
  const x = i => (i * (W / (n - 1))).toFixed(1);
  const y = v => (H - 2 - v / mx * (H - 5)).toFixed(1);
  // null（該桶無完成格）＝斷線缺口，不畫 0 假裝有資料
  const segs = [];
  let cur = [];
  vals.forEach((v, i) => {
    if(v == null){ if(cur.length > 1) segs.push(cur); cur = []; return; }
    cur.push(x(i) + ',' + y(v));
  });
  if(cur.length > 1) segs.push(cur);
  const lines = segs.map(s =>
    `<polyline points="${s.join(' ')}" fill="none" stroke="${col}" stroke-width="1.5"
       stroke-linecap="round" stroke-linejoin="round"/>`).join('');
  const fill = area && segs.length === 1 && vals.every(v => v != null)
    ? `<polygon points="0,${H} ${segs[0].join(' ')} ${W},${H}" fill="${col}" opacity=".14"/>` : '';
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${fill}${lines}</svg>`;
}
function renderKPIs(){
  const rows = cache.runs;
  if(rows){
    const act = rows.filter(r => !r.finished).length;
    const stall = rows.filter(r => r.stalled && !r.acked).length;
    const stallAck = rows.filter(r => r.stalled && r.acked).length;
    const tagEl = $('#k-stall-tag');
    tagEl.hidden = !stallAck;
    if(stallAck) tagEl.textContent = '已知悉 ' + stallAck;
    let pass = 0, fin = 0, tvoid = 0, ttotal = 0;
    rows.forEach(r => {
      pass += r.by_outcome.pass||0;
      fin += (r.by_outcome.pass||0) + (r.by_outcome.fail||0);
      tvoid += r.trace_void||0; ttotal += r.trace_total||0;
    });
    $('#k-active-num').textContent = act;
    $('#k-stall-num').textContent = stall;
    $('#k-stall-ico').className = 'kpi-ico' + (stall ? ' bad' : '');
    $('#kpi-stall').classList.toggle('alert', !!stall);
    $('#k-pass-num').innerHTML = fin ? Math.round(100*pass/fin) + '<small>%</small>' : '–';
    $('#k-pass-ico').className = 'kpi-ico' + (fin ? ' ok' : '');
    const vr = ttotal ? 100*tvoid/ttotal : null;
    $('#k-void-num').innerHTML = vr!=null ? vr.toFixed(1) + '<small>%</small>' : '–';
    $('#k-void-ico').className = 'kpi-ico' + (vr!=null ? (vr>5 ? ' bad' : ' ok') : '');
    kpiSparks(rows);
    // 對外統整卡（readonly 才顯示；用同一組 pass/fin，數字口徑一致）
    if(document.body.classList.contains('readonly')){
      const rate = fin ? Math.round(100*pass/fin) : null;
      $('#ps-done').textContent = fin || '–';
      $('#ps-fail').textContent = fin ? fin - pass : '–';
      $('#ps-rate').textContent = rate != null ? rate + '%' : '–';
      $('#ps-arc').setAttribute('stroke-dasharray',
        (rate != null ? (326.7 * rate / 100).toFixed(1) : 0) + ' 326.7');
      if(fin) $('#ps-story').innerHTML = `到目前為止，系統自動派發了 <b>${fin} 件任務</b>，
        審查通過率 <b>${rate}%</b>；未通過的 <b>${fin - pass} 件</b>被攔下退回，不會混進成果。`;
    }
  } else {
    // 來源關閉／尚無資料：誠實顯示 –，不留舊數字
    for(const id of ['k-active-num','k-stall-num','k-pass-num','k-void-num'])
      $('#'+id).textContent = '–';
    for(const id of ['k-stall-ico','k-pass-ico','k-void-ico'])
      $('#'+id).className = 'kpi-ico';
    $('#kpi-stall').classList.remove('alert');
    kpiSpark('k-active-spark', null);
    kpiSpark('k-pass-spark', null);
  }
  const l = cache.lm;
  if(l){
    let on = 0, tot = 0;
    (l.hubs||[]).forEach(h =>
      (((h.overview||{}).machines)||[]).forEach(m => { tot++; if(m.reachable) on++; }));
    $('#k-lm-num').innerHTML = tot ? `${on}<small>/${tot} 台</small>` : '–';
    $('#k-lm-ico').className = 'kpi-ico' +
      (tot ? (on===tot ? ' ok' : (on ? ' warn' : ' bad')) : '');
  }
  const lv = cache.live;
  if(lv){
    if(lv.enabled===false || lv.running===false){
      $('#k-hermes-num').textContent = '–';
      $('#k-hermes-ico').className = 'kpi-ico';
    } else {
      const m = {online:['直播中','ok'], connecting:['連線中','warn'], offline:['離線','bad']}[lv.status] || ['–',''];
      $('#k-hermes-num').textContent = m[0];
      $('#k-hermes-ico').className = 'kpi-ico' + (m[1] ? ' ' + m[1] : '');
    }
  }
  // 整體健康點：停滯／chain✗／hub 無回應 → 紅；void 過閾／機器離線／串流離線 → 黃
  const h = healthOf();
  const he = $('#health');
  he.className = 'dot ' + h + (h==='bad' ? ' pulse' : '');
  he.title = {ok: '系統正常', warn: '有項目需要留意', bad: '偵測到異常'}[h] || '';
  svDiag();  // 診斷句跟著所有來源的最新快取一起更新
}
function healthOf(){
  const rows = cache.runs || [];
  const eco = cache.eco, lm = cache.lm, lv = cache.live;
  const chainBad = !!(eco && (eco.roster||[]).some(r => !r.chain_ok));
  const hubDown = !!(lm && (lm.hubs||[]).some(h => h.ok === false));
  const machineDown = !!(lm && (lm.hubs||[]).some(h =>
    (((h.overview||{}).machines)||[]).some(m => !m.reachable)));
  const voidHot = rows.some(r => (r.void_rate||0) > 0.05);
  const liveOff = !!(lv && lv.enabled !== false && lv.running !== false && lv.status === 'offline');
  if(rows.some(r => r.stalled && !r.acked) || chainBad || hubDown) return 'bad';
  if(voidHot || machineDown || liveOff || rows.some(r => r.stalled && r.acked)
     || rows.some(lateOf)) return 'warn';
  return 'ok';
}

// ---------- 批次執行區共用小工具 ----------
// 數字 count-up（值有變才補間；reduced-motion 直接落定）
function tween(el, to, fmt){
  if(!el) return;
  let from = parseFloat(el.dataset.v);
  if(isNaN(from)) from = 0;
  el.dataset.v = to;
  if(from === to || document.hidden || matchMedia('(prefers-reduced-motion: reduce)').matches){
    el.textContent = fmt(to); return;  // 隱藏分頁 rAF 不跑，直接落定
  }
  const t0 = performance.now();
  (function f(){
    const p = Math.min(1, (performance.now() - t0) / 400);
    const e2 = 1 - Math.pow(1 - p, 3);
    el.textContent = fmt(from + (to - from) * e2);
    if(p < 1) requestAnimationFrame(f);
  })();
}
function updateTitle(){
  // 只數「未知悉」的停滯——已知悉不再佔用警示位
  const n = (cache.runs || []).filter(r => r.stalled && !r.acked).length;
  document.title = n ? `⚠(${n}) Vacant — 監測台` : 'Vacant — 監測台';
}
// 時間顯示統一：盯盤看相對、對帳看 title 絕對；跨日自動帶日期（夜跑跨午夜是常態）
function fmtWhen(ms){
  if(!ms) return '–';
  const d = Date.now() - ms;
  if(d < 60000) return '剛剛';
  if(d < 3600000) return Math.floor(d / 60000) + ' 分鐘前';
  const t = new Date(ms), now = new Date();
  const hh = ('0' + t.getHours()).slice(-2) + ':' + ('0' + t.getMinutes()).slice(-2);
  const sameDay = t.getFullYear() === now.getFullYear() &&
    t.getMonth() === now.getMonth() && t.getDate() === now.getDate();
  return sameDay ? hh : (t.getMonth() + 1) + '/' + t.getDate() + ' ' + hh;
}
const fmtAbs = ms => ms ? new Date(ms).toLocaleString() : '–';
let toastTimer = null;
function toast(msg){
  const el = $('#sv-toast');
  el.textContent = msg;
  el.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('on'), 2600);
}

// ---- 批次執行區：run 列（keyed DOM，跨輪詢原地更新＝動畫不被 innerHTML 打斷） ----
const svRowEls = new Map();
let svFilter = 'all', svQuery = '', svOpenRid = null, svEntered = false, svPrevOrder = '';
let svSort = 'sev';
try { svSort = localStorage.getItem('vacant_mon_sort') || 'sev'; } catch(e){}
let doneOpen = false;
try { doneOpen = localStorage.getItem('vacant_mon_done') === '1'; } catch(e){}
// 排序：停滯恆置頂、已完成恆沉底（摺疊群組依賴連續性），中間依所選鍵
function svKey(r){
  const o = r.by_outcome, d = (o.pass || 0) + (o.fail || 0);
  switch(svSort){
    case 'recent': return -(r.last_activity_ms || 0);
    case 'prog': return -(r.planned_total ? r.total_done / r.planned_total : (r.finished ? 1 : 0));
    case 'pass': return -(d ? o.pass / d : -1);
    case 'void': return -(r.void_rate || 0);
    case 'name': return 0;
    default: return svOrder(r);
  }
}
function svMatch(r){
  if(svQuery){  // 純 includes 比對（刻意不用 regex——_PAGE 是 Python 字串，跳脫序列是雷）
    const hay = (r.run_id + ' ' + Object.keys(r.by_worker || {}).join(' ')).toLowerCase();
    if(!hay.includes(svQuery)) return false;
  }
  if(svFilter === 'stalled') return r.stalled;
  if(svFilter === 'done') return r.finished;
  if(svFilter === 'paused') return !r.finished && !r.stalled &&
    (r.control_state === 'paused' || r.control_state === 'stop_after_current');
  if(svFilter === 'running') return !r.finished && !r.stalled && r.control_state === 'running';
  return true;
}
// 已知悉的停滯降一級（排在執行中之後），新停滯永遠最上；遲滯插在停滯與執行中之間
const svOrder = r => r.stalled ? (r.acked ? 2 : 0)
  : (lateOf(r) ? 0.5
  : (!r.finished && r.control_state === 'running' ? 1 : (!r.finished ? 3 : 4)));
// spark 桶序列（停滯/遲滯 run 尾端補零到現在、上限 36 桶）——列的迷你圖與面板大圖共用
function svBuckets(r){
  const sp = r.spark;
  let B = sp ? sp.buckets.slice() : [];
  if((r.stalled || lateOf(r)) && sp){
    const lastB = Math.floor(sp.t0_ms / 300000) + B.length - 1;
    let pad = Math.min(Math.floor(Date.now() / 300000) - lastB, 36 - B.length);
    while(pad-- > 0) B.push([0, 0]);
  }
  return B;
}
function svPhrase(r){
  if(r.stalled){
    const m = Math.floor((r.idle_s || 0) / 60);
    const span = m >= 60 ? Math.floor(m/60) + ' 小時 ' + (m%60) + ' 分' : m + ' 分鐘';
    if(r.acked) return {t: '停滯（已知悉）· ' + span + '無新進度', warn: true};
    return {t: '停滯 · ' + span + '無新進度', bad: true};
  }
  if(r.finished){
    const o = r.by_outcome, d = (o.pass||0) + (o.fail||0);
    return {t: '已完成' + (d ? ' · 通過率 ' + Math.round(100*o.pass/d) + '%' : '')};
  }
  if(r.control_state === 'paused')
    return {t: '已暫停 · 停在 ' + r.total_done + (r.planned_total ? '/' + r.planned_total : '') + ' 格'};
  if(r.control_state === 'stop_after_current') return {t: '收尾中 · 本題結束後停止'};
  if(lateOf(r)){
    const m = Math.floor((r.idle_s || 0) / 60);
    return {t: '遲滯 · ' + m + ' 分鐘無新進度（停滯門檻 ' + Math.round(r.stall_min || 0) + 'm）', warn: true};
  }
  let t = '執行中';
  if(r.eta_min != null)
    t += ' · 預計剩餘 ' + (r.eta_min >= 60 ? Math.floor(r.eta_min/60) + ' 小時 ' + (r.eta_min%60) + ' 分' : r.eta_min + ' 分鐘');
  else if(r.rate_per_min) t += ' · ' + r.rate_per_min + ' 格/分';
  return {t};
}
function svRowEl(r){
  const el = document.createElement('tr');
  el.className = 'sv-row';
  el.dataset.rid = r.run_id;
  el.tabIndex = 0;
  el.setAttribute('role', 'button');
  el.innerHTML = `
    <td><span class="nm" title="${esc(r.run_id)}">${esc(r.run_id)}</span></td>
    <td><span class="c-st"><svg class="sv-ico" aria-hidden="true"><use href="#i-play"/></svg>
      <span class="pill c-pill">–</span>
      <button class="sv-ack op-only" data-rid="${esc(r.run_id)}" hidden>知悉</button></span></td>
    <td><span class="hbm" aria-hidden="true"></span></td>
    <td><div class="pbar"><i class="p1"></i><i class="p2"></i></div></td>
    <td class="r num c-pass">–</td>
    <td class="r num c-void">–</td>
    <td class="r num c-act">–</td>`;
  el.addEventListener('click', () => svOpen(r.run_id));
  el.addEventListener('keydown', e => {
    if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); svOpen(r.run_id); }
  });
  el.querySelector('.sv-ack').addEventListener('click', e => {
    e.stopPropagation();
    svAck(r.run_id, true);
  });
  return el;
}
function svAck(rid, on){
  post('/api/runs/' + encodeURIComponent(rid) + '/ack', {on: on});
}
// 表格版狀態 pill：短字＋語意色；完整診斷句收進整列 title（hover 對帳）
function svPillOf(r){
  if(r.stalled) return r.acked
    ? {t:'停滯·已知悉', c:'warn'}
    : {t:'停滯 ' + Math.floor((r.idle_s || 0) / 60) + 'm', c:'bad'};
  if(r.finished) return {t:'完成', c:''};
  if(r.control_state === 'paused') return {t:'暫停', c:'warn'};
  if(r.control_state === 'stop_after_current') return {t:'收尾中', c:'warn'};
  if(lateOf(r)) return {t:'late ' + Math.floor((r.idle_s || 0) / 60) + 'm', c:'warn'};
  return {t:'執行中', c:'ok'};
}
function svUpdateRow(el, r){
  const st = statusOf(r);
  const running = !r.stalled && !r.finished && st.k === 'ok';
  const col = r.stalled ? (r.acked ? 'var(--warn)' : 'var(--bad)')
    : (r.finished ? 'rgba(62,207,142,.5)' : (st.k === 'warn' ? 'var(--warn)' : 'var(--ok)'));
  const ico = el.querySelector('.sv-ico');
  ico.querySelector('use').setAttribute('href', '#' + st.icon);
  ico.style.color = col;
  ico.setAttribute('class', 'sv-ico' + (running ? ' pulse-soft' : ''));
  const pill = svPillOf(r);
  const pe = el.querySelector('.c-pill');
  pe.textContent = pill.t;
  pe.className = 'pill c-pill' + (pill.c ? ' ' + pill.c : '');
  el.title = svPhrase(r).t + ' · ' + r.total_done
    + (r.planned_total ? '/' + r.planned_total : '') + ' 格';
  el.querySelector('.sv-ack').hidden = !(r.stalled && !r.acked);
  el.setAttribute('aria-expanded', svOpenRid === r.run_id ? 'true' : 'false');
  // 分段進度條：pass＋fail（＝完成進度）；停滯轉紅系維持警示強度
  const o = r.by_outcome, done = (o.pass || 0) + (o.fail || 0);
  const base = r.planned_total || (r.finished ? done : 0);
  const f1 = el.querySelector('.pbar .p1'), f2 = el.querySelector('.pbar .p2');
  f1.style.width = base ? Math.min(100, 100 * (o.pass || 0) / base).toFixed(1) + '%' : '0%';
  f2.style.width = base ? Math.min(100, 100 * (o.fail || 0) / base).toFixed(1) + '%' : '0%';
  f1.style.background = r.stalled ? (r.acked ? 'var(--warn)' : 'var(--bad)')
    : (r.finished ? 'rgba(62,207,142,.5)' : 'var(--ok)');
  f2.style.background = r.stalled ? (r.acked ? 'rgba(240,180,41,.45)' : 'rgba(255,84,112,.45)')
    : (r.finished ? 'rgba(240,180,41,.45)' : 'var(--warn)');
  el.querySelector('.pbar').title = `pass ${o.pass || 0} · fail ${o.fail || 0}`
    + (r.planned_total ? ` / 計畫 ${r.planned_total}` : '');
  // 通過率／void／最近活動（表格欄；等寬右對齊）
  el.querySelector('.c-pass').textContent = done ? Math.round(100 * (o.pass || 0) / done) + '%' : '–';
  const vr = r.trace_total ? 100 * (r.trace_void || 0) / r.trace_total : null;
  const cv = el.querySelector('.c-void');
  cv.textContent = vr != null ? vr.toFixed(1) + '%' : '–';
  cv.style.color = (vr || 0) > 5 ? 'var(--bad)' : '';
  const ca = el.querySelector('.c-act');
  ca.textContent = fmtWhen(r.last_activity_ms);
  ca.style.color = (r.stalled && !r.acked) ? 'var(--bad)' : (lateOf(r) ? 'var(--warn)' : '');
  el.classList.toggle('fin', !!r.finished);
  // 心跳欄：svBuckets 尾端最多 12 桶，高度跟量、顏色跟狀態（無資料留空不佔位）
  const hb = el.querySelector('.hbm');
  const B = svBuckets(r).slice(-12);
  if(B.length >= 2){
    const mx = Math.max.apply(null, B.map(b => b[0]).concat([1]));
    hb.innerHTML = B.map(b => {
      const h = b[0] ? Math.max(3, Math.round(3 + 12 * b[0] / mx)) : 2;
      const cls = !b[0] ? '' : (b[1] >= b[0] ? 'ok' : (b[1] > 0 ? 'mix' : 'bad'));
      return `<i class="${cls}" style="height:${h}px"></i>`;
    }).join('');
    hb.style.opacity = r.finished ? .5 : 1;
  } else hb.innerHTML = '';
  el.classList.toggle('sel', svOpenRid === r.run_id);
}
function renderRuns(rows){
  cache.runs = rows;
  updateTitle();
  watchTransitions(rows || []);
  const host = $('#sv-tbody');
  const tbl = $('#sv-tbl'), loading = $('#sv-loading');
  $('#sv-off').hidden = true;
  const alarm = r => (r.stalled && !r.acked) ? 1 : 0;  // 只有「未知悉」的停滯恆置頂
  const sorted = (rows || []).slice().sort((a,b) =>
    alarm(b) - alarm(a) ||
    (a.finished ? 1 : 0) - (b.finished ? 1 : 0) ||
    svKey(a) - svKey(b) ||
    (a.run_id < b.run_id ? -1 : 1));
  if(!sorted.length){
    svRowEls.clear(); svPrevOrder = '';
    host.innerHTML = '';
    tbl.hidden = true;
    loading.hidden = false;
    loading.textContent = 'runs 目錄下還沒有任何 run（找不到 ledger.jsonl）';
  } else {
    tbl.hidden = false;
    loading.hidden = true;
    const seen = new Set();
    sorted.forEach(r => {
      seen.add(r.run_id);
      let el = svRowEls.get(r.run_id);
      if(!el){ el = svRowEl(r); svRowEls.set(r.run_id, el); host.appendChild(el); }
      svUpdateRow(el, r);
    });
    for(const [rid, el] of [...svRowEls]){
      if(!seen.has(rid)){ el.remove(); svRowEls.delete(rid); }
    }
    // 順序（含「已完成」摺疊列位置）有變才搬 DOM，避免打斷 transition
    const firstFin = sorted.findIndex(r => r.finished);
    const order = sorted.map(r => r.run_id).join(',') + '|hdr@' + firstFin;
    if(order !== svPrevOrder){
      svPrevOrder = order;
      sorted.forEach((r, i) => {
        if(i === firstFin) host.appendChild(svDoneHdrEl());
        host.appendChild(svRowEls.get(r.run_id));
      });
      if(firstFin < 0 && doneHdr) doneHdr.remove();
    }
  }
  const cnt = {all: (rows||[]).length, running:0, stalled:0, paused:0, done:0};
  (rows||[]).forEach(r => {
    if(r.stalled) cnt.stalled++;
    else if(r.finished) cnt.done++;
    else if(r.control_state === 'paused' || r.control_state === 'stop_after_current') cnt.paused++;
    else cnt.running++;
  });
  $('#run-toolbar').hidden = !cnt.all;
  for(const k of ['all','running','stalled','paused','done']){
    const el = $('#svc-' + k);
    el.textContent = cnt[k] || '';
    el.style.color = (k === 'stalled' && cnt.stalled) ? 'var(--bad)' : '';
  }
  svApplyFilter();
  svPanelSync(); svFetchRecent(); renderKPIs();
  if(!svEntered && sorted.length){ svEntered = true; svEntrance(); }
  if(svHashPending){  // 深連結：資料到位後直開指定 run
    const rid = svHashPending;
    if(svRowEls.get(rid)){
      svHashPending = null;
      svOpen(rid);
      svRowEls.get(rid).scrollIntoView({block: 'center'});
    } else if((rows || []).length){
      svHashPending = null;
      toast('找不到 run：' + rid);
      history.replaceState(null, '', location.pathname + location.search);
    }
  }
}
// 已完成摺疊列（懶建、keyed reorder 時歸位）
let doneHdr = null;
function svDoneHdrEl(){
  if(doneHdr) return doneHdr;
  doneHdr = document.createElement('tr');
  doneHdr.id = 'sv-donehdr';
  doneHdr.innerHTML = '<td colspan="7"><span class="dh"><svg class="ic chev2"><use href="#i-chevron"/></svg>' +
    '<span>已完成 <b>0</b> 個 run</span></span></td>';
  doneHdr.addEventListener('click', () => {
    doneOpen = !doneOpen;
    try { localStorage.setItem('vacant_mon_done', doneOpen ? '1' : '0'); } catch(e){}
    svApplyFilter();
  });
  return doneHdr;
}
function svDoneApply(){
  const n = (cache.runs || []).filter(r => r.finished).length;
  const relevant = !!n && (svFilter === 'all' || svFilter === 'done');
  const host = $('#sv-list');
  if(doneHdr) doneHdr.hidden = !relevant;
  if(!relevant){ host.classList.remove('dc'); return; }
  const open = doneOpen || svFilter === 'done' || !!svQuery;
  host.classList.toggle('dc', !open);
  doneHdr.querySelector('b').textContent = n;
  doneHdr.querySelector('.chev2').style.transform = open ? 'rotate(180deg)' : '';
}
// 篩選套用（segs／搜尋／chips 共用單一出口）＋零結果空態
let noRes = null;
function svNoResEl(){
  if(noRes) return noRes;
  noRes = document.createElement('div');
  noRes.className = 'empty';
  noRes.id = 'sv-nores';
  noRes.innerHTML = '沒有符合目前篩選的 run　<button class="seg" id="sv-clearf">清除篩選</button>';
  noRes.querySelector('#sv-clearf').addEventListener('click', svClearFilters);
  return noRes;
}
function svClearFilters(){
  svFilter = 'all'; svQuery = '';
  $('#run-q').value = '';
  document.querySelectorAll('#sv-segs .seg').forEach(s =>
    s.classList.toggle('active', s.dataset.st === 'all'));
  svApplyFilter();
}
function svApplyFilter(){
  const rows = cache.runs || [];
  let vis = 0;
  rows.forEach(r => {
    const el = svRowEls.get(r.run_id);
    if(!el) return;
    const m = svMatch(r);
    el.classList.toggle('gone', !m);
    if(m) vis++;
  });
  const chips = [];
  if(svFilter !== 'all'){
    const nm = {running: '執行中', stalled: '停滯', paused: '暫停', done: '完成'}[svFilter];
    chips.push(`<span class="fchip" data-k="st">狀態: ${nm} <b>×</b></span>`);
  }
  if(svQuery) chips.push(`<span class="fchip" data-k="q">搜尋: ${esc(svQuery)} <b>×</b></span>`);
  const ch = $('#sv-chips');
  ch.hidden = !chips.length;
  ch.innerHTML = chips.join('') +
    (chips.length > 1 ? '<span class="fchip clear" data-k="all">全部清除</span>' : '');
  const host = $('#sv-list');
  if(rows.length && !vis) host.appendChild(svNoResEl());
  else if(noRes && noRes.parentNode) noRes.remove();
  svDoneApply();
}
$('#sv-chips').addEventListener('click', e => {
  const c = e.target.closest('.fchip');
  if(!c) return;
  if(c.dataset.k === 'st' || c.dataset.k === 'all'){
    svFilter = 'all';
    document.querySelectorAll('#sv-segs .seg').forEach(s =>
      s.classList.toggle('active', s.dataset.st === 'all'));
  }
  if(c.dataset.k === 'q' || c.dataset.k === 'all'){
    svQuery = ''; $('#run-q').value = '';
  }
  svApplyFilter();
});
$('#sv-sort').value = svSort;
$('#sv-sort').addEventListener('change', e => {
  svSort = e.target.value;
  try { localStorage.setItem('vacant_mon_sort', svSort); } catch(e2){}
  if(cache.runs) renderRuns(cache.runs);
});
// 背景警示三件套：轉變那一刻通知一次；favicon 紅點與 PWA badge 跟停滯數
let prevSnap = null, favAlert = false, notifAsked = false;
document.addEventListener('click', () => {
  if(notifAsked || !('Notification' in window)) return;
  notifAsked = true;
  if(Notification.permission === 'default') Notification.requestPermission().catch(()=>{});
}, {once: true});
function notify(body){
  try {
    if('Notification' in window && Notification.permission === 'granted')
      new Notification('Vacant 監測台', {body, icon: '/icon.svg'});
  } catch(e){}
}
function alertFavicon(on){
  if(on === favAlert) return;
  favAlert = on;
  const link = document.querySelector('link[rel="icon"]');
  if(!link) return;
  if(!on){ link.href = '/icon.svg'; return; }
  const cv = document.createElement('canvas');
  cv.width = 64; cv.height = 64;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#0f1115'; ctx.fillRect(0, 0, 64, 64);
  ctx.fillStyle = '#ff5470';
  ctx.beginPath(); ctx.arc(32, 32, 22, 0, 6.3); ctx.fill();
  link.href = cv.toDataURL('image/png');
}
function watchTransitions(rows){
  const snap = {};
  rows.forEach(r => {
    snap[r.run_id] = {st: !!r.stalled, fin: !!r.finished, vh: (r.void_rate || 0) > 0.05};
  });
  if(prevSnap) rows.forEach(r => {
    const p = prevSnap[r.run_id], c = snap[r.run_id];
    if(!p) return;
    if(c.st && !p.st) notify(r.run_id + ' 停滯：超過門檻無新進度');
    if(c.fin && !p.fin) notify(r.run_id + ' 已完成');
    if(c.vh && !p.vh) notify(r.run_id + ' void 率超過 5% 門檻');
  });
  prevSnap = snap;
  const n = rows.filter(r => r.stalled && !r.acked).length;
  alertFavicon(n > 0);
  try {
    if(navigator.setAppBadge){ n ? navigator.setAppBadge(n) : navigator.clearAppBadge(); }
  } catch(e){}
}
// 深連結：#run=<id> 直開側面板；返回手勢／hash 清除即關閉
let svHashPending = location.hash.indexOf('#run=') === 0
  ? decodeURIComponent(location.hash.slice(5)) : null;
function svSyncHash(){
  const want = svOpenRid ? '#run=' + encodeURIComponent(svOpenRid) : '';
  if(want && location.hash !== want) location.hash = want;
  else if(!want && location.hash.indexOf('#run=') === 0)
    history.replaceState(null, '', location.pathname + location.search);
}
addEventListener('hashchange', () => {
  const rid = location.hash.indexOf('#run=') === 0
    ? decodeURIComponent(location.hash.slice(5)) : null;
  if(!rid){ if(svOpenRid) svClose(true); return; }
  if(rid === svOpenRid) return;
  if(svRowEls.get(rid)){
    svOpen(rid);
    svRowEls.get(rid).scrollIntoView({block: 'center'});
  } else svHashPending = rid;
});
// 工具列是靜態 HTML（列表容器之外）——輪詢原地更新不會打斷搜尋框 focus
$('#run-q').addEventListener('input', e => {
  svQuery = e.target.value.trim().toLowerCase();
  svApplyFilter();
});
$('#sv-segs').addEventListener('click', e => {
  const b = e.target.closest('.seg');
  if(!b) return;
  svFilter = b.dataset.st;
  document.querySelectorAll('#sv-segs .seg').forEach(s => s.classList.toggle('active', s === b));
  svApplyFilter();
});
function svEntrance(){
  if(matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const els = [...document.querySelectorAll('.sv-row')].filter(el => !el.classList.contains('gone'));
  els.forEach(el => el.classList.add('pre'));
  void document.body.offsetHeight;
  els.forEach((el, i) => {
    el.style.transitionDelay = (i * 60) + 'ms';
    el.classList.remove('pre');
    setTimeout(() => { el.style.transitionDelay = ''; }, 500 + i * 60);
  });
}

// ---- 診斷句 hero：healthOf 翻成一句中文（KPI 上方） ----
function svDiag(){
  const rows = cache.runs || [];
  const h = healthOf();
  const stall = rows.filter(r => r.stalled && !r.acked).length;
  const stallAck = rows.filter(r => r.stalled && r.acked).length;
  const act = rows.filter(r => !r.finished && !r.stalled).length;
  const eco = cache.eco, lm = cache.lm, lv = cache.live;
  const chainBad = !!(eco && (eco.roster || []).some(x => !x.chain_ok));
  const hubDown = !!(lm && (lm.hubs || []).some(x => x.ok === false));
  const machineDown = !!(lm && (lm.hubs || []).some(x =>
    (((x.overview || {}).machines) || []).some(m => !m.reachable)));
  const voidHot = rows.some(r => (r.void_rate || 0) > 0.05);
  const liveOff = !!(lv && lv.enabled !== false && lv.running !== false && lv.status === 'offline');
  let t;
  if(stall) t = '偵測到 ' + stall + ' 個 run 停滯' +
    ((chainBad || hubDown) ? ' · 基礎設施亦有異常' : ' · 其餘系統正常');
  else if(chainBad) t = '信任生態 chain 驗證失敗 · 需要處理';
  else if(hubDown) t = 'LM Studio hub 無回應 · 請檢查機群';
  else if(stallAck) t = stallAck + ' 個停滯已知悉 · 處理中' + (act ? ' · ' + act + ' 個 run 執行中' : '');
  else if(voidHot) t = 'void 率超過 5% 門檻 · 請檢查看門狗';
  else if(machineDown) t = '部分 LM Studio 機器離線' + (act ? ' · ' + act + ' 個 run 執行中' : '');
  else if(liveOff) t = 'Hermes 串流離線 · 重連中' + (act ? ' · ' + act + ' 個 run 執行中' : '');
  else if(rows.some(lateOf)) t = rows.filter(lateOf).length + ' 個 run 遲滯（尚未到停滯門檻）'
    + (act ? ' · 共 ' + act + ' 個 run 執行中' : '');
  else if(act) t = act + ' 個 run 執行中 · 系統正常';
  else if(rows.length) t = '目前沒有執行中的 run · 系統正常';
  else t = '尚無 run 資料';
  $('#sv-dtext').textContent = t;
  const he = $('#health');
  he.title = t;
  he.setAttribute('aria-label', t);
}
// ---- 批次執行區：run 側面板（桌機在區內滑入／手機貼底 sheet） ----
let svTab = 'thru', svRecentJson = '';
function svOpen(rid){
  svOpenRid = rid;
  svTab = 'thru'; svRecentJson = '';
  $('#sv-panel').classList.add('open');
  $('#sv-panel').setAttribute('aria-hidden', 'false');
  $('#sv-backdrop').classList.add('on');
  svPanelSync(true);
  svFetchRecent();
  document.querySelectorAll('.sv-row').forEach(el =>
    el.classList.toggle('sel', el.dataset.rid === rid));
  svSyncHash();
}
function svClose(skipHash){
  svOpenRid = null; svRecentJson = '';
  $('#sv-panel').classList.remove('open');
  $('#sv-panel').setAttribute('aria-hidden', 'true');
  $('#sv-backdrop').classList.remove('on');
  document.querySelectorAll('.sv-row.sel').forEach(el => el.classList.remove('sel'));
  if(skipHash !== true) svSyncHash();
}
$('#sv-backdrop').addEventListener('click', () => { svClose(); ioClose(); });
addEventListener('keydown', e => {
  if(e.key !== 'Escape') return;
  if(ioOpenFlag) ioClose();
  else if(svOpenRid) svClose();
});
// 彈窗四周留白（.svp 之外）點擊即關——不必找叉叉
$('#sv-panel').addEventListener('click', e => { if(e.target === e.currentTarget) svClose(); });
$('#io-modal').addEventListener('click', e => { if(e.target === e.currentTarget) ioClose(); });
function svPanelBuild(r){
  $('#svp-body').innerHTML = `<div class="svp-head">
      <span class="sv-name">${esc(r.run_id)}</span>
      <span class="pill" id="svp-pill"></span>
      <button class="svp-close" id="svp-close" aria-label="關閉"><svg class="ic"><use href="#i-x"/></svg></button>
    </div>
    <div class="tiles two">
      <div class="tile"><b id="svp-pass">–</b><span>通過率 <small>累計</small></span></div>
      <div class="tile"><b id="svp-dur">–</b><span>執行時長</span></div>
      <div class="tile"><b id="svp-void">–</b><span>void 率 <small>門檻 5%</small></span></div>
      <div class="tile"><b id="svp-rate">–</b><span>速率 <small>近 20 格</small></span></div>
      <div class="tile"><b id="svp-idle">–</b><span>閒置 <small id="svp-idle-th">門檻 –</small></span></div>
      <div class="tile"><b id="svp-r30">–</b><span>近 30 分 <small>格/分</small></span></div>
    </div>
    <div class="svp-tabs">
      <button class="svp-tab on" data-t="thru">吞吐</button>
      <button class="svp-tab" data-t="pass">通過率</button>
    </div>
    <div class="svp-chart" id="svp-chart"></div>
    <div class="svp-hb" id="svp-hb"></div>
    <div id="svp-arms"></div>
    <div id="svp-fams"></div>
    <div class="svp-sec">最近紀錄</div>
    <div class="tasklist" id="svp-recent">載入中…</div>
    <div class="btns">
      <button class="op-only" id="svp-ackbtn" hidden></button>
      <button class="op-only" data-rid="${esc(r.run_id)}" onclick="runCtl(this,'pause')"><svg><use href="#i-pause"/></svg>暫停</button>
      <button class="op-only" data-rid="${esc(r.run_id)}" onclick="runCtl(this,'resume')"><svg><use href="#i-play"/></svg>恢復</button>
      <button class="op-only btn-danger" data-rid="${esc(r.run_id)}" onclick="runCtl(this,'stop')"><svg><use href="#i-stop"/></svg>終止</button>
    </div>
    <div class="skip op-only"><input placeholder="task_id（跳過這一題）">
      <button data-rid="${esc(r.run_id)}" onclick="runSkip(this)">跳過</button></div>`;
}
$('#svp-body').addEventListener('click', e => {
  if(e.target.closest('#svp-close')){ svClose(); return; }
  const ab = e.target.closest('#svp-ackbtn');
  if(ab){ svAck(svOpenRid, ab.dataset.on === '1'); return; }
  const tb = e.target.closest('.svp-tab');
  if(tb){
    svTab = tb.dataset.t;
    document.querySelectorAll('.svp-tab').forEach(x => x.classList.toggle('on', x === tb));
    const r = (cache.runs || []).find(x => x.run_id === svOpenRid);
    const c = $('#svp-chart');
    if(r && c){ c.dataset.j = ''; svChart(r, true); }
  }
});
function svDurText(r){
  if(!r.first_ts_ms || !r.last_activity_ms || r.last_activity_ms <= r.first_ts_ms) return '–';
  const m = Math.round((r.last_activity_ms - r.first_ts_ms) / 60000);
  return m >= 60 ? Math.floor(m/60) + 'h ' + (m%60) + 'm' : m + 'm';
}
function svPanelSync(fresh){
  if(!svOpenRid) return;
  const r = (cache.runs || []).find(x => x.run_id === svOpenRid);
  if(!r){ svClose(); return; }
  if(fresh === true || !document.getElementById('svp-pill')) svPanelBuild(r);
  const pill = $('#svp-pill');
  if(r.stalled && r.acked){ pill.className = 'pill warn'; pill.textContent = '停滯（已知悉）'; }
  else if(r.stalled){ pill.className = 'pill bad'; pill.textContent = '停滯'; }
  else if(r.finished){ pill.className = 'pill ok'; pill.textContent = '已完成'; }
  else if(lateOf(r)){ pill.className = 'pill warn'; pill.textContent = '遲滯'; }
  else {
    pill.className = 'pill ' + r.control_state;
    pill.textContent = r.control_state === 'running' ? '執行中'
      : (r.control_state === 'paused' ? '已暫停' : '收尾中');
  }
  const o = r.by_outcome, d = (o.pass||0) + (o.fail||0);
  if(d) tween($('#svp-pass'), Math.round(100 * o.pass / d), v => Math.round(v) + '%');
  else $('#svp-pass').textContent = '–';
  $('#svp-dur').textContent = svDurText(r);
  const ve = $('#svp-void');
  ve.textContent = r.void_rate != null ? (100 * r.void_rate).toFixed(1) + '%' : '–';
  ve.style.color = (r.void_rate || 0) > 0.05 ? 'var(--bad)' : '';
  $('#svp-rate').innerHTML = r.rate_per_min ? r.rate_per_min + '<small>/min</small>' : '–';
  // 對照格：閒置 vs 停滯門檻、近 30 分速率（spark 尾 6 桶，停滯含補零＝誠實掉速）
  const idleM = r.idle_s != null ? Math.floor(r.idle_s / 60) : null;
  const ie = $('#svp-idle');
  ie.textContent = idleM == null ? '–'
    : (idleM >= 60 ? Math.floor(idleM / 60) + 'h ' + (idleM % 60) + 'm' : idleM + 'm');
  ie.style.color = r.stalled ? (r.acked ? 'var(--warn)' : 'var(--bad)')
    : (lateOf(r) ? 'var(--warn)' : '');
  if(r.stall_min) $('#svp-idle-th').textContent = r.late_min
    ? '遲 ' + Math.round(r.late_min) + 'm · 停 ' + Math.round(r.stall_min) + 'm'
    : '門檻 ' + Math.round(r.stall_min) + 'm';
  const B30 = svBuckets(r).slice(-6);
  const done30 = B30.reduce((a, b) => a + b[0], 0);
  $('#svp-r30').textContent = B30.length >= 2 ? (done30 / (B30.length * 5)).toFixed(1) : '–';
  // 知悉切換鈕（僅停滯時出現）
  const ab = $('#svp-ackbtn');
  if(ab){
    ab.hidden = !r.stalled;
    ab.dataset.on = r.acked ? '0' : '1';
    ab.textContent = r.acked ? '取消知悉' : '知悉停滯';
  }
  svChart(r, fresh === true);
  svHeartbeat(r);
  svBars($('#svp-arms'), '臂通過率', r.by_worker);
  svBars($('#svp-fams'), '族別通過率', r.by_family);
}
// 心跳條（Uptime Kuma / Tremor Tracker 式）：一桶一格，灰=無活動、綠=全過、
// 琥珀=有 fail、紅=全 fail；資料與趨勢圖同一份 svBuckets（含停滯/遲滯補零尾）
function svHeartbeat(r){
  const host = $('#svp-hb');
  if(!host) return;
  const sp = r.spark;
  const B = svBuckets(r);
  const key = JSON.stringify(B);
  if(host.dataset.j === key) return;
  host.dataset.j = key;
  if(!sp || B.length < 2){ host.innerHTML = ''; return; }
  const fmt = ms => { const d2 = new Date(ms);
    return ('0' + d2.getHours()).slice(-2) + ':' + ('0' + d2.getMinutes()).slice(-2); };
  const bs = sp.bucket_s * 1000;
  const segs = B.map((b, i) => {
    const cls = !b[0] ? 'off' : (b[1] === b[0] ? 'ok' : (b[1] ? 'mix' : 'bad'));
    const t0 = sp.t0_ms + i * bs;
    const tip = fmt(t0) + '–' + fmt(t0 + bs)
      + (b[0] ? ' · 完成 ' + b[0] + ' · 通過 ' + b[1] : ' · 無活動');
    return `<i class="${cls}" title="${tip}"></i>`;
  }).join('');
  host.innerHTML = `<div class="hb-track">${segs}</div>
    <div class="hb-cap"><span>${fmt(sp.t0_ms)}</span><span>心跳 · 5 分鐘/格</span><span>${fmt(sp.t0_ms + (B.length - 1) * bs)}</span></div>`;
}
function svBars(host, title, obj){
  if(!host) return;
  const entries = Object.entries(obj || {});
  const key = JSON.stringify(entries);
  if(host.dataset.j === key) return;
  host.dataset.j = key;
  if(!entries.length){ host.innerHTML = ''; return; }
  host.innerHTML = `<div class="svp-sec">${title}</div>` + entries.map(([k, c]) => {
    const d = (c.pass||0) + (c.fail||0);
    const pc = d ? Math.round(100 * c.pass / d) : null;
    return `<div class="hbar"><span class="nm" title="${esc(k)}">${esc(k)}</span>
      <div class="trk"><div class="fl ${pc != null && pc < 50 ? 'warn' : ''}" data-w="${pc == null ? 0 : pc}"></div></div>
      <span class="pc">${pc == null ? '–' : pc + '%'}</span></div>`;
  }).join('');
  requestAnimationFrame(() =>
    host.querySelectorAll('.fl').forEach(f => { f.style.width = f.dataset.w + '%'; }));
}
let svChartGeo = null;  // hover 提示用的幾何狀態（重繪時更新）
function svChart(r, animate){
  const host = $('#svp-chart');
  if(!host) return;
  const sp = r.spark;
  const B = svBuckets(r);
  // W 用容器實寬（.svp 定寬所以開面板瞬間也量得準）：viewBox 與渲染 1:1，軸字不被拉伸
  const W = Math.max(280, Math.round(host.clientWidth || 360));
  const key = svTab + '|' + (r.stalled ? 1 : 0) + (lateOf(r) ? 'L' : '') + '|' + W + '|' + JSON.stringify(B);
  if(host.dataset.j === key) return;
  host.dataset.j = key;
  svChartGeo = null;
  if(B.length < 2){
    host.innerHTML = '<div class="empty" style="padding:10px">（資料不足，畫不出趨勢）</div>';
    return;
  }
  const H = 110, PT = 10, PB = 20, PL = 34, PR = 8;
  const vals = svTab === 'pass'
    ? B.map(b => b[0] ? Math.round(100 * b[1] / b[0]) : null)
    : B.map(b => b[0]);
  const nums = vals.filter(v => v != null);
  if(!nums.length){
    host.innerHTML = '<div class="empty" style="padding:10px">（此區間沒有完成格）</div>';
    return;
  }
  // Y 軸從 0 起算（吞吐與通過率都是），刻度：0／一半／最大
  const mx = svTab === 'pass' ? 100 : Math.max.apply(null, nums.concat([1]));
  const midV = Math.round(mx / 2);
  const x = i => PL + i * ((W - PL - PR) / (B.length - 1));
  const y = v => H - PB - (v / mx) * (H - PT - PB);
  const yLab = v => svTab === 'pass' ? v + '%' : String(v);
  const pts = [];
  vals.forEach((v, i) => { if(v != null) pts.push(Math.round(x(i)) + ',' + Math.round(y(v))); });
  let band = '';
  if(r.stalled || lateOf(r)){
    let z = B.length;
    while(z > 0 && B[z-1][0] === 0) z--;
    if(z < B.length && z > 0)
      band = `<rect x="${Math.round(x(z-1))}" y="${PT}" width="${Math.round(x(B.length-1) - x(z-1))}" height="${H-PT-PB}" fill="${r.stalled ? 'rgba(255,84,112,.12)' : 'rgba(240,180,41,.10)'}"/>`;
  }
  const fmt = ms => { const d2 = new Date(ms);
    return ('0' + d2.getHours()).slice(-2) + ':' + ('0' + d2.getMinutes()).slice(-2); };
  const bs = sp.bucket_s * 1000;
  const tMid = sp.t0_ms + Math.round((B.length - 1) / 2) * bs;
  const col = r.stalled ? 'var(--bad)'
    : (lateOf(r) ? 'var(--warn)' : (svTab === 'pass' ? 'var(--accent)' : 'var(--ok)'));
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
    <line x1="${PL}" y1="${H-PB}" x2="${W-PR}" y2="${H-PB}" stroke="var(--ax)"/>
    <line x1="${PL}" y1="${Math.round(y(midV))}" x2="${W-PR}" y2="${Math.round(y(midV))}" stroke="var(--ax-soft)"/>
    <line x1="${PL}" y1="${Math.round(y(mx))}" x2="${W-PR}" y2="${Math.round(y(mx))}" stroke="var(--ax-soft)"/>
    <text x="${PL-5}" y="${H-PB+3}" text-anchor="end">0</text>
    <text x="${PL-5}" y="${Math.round(y(midV))+3}" text-anchor="end">${yLab(midV)}</text>
    <text x="${PL-5}" y="${Math.round(y(mx))+3}" text-anchor="end">${yLab(mx)}</text>
    ${band}
    <polyline id="svp-line" points="${pts.join(' ')}" fill="none" stroke="${col}"
      stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    <line id="svp-cross" x1="0" x2="0" y1="${PT}" y2="${H-PB}" stroke="var(--ax-mid)" style="display:none"/>
    <circle id="svp-dot" r="3" fill="${col}" style="display:none"/>
    <text x="${PL}" y="${H-6}">${fmt(sp.t0_ms)}</text>
    <text x="${Math.round((PL + W - PR) / 2)}" y="${H-6}" text-anchor="middle">${fmt(tMid)}</text>
    <text x="${W-PR}" y="${H-6}" text-anchor="end">${fmt(sp.t0_ms + (B.length-1) * bs)}</text>
  </svg><div class="svp-tip" id="svp-tip" style="display:none"></div>`;
  svChartGeo = {vals, n: B.length, t0: sp.t0_ms, bs, W, H, PL, PR, PT, PB, mx, tab: svTab};
  // 畫線動畫用實測路徑長（原硬編 1200 導致前段時間隱形）；先關 transition 設起點再放行
  if(animate && !matchMedia('(prefers-reduced-motion: reduce)').matches)
    requestAnimationFrame(() => {
      const l = document.getElementById('svp-line');
      if(!l || !l.getTotalLength) return;
      const len = Math.ceil(l.getTotalLength()) + 2;
      l.style.transition = 'none';
      l.style.strokeDasharray = len;
      l.style.strokeDashoffset = len;
      void l.getBoundingClientRect();
      l.style.transition = '';
      l.style.strokeDashoffset = 0;
    });
}
// 趨勢圖 hover：十字線＋圓點＋數值提示（pointer 事件，滑鼠與觸控都吃；
// 容器由 svPanelBuild 重建，所以事件掛在恆存的 #svp-body 上代理）
function svTipHide(){
  for(const id of ['svp-cross', 'svp-dot', 'svp-tip']){
    const el = document.getElementById(id);
    if(el) el.style.display = 'none';
  }
}
$('#svp-body').addEventListener('pointermove', e => {
  const g = svChartGeo;
  const host = document.getElementById('svp-chart');
  const svg = host ? host.querySelector('svg') : null;
  if(!g || !svg){ return; }
  if(!host.contains(e.target)){ svTipHide(); return; }
  const rect = svg.getBoundingClientRect();
  if(!rect.width) return;
  const xv = (e.clientX - rect.left) / rect.width * g.W;
  const step = (g.W - g.PL - g.PR) / (g.n - 1);
  let i = Math.round((xv - g.PL) / step);
  i = Math.max(0, Math.min(g.n - 1, i));
  const cross = document.getElementById('svp-cross');
  const dot = document.getElementById('svp-dot');
  const tip = document.getElementById('svp-tip');
  if(!cross || !dot || !tip) return;
  const xi = g.PL + i * step;
  cross.setAttribute('x1', xi); cross.setAttribute('x2', xi);
  cross.style.display = '';
  const v = g.vals[i];
  const when = new Date(g.t0 + i * g.bs);
  const hh = ('0' + when.getHours()).slice(-2) + ':' + ('0' + when.getMinutes()).slice(-2);
  if(v == null){
    dot.style.display = 'none';
    tip.textContent = hh + ' · 無完成格';
  } else {
    dot.setAttribute('cx', xi);
    dot.setAttribute('cy', g.H - g.PB - (v / g.mx) * (g.H - g.PT - g.PB));
    dot.style.display = '';
    tip.textContent = hh + (g.tab === 'pass' ? ' · 通過率 ' + v + '%' : ' · 完成 ' + v + ' 格');
  }
  tip.style.display = '';
  const px = xi / g.W * rect.width;
  tip.style.left = Math.max(40, Math.min(rect.width - 40, px)) + 'px';
});
$('#svp-body').addEventListener('pointerleave', svTipHide);

// ---------- 鍵盤巡檢：/ 聚焦搜尋、j/k 選列、Enter 開面板（Esc 關閉已有） ----------
let kbdIdx = -1;
addEventListener('keydown', e => {
  const ae = document.activeElement, tag = ae ? ae.tagName : '';
  if(tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'){
    if(e.key === 'Escape') ae.blur();
    return;
  }
  if(e.key === '/'){
    e.preventDefault();
    const q = $('#run-q');
    if(q && !$('#run-toolbar').hidden) q.focus();
    return;
  }
  if(e.key === 'j' || e.key === 'k'){
    const rows = [...document.querySelectorAll('.sv-row')]
      .filter(el => el.getClientRects().length > 0);
    if(!rows.length) return;
    e.preventDefault();
    kbdIdx += e.key === 'j' ? 1 : -1;
    kbdIdx = Math.max(0, Math.min(rows.length - 1, kbdIdx));
    document.querySelectorAll('.sv-row.kbd').forEach(el => el.classList.remove('kbd'));
    rows[kbdIdx].classList.add('kbd');
    rows[kbdIdx].scrollIntoView({block: 'nearest'});
    return;
  }
  if(e.key === 'Enter' || e.key === ' '){
    const cur = document.querySelector('.sv-row.kbd');
    if(cur && ae !== cur){ e.preventDefault(); svOpen(cur.dataset.rid); }
  }
});

// ---------- 亮色模式：localStorage 記憶（舊 vacant_mon_night 鍵棄用不遷移） ----------
try {
  if(localStorage.getItem('vacant_mon_light') === '1') document.body.classList.add('light');
} catch(e){}
$('#rail-night').addEventListener('click', () => {
  const on = document.body.classList.toggle('light');
  try { localStorage.setItem('vacant_mon_light', on ? '1' : '0'); } catch(e){}
});
function svFetchRecent(){
  if(!svOpenRid) return;
  const rid = svOpenRid;
  fetch('/api/runs/' + encodeURIComponent(rid) + '/trace_tail').then(r => r.json()).then(rows => {
    if(rid !== svOpenRid) return;
    const key = JSON.stringify(rows);
    if(key === svRecentJson) return;
    svRecentJson = key;
    const host = document.getElementById('svp-recent');
    if(!host) return;
    host.innerHTML = rows.slice(-10).reverse().map(t => `<div>
      <span title="${fmtAbs(t.ts_ms)}">${t.ts_ms ? fmtWhen(t.ts_ms) : '–'}</span>
      <span class="o-${esc(t.outcome)}">${esc(t.outcome)}</span>
      <span>${esc(t.policy || '')}·${esc(t.seed || '')}</span>
      <span>${esc((t.task || '').slice(0, 10))}</span></div>`).join('')
      || '<div>（trace 尚無記錄）</div>';
  }).catch(()=>{});
}

// ---------- eco ----------
function ecoWipe(el){
  const name = el.dataset.name;
  if(!confirm('抹 '+name+' 的記憶？（key 保留、信用歸零）')) return;
  post('/api/eco/wipe', {name});
}
// persona → 色彩/線型（saboteur 加虛線：色盲情境下與 good 仍可辨）
const ECO_TIER = {good:  {col:'var(--ok)',   dash:''},
                  mediocre:{col:'var(--warn)', dash:''},
                  saboteur:{col:'var(--bad)',  dash:'5 3'}};
const ecoTier = t => ECO_TIER[t] || {col:'var(--muted)', dash:'2 3'};
let ecoChartGeo = null;  // hover 幾何（重繪時更新；#eco 整段 key-guard，不會每輪重建）

// 信用歷史多線圖：一 agent 一線，0.5 基準虛線，SLASH/WIPE 畫紅標
function ecoChart(e, W){
  const h = e.credit_history || {};
  const roster = e.roster || [];
  ecoChartGeo = null;
  if(!h.t0_ms || !h.t1_ms || h.t1_ms <= h.t0_ms)
    return '<div class="empty" style="padding:10px">（ledger 尚無事件——跑一次 delegate 曲線就會長出來）</div>';
  const H = 170, PT = 12, PB = 22, PL = 40, PR = 76;  // PR 留給線尾名字標籤
  const t0 = h.t0_ms, t1 = h.t1_ms;
  // 每 agent 的折線：起點 (t0, 0.5) → 各 REVIEW 節點 → 延伸到 t1（階梯語意：值到下一事件前不變）
  const lines = roster.map(r => {
    const pts = [[t0, 0.5]].concat((h.series||{})[r.name] || []);
    if(pts[pts.length-1][0] < t1) pts.push([t1, pts[pts.length-1][1]]);
    return {name:r.name, tier:r.tier, pts};
  });
  // Y 域：涵蓋所有值＋pad，最窄 0.5±0.06（避免微小差被放大成假劇烈）
  let lo = 0.5, hi = 0.5;
  lines.forEach(l => l.pts.forEach(p => { lo = Math.min(lo, p[1]); hi = Math.max(hi, p[1]); }));
  lo = Math.min(0.44, lo - 0.015); hi = Math.max(0.56, hi + 0.015);
  const x = t => PL + (t - t0) / (t1 - t0) * (W - PL - PR);
  const y = v => PT + (hi - v) / (hi - lo) * (H - PT - PB);
  const fmtT = ms => { const d = new Date(ms);
    return (d.getMonth()+1) + '/' + d.getDate() + ' ' +
      ('0'+d.getHours()).slice(-2) + ':' + ('0'+d.getMinutes()).slice(-2); };
  // 階梯折線（H-V step）：REVIEW 是離散事件，兩點間斜線會謊稱「連續爬升」
  const poly = l => {
    const seg = [];
    l.pts.forEach((p, i) => {
      const px = x(p[0]).toFixed(1), py = y(p[1]).toFixed(1);
      if(i){ seg.push(x(p[0]).toFixed(1) + ',' + y(l.pts[i-1][1]).toFixed(1)); }
      seg.push(px + ',' + py);
    });
    return seg.join(' ');
  };
  const paths = lines.map(l => {
    const tc = ecoTier(l.tier);
    return `<polyline class="eco-line" points="${poly(l)}" fill="none" stroke="${tc.col}"
      stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
      ${tc.dash ? `stroke-dasharray="${tc.dash}"` : ''} opacity=".9"/>` +
      l.pts.slice(1, -1).map(p =>
        `<circle cx="${x(p[0]).toFixed(1)}" cy="${y(p[1]).toFixed(1)}" r="2.5" fill="${tc.col}"/>`).join('');
  }).join('');
  // 線尾名字標籤：末值同值會疊字 → 依末值排序後最小間距 11px 錯開
  const ends = lines.map(l => ({name:l.name, col:ecoTier(l.tier).col,
    v:l.pts[l.pts.length-1][1], y:y(l.pts[l.pts.length-1][1])}))
    .sort((a, b) => a.y - b.y);
  for(let i = 1; i < ends.length; i++)
    if(ends[i].y - ends[i-1].y < 11) ends[i].y = ends[i-1].y + 11;
  const tags = ends.map(en => `<text x="${W-PR+6}" y="${en.y+3}" fill="${en.col}"
      style="font-family:ui-monospace,Consolas,monospace">${esc(en.name)} ${en.v.toFixed(3)}</text>`).join('');
  const marks = (h.marks||[]).map(m => {
    const mx2 = x(m.ts_ms).toFixed(1);
    return `<g><line x1="${mx2}" x2="${mx2}" y1="${PT}" y2="${H-PB}" stroke="var(--bad)"
        stroke-dasharray="2 3" opacity=".8"/>
      <text x="${mx2}" y="${PT-2}" text-anchor="middle" fill="var(--bad)">✕</text>
      <title>${esc(m.type)} ${esc(m.target||'')}${m.reason ? '：'+esc(m.reason) : ''}（${fmtT(m.ts_ms)}）</title></g>`;
  }).join('');
  ecoChartGeo = {lines, t0, t1, W, H, PL, PR, PT, PB, lo, hi};
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
    <line x1="${PL}" y1="${y(0.5).toFixed(1)}" x2="${W-PR}" y2="${y(0.5).toFixed(1)}"
      stroke="var(--ax-mid)" stroke-dasharray="4 4"/>
    <line x1="${PL}" y1="${H-PB}" x2="${W-PR}" y2="${H-PB}" stroke="var(--ax)"/>
    <text x="${PL-5}" y="${y(0.5)+3}" text-anchor="end">0.5</text>
    <text x="${PL-5}" y="${y(hi)+3}" text-anchor="end">${hi.toFixed(2)}</text>
    <text x="${PL-5}" y="${y(lo)+3}" text-anchor="end">${lo.toFixed(2)}</text>
    ${marks}${paths}${tags}
    <line id="eco-cross" x1="0" x2="0" y1="${PT}" y2="${H-PB}" stroke="var(--ax-mid)" style="display:none"/>
    <text x="${PL}" y="${H-6}">${fmtT(t0)}</text>
    <text x="${Math.round((PL+W-PR)/2)}" y="${H-6}" text-anchor="middle">${fmtT(t0+(t1-t0)/2)}</text>
    <text x="${W-PR}" y="${H-6}" text-anchor="end">${fmtT(t1)}</text>
  </svg><div class="tip" id="eco-tip" style="display:none"></div>`;
}

// 名冊列：0.5 基準的信用偏移條（共用刻度＝可跨列比較）
function ecoRoster(e){
  const roster = e.roster || [];
  if(!roster.length) return '';
  const dev = Math.max(0.05, ...roster.map(r => Math.abs(r.credit - 0.5) * 1.3));
  // 近期被攔計數（ledger tail）：拒收／稽核未過／交付未過都算——
  // 讓「被攔下的交付」與名冊建立資料層連結（老師 9/1 建議②）
  const blocked = {};
  (e.events || []).forEach(ev => {
    const hit = ev.type === 'REVIEW_REJECTED'
      || (ev.type === 'AUDIT' && ev.passed === false)
      || (ev.type === 'DELIVERED' && ev.passed === false)
      || ev.type === 'SLASH';
    const who = ev.target || ev.to;
    if(hit && who) blocked[who] = (blocked[who] || 0) + 1;
  });
  const rows = roster.map(r => {
    const off = Math.max(-1, Math.min(1, (r.credit - 0.5) / dev));  // -1..1
    const w = (Math.abs(off) * 50).toFixed(1);
    // mockup／老師裁定：顏色表「方向」不表身分——右=綠(上升)、左=紅(下降)
    const dir = Math.abs(r.credit - 0.5) < 0.0005 ? 'mid' : (off >= 0 ? 'pos' : 'neg');
    const flags = (r.flags||[]).map(f =>
      `<span class="chip" title="${f==='PROBATION'?'試用期：交付數未過門檻':'觀測不足：obs 未達門檻'}">${esc(f==='INSUFFICIENT_DATA'?'資料不足':'試用期')}</span>`).join('');
    return `<div class="erow" title="obs ${r.n_obs} · 交付 ${r.deliveries} · ep ${r.episodes}">
      <span class="e-nm">${esc(r.name)}<small> · ${esc(r.tier)}</small></span>
      <div class="dbar"><i class="${dir==='neg'?'neg':'pos'}" style="width:${dir==='mid'?0:w}%"></i></div>
      <b class="e-sc ${dir}">${r.credit.toFixed(3)}</b>
      <span class="e-meta">${blocked[r.name]
          ? `<span class="pill bad e-blk" title="ledger 近 ${ (e.events||[]).length } 筆事件中被攔次數">被攔 ×${blocked[r.name]}</span>` : ''}
        ${flags}
        ${r.chain_ok ? '' : '<span class="pill bad">chain ✗</span>'}
        ${e.mirror?'':`<button class="btn-danger op-only" data-name="${esc(r.name)}" onclick="ecoWipe(this)">wipe</button>`}
      </span></div>`;
  }).join('');
  return `<div class="eroster">${rows}</div>
    <div class="eaxis"><div class="ticks"><span>0.0</span><span class="mid">0.5 起點</span><span>1.0</span></div></div>
    <div class="pub-ecap"><div class="lr"><span class="l">← 常出包，信任下降</span>
      <span class="m">0.5＝剛入場，人人一樣</span><span class="r">交付過關，信任上升 →</span></div></div>
    <div class="meta" style="margin-top:4px">信用條刻度：0.5 ± ${dev.toFixed(2)}（0.5 = Beta(1,1) 中性起點）</div>`;
}

// 交付卡：ledger tail 依 task_id 收攏成「一卡一交付」；無 task_id 的事件（WIPE 等）單獨成列
function ecoDeliveries(e){
  const evs = e.events || [];
  if(!evs.length) return '<div class="empty">（無事件）</div>';
  const groups = new Map();  // task_id -> {events}
  const loose = [];
  evs.forEach(ev => {
    if(ev.task_id){
      if(!groups.has(ev.task_id)) groups.set(ev.task_id, []);
      groups.get(ev.task_id).push(ev);
    } else loose.push(ev);
  });
  const stg = (cls, html, tip) =>
    `<span class="stg ${cls}"${tip ? ` title="${esc(tip)}"` : ''}>${html}</span>`;
  const cards = [...groups.values()].reverse().map(g => {
    const route = g.find(ev => ev.type === 'ROUTE');
    const reviews = g.filter(ev => ev.type === 'REVIEW');
    const rejected = g.filter(ev => ev.type === 'REVIEW_REJECTED');
    const audit = g.find(ev => ev.type === 'AUDIT');
    const done = g.find(ev => ev.type === 'DELIVERED');
    const slash = g.find(ev => ev.type === 'SLASH');
    const who = (done||route||g[0]).target || (route||{}).to || '?';
    const last = Math.max(...g.map(ev => ev.ts_ms || 0));
    const nPass = reviews.filter(r => r.verdict === 'PASS').length;
    const parts = [];
    parts.push(route
      ? stg('', `ROUTE <b>${esc(route.mode||'')}</b>`, `路由到 ${route.to}（tier ${route.tier}）`)
      : stg('', '…', 'tail 之外（ledger 只顯示最近 20 筆）'));
    if(reviews.length) parts.push(stg(nPass === reviews.length ? 'ok' : 'warn',
      `REVIEW ${nPass}/${reviews.length} PASS`,
      reviews.map(r => `${r.reviewer}: ${r.verdict}（w=${r.weight}）`).join('　')));
    if(rejected.length) parts.push(stg('bad', `拒收 ${rejected.length}`,
      rejected.map(r => `${r.reviewer}: ${r.reason||''}`).join('　')));
    if(audit) parts.push(stg(audit.passed ? 'ok' : 'bad',
      `AUDIT ${audit.passed ? '✓' : '✗'}`, audit.forced ? '強制稽核（probation）' : ''));
    if(slash) parts.push(stg('bad', 'SLASH ✕', slash.reason || ''));
    if(done) parts.push(stg(done.passed ? 'ok' : 'bad', `交付 ${done.passed ? '✓' : '✗'}`));
    const caller = (g.find(ev => ev.caller)||{}).caller;
    return `<div class="dcard"><span class="dc-when" title="${fmtAbs(last)}">${fmtWhen(last)}</span>
      <b>${esc(who)}</b>${caller ? `<span class="chip">${esc(caller)}</span>` : ''}
      ${parts.join('<span class="arr">→</span>')}</div>`;
  });
  const looseRows = loose.reverse().map(ev =>
    `<div class="dcard"><span class="dc-when" title="${fmtAbs(ev.ts_ms||0)}">${fmtWhen(ev.ts_ms||0)}</span>
      ${stg(ev.type==='WIPE'||ev.type==='SLASH' ? 'bad' : '', esc(ev.type))}
      <b>${esc(ev.target||ev.to||'')}</b>${ev.reason ? `<span class="chip">${esc(ev.reason)}</span>` : ''}</div>`);
  return `<div class="dcards">${cards.concat(looseRows).join('')}</div>`;
}

function renderEco(e){
  cache.eco = e; renderKPIs();
  const host = $('#eco');
  // 空態都要清 key-guard：否則來源重新打開時資料沒變會被 dataset.j 擋住，永遠停在「已關閉」
  if(!e || e.enabled===false){ host.dataset.j=''; host.innerHTML='<div class="empty">來源已關閉</div>'; return; }
  if(!e.configured){ host.dataset.j=''; host.innerHTML='<div class="empty">未設定 --eco-root</div>'; return; }
  if(!e.exists){
    host.dataset.j='';
    host.innerHTML=`<div class="empty">生態不存在：${esc(e.root)}<br>
      （先跑 vacant up --root … 建生態，或用下方 Hermes 區「鏡像生態」拉遠端複本；
      本面板絕不代為創建）</div>`; return;
  }
  // 整段 key-guard：eco 資料變動很慢（TTL 10s／鏡像靜態），資料沒變就不重建
  // DOM——線圖動畫不被輪詢打斷，也不浪費重繪
  const W = Math.max(320, Math.round(host.clientWidth || 720));
  const key = W + '|' + JSON.stringify(e);
  if(host.dataset.j === key) return;
  host.dataset.j = key;
  const sb = e.scoreboard || {};
  const pct = o => o && o.n ? Math.round(100*o.pass/o.n) : null;
  const sbRow = (k, cls) => {
    const p = pct(sb[k]);
    const tip = k === 'on' ? 'trust ON（同儕審查＋信用路由啟用）期間的池化通過率'
                           : 'trust OFF（跳過信任機制直接交付）期間的池化通過率';
    return `<div class="sbrow" title="${tip}"><span>${k}</span><div class="trk">
      <div class="fl ${cls}" style="width:${p==null?0:p}%"></div></div>
      <span class="pc">${p==null ? '–' : p + '% (' + sb[k].pass + '/' + sb[k].n + ')'}</span></div>`;
  };
  // 區塊 header：鏡像資訊進 hint、trust 操作鈕進 actions（mockup 版面）
  $('#eco-hint').textContent = e.mirror
    ? `遠端鏡像（唯讀）· 收取於 ${e.mirrored_at_ms
        ? new Date(e.mirrored_at_ms).toLocaleTimeString() : '?'} · 操作請到 VM 上做`
    : '';
  // header actions：信用歷史切換鈕（mockup 把歷史圖收為次級檢視）＋ trust 操作鈕
  $('#eco-actions').innerHTML =
    `<button class="gw-tab${ecoShowHist?' on':''}" onclick="ecoToggleHist()">信用歷史</button>`
    + (e.mirror ? '' : `<span class="op-only" style="display:flex;gap:8px">
      <button onclick="post('/api/eco/trust',{on:true})">trust ON</button>
      <button class="btn-danger" onclick="post('/api/eco/trust',{on:false})">trust OFF</button></span>`);
  const h = e.credit_history || {};
  const legend = (e.roster||[]).map(r => { const tc = ecoTier(r.tier);
    return `<span class="lg"><span class="sw" style="background:${tc.col}"></span>${esc(r.name)}</span>`; }).join('');
  const mism = (h.replay_mismatch||[]).length
    ? `<div class="note">⚠ 重放終值與 registry 現值不符：${h.replay_mismatch.map(esc).join('、')}
       （可能是多 substrate 口徑差——曲線僅供觀察，現值以名冊為準）</div>` : '';
  const hist = !ecoShowHist ? '' : `
    <div class="ccard" style="margin-top:14px">
      <h3>信用歷史</h3>
      <div class="cap">ledger 重放 · ${h.n_events||0} 筆事件 · 垂直紅線 = SLASH／WIPE</div>
      <div class="eco-legend">${legend}</div>
      <div class="cchart" id="eco-chart">${ecoChart(e, W - 42)}</div>
      ${mism}
      <div class="sb-pair" style="margin-top:10px">${sbRow('on','')}${sbRow('off','off')}</div></div>`;
  host.innerHTML = `
    <div class="counts">
      <span>trust <span class="pill ${e.trust_on?'on':'off'}">${e.trust_on?'ON':'OFF'}</span></span>
      <span>Δ <b>${sb.paired_delta ?? '–'}</b>（池化差，非配對統計）</span></div>
    ${hist}
    <div class="eco-grid">
      <div class="ccard">
        <h3>名冊 — 信用 0.5 基準偏移</h3>
        <div class="cap">右=信任上升 · 左=信任下降 · ${
          (e.roster||[]).every(r => r.chain_ok)
            ? 'episode chain 全數驗證 ok'
            : '<span style="color:var(--bad)">有 episode chain 驗證失敗（紅列）</span>'}</div>
        ${ecoRoster(e)}</div>
      <div class="ccard">
        <h3>最近交付</h3>
        <div class="cap">ledger tail 20 · ROUTE → REVIEW → AUDIT → 交付</div>
        ${ecoDeliveries(e)}</div>
    </div>`;
  // 線繪動畫：資料真的變了才播（key-guard 已擋掉輪詢重播）
  if(!matchMedia('(prefers-reduced-motion: reduce)').matches)
    requestAnimationFrame(() => host.querySelectorAll('.eco-line').forEach(l => {
      if(!l.getTotalLength) return;
      if(l.getAttribute('stroke-dasharray')){
        // 虛線線型（saboteur）：dasharray 描線動畫會蓋掉線型 → 改淡入
        l.style.opacity = '0';
        void l.getBoundingClientRect();
        l.style.transition = 'opacity .8s ease';
        l.style.opacity = '.9';
        return;
      }
      const len = Math.ceil(l.getTotalLength()) + 2;
      l.style.transition = 'none';
      l.style.strokeDasharray = len;
      l.style.strokeDashoffset = len;
      void l.getBoundingClientRect();
      l.style.transition = 'stroke-dashoffset .8s ease';
      l.style.strokeDashoffset = 0;
    }));
}
// 信用圖 hover：最近節點的十字線＋各 agent 當下值（事件委派在恆存的 #eco 上）
$('#eco').addEventListener('pointermove', ev => {
  const g = ecoChartGeo;
  const chart = document.getElementById('eco-chart');
  const svg = chart ? chart.querySelector('svg') : null;
  if(!g || !svg) return;
  const tip = document.getElementById('eco-tip');
  const cross = document.getElementById('eco-cross');
  if(!tip || !cross) return;
  if(!chart.contains(ev.target)){ tip.style.display = 'none'; cross.style.display = 'none'; return; }
  const rect = svg.getBoundingClientRect();
  if(!rect.width) return;
  const xv = (ev.clientX - rect.left) / rect.width * g.W;
  const t = g.t0 + Math.max(0, Math.min(1, (xv - g.PL) / (g.W - g.PL - g.PR))) * (g.t1 - g.t0);
  const xi = g.PL + (t - g.t0) / (g.t1 - g.t0) * (g.W - g.PL - g.PR);
  cross.setAttribute('x1', xi); cross.setAttribute('x2', xi);
  cross.style.display = '';
  // 階梯語意取值：時間 t 的信用 = 最後一個 ts ≤ t 的節點值
  const at = l => { let v = 0.5;
    for(const p of l.pts){ if(p[0] <= t) v = p[1]; else break; } return v; };
  const d = new Date(t);
  const rows = g.lines.map(l => ({name:l.name, col:ecoTier(l.tier).col, v:at(l)}))
    .sort((a, b) => b.v - a.v)
    .map(r => `<div><span style="color:${r.col}">●</span> ${esc(r.name)} <b>${r.v.toFixed(3)}</b></div>`);
  tip.innerHTML = `<div style="color:var(--muted)">${(d.getMonth()+1)}/${d.getDate()} ${('0'+d.getHours()).slice(-2)}:${('0'+d.getMinutes()).slice(-2)}</div>` + rows.join('');
  tip.style.display = '';
  tip.style.left = Math.max(70, Math.min(rect.width - 70, xi / g.W * rect.width)) + 'px';
});
$('#eco').addEventListener('pointerleave', () => {
  const tip = document.getElementById('eco-tip');
  const cross = document.getElementById('eco-cross');
  if(tip) tip.style.display = 'none';
  if(cross) cross.style.display = 'none';
});

// ---------- lmstudio ----------
const LM_COL = ['var(--accent)', 'var(--ser2)', 'var(--ser3)', 'var(--ok)'];
// 看盤數字捨入（4.8M 比 4841079 好讀）；精確值由呼叫端放 title 供對帳
const fmtK = n => n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e4 ? Math.round(n/1e3)+'k' : String(n);
// 錯誤摘要：從原始 JSON 撈 "message" 首段（不用 regex——_PAGE 是 Python 字串）；
// 全文保留在 title 供 hover 對帳
function lmErrMsg(raw){
  const BS = String.fromCharCode(92);  // 反斜線：不能寫字面量——_PAGE 是 Python 字串
  raw = String(raw || '');
  const i = raw.indexOf('message');    // 寬鬆比對：巢狀跳脫（\\"message\\"）也吃得到
  if(i < 0) return raw.slice(0, 80);
  let s = raw.slice(raw.indexOf(':', i) + 1);
  s = s.split(BS + '"').join('"').split(BS).join('');  // 去跳脫殘渣
  while(s && (s[0] === '"' || s[0] === ' ')) s = s.slice(1);
  let cut = s.length;
  for(const ch of ['"', '}']){ const k = s.indexOf(ch); if(k >= 0 && k < cut) cut = k; }
  return s.slice(0, Math.min(cut, 100)) || raw.slice(0, 80);
}
// 請求量 × 延遲雙 lane 時間軸：上=請求分桶（堆疊 per machine，桶底紅條=錯誤），
// 下=chat 延遲散點（log 刻度），載入/卸載事件畫跨 lane 垂直虛線——
// 「JIT 載入＝延遲斷崖」從註解變成圖上可指的因果
function lmChart(h, W){
  const rows = (h.reqlog || []).filter(r => r.ts);
  if(rows.length < 3) return '';
  const machines = [...new Set(rows.map(r => r.m))].sort();
  const col = m => LM_COL[machines.indexOf(m) % LM_COL.length];
  const t0 = Math.min.apply(null, rows.map(r => r.ts)) * 1000;
  // t1 納入 load/unload 事件時間：模型剛載入、還沒有流量的那段也要看得到
  // （「載了沒人用」與「用了才 JIT 載」都是 demo 想指的現象）
  const evTs = (h.events || []).map(ev => Date.parse(String(ev.iso || '').replace(' ', 'T')))
    .filter(v => v && v > 0);
  const t1 = Math.max(Math.max.apply(null, rows.map(r => r.ts)) * 1000,
    evTs.length ? Math.max.apply(null, evTs) : 0, t0 + 60000);
  const H = 214, PL = 44, PR = 10, B0 = 14, B1 = 64, L0 = 80, L1 = 188;
  const x = t => PL + (t - t0) / (t1 - t0) * (W - PL - PR);
  const nb = Math.max(24, Math.min(72, Math.round(W / 16)));
  const bw = (W - PL - PR) / nb;
  const buckets = Array.from({length: nb}, () => ({}));
  rows.forEach(r => {
    let i = Math.floor((r.ts * 1000 - t0) / (t1 - t0) * nb);
    i = Math.max(0, Math.min(nb - 1, i));
    buckets[i][r.m] = (buckets[i][r.m] || 0) + 1;
    if(!r.ok) buckets[i]._err = (buckets[i]._err || 0) + 1;
  });
  const bmax = Math.max(1, Math.max.apply(null,
    buckets.map(b => machines.reduce((a, m) => a + (b[m] || 0), 0))));
  let bars = '';
  buckets.forEach((b, i) => {
    let yy = B1;
    machines.forEach(m => {
      const c = b[m] || 0;
      if(!c) return;
      const hh = c / bmax * (B1 - B0);
      yy -= hh;
      bars += `<rect x="${(PL + i * bw + 0.5).toFixed(1)}" y="${yy.toFixed(1)}"
        width="${Math.max(1, bw - 1).toFixed(1)}" height="${hh.toFixed(1)}" fill="${col(m)}" opacity=".85">
        <title>${fmtAbs(t0 + (i + 0.5) / nb * (t1 - t0))} · ${esc(m)} ${c} 筆</title></rect>`;
    });
    if(b._err) bars += `<rect x="${(PL + i * bw + 0.5).toFixed(1)}" y="${B1 + 2}"
      width="${Math.max(1, bw - 1).toFixed(1)}" height="3" fill="var(--bad)"><title>${b._err} 筆錯誤</title></rect>`;
  });
  const lats = rows.filter(r => r.chat && r.ok && r.lat > 0);
  let dots = '', ticks = '';
  if(lats.length){
    const lmax = Math.max.apply(null, lats.map(r => r.lat));
    const lmin = Math.min.apply(null, lats.map(r => r.lat));
    const lo = Math.log10(Math.max(20, lmin * 0.8)), hiL = Math.log10(lmax * 1.3);
    const yl = v => L1 - (Math.log10(v) - lo) / (hiL - lo) * (L1 - L0);
    [100, 1000, 10000, 60000].filter(v => Math.log10(v) > lo && Math.log10(v) < hiL).forEach(v => {
      ticks += `<line x1="${PL}" y1="${yl(v).toFixed(1)}" x2="${W - PR}" y2="${yl(v).toFixed(1)}"
          stroke="var(--ax-soft)"/>
        <text x="${PL - 5}" y="${(yl(v) + 3).toFixed(1)}" text-anchor="end">${v >= 1000 ? (v / 1000) + 's' : v + 'ms'}</text>`;
    });
    dots = lats.map(r => `<circle cx="${x(r.ts * 1000).toFixed(1)}" cy="${yl(r.lat).toFixed(1)}"
      r="3" fill="${col(r.m)}" opacity=".85">
      <title>${esc(r.m)} · ${(r.lat / 1000).toFixed(1)}s · ${fmtAbs(r.ts * 1000)}</title></circle>`).join('');
  }
  let evl = '';
  (h.events || []).forEach(ev => {
    const ts = Date.parse(String(ev.iso || '').replace(' ', 'T'));
    if(!ts || ts < t0 || ts > t1) return;
    const up = ev.event === 'loaded';
    const c = up ? 'var(--ok)' : 'var(--warn)';
    evl += `<g><line x1="${x(ts).toFixed(1)}" x2="${x(ts).toFixed(1)}" y1="${B0}" y2="${L1}"
        stroke="${c}" stroke-dasharray="3 4" opacity=".7"/>
      <text x="${x(ts).toFixed(1)}" y="${B0 - 3}" text-anchor="middle" fill="${c}">${up ? '▲' : '▽'}</text>
      <title>${esc(ev.machine || '')} ${esc(ev.event || '')} ${esc(ev.model || '')}（${esc(ev.iso || '')}）</title></g>`;
  });
  const fmtT = ms => { const d = new Date(ms);
    return (d.getMonth() + 1) + '/' + d.getDate() + ' ' +
      ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2); };
  const legend = machines.map(m =>
    `<span class="lg"><span class="sw" style="background:${col(m)}"></span>${esc(m)}</span>`).join('');
  return `<div class="esec">請求量 × 延遲（最近 ${rows.length} 筆 · 延遲 log 刻度 · ▲/▽＝模型載入/卸載）</div>
    <div class="eco-legend">${legend}
      <span class="lg"><span class="sw" style="background:var(--bad)"></span>錯誤</span></div>
    <div class="cchart"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
      <text x="${PL - 5}" y="${B0 + 8}" text-anchor="end">${bmax}</text>
      <line x1="${PL}" y1="${B1}" x2="${W - PR}" y2="${B1}" stroke="var(--ax)"/>
      ${bars}${ticks}${dots}${evl}
      <line x1="${PL}" y1="${L1}" x2="${W - PR}" y2="${L1}" stroke="var(--ax)"/>
      <text x="${PL}" y="${H - 6}">${fmtT(t0)}</text>
      <text x="${Math.round((PL + W - PR) / 2)}" y="${H - 6}" text-anchor="middle">${fmtT(t0 + (t1 - t0) / 2)}</text>
      <text x="${W - PR}" y="${H - 6}" text-anchor="end">${fmtT(t1)}</text>
    </svg></div>`;
}
function lmHub(h, W){
  if(!h.ok) return `<div class="card" style="margin-top:10px">
    <h3><span>${esc(h.url)}</span><span class="pill bad">無回應</span></h3>
    <div class="meta">${esc(h.error||'')}</div></div>`;
  const ov = h.overview || {};
  const t = ov.totals || {};
  const probe = h.probe || {};
  const cards = (ov.machines||[]).map(m => {
    const loaded = (m.models||[]).filter(md=>md.state==='loaded').map(md=>md.id);
    const noModel = m.reachable && loaded.length===0;
    const s = m.stats || {};
    const p = probe[m.name];
    const probeLine = p ? `<div class="meta">近 ${p.n} 筆 chat：p95 <b>${(p.p95_ms/1000).toFixed(1)}s</b>${p.med_tok_s?` · <b>${p.med_tok_s}</b> tok/s`:''}
        <span style="opacity:.7">（中位數口徑，抗長呼叫離群）</span></div>` : '';
    return `<div class="ccard mc">
      <header><span class="nm">${esc(m.name)}</span><span class="st">
        ${noModel?'<span class="pill warn">沒載模型</span>':''}
        <span class="pill ${m.reachable?'ok':'bad'}">${m.reachable?'online':'down'}</span></span></header>
      <div class="st4">
        <div><div class="v">${s.requests??0}</div><div class="k">24h 請求</div></div>
        <div title="${s.total_tokens??0}"><div class="v">${fmtK(s.total_tokens??0)}</div><div class="k">tokens</div></div>
        <div><div class="v${(s.errors??0)?' bad':''}">${s.errors??0}</div><div class="k">錯誤</div></div>
        <div><div class="v">${p?(p.med_ms/1000).toFixed(1)+'s':'–'}</div><div class="k">中位延遲</div></div>
      </div>
      ${probeLine}
      <div class="meta">已載入：${loaded.length?loaded.map(x=>`<span class="chip">${esc(x)}</span>`).join(' '):'（無）'}</div>
      <div class="meta">${esc(m.url)}</div></div>`;
  }).join('');
  // 模型 × 機器矩陣：●載入 ○僅下載 —無。兩台 ID 不一致會在這裡一眼現形。
  const machines = (ov.machines||[]).map(m=>m.name);
  const modelSet = {};
  (ov.machines||[]).forEach(m => (m.models||[]).forEach(md => {
    (modelSet[md.id] = modelSet[md.id] || {})[m.name] = md.state; }));
  const mxRows = Object.entries(modelSet).map(([id, st]) =>
    `<tr><td>${esc(id)}</td>${machines.map(mn =>
      `<td style="text-align:center">${st[mn]==='loaded'?'<span class="on">●</span>':(st[mn]?'○':'—')}</td>`).join('')}</tr>`).join('');
  const matrix = mxRows ? `<div class="mx"><table>
    <tr><th>模型 \\ 機器</th>${machines.map(m=>`<th>${esc(m)}</th>`).join('')}</tr>${mxRows}</table>
    <div class="meta">● 已載入　○ 僅下載　— 無。同一模型在兩台若 ID 不同，least-busy 分流不了。</div></div>` : '';
  // 錯誤摘要化 → terminal 風滾動窗（老師 8/14）；原始 JSON 收進 title，hover 對帳
  const errs = (h.errors||[]).map(e =>
    `<div class="ln" title="${esc(e.error||'')}${e.ts?'　（'+fmtAbs(e.ts*1000)+'）':''}"><span class="t">[${e.ts?fmtWhen(e.ts*1000):'–'}]</span>
     <span class="lv-e">${e.status??'?'}</span> <span class="src">${esc(e.machine||'')}</span>
     ${esc(String(e.model||'').split('/').pop())} — ${esc(lmErrMsg(e.error))}</div>`).join('');
  const evs = (h.events||[]).slice(0, 8).map(ev =>
    `<li>[${esc(ev.iso||'')}] ${esc(ev.machine||'')} ${esc(ev.event||'')} ${esc(ev.model||'')}</li>`).join('');
  return `<div style="margin-top:2px">
    <div class="machines">${cards}</div>
    ${lmShowChart ? lmChart(h, W) : ''}
    ${lmShowMatrix ? matrix : ''}
    ${errs?`<div class="term" style="margin-top:10px">
      <div class="tbar"><i></i><i></i><i></i><span class="ttl">recent-errors — ${esc(h.url)} · tail</span></div>
      <div class="tbody">${errs}<div class="ln"><span class="cursor"></span></div></div></div>`:''}
    ${evs?`<div class="meta" style="margin-top:6px">模型載入/卸載事件（時間軸上的 ▲/▽）：</div><ul class="ev">${evs}</ul>`:''}
  </div>`;
}
// gateway 分頁狀態：多 gateway 時只展示選中的那組（原本上下堆疊重複整組卡片）
let lmTab = 0;
// mockup 版式：請求×延遲圖與模型矩陣收為次級檢視（header 切換鈕），預設收合
let lmShowChart = false, lmShowMatrix = false;
function lmRefresh(){
  const host = $('#lmstudio');
  host.dataset.j = '';  // 清 key-guard 強制重建
  if(cache.lm) renderLM(cache.lm);
}
function lmSetTab(i){ lmTab = i; lmRefresh(); }
function lmToggle(k){
  if(k === 'chart') lmShowChart = !lmShowChart;
  else lmShowMatrix = !lmShowMatrix;
  lmRefresh();
}
// 信任生態的信用歷史同理（次級檢視切換）
let ecoShowHist = false;
function ecoToggleHist(){
  ecoShowHist = !ecoShowHist;
  const host = $('#eco');
  host.dataset.j = '';
  if(cache.eco) renderEco(cache.eco);
}
function renderLM(l){
  cache.lm = l; renderKPIs();
  const host = $('#lmstudio');
  if(!l || l.enabled===false){ host.dataset.j=''; host.innerHTML='<div class="empty">來源已關閉</div>'; return; }
  if(!l.configured){ host.dataset.j=''; host.innerHTML='<div class="empty">未設定 --lmstudio-url</div>'; return; }
  const hubs = l.hubs || [];
  if(lmTab >= hubs.length) lmTab = 0;
  // key-guard：資料沒變不重建（散點/桶圖不被 2.5s 輪詢重繪清掉 hover title）
  const W = Math.max(320, Math.round(host.clientWidth || 720)) - 10;
  const key = W + '|' + lmTab + '|' + lmShowChart + '|' + lmShowMatrix + '|' + JSON.stringify(l);
  if(host.dataset.j === key) return;
  host.dataset.j = key;
  const tabs = hubs.length > 1 ? `<div class="gw-tabs">${hubs.map((h, i) =>
    `<button class="gw-tab ${i===lmTab?'on':''}" onclick="lmSetTab(${i})"
       title="${esc(h.url)}">gateway :${esc(String(h.url).split(':').pop())}</button>`).join('')}</div>` : '';
  host.innerHTML = tabs +
    (hubs[lmTab] ? lmHub(hubs[lmTab], W) : '<div class="empty">（無 gateway）</div>');
  $('#lm-actions').innerHTML = `
    <button class="gw-tab${lmShowChart?' on':''}" onclick="lmToggle('chart')">請求×延遲圖</button>
    <button class="gw-tab${lmShowMatrix?' on':''}" onclick="lmToggle('matrix')">模型矩陣</button>`;
  // 區塊 header hint：目前 gateway 的 24h 總量摘要
  const t = ((hubs[lmTab]||{}).overview||{}).totals || {};
  $('#lm-hint').textContent = hubs[lmTab] && hubs[lmTab].ok
    ? `24h 總請求 ${t.requests??0} · ${fmtK(t.total_tokens??0)} tokens · 錯誤 ${t.errors??0}`
    : '';
}

// ---------- GitHub 歸檔 runs ----------
// 資料讀本機 git 的 <remote>/<branch> ref（不讀工作樹）；徽章比對 ls-remote 查到的遠端 sha。
// 列表只在 ref 的 sha 變了才重抓（歸檔資料是靜態的，不跟著 2.5s 輪詢重傳 180 列）。
let ghRows = null, ghRowsSha = null, ghShowAll = false, ghFilter = '';
const ghShort = s => s ? String(s).slice(0, 7) : '—';
function ghWeb(st){
  const m = String(st.url || '').match(/github\\.com[:/]+([^/]+)\\/([^/]+?)(?:\\.git)?\\/?$/);
  return m ? {repo: m[1] + '/' + m[2], base: 'https://github.com/' + m[1] + '/' + m[2]} : null;
}
function ghSyncPill(st){
  if(st.read_error) return '<span class="pill bad">讀取失敗</span>';
  if(st.in_sync === true) return '<span class="pill ok">✓ 與 GitHub 一致</span>';
  if(st.in_sync === false) return '<span class="pill warn">⚠ 本機落後 GitHub</span>';
  return '<span class="pill">遠端比對中…</span>';
}
function renderGH(st){
  cache.gh = st;
  const host = $('#gh-sync');
  if(!st || !st.configured){
    host.dataset.j = '';
    host.innerHTML = '<div class="empty">未設定 --github-repo（runs 根目錄不在 git repo 裡時要手動指定）</div>';
    $('#gh-body').innerHTML = ''; $('#gh-hint').textContent = ''; $('#gh-actions').innerHTML = '';
    return;
  }
  const t = ms => ms ? new Date(ms).toLocaleTimeString() : '—';
  const web = ghWeb(st);
  const k = st.by_kind || {};
  const errs = [st.read_error && ('讀取：' + st.read_error),
                st.remote_error && ('遠端比對：' + st.remote_error),
                st.fetch_error && ('同步：' + st.fetch_error)].filter(Boolean);
  const html = `<div class="gh-sync">${ghSyncPill(st)}
      <span class="chip" title="${esc(st.remote_sha || '')}">GitHub ${esc(st.branch)} ${ghShort(st.remote_sha)}</span>
      <span class="chip" title="${esc(st.local_sha || '')}">本機讀取 ${ghShort(st.local_sha)}</span>
      <span class="meta">遠端查於 ${t(st.remote_checked_ms)} · 上次同步 ${t(st.last_fetch_ms)}
      ${web ? `· <a href="${esc(web.base)}/tree/${esc(st.local_sha || st.branch)}/runs" target="_blank" rel="noopener">${esc(web.repo)}</a>` : ''}</span></div>
    ${errs.map(e => `<div class="note">${esc(e)}</div>`).join('')}
    ${st.index_entries != null ? `<div class="gh-kinds">runs/INDEX.json 共 ${st.index_entries} 項，列出 real_run ${k.real_run ?? 0}＋aborted ${k.aborted ?? 0}；
      依 INDEX 定義不列：analysis ${k.analysis ?? 0}（衍生物）、smoke ${k.smoke ?? 0}（不進統計）、other ${k.other ?? 0}、replay ${k.replay ?? 0}</div>` : ''}`;
  if(host.dataset.j !== html){ host.dataset.j = html; host.innerHTML = html; }
  $('#gh-hint').textContent = st.listed != null ? `${st.listed} 個歸檔 run · 唯讀` : '';
  $('#gh-actions').innerHTML = '<button class="op-only" onclick="ghFetch(this)">立即同步</button>';
  if(st.local_sha && st.local_sha !== ghRowsSha){
    const sha = st.local_sha;
    fetch('/api/github/runs').then(r => r.json()).then(rows => {
      ghRows = rows; ghRowsSha = sha; renderGHTable();
    }).catch(() => {});
  } else if(!st.local_sha){ ghRows = null; ghRowsSha = null; renderGHTable(); }
}
async function ghFetch(btn){
  btn.disabled = true; btn.textContent = '同步中…';
  try { await post('/api/github/fetch', {}); } finally { btn.disabled = false; btn.textContent = '立即同步'; }
}
function ghSetFilter(v){ ghFilter = v; renderGHTable(); }
function ghToggleAll(){ ghShowAll = !ghShowAll; renderGHTable(); }
function renderGHTable(){
  const body = $('#gh-body');
  if(!ghRows){ body.innerHTML = ''; return; }
  const st = cache.gh || {}, web = ghWeb(st);
  const q = ghFilter.trim().toLowerCase();
  const rows = q ? ghRows.filter(r => [r.run_id, r.bank, r.subkind, ...(r.arms || []).map(a => a.arm)]
                                 .some(x => String(x || '').toLowerCase().includes(q))) : ghRows;
  const shown = ghShowAll ? rows : rows.slice(0, 25);
  const n = v => v == null ? '—' : v;
  const done = r => r.complete === true ? '<span class="pill ok">完成</span>'
                  : r.complete === false ? '<span class="pill warn">未完成</span>' : '<span class="pill">—</span>';
  const tr = shown.map(r => {
    const link = web ? `<a href="${esc(web.base)}/tree/${esc(ghRowsSha)}/runs/${encodeURIComponent(r.run_id)}" target="_blank" rel="noopener">${esc(r.run_id)}</a>` : esc(r.run_id);
    const arms = (r.arms || []).map(a => `<span class="chip" title="正確交付 / 已處理（不含 void 之外的推論）">${esc(a.arm)} ${n(a.delivered)}/${n(a.done)}</span>`).join('');
    const verdict = r.headline ? `<div class="gh-hl">${esc(r.headline)}</div>`
                  : r.verdict_decisions.length ? `<span class="chip" title="${esc(r.verdict_decisions.join('\\n'))}">裁決檔 ${r.verdict_decisions.length}</span>` : '—';
    return `<tr><td class="nm">${link}${r.kind === 'aborted' ? ' <span class="pill warn">中止</span>' : ''}</td>
      <td class="num">${esc(r.date || '—')}</td><td>${esc(r.subkind || '')}</td><td>${esc(r.bank || '—')}</td>
      <td><div class="gh-arms">${arms || '—'}</div></td><td class="r num">${n(r.infra_void)}</td><td>${done(r)}</td><td>${verdict}</td></tr>`;
  }).join('');
  body.innerHTML = `<div class="gh-tools"><input placeholder="篩選 run／題庫／臂…" value="${esc(ghFilter)}"
      oninput="ghSetFilter(this.value)"><span class="meta">${rows.length} 筆${q ? '（已篩選）' : ''}</span></div>
    <table class="gh-tbl"><thead><tr><th>run</th><th>日期</th><th>類型</th><th>題庫</th>
      <th title="每臂：正確交付（accepted ∧ meets_demand）/ 已處理">各臂 正確交付/處理</th><th class="r">infra_void</th><th>完成</th><th>裁決</th></tr></thead>
      <tbody>${tr || '<tr><td colspan="8" class="empty">沒有符合的 run</td></tr>'}</tbody></table>
    ${rows.length > 25 ? `<div class="btns"><button onclick="ghToggleAll()">${ghShowAll ? '只顯示前 25 筆' : '顯示全部 ' + rows.length + ' 筆'}</button></div>` : ''}`;
  // 篩選框重建後游標保持在框內
  if(q){ const i = body.querySelector('input'); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }
}

// ---------- hermes ----------
function renderHermes(h){
  cache.hermes = h;
  if(!h || h.enabled===false){ $('#hermes').innerHTML='<div class="empty">來源已關閉</div>'; return; }
  if(!h.configured){ $('#hermes').innerHTML='<div class="empty">未設定 --hermes-ssh（例：user1@100.77.224.99）</div>'; return; }
  const last = h.last, lm = h.last_mirror;
  // 區塊 header：主機進 hint、操作鈕進 actions（mockup 版面）
  $('#hermes-hint').textContent = h.host || '';
  $('#hermes-actions').innerHTML = `<span class="op-only" style="display:flex;gap:8px">
    <button onclick="fetchHermes(this,'/api/hermes/fetch','收取 logs')">收取 logs</button>
    ${h.eco_remote_root?`<button onclick="fetchHermes(this,'/api/hermes/mirror_eco','鏡像生態')">鏡像生態</button>`:''}</span>`;
  let status = `<div class="ccard"><h3>收取狀態</h3>
    <div class="cap">存到 ${esc(h.save_dir)}</div><div style="display:grid;gap:6px">`;
  if(lm) status += `<div class="meta" style="margin:0">生態鏡像：${lm.ok
      ? `<span class="pill ok">ok</span> ${lm.files} 檔 · <span title="${fmtAbs(lm.fetched_at_ms)}">${fmtWhen(lm.fetched_at_ms)}</span>（見上方信任生態區）`
      : `<span class="pill bad">失敗</span> ${esc(lm.error)}`}</div>`
    + (lm.hint ? `<div class="note">${esc(lm.hint)}</div>` : '');
  if(last) status += `<div class="meta" style="margin:0">上次收取：<span title="${fmtAbs(last.fetched_at_ms)}">${fmtWhen(last.fetched_at_ms)}</span> ·
      ${last.ok?'<span class="pill ok">ok</span>':'<span class="pill bad">失敗</span>'}</div>`
    + (last.hint ? `<div class="note">${esc(last.hint)}</div>` : '');
  status += `</div><div class="btns" style="margin-top:12px">
    <button id="io-btn" onclick="ioOpen()">模型 I/O 記錄${(cache.app||[]).length?`（${cache.app.length} 筆）`:''}</button></div></div>`;
  let tails = '';
  for(const r of ((last||{}).results||[])){
    tails += r.ok
      ? `<div class="meta" title="→ ${esc(r.saved_to)}">${esc(r.path)} · 新增 ${r.new_bytes} / 累計 ${r.total_bytes} bytes</div>
         <div class="term" style="margin-bottom:10px">
           <div class="tbar"><i></i><i></i><i></i><span class="ttl">${esc(r.path)} · tail</span></div>
           <div class="tbody" style="white-space:pre-wrap">${esc(r.tail)}</div></div>`
      : `<div class="meta">${esc(r.path)} · <span class="pill bad">失敗</span> ${esc(r.error)}</div>`;
  }
  $('#hermes').innerHTML = (last || lm)
    ? `<div class="hermes-grid">${status}<div>${tails || '<div class="empty">（尚未收取）</div>'}</div></div>`
    : status;
}
let lastLiveJson = '';
function renderLive(l){
  cache.live = l; renderKPIs();
  const el = $('#hermes-live');
  if(!l || l.enabled===false){ el.innerHTML=''; return; }
  if(l.running===false){
    el.innerHTML = '<div class="meta" style="margin-top:10px">即時串流未啟用（vacant runs up 加 --hermes-live）</div>';
    return;
  }
  const key = JSON.stringify(l);
  if(key === lastLiveJson) return;  // 沒變不重繪（保住展開狀態）
  lastLiveJson = key;
  const pill = l.status==='online'
      ? '<span class="pill ok"><span class="livedot"></span>直播中</span>'
    : l.status==='connecting'
      ? '<span class="pill warn">連線中…</span>'
      : `<span class="pill bad">離線</span>`;
  let head = `<div class="meta" style="margin-top:10px">即時串流（ssh tail -F）· ${pill}`;
  if(l.status==='online' && l.connected_at_ms)
    head += ` 自 ${new Date(l.connected_at_ms).toLocaleTimeString()}`;
  if(l.status==='offline'){
    if(l.retry_in_s!=null) head += ` · ${l.retry_in_s} 秒後重連（第 ${l.fails} 次失敗）`;
    if(l.error) head += `<div class="note">${esc(l.error)}</div>`;
  }
  if(l.catchups) head += ` · 上線自動補收 ×${l.catchups}`;
  head += '</div>';
  const rows = (l.entries||[]).slice().reverse().map(e => {
    const r = e.rec;
    if(r){
      const line = r.human
        ? [(r.t||''), r.human].filter(Boolean).join(' · ')
        : [r.t||'', r.kind||r.tool||'', r.brain||'', r.caller?('caller='+r.caller):'',
           r.latency_s!=null?(r.latency_s+'s'):''].filter(Boolean).join(' · ');
      return `<details class="card" style="margin-top:6px">
        <summary>[${esc(e.file)}] ${esc(line)||'（無摘要）'}
          ${r.error?'<span class="pill bad">error</span>':''}
          ${r.verified===true?'<span class="pill ok">verified</span>':''}</summary>
        ${r.prompt?`<div class="meta">prompt：</div><pre class="log">${esc(r.prompt)}</pre>`:''}
        ${r.answer?`<div class="meta">answer：</div><pre class="log">${esc(r.answer)}</pre>`:''}
        ${!r.prompt&&!r.answer?`<pre class="log">${esc(e.raw)}</pre>`:''}
      </details>`;
    }
    return `<details class="card" style="margin-top:6px">
      <summary>[${esc(e.file)}] ${esc(e.raw.slice(0,120))}</summary>
      <pre class="log">${esc(e.raw)}</pre></details>`;
  }).join('');
  el.innerHTML = head + (rows ||
    (l.status==='online' ? '<div class="meta">（線上，等新流量——Hermes 一有收發會即時出現）</div>' : ''));
}
let lastAppJson = '';
function renderAppRecords(rows){
  // 改獨立彈窗：資料進 cache，入口鈕在 Hermes 收取狀態卡（版面不再被長列表撐爆）
  cache.app = rows || [];
  const btn = $('#io-btn');
  if(btn) btn.textContent = '模型 I/O 記錄' + (cache.app.length ? `（${cache.app.length} 筆）` : '');
  const key = JSON.stringify(rows||[]);
  if(key === lastAppJson) return;  // 內容沒變不重繪（保住 <details> 展開狀態）
  lastAppJson = key;
  if(ioOpenFlag) renderIO();
}
let ioOpenFlag = false;
function renderIO(){
  const rows = cache.app || [];
  const el = $('#io-list');
  $('#io-hint').textContent = rows.length ? `app trace · 最近 ${rows.length} 筆 · 點開看全文` : '';
  if(!rows.length){ el.innerHTML = '<div class="empty">（尚無記錄——先按「收取 logs」）</div>'; return; }
  // 耗時橫條：同批最大值定刻度——慢呼叫（離群）不用讀數字就跳出來
  const lmax = Math.max(1, ...rows.map(r => r.latency_s || 0));
  const latbar = r => r.latency_s == null ? '' :
    `<span class="latbar" title="${r.latency_s}s（本批最長 ${lmax}s）"><i style="width:${
       Math.max(2, 100 * r.latency_s / lmax).toFixed(1)}%;background:${
       r.error ? 'var(--bad)' : (r.latency_s >= 20 ? 'var(--warn)' : 'var(--accent)')}"></i></span>`;
  el.innerHTML = rows.slice().reverse().map(r => `<details class="card" style="margin-top:6px">
      <summary>${r.human ? esc((r.t?r.t+' · ':'')+r.human)
        : esc(r.t||'')+' · '+esc(r.kind)+' · '+esc(r.brain||'')+' · '+(r.latency_s!=null?r.latency_s+'s':'')}
        ${r.error?'<span class="pill bad">error</span>':''}
        ${r.verified===true?'<span class="pill ok">verified</span>':''}${latbar(r)}</summary>
      <div class="meta">prompt：</div><pre class="log">${esc(r.prompt||'（無）')}</pre>
      <div class="meta">answer：</div><pre class="log">${esc(r.answer||r.error||'（無）')}</pre>
    </details>`).join('');
}
function ioOpen(){
  ioOpenFlag = true;
  renderIO();
  const m = $('#io-modal');
  m.classList.add('open'); m.setAttribute('aria-hidden', 'false');
  $('#sv-backdrop').classList.add('on');
}
// 攔截卡 → 信任生態：平滑捲動＋閃爍標出信任下降（左偏紅條）的 agent 列
function pubGoEco(){
  document.getElementById('sec-eco').scrollIntoView({behavior:'smooth', block:'start'});
  const rows = [...document.querySelectorAll('#eco .erow')];
  // 首選：有被攔記錄或信任左偏的列；資料稀疏時退而標「信任 ≤ 0.5 的低信任群」
  let hits = rows.filter(el => el.querySelector('.dbar i.neg') || el.querySelector('.e-blk'));
  if(!hits.length) hits = rows.filter(el => {
    const sc = el.querySelector('.e-sc');
    return sc && parseFloat(sc.textContent) <= 0.5;
  });
  hits.forEach(el => {
    el.classList.add('flash');
    setTimeout(() => el.classList.remove('flash'), 2600);
  });
}
function ioClose(){
  if(!ioOpenFlag) return;
  ioOpenFlag = false;
  const m = $('#io-modal');
  m.classList.remove('open'); m.setAttribute('aria-hidden', 'true');
  if(!svOpenRid) $('#sv-backdrop').classList.remove('on');
}
async function fetchHermes(btn, url, label){
  btn.disabled = true; btn.textContent = label + '中…';
  try { await post(url, {}); }
  finally { btn.disabled = false; btn.textContent = label; }
}

// ---------- 主輪詢 ----------
// 四個來源各自獨立更新——最慢的來源（如斷線的 hub 吃滿 timeout）不拖累其他區塊
// 的即時性（停滯警示尤其不能等）。分頁隱藏時暫停輪詢（手機/tailscale 看盤省電）。
let lastOkTs = 0, lastOkClock = '', connDown = false;
async function refresh(){
  let src;
  try {
    src = await fetch('/api/sources').then(r=>r.json());
  } catch(e) {
    connDown = true;
    $('#status').textContent = '○ 連線中斷，重試中…';
    $('#health').className = 'dot';
    // 舊資料不准裝新的：斷線超過 10s 全頁降飽和並把診斷句改成快照警示
    if(lastOkTs && Date.now() - lastOkTs > 10000){
      document.body.classList.add('stale');
      $('#sv-dtext').textContent = '⚠ 資料為 ' + lastOkClock + ' 快照 · 連線中斷';
      $('#health').className = 'dot warn';
    }
    return;
  }
  const reconnected = document.body.classList.contains('stale');
  document.body.classList.remove('stale');
  connDown = false;
  lastOkTs = Date.now();
  lastOkClock = new Date().toLocaleTimeString();
  SRC = src;
  renderSrcBar();
  $('#status').textContent = (reconnected ? '● 已重連 · ' : '● 已連線 · ') + lastOkClock;
  if(SRC.runs) fetch('/api/runs').then(r=>r.json()).then(renderRuns).catch(()=>{});
  else {
    cache.runs = null; updateTitle();
    $('#run-toolbar').hidden = true;
    svRowEls.clear(); svPrevOrder = '';
    // 不能整段 innerHTML 抹掉——表格骨架是靜態 DOM，砍了 renderRuns 就找不到 tbody
    $('#sv-tbody').innerHTML = '';
    $('#sv-tbl').hidden = true;
    $('#sv-loading').hidden = true;
    $('#sv-off').hidden = false;
    renderKPIs();
  }
  fetch('/api/github').then(r=>r.json()).then(renderGH).catch(()=>{});
  if(SRC.eco) fetch('/api/eco').then(r=>r.json()).then(renderEco).catch(()=>{});
  else renderEco({enabled:false});
  if(SRC.lmstudio) fetch('/api/lmstudio').then(r=>r.json()).then(renderLM).catch(()=>{});
  else renderLM({enabled:false});
  if(SRC.hermes){
    fetch('/api/hermes').then(r=>r.json()).then(renderHermes).catch(()=>{});
    fetch('/api/hermes/live').then(r=>r.json()).then(renderLive).catch(()=>{});
    fetch('/api/hermes/app_records').then(r=>r.json()).then(renderAppRecords).catch(()=>{});
  } else { renderHermes({enabled:false}); renderLive({enabled:false}); renderAppRecords([]); }
}
// 自適應輪詢：前景有活 run 2.5s／全部完成 10s／背景分頁 30s（背景仍偵測轉變以發通知）
let pollTimer = null;
function pollDelay(){
  if(document.hidden) return 30000;
  const rows = cache.runs || [];
  return (!rows.length || rows.some(r => !r.finished)) ? 2500 : 10000;
}
function schedulePoll(){
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => { await refresh(); schedulePoll(); }, pollDelay());
}
document.addEventListener('visibilitychange', () => {
  if(!document.hidden) refresh();
  schedulePoll();
});
// 「更新於 X 秒前」：資料時效常駐可見（>=5s 才接手，剛更新時保留「已連線」字樣）
setInterval(() => {
  if(!lastOkTs || connDown) return;
  const s = Math.round((Date.now() - lastOkTs) / 1000);
  if(s >= 5) $('#status').textContent =
    '● 更新於 ' + (s < 60 ? s + ' 秒前' : Math.floor(s / 60) + ' 分鐘前');
}, 1000);
refresh();
schedulePoll();
</script>
</body></html>
"""


# --- HTTP handler ---------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a: Any) -> None:  # 靜音（測試/常駐皆然）
        pass

    @property
    def _ctx(self) -> "_Ctx":
        return self.server._vacant_ctx  # type: ignore[attr-defined]

    def _send_json(self, obj: Any, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return None
        return body if isinstance(body, dict) else None

    def _gate(self, source: str) -> bool:
        """來源關閉時：GET 回 {"enabled": false}；呼叫端據此短路。"""
        return self._ctx.toggles.enabled(source)

    def _enriched(self, run_id: str, summary: dict[str, Any] | None = None) -> dict[str, Any]:
        """run 摘要 ＋ trace 統計 ＋ 停滯/完成判定 ＋ 知悉狀態。"""
        d = _run_dir(self._ctx.runs_root, run_id)
        if summary is None:
            summary = summarize_run(self._ctx.runs_root, run_id)
        out = _enrich(summary, self._ctx.trace_stats.for_run(d),
                      self._ctx.stall_min, int(time.time() * 1000),
                      late_min=self._ctx.late_min)
        out["acked"] = self._ctx.acks.acked(run_id, out.get("last_activity_ms") or 0)
        out["stall_min"] = self._ctx.stall_min  # 前端「閒置對門檻」對照格用
        out["late_min"] = self._ctx.late_min if self._ctx.late_min is not None \
            else self._ctx.stall_min / 2
        return out

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path, qs = parsed.path, parse_qs(parsed.query)
        try:
            if path == "/":
                self._send_html(_PAGE)
            elif path == "/api/mode":
                self._send_json({"readonly": self._ctx.readonly})
            elif path == "/manifest.json":
                self._send_json({
                    "name": "Vacant 監測台", "short_name": "Vacant",
                    "start_url": "/", "display": "standalone",
                    "background_color": "#0f1115", "theme_color": "#0f1115",
                    "icons": [{"src": "/icon.svg", "sizes": "any",
                               "type": "image/svg+xml", "purpose": "any"}],
                })
            elif path == "/icon.svg":
                svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
                       '<rect width="100" height="100" fill="#0f1115"/>'
                       '<rect x="16" y="42" width="16" height="16" fill="#FF4D00"/>'
                       '<rect x="42" y="42" width="16" height="16" fill="#FF4D00" opacity=".72"/>'
                       '<rect x="68" y="42" width="16" height="16" fill="#FF4D00" opacity=".45"/>'
                       '</svg>').encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Content-Length", str(len(svg)))
                self.end_headers()
                self.wfile.write(svg)
            elif path == "/api/sources":
                self._send_json(self._ctx.toggles.all())
            elif path == "/api/eco":
                if not self._gate("eco"):
                    self._send_json({"enabled": False})
                    return
                self._send_json(self._ctx.eco.snapshot())
            elif path == "/api/lmstudio":
                if not self._gate("lmstudio"):
                    self._send_json({"enabled": False})
                    return
                self._send_json(self._ctx.lmstudio.overview())
            elif path == "/api/hermes":
                if not self._gate("hermes"):
                    self._send_json({"enabled": False})
                    return
                self._send_json(self._ctx.hermes.config())
            elif path == "/api/hermes/app_records":
                if not self._gate("hermes"):
                    self._send_json([])
                    return
                limit = int(qs.get("limit", ["20"])[0])
                self._send_json(self._ctx.hermes.app_records(limit))
            elif path == "/api/hermes/live":
                if not self._gate("hermes"):
                    self._send_json({"enabled": False})
                    return
                live = self._ctx.hermes_live
                if live is None:
                    self._send_json({"running": False})
                    return
                limit = int(qs.get("limit", ["30"])[0])
                self._send_json(live.snapshot(limit))
            elif path == "/api/github":
                gh = self._ctx.github
                gh.kick(allow_fetch=not self._ctx.readonly)
                self._send_json(gh.status())
            elif path == "/api/github/runs":
                self._send_json(self._ctx.github.runs())
            elif path == "/api/runs":
                if not self._gate("runs"):
                    self._send_json([])
                    return
                self._send_json([self._enriched(s["run_id"], s)
                                 for s in scan_runs(self._ctx.runs_root)])
            elif path.startswith("/api/runs/") and path.endswith("/log"):
                run_id = path[len("/api/runs/"):-len("/log")] or "."
                if not _is_safe_run_id(run_id):
                    self.send_error(404, "not found")
                    return
                limit = int(qs.get("limit", ["50"])[0])
                self._send_json(tail_records(self._ctx.runs_root, run_id, limit))
            elif path.startswith("/api/runs/") and path.endswith("/trace_tail"):
                run_id = path[len("/api/runs/"):-len("/trace_tail")] or "."
                if not _is_safe_run_id(run_id):
                    self.send_error(404, "not found")
                    return
                trace = self._ctx.trace_stats.for_run(_run_dir(self._ctx.runs_root, run_id))
                self._send_json(trace["recent"])
            elif path.startswith("/api/runs/"):
                run_id = path[len("/api/runs/"):] or "."
                if not _is_safe_run_id(run_id):
                    self.send_error(404, "not found")
                    return
                self._send_json(self._enriched(run_id))

            else:
                self.send_error(404, "not found")
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客戶端斷線：安靜收工

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        # 唯讀公開模式：一律拒絕操作——這道閘在 token 之前，公開實例沒有例外
        if self._ctx.readonly:
            self._send_json({"ok": False, "error": "唯讀公開模式：操作已停用"}, 403)
            return
        # B-5：設了 token 就要求所有操作類請求帶 X-Vacant-Token（讀取 GET 不擋——
        # 遠端看盤方便；操作鈕 wipe/終止/trust 才是要守的東西）
        token = self._ctx.token
        if token and self.headers.get("X-Vacant-Token", "") != token:
            self._send_json({"ok": False, "error": "unauthorized（缺 X-Vacant-Token）"}, 401)
            return
        body = self._read_body()
        if body is None:
            self.send_error(400, "bad json body")
            return
        try:
            if path == "/api/github/fetch":
                gh = self._ctx.github
                if not gh.configured:
                    self._send_json({"ok": False, "error": "未設定 --github-repo"}, 400)
                    return
                res = gh.fetch()
                self._send_json({**res, "status": gh.status()},
                                200 if res["ok"] else 502)
            elif path == "/api/sources":
                source = body.get("source")
                if source not in SOURCES:
                    self._send_json({"ok": False, "error": f"unknown source: {source!r}"}, 400)
                    return
                self._ctx.toggles.set(source, bool(body.get("enabled", True)))
                self._send_json(self._ctx.toggles.all())
            elif path == "/api/eco/trust":
                if not self._gate("eco"):
                    self._send_json({"ok": False, "error": "eco 來源已關閉"}, 409)
                    return
                if self._ctx.eco.root is None:
                    self._send_json({"ok": False, "error": "未設定 --eco-root"}, 400)
                    return
                self._send_json(self._ctx.eco.toggle_trust(bool(body.get("on", True))))
            elif path == "/api/eco/wipe":
                if not self._gate("eco"):
                    self._send_json({"ok": False, "error": "eco 來源已關閉"}, 409)
                    return
                name = body.get("name")
                if not name:
                    self._send_json({"ok": False, "error": "wipe 需要 name"}, 400)
                    return
                res = self._ctx.eco.wipe(str(name))
                self._send_json(res, 200 if res.get("ok") else 400)
            elif path == "/api/hermes/fetch":
                if not self._gate("hermes"):
                    self._send_json({"ok": False, "error": "hermes 來源已關閉"}, 409)
                    return
                self._send_json(self._ctx.hermes.fetch())
            elif path == "/api/hermes/mirror_eco":
                if not self._gate("hermes"):
                    self._send_json({"ok": False, "error": "hermes 來源已關閉"}, 409)
                    return
                res = self._ctx.hermes.mirror_eco()
                if res.get("ok"):
                    self._ctx.eco.invalidate()  # 新鏡像立即反映到 eco 面板
                self._send_json(res)
            elif path.startswith("/api/runs/") and path.endswith("/control"):
                run_id = path[len("/api/runs/"):-len("/control")] or "."
                if not _is_safe_run_id(run_id):
                    self.send_error(404, "not found")
                    return
                control = RunControl(_run_dir(self._ctx.runs_root, run_id) / "control.json")
                cmd = body.get("cmd")
                if cmd == "pause":
                    control.pause()
                elif cmd == "resume":
                    control.resume()
                elif cmd == "stop":
                    control.request_stop()
                elif cmd == "skip":
                    task_id = body.get("task_id")
                    if not task_id:
                        self.send_error(400, "skip requires task_id")
                        return
                    control.request_skip(task_id)
                else:
                    # HTTP 狀態行只能 latin-1（RFC 7230）：reason 一律 ASCII
                    self.send_error(400, f"unknown cmd: {cmd!r}")
                    return
                self._send_json({"ok": True, "state": control.state()})
            elif path.startswith("/api/runs/") and path.endswith("/ack"):
                run_id = path[len("/api/runs/"):-len("/ack")] or "."
                if not _is_safe_run_id(run_id):
                    self.send_error(404, "not found")
                    return
                enriched = self._enriched(run_id)
                on = bool(body.get("on", True))
                self._ctx.acks.set(run_id, on, enriched.get("last_activity_ms") or 0)
                self._send_json({"ok": True, "acked": on})
            else:
                self.send_error(404, "not found")
        except (BrokenPipeError, ConnectionResetError):
            pass


class _Ctx:
    """注入給 handler 的執行脈絡（避免用全域）。"""

    def __init__(self, runs_root: Path, toggles: SourceToggles, eco: EcoView,
                 lmstudio: LMStudioProxy, hermes: HermesLogs, token: str = "",
                 stall_min: float = 15.0, late_min: float | None = None,
                 readonly: bool = False,
                 github: "GitHubRuns | None" = None) -> None:
        self.runs_root = runs_root
        self.toggles = toggles
        self.eco = eco
        self.lmstudio = lmstudio
        self.hermes = hermes
        self.token = token
        self.stall_min = stall_min
        self.late_min = late_min
        self.readonly = readonly
        self.trace_stats = TraceStats()
        self.acks = RunAcks(runs_root / "monitor_acks.json")
        self.hermes_live: HermesLive | None = None  # make_run_monitor 開串流時填入
        self.github = github or GitHubRuns(None)


class RunAcks:
    """停滯「知悉」triage 標記——monitor 端狀態，絕不碰 ledger（實驗資料紀律）。

    存 `runs_root/monitor_acks.json`：{run_id: {"ack_ms", "seen_ms"}}。seen_ms 記
    知悉當下的 last_activity_ms；一旦有新進度（last_activity 超過 seen_ms）自動
    失效——「知悉」只蓋住當時那一次停滯，不會把未來的新停滯一起靜音。
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._acks: dict[str, dict[str, int]] = {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._acks = {k: v for k, v in data.items() if isinstance(v, dict)}
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._acks, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def set(self, run_id: str, on: bool, last_activity_ms: int) -> None:
        if on:
            self._acks[run_id] = {"ack_ms": int(time.time() * 1000),
                                  "seen_ms": int(last_activity_ms or 0)}
        else:
            self._acks.pop(run_id, None)
        self._save()

    def acked(self, run_id: str, last_activity_ms: int) -> bool:
        a = self._acks.get(run_id)
        if not a:
            return False
        if (last_activity_ms or 0) > a.get("seen_ms", 0):  # 有新進度 → 自動解除
            self._acks.pop(run_id, None)
            self._save()
            return False
        return True


_LOOPBACK = ("127.0.0.1", "localhost", "::1")


def make_run_monitor(
    runs_root: Path,
    port: int = 7778,
    *,
    eco_root: Path | str | None = None,
    lmstudio_url: str = "",
    hermes_ssh: str = "",
    hermes_paths: tuple[str, ...] = (),
    hermes_eco_root: str = "",
    host: str = "127.0.0.1",
    token: str = "",
    stall_min: float = 15.0,
    late_min: float | None = None,
    hermes_auto_s: float = 0.0,
    notify_url: str = "",
    notify_post: Callable[[str, str], None] | None = None,
    house_tick_s: float = 30.0,
    http_get: Callable[[str], bytes] | None = None,
    ssh_run: Callable[[str, str], subprocess.CompletedProcess] | None = None,
    hermes_live: bool = False,
    live_popen: Callable[[str, str], Any] | None = None,
    readonly: bool = False,
    github_repo: Path | str | None = None,
    github_remote: str = "origin",
    github_branch: str = "main",
    github_fetch_s: float = 600.0,
    git_run: Callable[[list[str], bytes | None], subprocess.CompletedProcess] | None = None,
) -> ThreadingHTTPServer:
    """組出統一監測台 server（呼叫端自行 serve_forever / shutdown）。

    runs_root：批次實驗輸出根目錄（開關檔 monitor_config.json 也存這）。
    eco_root／lmstudio_url／hermes_ssh：不給＝該來源顯示「未設定」。
    hermes_eco_root：遠端生態根（設了才有「鏡像生態」）；鏡像存 runs_root/eco_mirror。
    host/token（B-5）：非 loopback 繫結必須帶 token（操作鈕不裸奔）；設了 token
    之後所有 POST 要帶 X-Vacant-Token。手機看盤的零程式替代：tailscale serve 7778。
    hermes_auto_s：>0 開自動收取（管家執行緒每隔此秒數 fetch 一次；增量拉，便宜）。
    hermes_live：開 HermesLive 常駐 `ssh tail -F` 直播（斷線退避重連；離線→在線
    自動 fetch＋mirror_eco 補齊，實驗自動接續）。live_popen：測試注入點。
    readonly：唯讀公開模式——全部 POST 回 403、面板隱藏操作件、自動收取關閉
    （不寫檔，可與主實例共用 runs_root 併行）。給 tailscale funnel 對外展示用；
    對外仍應只 funnel 唯讀實例，完整實例留在 loopback。
    notify_url：設了就在 run 狀態轉變（停滯/void 超標/完成）時 POST 純文字過去
    （ntfy.sh/<topic> 即手機推播）。notify_post/http_get/ssh_run：測試注入點。
    late_min：遲滯門檻（分鐘；None＝stall_min 的一半）。遲滯是停滯前的琥珀
    中間態，只上版面不進通知（分級紀律：record/notify/page）。
    github_repo：本機一份 cosmopig/Vacant 的 git clone（任一 worktree 皆可）；設了就
    多一個「GitHub 歸檔 runs」區塊，資料從 `<github_remote>/<github_branch>` ref 讀，
    並以 ls-remote 對照遠端。github_fetch_s：背景 git fetch 間隔（0＝不自動 fetch；
    readonly 實例一律不 fetch）。git_run：測試注入點。
    port=0 → 隨機埠（真埠見 server.server_address[1]）。
    """
    runs_root = Path(runs_root)
    if host not in _LOOPBACK and not token and not readonly:
        raise ValueError("非 loopback 繫結（--host）必須同時設 --token——"
                         "監測台的操作鈕（終止/wipe/trust）不能無認證暴露")
    if readonly:
        hermes_auto_s = 0.0  # 唯讀實例不寫檔：自動收取交給主實例做
    mirror_dir = runs_root / "eco_mirror"
    server = ThreadingHTTPServer((host, port), _Handler)
    server.daemon_threads = True
    ctx = _Ctx(
        runs_root=runs_root,
        toggles=SourceToggles(runs_root / "monitor_config.json"),
        eco=EcoView(Path(eco_root) if eco_root else None, mirror_dir=mirror_dir),
        lmstudio=LMStudioProxy(lmstudio_url, http_get=http_get),
        hermes=HermesLogs(hermes_ssh, tuple(hermes_paths) or DEFAULT_HERMES_PATHS,
                          runs_root / "hermes_logs", ssh_run=ssh_run,
                          eco_remote_root=hermes_eco_root, mirror_dir=mirror_dir),
        token=token,
        stall_min=stall_min,
        late_min=late_min,
        readonly=readonly,
        github=GitHubRuns(github_repo, remote=github_remote, branch=github_branch,
                          fetch_every_s=github_fetch_s, git_run=git_run),
    )
    server._vacant_ctx = ctx  # type: ignore[attr-defined]
    need_bg = (hermes_auto_s > 0 or notify_url
               or (hermes_live and hermes_ssh))
    if need_bg:
        stop_ev = threading.Event()
        if hermes_auto_s > 0 or notify_url:
            _Housekeeper(ctx, stop_ev, hermes_auto_s=hermes_auto_s,
                         notify_url=notify_url,
                         notify_post=notify_post or _default_notify_post,
                         tick_s=house_tick_s).start()
        live: HermesLive | None = None
        if hermes_live and hermes_ssh:
            # 唯讀實例不寫檔：上線補收（fetch+mirror_eco）只留給主實例——
            # 否則 7778/7779 同秒開機會對同一 eco_mirror 併發 rmtree+解包互踩
            # （實際踩過：2026-09-01，7779 rmtree 撞上 7778 解包 → 鏡像半殘）
            live = HermesLive(ctx.hermes, stop_ev, popen=live_popen,
                              catchup=not readonly)
            ctx.hermes_live = live
            live.start()
        _orig_shutdown = server.shutdown

        def _shutdown() -> None:
            stop_ev.set()
            if live is not None:
                live.close()  # 殺常駐 ssh，阻塞中的 readline 立刻 EOF
            _orig_shutdown()

        server.shutdown = _shutdown  # type: ignore[method-assign]
    return server
