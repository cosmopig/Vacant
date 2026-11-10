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


def _is_transient(exc: BaseException) -> bool:
    """逾時或連線中斷。HTTP 4xx 不重試。`think: false` 不是這個路徑。"""
    if _is_timeout(exc) or isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (502, 503, 504)
    if isinstance(exc, urllib.error.URLError):
        return not isinstance(exc, urllib.error.HTTPError)
    name = type(exc).__name__.lower()
    return "timeout" in name or "connection" in name


class FixtureBackend:
    """不連網。responses 以 purpose 取出預先寫好的文字，或用 handler 現做結構見證。"""

    name = "fixture"

    def __init__(self, responses: dict[str, Any] | None = None, *, handler: Callable[..., dict[str, Any]] | None = None, ledger: BudgetLedger | None = None):
        self.responses = dict(responses or {})
        self.handler = handler
        self.ledger = ledger
        self.invocations: list[dict[str, Any]] = []

    def complete(self, prompt: str, *, purpose: str, max_output_tokens: int, call_id: str | None = None, system: str = "", retry_transient: bool = False) -> dict[str, Any]:
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
    """包住 OpenAIBrain。預設一次請求、失敗不重送。

    `retry_transient=True` 只給 twin 跑：逾時或連線錯誤再送一次。第一筆沒有
    usage 時不計入額度，避免同一格的 usage 算兩次。其他命令維持不重試。
    """

    name = "single_call"

    def __init__(self, brain: Any, ledger: BudgetLedger):
        self.brain = brain
        self.ledger = ledger
        self.generate_calls = 0

    def complete(self, prompt: str, *, purpose: str, max_output_tokens: int, call_id: str | None = None, system: str = "", retry_transient: bool = False) -> dict[str, Any]:
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
                "attempts": 0,
            }
        first, transient = self._once(
            prompt, purpose=purpose, max_output_tokens=max_output_tokens,
            call_id=call_id, system=system, request_hash=request_hash,
            stop_on_failure=not retry_transient,
        )
        if not (retry_transient and transient and first.get("status") in ("timeout", "model_failed")):
            first["attempts"] = 1
            return first
        failed = next(item for item in self.ledger.calls if item["call_id"] == first["call_id"])
        failed["budget_request"] = False
        failed["superseded_by_retry"] = True
        failed["cost_note"] = "transient failure with no usage; not counted, one retry follows"
        if self.ledger.stop_reason in ("usage_unknown",) and failed.get("status") in ("timeout", "model_failed"):
            self.ledger.stopped = False
            self.ledger.stop_reason = None
        second, _transient = self._once(
            prompt, purpose=purpose, max_output_tokens=max_output_tokens,
            call_id=None, system=system, request_hash=request_hash,
            stop_on_failure=False,
        )
        second["attempts"] = 2
        second["retried"] = True
        return second

    def _once(self, prompt: str, *, purpose: str, max_output_tokens: int, call_id: str | None, system: str, request_hash: str, stop_on_failure: bool) -> tuple[dict[str, Any], bool]:
        self.brain.last_usage = None
        self.brain.max_tokens = max_output_tokens
        if system:
            self.brain.system = system
        extra = getattr(self.brain, "request_extra", None)
        row = self.ledger.begin(purpose=purpose, request_hash=request_hash, call_id=call_id, extra=extra if isinstance(extra, dict) else None)
        started = time.perf_counter()
        self.generate_calls += 1
        try:
            content = self.brain.generate(prompt)
        except Exception as exc:  # noqa: BLE001 — 端點失敗要落成這一筆的終態
            wall_ms = int((time.perf_counter() - started) * 1000)
            transient = _is_transient(exc)
            status = "timeout" if _is_timeout(exc) else "model_failed"
            self.ledger.finish(
                row["call_id"], status=status, usage=None, wall_ms=wall_ms,
                response_hash=None, error=f"{type(exc).__name__}: {exc}",
                stop_run=stop_on_failure,
            )
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
                "request_extra": extra,
            }, transient
        wall_ms = int((time.perf_counter() - started) * 1000)
        usage = self.brain.last_usage if isinstance(self.brain.last_usage, dict) else None
        from .budget import map_usage
        if map_usage(usage) is None:
            self.ledger.finish(
                row["call_id"], status="usage_unknown", usage=None, wall_ms=wall_ms,
                response_hash=_hash_text(content or ""),
                error="last_usage missing or unmapped; previous usage was not reused",
                stop_run=True,
            )
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
                "request_extra": extra,
            }, False
        finished = self.ledger.finish(
            row["call_id"], status="completed", usage=usage, wall_ms=wall_ms,
            response_hash=_hash_text(content or ""), error=None, stop_run=False,
        )
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
            "request_extra": extra,
        }, False


