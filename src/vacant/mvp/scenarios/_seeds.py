"""Default seeds for the four demo scenarios (dispatch/P7_demo_seed.md)."""

from __future__ import annotations

from typing import Final

DEFAULT_SEEDS: Final[dict[str, int]] = {
    "law_firm": 42,
    "code_review": 137,
    "multilingual_translation": 271,
    "self_replication": 314,
}

ADVERSARIAL_SEED: Final[int] = 666

__all__ = ["ADVERSARIAL_SEED", "DEFAULT_SEEDS"]
