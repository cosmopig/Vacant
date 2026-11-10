"""端點選項、續跑與 unsure。不連線。"""

from __future__ import annotations

import json
from pathlib import Path

from vacant_network.personal.backend import PersonalOpenAIBrain, SingleCallBackend
from vacant_network.personal.budget import BudgetLedger
from vacant_network.personal.metrics import score_twin
from vacant_network.personal.twin2k import convert_participant, load_rows_json
from vacant_network.personal.twin_runner import execute_twin, fixture_handler

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "twin2k_min.json"


def test_reasoning_effort_is_sent_and_think_is_not():
    brain = PersonalOpenAIBrain(
        "http://127.0.0.1:9/v1", "qwen3.8:27b", max_tokens=16, timeout=1,
        reasoning_effort="none",
    )
    payload = brain.build_payload("ping")
    assert payload["reasoning_effort"] == "none"
    assert payload["max_tokens"] == 16
    assert "think" not in payload
    assert "tools" not in payload
    other = PersonalOpenAIBrain(
        "http://127.0.0.1:9/v1", "gemma4:12b",
        extra_body={"reasoning_effort": "none"},
    )
    assert other.build_payload("ping")["reasoning_effort"] == "none"


def test_retry_once_does_not_count_the_failed_attempt_usage():
    class Flaky:
        def __init__(self):
            self.n = 0
            self.last_usage = {"prompt_tokens": 9, "completion_tokens": 9, "total_tokens": 18}
            self.max_tokens = None
            self.system = ""
            self.request_extra = {"reasoning_effort": "none"}

        def generate(self, prompt: str) -> str:
            self.n += 1
            if self.n == 1:
                raise TimeoutError("tunnel dropped")
            self.last_usage = {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}
            return '{"prediction":"B","uncertainty":"low"}'

    ledger = BudgetLedger(pricing="local")
    backend = SingleCallBackend(Flaky(), ledger)
    result = backend.complete("p", purpose="twin|p|RAW|W4:Q", max_output_tokens=16, system="s", retry_transient=True)
    assert result["status"] == "completed"
    assert result["attempts"] == 2
    assert result["usage"]["completion_tokens"] == 2
    counted = [row for row in ledger.calls if row.get("budget_request", True)]
    assert len(counted) == 1
    assert counted[0]["usage"]["completion_tokens"] == 2
    assert ledger.calls[0]["superseded_by_retry"] is True
    assert ledger.calls[0]["request_extra"] == {"reasoning_effort": "none"}
    assert ledger.stopped is False


def test_predictions_are_flushed_and_resume_skips_completed(tmp_path):
    rows = load_rows_json(FIXTURE)
    people = [convert_participant(rows[0], seed=3)]
    seen = []

    def handler(prompt, *, purpose, max_output_tokens):
        seen.append((tmp_path / "predictions.jsonl").read_text(encoding="utf-8").count("\n"))
        return fixture_handler(prompt, purpose=purpose, max_output_tokens=max_output_tokens)

    from vacant_network.personal.backend import FixtureBackend
    from vacant_network.personal.budget import BudgetLedger
    backend = FixtureBackend(handler=handler, ledger=BudgetLedger({"max_requests": 100}, pricing="local"))
    first = execute_twin(people, backend, tmp_path, max_output_tokens=32, retry_transient=False)
    assert seen and seen[0] >= 1
    assert first["stopped"] is False
    calls = (tmp_path / "calls.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(calls) == len(backend.invocations)
    again = FixtureBackend(handler=handler, ledger=BudgetLedger({"max_requests": 100}, pricing="local"))
    before = len(seen)
    execute_twin(people, again, tmp_path, max_output_tokens=32, resume=True, retry_transient=False)
    assert len(seen) == before


def test_unsure_is_abstention_and_a_strict_miss():
    labels = [{
        "pid": "p", "case_id": "W4:Q", "choice": "A", "choice_option_id": "option_1",
        "presented_order": ["option_1", "option_2"],
    }]
    predictions = [{
        "pid": "p", "case_id": "W4:Q", "arm": "SUMMARY", "status": "completed",
        "prediction": "unsure", "presented_order": ["option_1", "option_2"],
    }]
    scored = score_twin(predictions, labels, {"p": {"rate": 1.0}}, n_boot=20, seed=0)
    arm = scored["arms"]["SUMMARY"]
    assert arm["unsure_n"] == 1
    assert arm["unsure_rate"] == 1.0
    assert arm["strict_accuracy"] == 0.0
