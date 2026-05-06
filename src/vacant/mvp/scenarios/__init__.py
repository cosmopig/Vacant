"""Demo scenarios. Each module exports `run(*, substrate, seed)`."""

from collections.abc import Awaitable, Callable
from typing import Any

from vacant.mvp.scenarios import (
    adversarial,
    code_review,
    law_firm,
    multilingual_translation,
    self_replication,
)
from vacant.mvp.scenarios._harness import ScenarioResult, VacantSeed
from vacant.mvp.scenarios._seeds import ADVERSARIAL_SEED, DEFAULT_SEEDS

ScenarioRunner = Callable[..., Awaitable[ScenarioResult]]

SCENARIOS: dict[str, ScenarioRunner] = {
    law_firm.SCENARIO_NAME: law_firm.run,
    code_review.SCENARIO_NAME: code_review.run,
    multilingual_translation.SCENARIO_NAME: multilingual_translation.run,
    self_replication.SCENARIO_NAME: self_replication.run,
    adversarial.SCENARIO_NAME: adversarial.run,
}


def get_runner(name: str) -> ScenarioRunner:
    if name not in SCENARIOS:
        raise KeyError(f"unknown scenario {name!r}; known: {sorted(SCENARIOS)}")
    return SCENARIOS[name]


__all__ = [
    "ADVERSARIAL_SEED",
    "DEFAULT_SEEDS",
    "SCENARIOS",
    "ScenarioResult",
    "ScenarioRunner",
    "VacantSeed",
    "adversarial",
    "code_review",
    "get_runner",
    "law_firm",
    "multilingual_translation",
    "self_replication",
]


_ = Any  # silence unused-import lint
