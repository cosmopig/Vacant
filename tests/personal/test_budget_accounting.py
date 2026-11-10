"""缺用量不沿用上一筆，餘額不夠就不送。"""

from __future__ import annotations

from vacant_network.personal.backend import SingleCallBackend
from vacant_network.personal.budget import BudgetLedger, known_cost, map_usage


class Scripted:
    def __init__(self, steps):
        self.steps = list(steps)
        self.last_usage = {"prompt_tokens": 99, "completion_tokens": 99, "total_tokens": 198}
        self.max_tokens = None
        self.system = ""
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        self.last_usage = step.get("usage")
        return step.get("content", "ok")


def test_missing_usage_does_not_reuse_the_previous_call():
    brain = Scripted([
        {"usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}, "content": "a"},
        {"usage": None, "content": "b"},
    ])
    ledger = BudgetLedger(pricing="local")
    backend = SingleCallBackend(brain, ledger)
    first = backend.complete("one", purpose="probe", max_output_tokens=16, system="s")
    second = backend.complete("two", purpose="probe", max_output_tokens=16, system="s")
    third = backend.complete("three", purpose="probe", max_output_tokens=16, system="s")
    assert first["usage"]["prompt_tokens"] == 4
    assert second["status"] == "usage_unknown"
    assert second["usage"] is None
    assert ledger.calls[1]["usage"] is None
    assert third["sent"] is False
    assert brain.calls == 2


def test_timeout_and_empty_budget_do_not_send_another_request():
    blocked = SingleCallBackend(Scripted([]), BudgetLedger({"max_requests": 0}, pricing="local"))
    assert blocked.complete("x", purpose="probe", max_output_tokens=8, system="s")["sent"] is False
    assert blocked.generate_calls == 0
    brain = Scripted([TimeoutError("slow")])
    backend = SingleCallBackend(brain, BudgetLedger(pricing="local"))
    hit = backend.complete("x", purpose="probe", max_output_tokens=8, system="s")
    again = backend.complete("y", purpose="probe", max_output_tokens=8, system="s")
    assert hit["status"] == "timeout"
    assert again["sent"] is False
    assert brain.calls == 1


def test_usage_mapping_does_not_add_prompt_and_total():
    mapped = map_usage({
        "prompt_tokens": 10,
        "completion_tokens": 4,
        "total_tokens": 14,
        "prompt_tokens_details": {"cached_tokens": 3},
    })
    assert mapped["input_total"] == 10
    assert mapped["output_total"] == 4
    assert mapped["cached_input"] == 3
    cost, note = known_cost(mapped, {
        "input_usd_per_million": 2,
        "cached_input_usd_per_million": 1,
        "output_usd_per_million": 4,
    })
    assert note
    assert cost == ((7 * 2) + (3 * 1) + (4 * 4)) / 1_000_000
    local = BudgetLedger(pricing="local")
    brain = Scripted([{"usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}])
    done = SingleCallBackend(brain, local).complete("x", purpose="probe", max_output_tokens=8, system="s")
    assert done["cost_usd"] == 0.0
    assert "local" in done["cost_note"]


def test_unset_price_refuses_a_paid_call_and_allows_a_fixture_purpose_check():
    ledger = BudgetLedger(pricing="unset")
    allowed, why = ledger.authorize(purpose="predict:H01:RAW", estimated_output_tokens=200)
    assert allowed is False
    assert "unset" in why
