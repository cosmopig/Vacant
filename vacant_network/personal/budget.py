"""單次呼叫帳本。

這支在架構裡承重什麼：在送出下一個請求之前看剩餘額度，送出之後只記
端點實回的 usage。缺 usage 或逾時可能已被計費，就停止後續付費請求。
calls 只記真正送出的請求；實驗格另記，並用 call_id 引用。

本地端點的 cost_usd 記 0，並標 local。不把缺價格當成 0 元，也不把
prompt_tokens 與 total_tokens 加在一起。
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from .schemas import SchemaError


class BudgetError(RuntimeError):
    pass


DEFAULT_LIMITS = {
    "max_requests": 112,
    "max_input_tokens": 1_000_000,
    "max_output_tokens": 150_000,
    "cash_limit_usd": 15.0,
    "request_timeout_seconds": 90,
    "max_model_wall_seconds": 3600,
    "profile_build_request_cap": 4,
    "stage1_output_tokens": 200,
    "stage2_output_tokens": 1800,
    "profile_output_tokens": 2200,
}


def map_usage(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    """保留原始 usage。不把 prompt_tokens 與 total_tokens 相加。"""
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if isinstance(prompt, bool) or not isinstance(prompt, int):
        return None
    if isinstance(completion, bool) or not isinstance(completion, int):
        return None
    details = usage.get("prompt_tokens_details")
    cached = None
    if isinstance(details, dict) and "cached_tokens" in details:
        cached = details.get("cached_tokens")
        if isinstance(cached, bool) or not isinstance(cached, int):
            return None
    return {
        "input_total": prompt,
        "output_total": completion,
        "cached_input": cached,
        "total_tokens_field": usage.get("total_tokens"),
        "raw": dict(usage),
        "mapping": "prompt_tokens->input_total, completion_tokens->output_total, prompt_tokens_details.cached_tokens->cached_input; total_tokens is stored and not added",
    }


def known_cost(mapped: dict[str, Any], rates: dict[str, Any]) -> tuple[float | None, str]:
    cached = mapped["cached_input"]
    note = "cached_tokens absent; treated as 0"
    if cached is None:
        cached = 0
    else:
        note = "cached_tokens taken from prompt_tokens_details"
    if cached > mapped["input_total"]:
        return None, "cached_input exceeds input_total; cost unknown"
    input_rate = rates.get("input_usd_per_million")
    output_rate = rates.get("output_usd_per_million")
    cached_rate = rates.get("cached_input_usd_per_million")
    if input_rate is None or output_rate is None:
        return None, "rates unset; cost unknown, not zero"
    if cached and cached_rate is None:
        return None, "cached input present but cached rate unset; cost unknown"
    if cached_rate is None:
        cached_rate = input_rate
    cost = (
        (mapped["input_total"] - cached) * float(input_rate)
        + cached * float(cached_rate)
        + mapped["output_total"] * float(output_rate)
    ) / 1_000_000
    return cost, note


class BudgetLedger:
    def __init__(self, limits: dict[str, Any] | None = None, *, pricing: str = "unset", rates: dict[str, Any] | None = None):
        if pricing not in ("unset", "local", "rated"):
            raise BudgetError("pricing must be unset, local, or rated")
        self.limits = dict(DEFAULT_LIMITS)
        if limits:
            self.limits.update(limits)
        self.pricing = pricing
        self.rates = dict(rates or {})
        self.calls: list[dict[str, Any]] = []
        self.stopped = False
        self.stop_reason: str | None = None

    def sent_calls(self) -> list[dict[str, Any]]:
        """計入額度的請求。被一次重試取代、且沒有 usage 的那一筆不計，避免把同一格算兩次。"""
        return [row for row in self.calls if row.get("sent") and row.get("budget_request", True)]

    def _totals(self) -> dict[str, float]:
        input_tokens = 0
        output_tokens = 0
        cash = 0.0
        wall_ms = 0
        unknown_cost = False
        for row in self.calls:
            if not row.get("sent"):
                continue
            if isinstance(row.get("wall_ms"), int):
                wall_ms += row["wall_ms"]
            if not row.get("budget_request", True):
                continue
            mapped = row.get("usage_mapped")
            if isinstance(mapped, dict):
                input_tokens += int(mapped["input_total"])
                output_tokens += int(mapped["output_total"])
            if row.get("cost_usd") is None and self.pricing == "rated" and row.get("status") == "completed":
                unknown_cost = True
            elif isinstance(row.get("cost_usd"), (int, float)) and not isinstance(row.get("cost_usd"), bool):
                cash += float(row["cost_usd"])
        return {
            "requests": len(self.sent_calls()),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cash_usd": cash,
            "wall_ms": wall_ms,
            "unknown_cost": unknown_cost,
        }

    def profile_slots_used(self) -> int:
        return sum(1 for row in self.sent_calls() if str(row.get("purpose", "")).startswith("profile") or row.get("purpose") == "compat-check")

    def authorize(self, *, purpose: str, estimated_output_tokens: int) -> tuple[bool, str]:
        if self.stopped:
            return False, self.stop_reason or "stopped"
        if purpose in ("profile-summary", "profile-structured", "profile-repair", "compat-check"):
            if self.profile_slots_used() >= int(self.limits["profile_build_request_cap"]):
                return False, "profile_build_request_cap"
        if self.pricing == "unset" and purpose != "fixture":
            return False, "pricing is unset; fixture runs are allowed, a paid or local model batch is not"
        totals = self._totals()
        if totals["requests"] >= int(self.limits["max_requests"]):
            return False, "max_requests"
        if totals["input_tokens"] >= int(self.limits["max_input_tokens"]):
            return False, "max_input_tokens"
        if totals["output_tokens"] + estimated_output_tokens > int(self.limits["max_output_tokens"]):
            return False, "max_output_tokens"
        if totals["wall_ms"] >= int(self.limits["max_model_wall_seconds"]) * 1000:
            return False, "max_model_wall_seconds"
        if self.pricing == "rated":
            if self.rates.get("input_usd_per_million") is None or self.rates.get("output_usd_per_million") is None:
                return False, "rated pricing is missing a rate"
            if totals["unknown_cost"]:
                return False, "earlier cost is unknown"
            if totals["cash_usd"] >= float(self.limits["cash_limit_usd"]):
                return False, "cash_limit_usd"
        return True, "ok"

    def begin(self, *, purpose: str, request_hash: str, call_id: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        row = {
            "call_id": call_id or uuid.uuid4().hex,
            "purpose": purpose,
            "sent": True,
            "budget_request": True,
            "status": "in_flight",
            "request_hash": request_hash,
            "response_hash": None,
            "usage": None,
            "usage_mapped": None,
            "cost_usd": None,
            "cost_note": None,
            "wall_ms": None,
            "error": None,
            "request_extra": dict(extra) if extra else None,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self.calls.append(row)
        return row

    def finish(self, call_id: str, *, status: str, usage: dict[str, Any] | None, wall_ms: int, response_hash: str | None, error: str | None, stop_run: bool = True) -> dict[str, Any]:
        row = next(item for item in self.calls if item["call_id"] == call_id)
        mapped = map_usage(usage)
        row["status"] = status
        row["usage"] = usage if isinstance(usage, dict) else None
        row["usage_mapped"] = mapped
        row["wall_ms"] = wall_ms
        row["response_hash"] = response_hash
        row["error"] = error
        if status == "completed" and mapped is not None:
            if self.pricing == "local":
                row["cost_usd"] = 0.0
                row["cost_note"] = "local; API USD is not inferred"
            elif self.pricing == "rated":
                cost, note = known_cost(mapped, self.rates)
                row["cost_usd"] = cost
                row["cost_note"] = note
                if cost is None:
                    self.stopped = True
                    self.stop_reason = "usage_unknown"
                    row["status"] = "usage_unknown"
            else:
                row["cost_usd"] = None
                row["cost_note"] = "pricing unset"
        else:
            row["cost_usd"] = None
            row["cost_note"] = "no measured usage"
            if stop_run and status in ("usage_unknown", "timeout", "model_failed"):
                self.stopped = True
                self.stop_reason = "usage_unknown"
                if status == "model_failed":
                    row["status"] = "model_failed"
        return row

    def public_rows(self) -> list[dict[str, Any]]:
        hidden = {"usage_mapped"}
        return [{key: value for key, value in row.items() if key not in hidden} for row in self.calls]


def require_limits(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise SchemaError(["budget limits must be an object"])
    return obj
