"""這支在架構裡承重什麼：`vacant run` **跑的當下**對外講「現在發生了什麼」的那一條線。

## 為什麼要有這一支（2026-09-24）

在此之前，外面（數位分身的電視、任何觀測台）要知道一跑發生了什麼，只能等它
**跑完**，再去讀 run 目錄——`run_<ARM>.json`、`visible_*.json`、收據鏈——自己
推回一串事件（`ops/exhibit/twin/to_events.py` 就是這樣做的）。兩個後果：

1. **畫面跟不上過程。** 真模型一題約 114 秒（E10），那段時間裡外面什麼都看不到。
2. **外面綁死在 run 目錄的形狀上。** `launcher` 每改一次落盤格式（`_a<n>` 後綴、
   `attempts` 陣列、`model_wire`…），推事件的那一支就得跟著改，改漏了畫面就說錯。

人類的要求是：「vacant 就算迭代，數位分身也可以吃到資料正確顯示各種的反應」。
⇒ 事件改由**觀察到那件事的人**當場寫出來：proxy 轉完一通就寫 `model_call`，
閘門跑完就寫 `gate_ran`。外面只認這一份契約（`SCHEMA`），不再讀 run 目錄的內臟。

## 契約（`vacant.lifecycle/1`）

每一行一個 JSON 物件，共同欄位：

| 欄位 | 意思 |
|---|---|
| `schema` | 恆為 `SCHEMA`。**改語意就換版號**，不准原地改 |
| `type` | 見 `TYPES` |
| `run_id` | 這一次 `run()` 的隨機 id（同一個檔可以裝很多跑） |
| `seq` | 這一跑內從 1 起算、嚴格遞增、不跳號 |
| `ts_ms` | 牆鐘毫秒 |
| `task_id`／`arm` | 與收據上的同名欄位相同 |

各型別的專屬欄位寫在 `FIELDS`，`validate_stream()` 是它的可執行版本。

## 誠實邊界（改碼請保留）

1. **事件流沒有簽章，不是證據。** 可驗的那一份仍然是收據鏈
   （`verify_receipts.py`）。這一條線只負責「讓畫面跟得上」，面板不是信任來源。
   `run_ended.verdict_hash` 讓看的人**可以**去對鏈，但事件本身不背書任何東西。
2. **寫事件永遠不准改變一跑的結果。** 寫不進去（磁碟滿、路徑錯）只累計
   `emit_errors`，裁決、退出碼、wire 位元組、argv 一個位元都不動。
   可執行證明＝`tests/test_vrun_lifecycle.py::test_unwritable_events_path_changes_nothing`。
3. **不帶內容。** 不寫 request／response body、不寫 argv 原文、不寫回饋全文
   （只寫位元組數與 sha256）。這條線會被接到公開的螢幕上，而那些東西裡可能有
   使用者的 prompt、有金鑰的痕跡。要看內容去讀 run 目錄。
4. **跑到一半不知道總共會試幾次。** `attempt_started` 只帶 `max_attempts`（上限）；
   實際用了幾次要等 `run_ended.attempts_used`。不准在前面的事件裡「猜」一個總數。
5. **`caller` 是呼叫端塞進來的標籤，Vacant 沒有驗過它。** 它原樣出現在
   `run_started.caller`，用途是讓外面知道「這一跑是哪一格、哪位居民」。
   它不是收據的一部分，不准被讀成 Vacant 的宣告。
6. **`model_call` 是下界，跟 `requests_seen` 同一個語意。** proxy 在回應送完之後
   才記一通；被 `-9` 砍掉那一刻在途的請求不會有事件（見 `launcher` 的
   `model_wire.count_semantics`）。最後以 `run_ended.count_semantics` 為準。
"""
from __future__ import annotations

import json
import os
import pathlib
import threading
import time
import uuid
from typing import Any, Iterable

SCHEMA = "vacant.lifecycle/1"

#: 環境變數：給改不動 argv 的 wrapper（與 `VACANT_RUN_ALLOW_PUBLIC_UPSTREAM` 同一個理由）。
ENV_EVENTS = "VACANT_EVENTS"

TYPES = ("run_started", "attempt_started", "model_call", "agent_exited",
         "gate_ran", "feedback_ready", "run_ended")

COMMON = ("schema", "type", "run_id", "seq", "ts_ms", "task_id", "arm")

#: 每個型別**一定要有**的欄位（值可以是 `None`，但 key 要在——「沒量到」要看得見）。
FIELDS: dict[str, tuple[str, ...]] = {
    "run_started": ("vacant", "retry", "max_attempts", "feedback_into",
                    "ws_start_sha256", "caller"),
    "attempt_started": ("attempt", "max_attempts", "reset",
                        "feedback_delivery", "feedback_in_prompt_bytes"),
    "model_call": ("attempt", "n_total", "wire", "blocked", "error",
                   "elapsed_s"),
    "agent_exited": ("attempt", "agent_rc", "timed_out", "agent_wall_s",
                     "requests_seen", "wire_quiesced"),
    "gate_ran": ("attempt", "passed", "n_passed", "n_tests", "failed_case",
                 "verdict_sha256"),
    "feedback_ready": ("attempt", "next_attempt", "retry", "delivery",
                       "bytes", "text_sha256"),
    "run_ended": ("stop_reason", "accepted", "refused", "infra_void",
                  "attempts_used", "requests_seen", "count_semantics",
                  "ws_end_sha256", "verdict_sha256", "has_receipt",
                  "verdict_hash"),
}


