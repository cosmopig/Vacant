"""twin/twinprogress — 手機即時進度（2026-10-01，PROC4 線 A）。

## 這支在架構裡承重什麼

人類 2026-10-01 實測：「下個就是你那邊還是沒改，他還會卡住明明已經在處理了」。

**卡住的確切原因**：分身那一跑要四、五分鐘，而這段時間雲端 `/api/status/:id` 一直是
`status=queued`、`queue.position=1`——手機畫的就是「下一個就是你」。沒有任何一方會把雲端
那筆從 `queued` 改掉：

* `twinlink ingest` **唯讀抄寫**（刻意不 claim：claim 會讓 `/api/queue` 看不到那筆，抄寫端要走
  `/api/all`；電視端 `world3/bridge.js` 也寫死 `claims:false`）；
* 迴圈只在**跑完**那一刻 `publish` → `/api/result`，才一次把狀態翻成 `done`。

所以中間整段時間，雲端對這個人一無所知。這支補上：迴圈在**跑的當下**把進度推上去
（`POST /api/progress`，venue-token）：成形中 → 在做（它說的話、步驟）→ 審查中（逐條結果）→ 收尾。

## 設計

* **獨立背景執行緒**，不綁迴圈的輪次（一輪含 ingest／publish／export，可能很久）。
  執行緒**只讀檔案**（run 目錄裡 pi 的 stdout、步驟紀錄、驗收結果），**不碰 sqlite**
  （twinstore 的紀律：sqlite 只在主執行緒碰）；原文清單（`secrets`）由主執行緒在 `track`
  時算好交進來。
* **節流**：每人每 `MIN_INTERVAL_S`（5 秒）最多送一次；內容沒變就不送（除了每 `KEEPALIVE_S`
  一次心跳，讓雲端的「這筆還活著」判斷成立）。
* **失敗不影響現場**：任何例外只記計數，不往外丟、不重試到卡死（跟 `publish` 同一條紀律）。
* **階段只講已經成立的事**（從 run 目錄的檔案推，不是計時器猜）：
  `claimed`（登記了、run 目錄還沒東西）→ `forming`（launcher 起來了、pi 還沒說話也沒動手）
  → `working`（有 says 或步驟）→ `reviewing`（有驗收套件 `tests_visible/`、agent 已交出
  凍結的工作區、之後沒有再動手）→ `done`（`run_*.json` 寫了）。
  **沒有驗收套件的 run 永遠不會是 `reviewing`**——不能在沒有檢查的時候講「Vacant 在檢查」。

## 審查結果怎麼讀（與線 B／C 的介面）

驗收結果在 `run/visible_<arm>[_a<n>].json`（`acceptance.run_suite` 的輸出：`files[].cases[]`，
`{case, ok, kind, message}`）。每一次嘗試一個檔；`attempt` 0 起算（無後綴＝第 1 次＝0，`_a2`＝第 2 次＝1）。
這裡把每個 case 轉成 `{id, ok, label, attempt}`：

* 若 `ops.exhibit.twin.review_suite` 存在且有 `describe(case, ok, message) -> (id, label)`，
  用它（label 是給人看的短句，由審查那一側決定）；
* 否則退到通用寫法：`id`＝case 名裡的 `r\\d+`（大寫）或 case 名前 24 字，`label`＝失敗時用
  訊息第一行、通過時用 case 名去掉 `test_`。

## 誠實邊界

1. **進度是檔案推出來的、不是 agent 自述**：`reviewing` 的判準是檔案時間先後（凍結目錄的
   mtime ≥ agent 最後活動），在 NFS／時鐘怪的檔案系統上可能判成 `working`——只會「少講」，
   不會多講（`reviewing` 還要求套件存在）。
2. **撤回的空窗**：本機撤回到下一輪 `untrack` 之間（≤ 一個迴圈間隔）執行緒可能再送一次；
   雲端對 `withdrawn` 一律忽略（`ignored`），且撤回時會把 says／steps／review 一起刪。
3. says 只擋逐字抄觀眾原文（`read_says` 的 LEAK 規則）；手機是本人私人看，含檔名也送。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import threading
import time
from typing import Any, Callable

_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ops.exhibit.twin import twinagent  # noqa: E402

#: 每人每幾秒最多送一次（計畫 PROC4 線 A）。不是量到的事實，是「手機跟得上又不打爆雲端」的策展參數。
MIN_INTERVAL_S = 5.0
#: 內容沒變也要有一次心跳的間隔：雲端用「最近有沒有消息」判斷 claimed 是不是已經死掉
#: （`STALE_CLAIM_MS`＝15 分鐘），心跳要遠小於它。
KEEPALIVE_S = 60.0
#: 執行緒醒來的間隔。比 MIN_INTERVAL_S 小，才能讓節流真的是 5 秒而不是 5–10 秒。
TICK_S = 1.0
POST_TIMEOUT_S = 8.0

STAGES = ("claimed", "forming", "working", "reviewing", "done")
SUITE_DIRNAME = "tests_visible"

_VISIBLE_RE = re.compile(r"^visible_(?P<arm>.+?)(?:_a(?P<n>\d+))?\.json$")
_RID_RE = re.compile(r"r\d+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 從 run 目錄推階段、讀審查結果（純檔案讀取，執行緒安全）
# ---------------------------------------------------------------------------

def _mtime(p: pathlib.Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _visible_files(rd: pathlib.Path) -> list[tuple[int, pathlib.Path]]:
    out: list[tuple[int, pathlib.Path]] = []
    try:
        names = sorted(rd.iterdir())
    except OSError:
        return out
    for p in names:
        m = _VISIBLE_RE.match(p.name)
        if m and p.is_file():
            # launcher：第 1 次嘗試的檔名沒有後綴，第 n 次（n≥2）才加 `_a<n>`；attempt 取 0 起算。
            out.append((int(m.group("n")) - 1 if m.group("n") else 0, p))
    out.sort(key=lambda t: t[0])
    return out


def _describe_default(case: str, ok: bool, message: str) -> tuple[str, str]:
    m = _RID_RE.search(case or "")
    rid = (m.group(0).upper() if m else (case or "check")[:24]) or "check"
    rid = re.sub(r"[^A-Za-z0-9_.-]", "_", rid)[:24] or "check"
    if not ok:
        first = (message or "").strip().splitlines()[0] if (message or "").strip() else ""
        label = first or (case or "這一條").replace("test_", "", 1)
    else:
        label = (case or "這一條").replace("test_", "", 1)
    return rid, label[:120]


def _describer() -> Callable[[str, bool, str], tuple[str, str]]:
    try:
        from ops.exhibit.twin import review_suite  # type: ignore
        fn = getattr(review_suite, "describe", None)
        if callable(fn):
            return fn
    except Exception:  # noqa: BLE001 —— 審查那一側還沒合進來／壞了 ⇒ 退通用寫法
        pass
    return _describe_default


def read_review(rd: pathlib.Path) -> list[dict[str, Any]]:
    """把每一次嘗試的驗收結果轉成 `[{id, ok, label, attempt}]`（見模組 docstring）。"""
    describe = _describer()
    out: list[dict[str, Any]] = []
    for attempt, p in _visible_files(rd):
        try:
            res = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for f in (res.get("files") or []):
            for c in (f.get("cases") or []):
                if not isinstance(c, dict):
                    continue
                ok = bool(c.get("ok"))
                try:
                    rid, label = describe(str(c.get("case") or ""), ok, str(c.get("message") or ""))
                except Exception:  # noqa: BLE001
                    rid, label = _describe_default(str(c.get("case") or ""), ok,
                                                   str(c.get("message") or ""))
                out.append({"id": str(rid)[:24], "ok": ok, "label": str(label)[:120],
                            "attempt": min(max(attempt, 0), 9)})
                if len(out) >= 30:
                    return out
    return out


def infer_stage(rd: pathlib.Path) -> str:
    """這一跑現在到哪一步（只講檔案上已經成立的事）。"""
    if not rd.is_dir():
        return "claimed"
    try:
        if any(p.name.startswith("run_") and p.suffix == ".json" for p in rd.iterdir()):
            return "done"
    except OSError:
        return "claimed"
    stdout = rd / twinagent.AGENT_STDOUT_NAME
    steps = rd / twinagent.STEP_LOG_NAME
    activity = max(_mtime(stdout), _mtime(steps))
    acted = (stdout.is_file() and stdout.stat().st_size > 0) or \
            (steps.is_file() and steps.stat().st_size > 0)
    if not acted:
        return "forming"
    if (rd / SUITE_DIRNAME).is_dir():
        frozen = [p for p in rd.iterdir() if p.is_dir() and p.name.startswith("_frozen_")]
        if frozen and max(_mtime(p) for p in frozen) >= activity:
            return "reviewing"
    return "working"


def snapshot(work_root: pathlib.Path, sub_id: str,
             secrets: list[str] | None = None) -> dict[str, Any]:
    """這個人現在的進度，形狀＝`POST /api/progress` 的本體（不含 token／id／ts）。"""
    _ws, rd = twinagent.paths_for(pathlib.Path(work_root), sub_id)
    stage = infer_stage(rd)
    snap: dict[str, Any] = {"stage": stage}
    if stage in ("working", "reviewing", "done"):
        snap["says"] = twinagent.read_says(rd, secrets or [])
        snap["steps"] = twinagent.read_step_log(rd)
    if stage in ("reviewing", "done"):
        rv = read_review(rd)
        if rv:
            snap["review"] = rv
    return snap


def _digest(snap: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(snap, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 背景呈報者
# ---------------------------------------------------------------------------

class ProgressReporter:
    """把「已登記、還在跑」的人的進度推上雲端。**只讀檔案、不碰 sqlite。**"""

    def __init__(self, cloud: str, token: str, work_root: pathlib.Path, *,
                 min_interval_s: float = MIN_INTERVAL_S, keepalive_s: float = KEEPALIVE_S,
                 tick_s: float = TICK_S, post: Callable[..., tuple[int, Any]] | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.cloud = cloud.rstrip("/")
        self.token = token
        self.work_root = pathlib.Path(work_root)
        self.min_interval_s = float(min_interval_s)
        self.keepalive_s = float(keepalive_s)
        self.tick_s = float(tick_s)
        self._clock = clock
        self._post = post
        self._lock = threading.Lock()
        self._tracked: dict[str, list[str]] = {}
        self._last: dict[str, tuple[float, str]] = {}      # sid → (上次送的時間, 內容摘要)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.stats = {"sent": 0, "failed": 0, "skipped_throttle": 0, "skipped_same": 0,
                      "ignored_by_cloud": 0}

    # ---- 主執行緒呼叫 ----
    def track(self, sub_id: str, secrets: list[str] | None = None) -> None:
        with self._lock:
            self._tracked[sub_id] = list(secrets or [])

    def untrack(self, sub_id: str) -> None:
        with self._lock:
            self._tracked.pop(sub_id, None)
            self._last.pop(sub_id, None)

    def tracked(self) -> set[str]:
        with self._lock:
            return set(self._tracked)

    def sync(self, keep: set[str]) -> None:
        """只留 `keep` 裡的（跑完收成的、被撤回的從這裡退場）。"""
        for sid in self.tracked() - set(keep):
            self.untrack(sid)

    # ---- 一次掃描（測試直接呼叫；執行緒每 tick 呼叫） ----
    def tick_once(self) -> list[str]:
        sent: list[str] = []
        with self._lock:
            items = list(self._tracked.items())
        for sid, secrets in items:
            now = self._clock()
            last = self._last.get(sid)
            if last is not None and now - last[0] < self.min_interval_s:
                self.stats["skipped_throttle"] += 1
                continue
            try:
                snap = snapshot(self.work_root, sid, secrets)
            except Exception:  # noqa: BLE001 —— 讀檔失敗不影響現場
                self.stats["failed"] += 1
                continue
            dg = _digest(snap)
            if last is not None and last[1] == dg and now - last[0] < self.keepalive_s:
                self.stats["skipped_same"] += 1
                continue
            if self._send(sid, snap):
                self._last[sid] = (now, dg)
                sent.append(sid)
            else:
                # 失敗也記時間：等下一個節流週期再試，不連環打。
                self._last[sid] = (now, "")
        return sent

    def _send(self, sid: str, snap: dict[str, Any]) -> bool:
        payload = {"token": self.token, "id": sid, "ts": int(time.time() * 1000), **snap}
        try:
            post = self._post
            if post is None:
                from ops.exhibit.twin import twinlink
                post = twinlink._http_json
            status, body = post(f"{self.cloud}/api/progress", payload, timeout=POST_TIMEOUT_S)
        except Exception:  # noqa: BLE001
            self.stats["failed"] += 1
            return False
        if status != 200:
            self.stats["failed"] += 1
            return False
        if isinstance(body, dict) and body.get("ignored"):
            self.stats["ignored_by_cloud"] += 1
        self.stats["sent"] += 1
        return True

    # ---- 執行緒 ----
    def start(self) -> "ProgressReporter":
        if self._thread is not None:
            return self
        self._stop.clear()

        def _run() -> None:
            while not self._stop.is_set():
                try:
                    self.tick_once()
                except Exception:  # noqa: BLE001 —— 呈報者死掉不能拖垮迴圈
                    self.stats["failed"] += 1
                self._stop.wait(self.tick_s)

        self._thread = threading.Thread(target=_run, name="twin-progress", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=2.0)
        self._thread = None
