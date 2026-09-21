"""端點打錯的時候，收據不准怪到 thinking 頭上（2026-09-22 實跑抓到）。

## 這一份在守什麼

展場那條線是 `ingest → generate → publish`。`generate` 打 LM Studio。
**LM Studio 的錯誤是用 HTTP 200 ＋ `{"error": …}` 回的，不是 4xx。**

實測：`--endpoint http://100.119.113.56:1234`（少了 `/v1`）
  ⇒ `POST …:1234/chat/completions` → `status=200`、
    `body={"error":"Unexpected endpoint or method. (POST /chat/completions)"}`、178ms
  ⇒ 沒有 `choices` ⇒ `content` 是空的
  ⇒ 舊碼判 `empty_content`，收據寫「**thinking 吃光額度**」

那句話指向完全錯誤的方向。展場操作員很可能照 LM Studio 介面上顯示的
`http://127.0.0.1:1234` 打（介面不顯示 `/v1`），然後照著收據去查 thinking 設定。

🔴 **三件事疊起來才是真正的危險**：
  1. **靜默**——HTTP 200，沒有任何一層會紅
  2. **怪錯人**——收據把 API 錯誤說成模型的 thinking 行為
  3. **不可逆**——`TwinStore.pending()` 排除已經有 `generated` 事件的 sub_id，
     所以退化過的卡**永遠不會再被撿起來**。展場頭一小時端點打錯，
     那一小時的每個觀眾都永久拿到查表版。

紀律：三種失效要有三個名字，不准塞進同一個桶——
`api_error`（API 回報錯誤）／`empty_content`（模型真的回空）／
`URLError`（連不上）。分不出來就修不對東西。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import twinlink  # noqa: E402

CARD = ("需求：把陽台枯掉的盆栽換成好養的多肉\n形狀：小巧\n質感：絨面\n"
        "色系：苔綠\n氣質：安靜、耐旱、不挑\n第一句話：我不太需要人照顧。")


def _fake_http(status, body):
    """把 `_http_json` 換成回固定東西的版本。"""
    def f(url, payload=None, timeout=30.0, **kw):
        return status, body
    return f


def test_api_error_不准被說成_empty_content(monkeypatch):
    """LM Studio 用 200 回 error ⇒ 要判 `api_error`，而且訊息要原樣帶出來。"""
    monkeypatch.setattr(twinlink, "_http_json", _fake_http(
        200, {"error": "Unexpected endpoint or method. (POST /chat/completions)"}))
    out = twinlink.generate_one(None, CARD, "http://x:1234", "m", 5.0, True)
    assert out["engine"] == "fallback_deterministic"
    assert out["degrade_kind"] == "api_error", (
        "API 錯誤被判成 %r——那是怪錯人" % out["degrade_kind"])
    assert "Unexpected endpoint" in out["degrade_reason"], "API 的原話要帶出來"
    assert "thinking" not in out["degrade_reason"], (
        "🔴 收據把 API 錯誤說成 thinking，展場會照著它查錯方向")


def test_少了_v1_要被點名(monkeypatch):
    """端點不以 `/v1` 結尾 ⇒ 訊息要直接講出這個最可能的原因。"""
    monkeypatch.setattr(twinlink, "_http_json", _fake_http(
        200, {"error": "Unexpected endpoint or method."}))
    out = twinlink.generate_one(None, CARD, "http://x:1234", "m", 5.0, True)
    assert "/v1" in out["degrade_reason"]


def test_負控制_端點正確時不要亂點名(monkeypatch):
    """端點已經帶 `/v1` 還出錯 ⇒ **不可以**再叫人去加 `/v1`（那是誤導）。"""
    monkeypatch.setattr(twinlink, "_http_json", _fake_http(
        200, {"error": "model not loaded"}))
    out = twinlink.generate_one(None, CARD, "http://x:1234/v1", "m", 5.0, True)
    assert out["degrade_kind"] == "api_error"
    assert "端點少了" not in out["degrade_reason"], (
        "端點是對的還叫人加 /v1 ⇒ 把人帶去另一個錯方向")
    assert "model not loaded" in out["degrade_reason"]


def test_負控制_模型真的回空_仍然要判_empty_content(monkeypatch):
    """沒有 `error`、但 `content` 是空的 ⇒ 這一格才是 thinking 吃光額度。

    ⚠ 這是上面那幾條的負控制：證明新的分支**沒有把所有空回應都吃掉**。
    """
    monkeypatch.setattr(twinlink, "_http_json", _fake_http(200, {
        "choices": [{"message": {"content": "", "reasoning_content": "想了很久"}}],
        "usage": {"completion_tokens": 2400,
                  "completion_tokens_details": {"reasoning_tokens": 2399}},
    }))
    out = twinlink.generate_one(None, CARD, "http://x:1234/v1", "m", 5.0, True)
    assert out["degrade_kind"] == "empty_content"
    assert "thinking" in out["degrade_reason"]


def test_負控制_模型正常回話時不准退化(monkeypatch):
    """最後一道：證明這些分支沒有把好的回應也推去 fallback。"""
    good = ('{"arrival":"我到了。","working":"我在做事。","handover":"交給你。"}')
    monkeypatch.setattr(twinlink, "_http_json", _fake_http(200, {
        "choices": [{"message": {"content": good}}],
        "usage": {"completion_tokens": 40,
                  "completion_tokens_details": {"reasoning_tokens": 10}},
    }))
    out = twinlink.generate_one(None, CARD, "http://x:1234/v1", "m", 5.0, True)
    assert out["engine"].startswith("lmstudio:"), (
        "正常回應被推去 fallback ⇒ 上面那幾條只是把功能關掉")
    assert out.get("degrade_kind") is None
