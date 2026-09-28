"""Isolated mechanism-level probe for Vacant EQ5 gain.

This is deliberately synthetic and has no external model/API dependency.  It exercises
the real arm_eq5 implementation, sandboxed executable checks, signed Logbook, and equal
5-call candidate budget.  It includes a positive condition and a hidden-blindspot
negative control so the probe cannot be read as a universal-effect claim.
"""

from __future__ import annotations

import json
import math
import random
import re
import warnings

from ops.gain.gain_run import arm_eq5, meets_demand
from vacant_network.identity import Identity
from vacant_network.logbook import Logbook


class _SyntheticAgent:
    def __init__(self, agent_id: str, mode: str) -> None:
        self.agent_id = agent_id
        self.mode = mode
        self.model = f"synthetic/{mode}"

    def generate(self, prompt: str, **_kwargs) -> str:
        m = re.search(r"K=(\\d+)", prompt)
        assert m is not None
        k = int(m.group(1))
        if self.mode == "good":
            return f"def solve(n):\\n    return (n + {k} - 1) // {k}\\n"
        if self.mode == "common_bug":
            # Common correlated error: floor division instead of ceil division.
            return f"def solve(n):\\n    return n // {k}\\n"
        if self.mode == "hidden_bug":
            # Passes every public/visible probe, but fails one hidden boundary.
            bad_n = 2 * k + 1
            return (
                "def solve(n):\\n"
                f"    if n == {bad_n}:\\n"
                f"        return n // {k}\\n"
                f"    return (n + {k} - 1) // {k}\\n"
            )
        raise AssertionError(self.mode)


def _task(i: int, *, blindspot: bool) -> dict:
    k = 2 + (i % 9)
    hidden_edge = 2 * k + 1
    expected_97 = (97 + k - 1) // k
    return {
        "task_id": f"{'blind' if blindspot else 'positive'}-{i:03d}",
        "prompt": (
            "Write Python function solve(n) for non-negative integer n. "
            f"Return ceil(n / K), where K={k}. Return code only."
        ),
        "entry_point": "solve",
        "visible_check": {
            "type": "run_python",
            "code": (
                "assert solve(0) == 0\\n"
                "assert solve(1) == 1\\n"
                f"assert solve({k}) == 1\\n"
                f"assert solve({k + 1}) == 2\\n"
            ),
        },
        "hidden_check": {
            "type": "run_python",
            "code": (
                "assert solve(0) == 0\\n"
                f"assert solve({2 * k - 1}) == 2\\n"
                f"assert solve({2 * k}) == 2\\n"
                f"assert solve({hidden_edge}) == 3\\n"
                f"assert solve(97) == {expected_97}\\n"
            ),
        },
        # Public inputs only; no expected outputs and no hidden-only boundary.
        "behavior_inputs": [[0], [1], [k], [k + 1]],
    }


def _mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def _run_case(*, blindspot: bool, seed: int, n: int = 40) -> dict:
    if blindspot:
        pool = [
            _SyntheticAgent("good-1", "good"),
            _SyntheticAgent("good-2", "good"),
            _SyntheticAgent("blind-1", "hidden_bug"),
            _SyntheticAgent("blind-2", "hidden_bug"),
            _SyntheticAgent("blind-3", "hidden_bug"),
        ]
    else:
        pool = [
            _SyntheticAgent("good-1", "good"),
            _SyntheticAgent("good-2", "good"),
            _SyntheticAgent("bug-1", "common_bug"),
            _SyntheticAgent("bug-2", "common_bug"),
            _SyntheticAgent("bug-3", "common_bug"),
        ]

    rng = random.Random(seed)
    calls = [0]
    book = Logbook()
    ident = Identity.generate()
    pairs: list[tuple[bool, bool]] = []
    released = 0
    leaked = 0

    for i in range(n):
        task = _task(i, blindspot=blindspot)
        gate_code, _worker, _assigned, meta = arm_eq5(
            task, pool, rng, calls, book, ident, k=5
        )
        gate_hidden, _ = meets_demand(
            gate_code, task["hidden_check"]["code"], entry_point="solve"
        )
        vote_hidden, _ = meets_demand(
            meta["vote_code"], task["hidden_check"]["code"], entry_point="solve"
        )

        gate_correct_delivery = bool(meta["accepted"] and gate_hidden)
        vote_correct_delivery = bool(vote_hidden)  # vote arm always releases
        released += int(bool(meta["accepted"]))
        leaked += int(bool(meta["accepted"]) and not gate_hidden)
        pairs.append((gate_correct_delivery, vote_correct_delivery))

    b = sum(g and not v for g, v in pairs)
    c = sum((not g) and v for g, v in pairs)
    gate = sum(g for g, _ in pairs)
    vote = sum(v for _, v in pairs)
    return {
        "n": n,
        "gate_correct_delivery": gate,
        "vote_correct_delivery": vote,
        "delta_pp": round(100.0 * (gate - vote) / n, 1),
        "gate_released": released,
        "gate_coverage": round(released / n, 3),
        "gate_wrong_released": leaked,
        "discordant_gate_only": b,
        "discordant_vote_only": c,
        "mcnemar_exact_p": _mcnemar_exact(b, c),
        "calls_total": calls[0],
        "calls_per_task": calls[0] / n,
        "receipt_entries": len(book.entries),
    }


def test_vacant_eq5_mechanism_gain_and_blindspot_control() -> None:
    positive = _run_case(blindspot=False, seed=20260928)
    blindspot = _run_case(blindspot=True, seed=20260929)

    result = {
        "probe": "vacant-eq5-synthetic-20260928",
        "mechanism_positive": positive,
        "hidden_blindspot_control": blindspot,
    }
    warnings.warn("VACANT_GAIN_PROBE_JSON=" + json.dumps(result, sort_keys=True))

    # Structural integrity: same exact 5-call budget in both conditions.
    assert positive["calls_per_task"] == 5.0
    assert blindspot["calls_per_task"] == 5.0
    assert positive["receipt_entries"] > 0
    assert blindspot["receipt_entries"] > 0

    # Positive-control hypothesis: executable acceptance beats behavioral majority
    # when the common error is exposed by the acceptance suite.
    assert positive["gate_correct_delivery"] > positive["vote_correct_delivery"]
    assert positive["discordant_gate_only"] > positive["discordant_vote_only"]

    # Negative control is intentionally not asserted to equality: finite random pairing
    # can move either direction. It exists to show that hidden-only common errors are not
    # magically repaired by Vacant when the executable acceptance suite cannot see them.
