"""batch — 批次實驗的強韌層（裁決 B4：斷點續跑＋端點看門狗，寫成有測試的功能）。

背景：X1 主臂一晚 60–70h 級的夜跑，LM Studio 有行程級崩潰前科（裁決 §1 major）。
兩個機制：

  - **RunLedger**：每完成一個 (worker, task, seed) 立即 append 落盤（JSONL）；
    重啟後 `is_done` 自動跳過已完成格——斷點續跑不靠人工對帳。
    JSONL 逐行自足，崩潰最多壞最後一行（載入時容忍尾行截斷並如實計數）。
  - **Watchdog**：定期 ping OpenAI 相容端點（GET /v1/models）；掛掉→回呼通知
    （自動重啟 LM Studio 屬機器端腳本，此處負責偵測與等待復活）。

沿用 09 §3.5 紀律：全 I/O JSONL、retry×4、infra_void 規則由 harness 端執行。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


class RunLedger:
    """斷點續跑帳本：(worker, task, seed) → 完成記錄。append-only JSONL。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._done: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.corrupt_lines = 0
        if self.path.exists():
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        key = (str(rec["worker"]), str(rec["task"]), str(rec["seed"]))
                    except (ValueError, KeyError):
                        self.corrupt_lines += 1  # 崩潰截斷的尾行：如實計數、不吞
                        continue
                    self._done[key] = rec

    def is_done(self, worker: str, task: str, seed: str | int) -> bool:
        return (worker, task, str(seed)) in self._done

    def result(self, worker: str, task: str, seed: str | int) -> dict[str, Any] | None:
        return self._done.get((worker, task, str(seed)))

    def mark_done(
        self, worker: str, task: str, seed: str | int, result: dict[str, Any]
    ) -> None:
        rec = {"worker": worker, "task": task, "seed": str(seed), **result}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
        self._done[(worker, task, str(seed))] = rec

    def __len__(self) -> int:
        return len(self._done)


class Watchdog:
    """端點看門狗：ping /v1/models；掛掉 → on_down 通知 ＋ 等復活。"""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 5.0,
        on_down: Callable[[str], None] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.on_down = on_down

    def ping(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/v1/models", method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def wait_alive(
        self, *, retries: int = 60, interval: float = 10.0,
        _sleep: Callable[[float], None] = time.sleep,
    ) -> bool:
        """掛掉時阻塞等端點復活（給夜跑主迴圈用）。回 False＝等滿仍死。"""
        if self.ping():
            return True
        if self.on_down:
            self.on_down(f"端點 {self.base_url} 無回應，開始等待復活")
        for _ in range(retries):
            _sleep(interval)
            if self.ping():
                return True
        if self.on_down:
            self.on_down(f"端點 {self.base_url} 等滿 {retries}×{interval}s 仍無回應")
        return False
