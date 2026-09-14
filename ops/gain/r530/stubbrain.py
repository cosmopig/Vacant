#!/usr/bin/env python3
"""離線替身後端——讓整條迴圈在**零模型呼叫**下跑得完。

它承重的是「發射之前就知道 harness 會不會壞」：R530 的迴圈有三條臂、
五種停止理由、工作區重置、收據鏈與樹雜湊斷言，而真後端一格要跑幾分鐘。
用真模型去 debug 迴圈是把機時燒在 harness 的 bug 上。

⚠ **它的輸出不是資料**。`run_r530.py --brain stub` 會在 `summary.json` 裡把
`brain` 記成 `stub`，並在 run 目錄寫一個 `NOT_EVIDENCE` 檔。
`tests/` 與 `--smoke` 以外的地方不准用它。

腳本化的行為（刻意做成三條臂會走到不同結局）：

  · 第一稿的好壞**由 persona 決定**——system 裡含 "senior engineer" 或
    "cares about correctness"（＝ careful-1／careful-2）就直接寫對的解，
    其餘 persona 先寫一份**過不了可見驗收**的解。
  · 收到回饋（user 訊息以凍結的 FEEDBACK 開頭）之後一律改寫成對的解。
  · 寫完就在下一輪交回純文字（＝宣告完成）。

⇒ `A-SOLO` 在 hasty persona 上會**假交付**；`A-GATE` 會在第一個閘門輪之後修好；
  `A-CONF` 會一直重抽到抽中 careful persona 為止（或 5 份用完拒交）。
這三種結局都是迴圈路徑，不是模型能力——**不准拿去當任何一格結果**。
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

GOOD_MARKERS = ("senior engineer", "cares about correctness")

#: 每題一份「寫對的解」與一份「寫壞的解」的 shell。
#: 取自 `ops/gain/r530/gauge/<task_id>/`——那是 `export_bank.py` 從 `bank/`
#: 投影出來的，**同一份檔案**，不另外維護一份會漂掉的副本。
#: 檔名由投影固定成 `good.py` ＋ `bad_a/b/c.py`（20 題一致），
#: 所以這裡不需要逐題的對照表。
GAUGE_DIR = pathlib.Path(__file__).resolve().parent / "gauge"
BAD_NAME = "bad_a.py"


def _heredoc(body: str) -> str:
    return ("```bash\ncat > solution.py <<'R530EOF'\n"
            + body.rstrip("\n") + "\nR530EOF\n```\n")


class StubBrain:
    """與 `ops.gain.brain_cline.ClineBrain` 同形的 `chat()`。零網路。"""

    def __init__(self, *, log_path: pathlib.Path | None = None,
                 model: str = "stub", agent_id: str = "stub-0") -> None:
        self.model = model
        self.agent_id = agent_id
        self.log_path = log_path
        self.calls = 0
        self.cost = 0.0
        self.market_cost = 0.0
        self.reasoning_effort = None
        self.temperature = 0.0
        #: 替身走**文字協定**：它產生的是 ```bash 圍欄。真後端走 native
        #: （`ops/gain/r530/brain_native.py`，2026-09-13 冒煙實測）。
        self.tool_protocol = "text"

    def _log(self, rec: dict) -> None:
        """與 `ClineBrain._log` 同一個欄位形狀。

        ⚠ 這件事承重：`ops/gain/harness_vgt_audit.py --scope r530` 唯一的
          輸入是 `calls.jsonl` 的 `system`／`messages`。替身後端不落盤的話，
          冒煙會跑出一份「稽核 0 筆、判 CLEAN」的報告——那正是
          「沒有檢查」冒充「沒有違規」（稽核端對這件事有 fail-closed，
          但替身後端本來就該落盤，鐵律 3 不分後端）。
        """
        if self.log_path is None:
            return
        p = pathlib.Path(self.log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _source(self, task_id: str, good: bool) -> str:
        name = "good.py" if good else BAD_NAME
        p = GAUGE_DIR / task_id / name
        if not p.is_file():
            raise FileNotFoundError(f"stub 找不到 {p}")
        return p.read_text(encoding="utf-8")

    def propose(self, messages, *, system, meta=None, role="r530"):
        """與 `NativeToolBrain.propose` 同形：回 `{"text","tool_calls","usage",…}`。

        文字協定 ⇒ `tool_calls` 由 `openwork_arms.parse_commands` 從
        ```bash 圍欄解析出來，`id` 是空字串（工具結果以 user 訊息回灌）。
        """
        from ops.gain.r530.openwork_arms import parse_commands
        text, info = self.chat(messages, role=role, meta=meta, system=system)
        return {"text": text,
                "tool_calls": [{"id": "", "name": "run_bash", "command": c,
                                "timeout_s": None}
                               for c in parse_commands(text)],
                "usage": info.get("usage") or {},
                "finish_reason": info.get("finish_reason"), "raw": {}}

    def chat(self, messages, *, role="gen", meta=None, system=None,
             timeout_s=None, retries=None, turn=None, max_tokens=None,
             reasoning_effort=None):
        self.calls += 1
        meta = meta or {}
        task_id = meta.get("task_id") or "ow_01_csvjson"
        system = system or ""
        got_feedback = any(
            m.get("role") == "user"
            and m.get("content", "").startswith("The checks that ship with this task")
            for m in messages)
        wrote = any(m.get("role") == "assistant" and "R530EOF" in (m.get("content") or "")
                    for m in messages)
        info = {"finish_reason": "stop",
                "usage": {"prompt_tokens": 400, "completion_tokens": 300,
                          "total_tokens": 700},
                "model": self.model, "server_model": self.model,
                "latency_ms": 1, "attempt": 1, "stub": True}

        def done(text):
            last_user = next((m["content"] for m in reversed(messages)
                              if m["role"] == "user"), "")
            self._log({
                "ts_ms": int(time.time() * 1000),
                "agent_id": self.agent_id, "role": role, "api": "stub://",
                "model": self.model, "server_model": self.model,
                "model_configured": self.model, "temperature": self.temperature,
                "attempt": 1, "ok": True, "stub": True,
                "reasoning_effort": None, "latency_ms": 1,
                "usage": info["usage"], "system": system,
                "prompt": last_user,
                "messages": [{"role": m["role"], "content": m["content"]}
                             for m in messages],
                "finish_reason": "stop", "turn": turn,
                "response": text, "meta": meta,
            })
            return text, info

        if got_feedback:
            # 收到失敗原文 ⇒ 改寫成對的解（`A-GATE` 才走得到這一條）
            last_was_write = (messages[-1].get("role") == "user"
                              and messages[-1].get("content", "").startswith(
                                  "The checks that ship with this task"))
            if last_was_write:
                return done("I will rewrite it.\n\n"
                            + _heredoc(self._source(task_id, True)))
            return done("Rewrote solution.py; the checks should pass now.")
        if not wrote:
            good = any(m in system for m in GOOD_MARKERS)
            return done("Writing the solution now.\n\n"
                        + _heredoc(self._source(task_id, good)))
        return done("Wrote solution.py. That is the whole task.")

    def generate(self, prompt, **kwargs):        # pragma: no cover - 用不到
        raise NotImplementedError("stub 只實作 chat()")