from vacant_network.brains import OpenAIBrain as _OpenAIBrain


class PersonalOpenAIBrain(_OpenAIBrain):
    """個人試驗用的 OpenAI 相容呼叫。不改 `vacant_network.brains` 的本體。

    qwen3 / gemma 這類推理模型在 `/v1/chat/completions` 上若只設 max_tokens，
    token 會花在 reasoning、`content` 是空的。同一條路徑加
    `reasoning_effort: none` 才有正文。`think: false` 不會被這條相容路由看懂，
    所以這裡不送它。
    """

    def __init__(self, base_url: str, model: str, *, temperature: float = 0.0,
                 max_tokens: int | None = None, timeout: int = 90,
                 system: str = "You are a precise assistant. Output only the answer.",
                 api_key: str | None = None, extra_body: dict[str, Any] | None = None,
                 reasoning_effort: str | None = None):
        super().__init__(
            base_url, model, temperature=temperature, max_tokens=max_tokens,
            timeout=timeout, system=system, api_key=api_key,
        )
        extra = dict(extra_body or {})
        if reasoning_effort and "reasoning_effort" not in extra:
            extra["reasoning_effort"] = reasoning_effort
        if "think" in extra:
            raise BackendError("model.extra_body must not set think; the OpenAI-compat route ignores think:false. Use reasoning_effort.")
        self.request_extra = extra

    def build_payload(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": self.system},
                {"role": "user", "content": prompt},
            ],
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        payload.update(self.request_extra)
        if "tools" in payload:
            raise BackendError("personal backend does not send tools")
        return payload

    def generate(self, prompt: str) -> str:
        from vacant_network.brains import _post
        payload = self.build_payload(prompt)
        body = _post(self.base_url + "/chat/completions", payload, self.timeout, api_key=self.api_key)
        usage = body.get("usage") if isinstance(body, dict) else None
        self.last_usage = dict(usage) if isinstance(usage, dict) else None
        try:
            content = body["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise BackendError(f"chat completion has no message content: {exc}") from exc
        return content.strip()


def resolve_model(config: dict[str, Any]) -> dict[str, Any]:
    """VACANT_MODEL 覆寫 model_id，並套用 config.models 裡同名的那一筆。不連線。"""
    import os
    model = dict(config.get("model") or {})
    chosen = os.environ.get("VACANT_MODEL")
    if chosen:
        model["model_id"] = chosen
        for alt in config.get("models") or []:
            if isinstance(alt, dict) and alt.get("model_id") == chosen:
                merged = dict(model)
                merged.update(alt)
                model = merged
    return model


def brain_from_config(model: dict[str, Any]):
    """base_url、model id、api key 只從設定與環境變數來。此函式不發送請求。"""
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
    extra = model.get("extra_body")
    if extra is not None and not isinstance(extra, dict):
        raise BackendError("model.extra_body must be an object")
    effort = model.get("reasoning_effort")
    if effort is not None and not isinstance(effort, str):
        raise BackendError("model.reasoning_effort must be a string")
    return PersonalOpenAIBrain(
        base_url=base_url,
        model=model_id,
        temperature=temperature,
        max_tokens=None,
        timeout=timeout,
        api_key=api_key,
        extra_body=extra,
        reasoning_effort=effort,
    )
