"""`ops/realrun/mini_agent.py` 的 file-mode 回饋讀取契約（v5 的前置修正）。

為什麼這支承重
──────────────
`--retry fresh_hint`（與 `revise`）的**預設**回饋通道是 file-mode：launcher 把
hint 寫進工作區的 `VACANT_FEEDBACK.md`（`vacant_network/vrun/retry.py`
`FEEDBACK_FILENAME`），而 agent 端必須自己讀它。v4 用的 `mini_agent.py`
**不讀這個檔**——在 file-mode 下 fresh_hint 臂會靜默退化成純 resample，
「fresh_hint vs resample」的比較就會在模型輸入端完全沒有差異（實驗失效，
但每一格都綠燈）。

本檔把 agent 端契約釘死（零模型、零網路：上游是本機假 server，逐字錄下
user message）：

1. **檔不存在** → user message 與 task prompt **逐位元組相同**
   （＝ resample 臂的行為完全不變；兩臂的模板逐字相同，KS-1）。
2. **檔存在且非空** → user message ＝ prompt + "\\n\\n---\\n" + 全文
   （hint 是**資料**，不是模板；兩臂差異只可能在檔的有無）。
3. **檔存在但全空白** → 視同不存在（不產生空尾巴）。
4. 基本 sanity：回傳的 fenced code block 仍被寫進 output file。

負對照：假 server 錄下的 request 是唯一證據——agent 若「假装讀了」
（例如只改 stdout 不改 user message），測試 1/2 會翻紅。
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
MINI_AGENT = REPO / "ops" / "realrun" / "mini_agent.py"
FEEDBACK = "VACANT_FEEDBACK.md"
PROMPT = "Write solve(x) that returns x + 1."
CODE = "def solve(x):\n    return x + 1\n"


class _FakeUpstream(BaseHTTPRequestHandler):
    """錄下 request body、回一則固定的 fenced code block 完成訊息。"""
    protocol_version = "HTTP/1.1"
    seen: list[dict] = []

    def log_message(self, *a):  # 安靜
        return

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        type(self).seen.append(body)
        content = "```python\n" + CODE + "```\n"
        payload = json.dumps({"choices": [{"message": {"role": "assistant",
                                                       "content": content},
                                          "finish_reason": "stop"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture()
def upstream():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _FakeUpstream)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    _FakeUpstream.seen = []
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()
    srv.server_close()


def _last_user_message() -> str:
    assert _FakeUpstream.seen, "agent 沒有打任何 model call"
    body = _FakeUpstream.seen[-1]
    msgs = body["messages"]
    assert msgs[0]["role"] == "system" and msgs[1]["role"] == "user"
    return msgs[1]["content"]


def _run(tmp_path: pathlib.Path, upstream: str) -> subprocess.CompletedProcess:
    env = dict(os.environ,
               OPENAI_BASE_URL=upstream,
               OPENAI_API_KEY="sk-test",
               VACANT_EXP_MODEL="fake/model")
    return subprocess.run(
        [sys.executable, str(MINI_AGENT), "solution.py", PROMPT],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)


def test_no_feedback_file_user_prompt_is_byte_identical(tmp_path, upstream):
    """resample 臂（工作區無回饋檔）：model 輸入與純 prompt 逐位元組相同。"""
    r = _run(tmp_path, upstream)
    assert r.returncode == 0, r.stderr
    assert _last_user_message() == PROMPT


def test_feedback_file_appended_verbatim(tmp_path, upstream):
    """fresh_hint 臂（檔在）：hint 全文逐字接在 prompt 後，不多不少。"""
    hint = ("<!-- Attempt 1 failed; workspace restored to clean origin -->\n"
            "Previous attempt failed acceptance check:\n"
            "FAIL: solve(1) == 2 -> got 1\n"
            "Avoid this failure in your clean implementation.")
    (tmp_path / FEEDBACK).write_text(hint, encoding="utf-8")
    r = _run(tmp_path, upstream)
    assert r.returncode == 0, r.stderr
    assert _last_user_message() == PROMPT + "\n\n---\n" + hint


def test_blank_feedback_file_is_ignored(tmp_path, upstream):
    (tmp_path / FEEDBACK).write_text("   \n\n", encoding="utf-8")
    r = _run(tmp_path, upstream)
    assert r.returncode == 0, r.stderr
    assert _last_user_message() == PROMPT


def test_solution_still_written(tmp_path, upstream):
    """讀檔分支不得破壞主職：fenced code block 仍落盤。"""
    (tmp_path / FEEDBACK).write_text("hint line", encoding="utf-8")
    r = _run(tmp_path, upstream)
    assert r.returncode == 0, r.stderr
    out = (tmp_path / "solution.py").read_text(encoding="utf-8")
    assert out == CODE
