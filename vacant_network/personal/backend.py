"""生成後端。

這支在架構裡承重什麼：FixtureBackend 不連網，用來把 memo.md／plan.json
送進 intake。SingleCallBackend 包住既有 OpenAIBrain：每次一個沒有工具的
請求、不自動重試、呼叫前把 last_usage 清成 None。缺 usage 不沿用上一筆。

OpenAIBrain.generate 只回助理文字與 last_usage，不回 HTTP 封套。相容性
預檢若要看回應裡的 model 欄位，走 endpoint_smoke 那一個請求，不在這裡
多打一通。
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
from typing import Any, Callable

from .budget import BudgetLedger


class BackendError(RuntimeError):
    pass


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, urllib.error.URLError) and isinstance(getattr(exc, "reason", None), TimeoutError):
        return True
    name = type(exc).__name__.lower()
    return "timeout" in name


class FixtureBackend:
    """不連網。responses 以 purpose 取出預先寫好的文字，或用 handler 現做結構見證。"""

    name = "fixture"

    def __init__(self, responses: dict[str, Any] | None = None, *, handler: Callable[..., dict[str, Any]] | None = None, ledger: BudgetLedger | None = None):
        self.responses = dict(responses or {})
        self.handler = handler
        self.ledger = ledger
        self.invocations: list[dict[str, Any]] = []

    def complete(self, prompt: str, *, purpose: str, max_output_tokens: int, call_id: str | None = None, system: str = "") -> dict[str, Any]:
        self.invocations.append({"purpose": purpose, "max_output_tokens": max_output_tokens})
        request_hash = _hash_text(system + "\n" + prompt)
        if self.handler is not None:
            produced = self.handler(prompt, purpose=purpose, max_output_tokens=max_output_tokens)
        else:
            produced = self.responses.get(purpose, self.responses.get("default"))
        if produced is None:
            content = ""
            status = "parse_failed"
            error = f"fixture has no response for {purpose}"
        elif isinstance(produced, str):
            content, status, error = produced, "completed", None
        else:
            content = str(produced.get("content") or "")
            status = str(produced.get("status") or "completed")
            error = produced.get("error")
        row = None
        if self.ledger is not None:
            row = self.ledger.begin(purpose=purpose, request_hash=request_hash, call_id=call_id)
            # fixture 沒有端點 usage。不填假 token。
            self.ledger.finish(
                row["call_id"], status=status, usage=None, wall_ms=0,
                response_hash=_hash_text(content) if content else None, error=error,
            )
            done = next(item for item in self.ledger.calls if item["call_id"] == row["call_id"])
            if status == "completed":
                done["status"] = "completed"
                done["cost_note"] = "fixture; no HTTP request and no measured usage"
                done["cost_usd"] = None
                done["usage"] = None
        return {
            "sent": True,
            "backend": self.name,
            "call_id": None if row is None else row["call_id"],
            "status": status,
            "content": content,
            "usage": None,
            "cost_usd": None,
            "wall_ms": 0,
            "error": error,
            "request_hash": request_hash,
            "response_hash": _hash_text(content) if content else None,
        }


class SingleCallBackend:
    """包住 OpenAIBrain。generate 前後只發生一次，失敗不重送。"""

    name = "single_call"

    def __init__(self, brain: Any, ledger: BudgetLedger):
        self.brain = brain
        self.ledger = ledger
        self.generate_calls = 0

    def complete(self, prompt: str, *, purpose: str, max_output_tokens: int, call_id: str | None = None, system: str = "") -> dict[str, Any]:
        allowed, why = self.ledger.authorize(purpose=purpose, estimated_output_tokens=max_output_tokens)
        request_hash = _hash_text(system + "\n" + prompt)
        if not allowed:
            return {
                "sent": False,
                "backend": self.name,
                "call_id": None,
                "status": "budget_stopped",
                "content": "",
                "usage": None,
                "cost_usd": None,
                "wall_ms": 0,
                "error": why,
                "request_hash": request_hash,
                "response_hash": None,
            }
        self.brain.last_usage = None
        self.brain.max_tokens = max_output_tokens
        if system:
            self.brain.system = system
        row = self.ledger.begin(purpose=purpose, request_hash=request_hash, call_id=call_id)
        started = time.perf_counter()
        self.generate_calls += 1
        try:
            content = self.brain.generate(prompt)
        except Exception as exc:  # noqa: BLE001 — 端點失敗要落成這一筆的終態，不能重試
            wall_ms = int((time.perf_counter() - started) * 1000)
            status = "timeout" if _is_timeout(exc) else "model_failed"
            # 例外路徑不讀 last_usage：清過之後若端點沒寫回，沿用舊值就是錯的。
            self.ledger.finish(row["call_id"], status=status, usage=None, wall_ms=wall_ms, response_hash=None, error=f"{type(exc).__name__}: {exc}")
            return {
                "sent": True,
                "backend": self.name,
                "call_id": row["call_id"],
                "status": status,
                "content": "",
                "usage": None,
                "cost_usd": None,
                "wall_ms": wall_ms,
                "error": f"{type(exc).__name__}: {exc}",
                "request_hash": request_hash,
                "response_hash": None,
            }
        wall_ms = int((time.perf_counter() - started) * 1000)
        usage = self.brain.last_usage if isinstance(self.brain.last_usage, dict) else None
        from .budget import map_usage
        if map_usage(usage) is None:
            self.ledger.finish(row["call_id"], status="usage_unknown", usage=None, wall_ms=wall_ms, response_hash=_hash_text(content or ""), error="last_usage missing or unmapped; previous usage was not reused")
            return {
                "sent": True,
                "backend": self.name,
                "call_id": row["call_id"],
                "status": "usage_unknown",
                "content": content or "",
                "usage": None,
                "cost_usd": None,
                "wall_ms": wall_ms,
                "error": "last_usage missing or unmapped; previous usage was not reused",
                "request_hash": request_hash,
                "response_hash": _hash_text(content or ""),
            }
        finished = self.ledger.finish(row["call_id"], status="completed", usage=usage, wall_ms=wall_ms, response_hash=_hash_text(content or ""), error=None)
        return {
            "sent": True,
            "backend": self.name,
            "call_id": row["call_id"],
            "status": finished["status"],
            "content": content or "",
            "usage": usage,
            "cost_usd": finished["cost_usd"],
            "cost_note": finished["cost_note"],
            "wall_ms": wall_ms,
            "error": finished["error"],
            "request_hash": request_hash,
            "response_hash": _hash_text(content or ""),
        }


def brain_from_config(model: dict[str, Any]):
    """base_url、model id、api key 只從設定與環境變數來。此函式不發送請求。"""
    from vacant_network.brains import OpenAIBrain

    if not isinstance(model, dict):
        raise BackendError("model config must be an object")
    base_url = model.get("base_url")
    model_id = model.get("model_id")
    if not isinstance(base_url, str) or not base_url.strip():
        raise BackendError("model.base_url is required")
    if not isinstance(model_id, str) or not model_id.strip():
        raise BackendError("model.model_id is required")
    if "api_key" in model:
        raise BackendError("put the API key in the environment named by api_key_env, not in the config file")
    import os
    key_env = model.get("api_key_env")
    api_key = os.environ.get(key_env) if isinstance(key_env, str) and key_env else None
    timeout = int(model.get("request_timeout_seconds") or 90)
    temperature = float(model.get("temperature", 0.0))
    return OpenAIBrain(
        base_url=base_url,
        model=model_id,
        temperature=temperature,
        max_tokens=None,
        timeout=timeout,
        api_key=api_key,
    )
