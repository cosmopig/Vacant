#!/usr/bin/env python3
"""R530 的收據：兩種新事件別，**簽 digest、全文進 `calls.jsonl`**。

這支在架構裡承重什麼（`DECISION_20260913_R530_…_PREREG.md` §五-4）：

既有收據（`harness_attempt`／`conform_verdict`）簽的是「模型說了什麼、判了什麼」。
R530 的處理是**一個目錄**，所以收據要多簽一樣東西：**工作區當時的樹雜湊**
（`vacant/vrun/wshash.py`）。沒有它，鏈能說「這段對話沒被改過」，
說不了「當時交出去的目錄長這樣」。

兩種事件別（`etype` 是自由字串，`vacant/logbook.py` 一個字都不用改）：

  · `ws_attempt` ——**每一個閘門輪／每一次重抽嘗試各一筆**。
  · `ws_verdict` ——**每格一筆**（每題每臂）。

⚠ **為什麼是 digest 不是全文**：`vacant/logbook.py:34` 的
`MAX_PAYLOAD_BYTES = 64 KiB` 是硬限制，而一輪工作區記錄（指令、完整
stdout/stderr、樹的逐檔葉子）動輒超過。手法逐字沿用
`harness_arms._append_turn`（把 `fail_message` 換成 `fail_message_full_sha256`）：
**鏈上放雜湊，全文放 `calls.jsonl`／`rows.jsonl`**。
兩邊對得起來才算數——`vacant/vrun/verify_receipts.py` 的條數對帳
（verdict 數 == 該臂 row 數、attempt 數 ≥ verdict 數）認得這兩個新型別。

⚠ **誠實邊界（逐字沿用 `gain_run.save_receipts`，不准刪）**：
金鑰是一次性的匿名身分、私鑰不落盤（RECORD_SPEC §7）。這條鏈能說的是
**「事後沒有被改過」**（要改就得重簽，而私鑰隨行程消失），
**不是**「由某個已知的人簽的」。收據的究責宣稱只能講到這裡。

⚠ 還有一條 R530 專屬的邊界：樹雜湊證明的是「這棵樹的內容在被雜湊的當下是這樣」，
不證明**中間沒有被改過又改回來**。逐輪簽進鏈之後，時間次序由鏈承接，
但鏈本身只能說「這個次序事後沒被改過」。
"""
from __future__ import annotations

import hashlib
import json
import time

from ..logbook import Logbook

#: 兩種新事件別。**逐字凍結**——`verify_run_receipts.py` 與
#: `tests/test_r530_receipts.py` 引用的是這兩個常數，不是字面字串。
WS_ATTEMPT = "ws_attempt"
WS_VERDICT = "ws_verdict"

#: `ws_attempt` 的 payload 必備欄位（少一個就不是一筆合格的收據）。
ATTEMPT_FIELDS = ("task_id", "arm", "attempt", "gate_round",
                  "ws_sha256", "verdict_sha256", "conversation_sha256")
#: `ws_verdict` 的 payload 必備欄位。
VERDICT_FIELDS = ("task_id", "arm", "accepted", "ws_start_sha256",
                  "ws_end_sha256", "verdict_sha256", "conversation_sha256",
                  "stop_reason")


def conversation_digest(messages: list[dict]) -> str:
    """整段對話的 sha256。

    只取 `role` 與 `content` 兩個欄位、依原順序——`tool_call_id` 之類的
    傳輸細節每次都不同，算進去會讓同一段對話得到不同的雜湊。
    """
    reduced = [{"role": m.get("role"), "content": m.get("content", "")}
               for m in (messages or [])]
    return hashlib.sha256(
        json.dumps(reduced, sort_keys=False, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")).hexdigest()


def _append(book: Logbook, ident, etype: str, payload: dict,
            required: tuple[str, ...]):
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValueError(f"{etype} 收據缺欄位 {missing}——不完整的收據不是收據")
    entry = book.append(etype, payload, ident, ts_ms=int(time.time() * 1000))
    return entry


def append_attempt(book: Logbook, ident, *, task_id: str, arm: str,
                   attempt: int, gate_round: int, ws_sha256: str,
                   verdict_sha256: str | None,
                   conversation_sha256: str, **extra):
    """一輪／一次嘗試的收據。回 `LogEntry`（呼叫端把 `entry.hash()` 落進 row）。

    `verdict_sha256` 為 None ＝ **這一輪沒有跑驗收**（`A-SOLO` 的每一輪、
    以及還沒宣告完成的中間輪）。None 與「跑了但全錯」是兩件事，不可合併。
    """
    payload = {
        "task_id": task_id, "arm": arm, "attempt": attempt,
        "gate_round": gate_round, "ws_sha256": ws_sha256,
        "verdict_sha256": verdict_sha256,
        "conversation_sha256": conversation_sha256,
        **extra,
    }
    return _append(book, ident, WS_ATTEMPT, payload, ATTEMPT_FIELDS)


def append_verdict(book: Logbook, ident, *, task_id: str, arm: str,
                   accepted: bool, ws_start_sha256: str, ws_end_sha256: str,
                   verdict_sha256: str | None, conversation_sha256: str,
                   stop_reason: str | None, **extra):
    """每格一筆的裁決收據。

    ⚠ `A-SOLO` 的 `accepted` **恆為 True**（它沒有拒交語意）。
      這一格照樣落盤成 True，而**每一次引用都要跟著講這句**
      （§六-0、§八-4）——那是結構差不是量測差。
    """
    payload = {
        "task_id": task_id, "arm": arm, "accepted": bool(accepted),
        "ws_start_sha256": ws_start_sha256, "ws_end_sha256": ws_end_sha256,
        "verdict_sha256": verdict_sha256,
        "conversation_sha256": conversation_sha256,
        "stop_reason": stop_reason,
        **extra,
    }
    return _append(book, ident, WS_VERDICT, payload, VERDICT_FIELDS)
