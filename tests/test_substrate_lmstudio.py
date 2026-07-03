"""NW-1 · LMStudioSubstrate（真模型腦）單元測試。

全程 monkeypatch urllib.request.urlopen 模擬 HTTP，**不連真 VM**——驗：
  - retry×N（前幾次失敗、末次成功仍取得答案）
  - retry 全失敗 → SubstrateResult(output="", error="infra_void")
  - strip <think>…</think>、取最後 message content
  - max_tokens=None → 送出的 body **不含** max_tokens 欄；設值 → 含之
  - /no_think 批次指令注入
  - substrate_id 值（per-substrate 信譽 keying）
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from vacant.substrate import LMStudioSubstrate, SubstrateResult


class _FakeResp:
    """假的 urlopen 回傳物件：支援 context manager 與 json.load 的 .read()。"""

    def __init__(self, payload: dict) -> None:
        self._b = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._b

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *a: object) -> bool:
        return False


def _msg_payload(content: str) -> dict:
    """responses 風格回應：一則 reasoning + 一則 message（最終答案）。"""
    return {
        "output": [
            {"type": "reasoning", "content": "（內部思考，不該被當答案）"},
            {"type": "message", "content": content},
        ]
    }


def _install_urlopen(monkeypatch, handler):
    """把 handler 掛成 urllib.request.urlopen；handler(req, timeout) 回 _FakeResp 或 raise。

    回傳一個 list，記錄每次呼叫送出的 (url, decoded_body)，供斷言檢查。
    """
    calls: list[dict] = []

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        calls.append({
            "url": req.full_url,
            "body": json.loads(req.data.decode("utf-8")),
            "timeout": timeout,
        })
        return handler(len(calls))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


# --- think-strip + 取最後 message ------------------------------------------

def test_strip_think_and_take_last_message(monkeypatch, tmp_path):
    _install_urlopen(
        monkeypatch,
        lambda n: _FakeResp(_msg_payload("<think>一堆推理\n多行</think>42")),
    )
    sub = LMStudioSubstrate()
    res = sub.run(tmp_path, "1+41=?", None)
    assert res.output == "42"          # <think> 被移除、只留答案
    assert res.error is None
    assert res.learned_skill is None   # 真腦不在 substrate 內決定學習


def test_extract_ignores_reasoning_object(monkeypatch, tmp_path):
    # reasoning 物件的 content 不該被當答案；只取 type=="message" 的最後一則。
    payload = {
        "output": [
            {"type": "reasoning", "content": "WRONG"},
            {"type": "message", "content": "first"},
            {"type": "message", "content": "LAST"},
        ]
    }
    _install_urlopen(monkeypatch, lambda n: _FakeResp(payload))
    sub = LMStudioSubstrate()
    assert sub.run(tmp_path, "q", None).output == "LAST"


# --- retry×N ---------------------------------------------------------------

def test_retry_then_success(monkeypatch, tmp_path):
    # 前 3 次網路錯，第 4 次成功 → 仍取得答案（預設 retry=4）。
    def handler(n: int):
        if n < 4:
            raise urllib.error.URLError("connection refused")
        return _FakeResp(_msg_payload("ok"))

    calls = _install_urlopen(monkeypatch, handler)
    sub = LMStudioSubstrate()
    res = sub.run(tmp_path, "q", None)
    assert res.output == "ok"
    assert res.error is None
    assert len(calls) == 4   # 剛好用滿 4 次


def test_retry_respects_custom_count(monkeypatch, tmp_path):
    # retry=2：兩次全失敗即放棄（不多打）。
    def handler(n: int):
        raise urllib.error.URLError("down")

    calls = _install_urlopen(monkeypatch, handler)
    sub = LMStudioSubstrate(retry=2)
    res = sub.run(tmp_path, "q", None)
    assert res.error == "infra_void"
    assert len(calls) == 2


# --- infra_void ------------------------------------------------------------

def test_infra_void_on_all_failures(monkeypatch, tmp_path):
    def handler(n: int):
        raise OSError("network unreachable")

    calls = _install_urlopen(monkeypatch, handler)
    sub = LMStudioSubstrate()  # retry=4
    res = sub.run(tmp_path, "q", None)
    assert isinstance(res, SubstrateResult)
    assert res.output == ""            # 無輸出
    assert res.error == "infra_void"   # 呼叫端據此不計為一票
    assert res.learned_skill is None
    assert len(calls) == 4             # 打滿 retry 才放棄


def test_malformed_response_counts_as_failure(monkeypatch, tmp_path):
    # HTTP 成功但抽不到 message（如被 max_tokens 砍成空）→ 視為失敗、retry → infra_void。
    def handler(n: int):
        return _FakeResp({"output": [{"type": "reasoning", "content": "只有思考沒有答案"}]})

    calls = _install_urlopen(monkeypatch, handler)
    sub = LMStudioSubstrate()
    res = sub.run(tmp_path, "q", None)
    assert res.error == "infra_void"
    assert len(calls) == 4


# --- max_tokens 欄位規則 ----------------------------------------------------

def test_no_max_tokens_field_by_default(monkeypatch, tmp_path):
    calls = _install_urlopen(monkeypatch, lambda n: _FakeResp(_msg_payload("x")))
    sub = LMStudioSubstrate()  # max_tokens 預設 None
    sub.run(tmp_path, "q", None)
    assert "max_tokens" not in calls[0]["body"]   # None → 不傳該欄（不砍 reasoning）


def test_max_tokens_field_present_when_set(monkeypatch, tmp_path):
    # demo 模式：傳有界 max_tokens → body 應含之。
    calls = _install_urlopen(monkeypatch, lambda n: _FakeResp(_msg_payload("x")))
    sub = LMStudioSubstrate(max_tokens=2048)
    sub.run(tmp_path, "q", None)
    assert calls[0]["body"]["max_tokens"] == 2048


# --- /no_think 注入 --------------------------------------------------------

def test_no_think_injected_by_default(monkeypatch, tmp_path):
    calls = _install_urlopen(monkeypatch, lambda n: _FakeResp(_msg_payload("x")))
    sub = LMStudioSubstrate()  # no_think 預設 True（批次）
    sub.run(tmp_path, "solve me", None)
    assert "/no_think" in calls[0]["body"]["input"]
    assert "solve me" in calls[0]["body"]["input"]


def test_no_think_absent_when_disabled(monkeypatch, tmp_path):
    calls = _install_urlopen(monkeypatch, lambda n: _FakeResp(_msg_payload("x")))
    sub = LMStudioSubstrate(no_think=False)  # demo 模式可關
    sub.run(tmp_path, "solve me", None)
    assert "/no_think" not in calls[0]["body"]["input"]


def test_feedback_appended_to_input(monkeypatch, tmp_path):
    # 互查回饋（Composer verify-fix）應併入使用者輸入。
    calls = _install_urlopen(monkeypatch, lambda n: _FakeResp(_msg_payload("x")))
    sub = LMStudioSubstrate()
    sub.run(tmp_path, "task", {"feedback": "上次答案錯了，重想"})
    assert "上次答案錯了，重想" in calls[0]["body"]["input"]


# --- 端點 / substrate_id / body 基本欄位 ------------------------------------

def test_endpoint_and_body_basics(monkeypatch, tmp_path):
    calls = _install_urlopen(monkeypatch, lambda n: _FakeResp(_msg_payload("x")))
    sub = LMStudioSubstrate(base="http://192.168.56.1:8765", api="/api/v1/chat")
    sub.run(tmp_path, "q", None)
    assert calls[0]["url"] == "http://192.168.56.1:8765/api/v1/chat"
    assert calls[0]["body"]["model"] == "qwen/qwen3.6-35b-a3b"
    assert "system_prompt" in calls[0]["body"]
    assert calls[0]["timeout"] == 180  # 預設 timeout 有傳進 urlopen


def test_substrate_id_default():
    sub = LMStudioSubstrate()
    assert sub.substrate_id == "lmstudio:qwen3.6-35b-a3b"


def test_import_without_vm():
    # 無 VM 環境下也能 import 與實例化（不觸網）。
    sub = LMStudioSubstrate(base="http://127.0.0.1:9/unreachable")
    assert isinstance(sub, LMStudioSubstrate)
    assert sub.max_tokens is None