class Emitter:
    """把事件逐行追加到一個 JSONL 檔。`path=None` ⇒ 什麼都不做（預設行為逐字不變）。

    執行緒安全：`model_call` 從 proxy 的 handler 執行緒發，其餘從 launcher 主執行緒發。
    每一行寫完就 `flush()`，讓另一個行程 tail 得到（不 `fsync`：這條線不是證據，
    斷電掉最後幾行可以接受；收據鏈才是要撐過斷電的那一份）。
    """

    def __init__(self, path: str | os.PathLike | None, *, task_id: str,
                 arm: str, run_id: str | None = None) -> None:
        self.path = pathlib.Path(path) if path else None
        self.task_id, self.arm = task_id, arm
        self.run_id = run_id or uuid.uuid4().hex
        self.seq = 0
        self.emitted = 0
        self.emit_errors = 0
        self.last_error: str | None = None
        self._lock = threading.Lock()
        self._fh = None
        if self.path is not None:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._fh = self.path.open("a", encoding="utf-8")
            except OSError as exc:
                # 誠實邊界 2：開不了檔不准弄死一跑。記下來，之後每一筆都算一次錯。
                self._fh = None
                self.last_error = f"open: {type(exc).__name__}: {exc}"

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def emit(self, type_: str, **fields: Any) -> None:
        if self.path is None:
            return
        with self._lock:
            self.seq += 1
            rec = {"schema": SCHEMA, "type": type_, "run_id": self.run_id,
                   "seq": self.seq, "ts_ms": int(time.time() * 1000),
                   "task_id": self.task_id, "arm": self.arm, **fields}
            if self._fh is None:
                self.emit_errors += 1
                return
            try:
                self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                self._fh.flush()
                self.emitted += 1
            except (OSError, TypeError, ValueError) as exc:
                self.emit_errors += 1
                self.last_error = f"write: {type(exc).__name__}: {exc}"

    def close(self) -> None:
        with self._lock:
            if self._fh is not None:
                try:
                    self._fh.close()
                except OSError:
                    pass
                self._fh = None

    def manifest(self) -> dict[str, Any]:
        """落進 summary 的那一塊：外面看得到「事件流寫了幾筆、壞了幾筆」。"""
        return {"schema": SCHEMA, "path": str(self.path) if self.path else None,
                "run_id": self.run_id if self.path else None,
                "emitted": self.emitted, "emit_errors": self.emit_errors,
                "last_error": self.last_error}


def resolve_path(explicit: str | os.PathLike | None) -> str | None:
    """旗標優先，其次 `VACANT_EVENTS`；都沒有 ⇒ `None`（不寫）。"""
    if explicit:
        return str(explicit)
    env = (os.environ.get(ENV_EVENTS) or "").strip()
    return env or None


def read(path: str | os.PathLike) -> list[dict]:
    """讀整個檔。**最後一行寫到一半**（另一個行程正在寫）⇒ 那一行不算，不炸。"""
    out = []
    text = pathlib.Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            break
    return out


def validate_stream(events: Iterable[dict]) -> list[str]:
    """契約自檢。回傳問題清單（空＝合格）。**外面換版本之前先跑這一支。**"""
    bad: list[str] = []
    last_seq: dict[str, int] = {}
    ended: set[str] = set()
    started: set[str] = set()
    for i, e in enumerate(events, 1):
        for k in COMMON:
            if k not in e:
                bad.append(f"第 {i} 筆缺共同欄位 {k}")
        if e.get("schema") != SCHEMA:
            bad.append(f"第 {i} 筆 schema 是 {e.get('schema')!r}，不是 {SCHEMA}")
        t = e.get("type")
        if t not in FIELDS:
            bad.append(f"第 {i} 筆 type 不在契約裡：{t!r}")
            continue
        for k in FIELDS[t]:
            if k not in e:
                bad.append(f"第 {i} 筆（{t}）缺欄位 {k}")
        rid = e.get("run_id", "")
        seq = e.get("seq")
        if isinstance(seq, int):
            want = last_seq.get(rid, 0) + 1
            if seq != want:
                bad.append(f"第 {i} 筆 seq={seq}，這一跑預期 {want}（跳號或重複）")
            last_seq[rid] = seq
        if t == "run_started":
            if rid in started:
                bad.append(f"第 {i} 筆：run {rid} 開始了兩次")
            started.add(rid)
        elif rid not in started:
            bad.append(f"第 {i} 筆（{t}）出現在 run_started 之前")
        if rid in ended:
            bad.append(f"第 {i} 筆（{t}）出現在 run_ended 之後")
        if t == "run_ended":
            ended.add(rid)
            # 三值：`None` ＝沒量，不可以被壓成 False（與收據的 `accepted_is_null` 同一條）。
            if e.get("accepted") not in (True, False, None):
                bad.append(f"第 {i} 筆：accepted 只能是 true／false／null")
            if e.get("has_receipt") is False and e.get("verdict_hash"):
                bad.append(f"第 {i} 筆：沒有收據卻帶了 verdict_hash")
        if t == "gate_ran" and e.get("arm") == "RUN-OFF":
            bad.append(f"第 {i} 筆：OFF 臂沒有閘門，不可以有 gate_ran")
        if t == "model_call":
            # 誠實邊界 3：不帶內容。
            for k in ("body", "request", "response", "messages", "prompt"):
                if k in e:
                    bad.append(f"第 {i} 筆 model_call 夾帶了內容欄位 {k}")
    return bad
