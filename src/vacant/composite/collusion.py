"""Collusion-detection adapter for the graduation flow (P5 §6, dispatch §5).

Before a closed child's halo is published, the graduation flow must
confirm that the parent <-> child pair does NOT exhibit the canonical
collusion signals (same-controller, same-substrate, same-stylo).
Above-threshold signals indicate the parent is trying to graduate a
sock-puppet rather than a genuinely independent capability.

This module wraps P3's `same_detect` for the graduation path. P3 is not
a hard dependency: callers may pass any `CollusionDetector` Protocol
implementation. A `default_detector()` is provided that returns 0.0 on
every signal -- safe default so graduation works in P3-less builds and
defers to other gates (parent consent + rate limit). Tests inject a
detector that returns specific signal strengths.

Per the stated theory invariant (CLAUDE.md): same-* detection raises
cost, not prevents. The graduation gate's role is the same: a high
collusion signal blocks *this* graduation; the attacker can re-attempt
after burning more identity capital.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from vacant.core.types import VacantId

__all__ = [
    "CollusionDetector",
    "CollusionSignals",
    "CompositeStubDetector",
    "default_detector",
    "max_signal_strength",
]


@dataclass(frozen=True)
class CollusionSignals:
    """Strengths of the three collusion signals (THEORY_V5 §6 framing).

    Each strength is in `[0.0, 1.0]`. `same_controller` -- both vacants
    appear to be operated by the same human/org. `same_substrate` --
    both run on the same base model family. `same_stylo` -- the
    children's behavioural fingerprints (STYLO Vec16) are within the
    drift threshold of each other or of the parent.
    """

    same_controller: float
    same_substrate: float
    same_stylo: float

    def __post_init__(self) -> None:
        for name, v in (
            ("same_controller", self.same_controller),
            ("same_substrate", self.same_substrate),
            ("same_stylo", self.same_stylo),
        ):
            if not (0.0 <= v <= 1.0):
                raise ValueError(f"{name}={v} not in [0, 1]")


def max_signal_strength(signals: CollusionSignals) -> float:
    """Conservative composition: the *highest* signal is the trip line."""
    return max(signals.same_controller, signals.same_substrate, signals.same_stylo)


class CollusionDetector(Protocol):
    """Plug-point for the graduation flow.

    Concrete impls call into P3's `same_detect` (substrate fingerprint
    comparison, controller graph, STYLO embedding distance). Tests pass
    a stub returning fixed signals."""

    def signals_for(
        self,
        parent_id: VacantId,
        child_id: VacantId,
    ) -> CollusionSignals: ...


@dataclass(frozen=True)
class CompositeStubDetector:
    """Constant-returning detector. Useful in tests + the P3-less default."""

    same_controller: float = 0.0
    same_substrate: float = 0.0
    same_stylo: float = 0.0

    def signals_for(
        self,
        parent_id: VacantId,
        child_id: VacantId,
    ) -> CollusionSignals:
        del parent_id, child_id
        return CollusionSignals(
            same_controller=self.same_controller,
            same_substrate=self.same_substrate,
            same_stylo=self.same_stylo,
        )


def default_detector() -> CollusionDetector:
    """Return a no-signal detector. Used when P3 is not wired (D012 §B);
    graduation then defers to parent consent + rate limit."""
    return CompositeStubDetector()
