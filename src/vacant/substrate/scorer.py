"""LLM-driven 5D scorer (Pfix9 Phase 2 → Phase 4 spec alignment).

The existing `runtime.peer_review.score_response_heuristic` only looks at
text length / refusal markers / echo detection — it does NOT check
whether a response actually answered the prompt. technical.html
§Reputation row 2 / row 3 / row 5 explicitly says "Peer Review" /
"Ground Truth Check" / "Adoption Signal" should be **semantic** judgements.

This module gives `peer_review_tick` a real LLM-backed scorer that
reads `(request, response)` and emits **3-dim** semantic scores in [0, 1]:

    factual, logical, relevance

**Why only 3 dims and not 5?** Per `architecture/components/P3_reputation.md`
§Channel decomposition the 5 reputation dims have *different signal
sources*:

  | dim       | source                                       |
  | ----------| ---------------------------------------------|
  | factual   | ground truth check / caller fact verification |
  | logical   | peer consistency / self-consistency           |
  | relevance | caller "did you solve my problem?"            |
  | honesty   | **self-eval vs peer-consensus gap** (separate channel — `Aggregator.record_self_eval_gap`) |
  | adoption  | **downstream chain references** in a 24-72h window (separate channel — `AdoptionLedger`) |

A peer-review LLM evaluator can legitimately judge F/L/R from a single
(question, answer) pair. It CANNOT judge honesty (that requires
comparing the responder's self-eval against peer consensus) or
adoption (that requires waiting hours for downstream citations).
Including H/A in the peer-review prompt would have the LLM
*confabulate* values for channels that should come from elsewhere —
polluting the aggregator with the wrong source weight.

This is why the spec keeps the channels separate. The peer-review path
contributes to F/L/R; honesty is updated by `record_self_eval_gap`;
adoption is updated by `record_adoption`.

Operators who want to test with a 5D prompt for ablation studies can
override `dimensions=REPUTATION_DIMS`; production peer-review keeps
the default `PEER_REVIEW_DIMS`.

Cost containment:
- One scorer call per peer-review tick (caller decides cadence).
- `max_tokens=200` cap on the scorer response — the JSON is tiny.
- `temperature=0` deterministic so a re-score gives the same answer.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from vacant.core.constants import REPUTATION_DIMS
from vacant.substrate.base import SubstrateBackend, SubstrateRequest

__all__ = [
    "PEER_REVIEW_DIMS",
    "SCORER_SYSTEM_PROMPT",
    "LLMScorer",
    "build_scorer_prompt",
    "parse_scorer_response",
    "score_response_with_llm",
]


_log = logging.getLogger(__name__)


PEER_REVIEW_DIMS: tuple[str, ...] = ("factual", "logical", "relevance")
"""The 3 dimensions a peer-review LLM evaluator is allowed to grade.

Spec source: `architecture/components/P3_reputation.md` §Channel
decomposition. Honesty + adoption are sourced from separate channels
(self-eval gap, adoption ledger) so the peer-review path doesn't
double-write and confound the aggregator's source weighting."""


SCORER_SYSTEM_PROMPT = """\
You are a strict, calibrated peer reviewer in a decentralised AI agent \
network. You will be given a question and an answer, and you must rate \
the answer along THREE dimensions, each from 0.0 to 1.0. These are the \
three dimensions a peer review can legitimately judge from a single \
(question, answer) pair — honesty (self/peer eval gap) and adoption \
(downstream citation) come from separate measurement channels and are \
NOT your responsibility here.

- factual: Is the answer factually correct? Does it match ground truth \
  on verifiable claims? Score low if it contains demonstrable falsehoods.
- logical: Is the reasoning internally consistent and free of \
  contradictions? Score low for non-sequitur, circular logic, or \
  contradictory statements.
- relevance: Does the answer actually solve the caller's problem? \
  Score low if the answer dodges the question, answers a different \
  question, or is tangential.

Respond with ONLY a JSON object:
{"factual": x, "logical": x, "relevance": x}

Be strict. Do not give 1.0 unless the answer is genuinely excellent on \
that dimension. An empty / off-topic / hallucinated answer should score \
near 0.0 on the affected dimensions. Pure-echo or trivially-reformatted \
answers should score near 0.5 on relevance.\
"""


def build_scorer_prompt(*, question: str, answer: str) -> str:
    """The user-side prompt fed to the scorer LLM.

    Format keeps the LLM's input small + structured: explicit `Q:` /
    `A:` labels so the model knows which is which even after long
    context windows. Trims to 4 000 chars per side as a soft guard
    against runaway prompts.
    """
    q = question.strip()
    a = answer.strip()
    if len(q) > 4000:
        q = q[:3997] + "..."
    if len(a) > 4000:
        a = a[:3997] + "..."
    return f"Q: {q}\n\nA: {a}\n\nRespond with the JSON object only."


_JSON_BLOCK_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def parse_scorer_response(
    raw: str, *, dimensions: tuple[str, ...] = PEER_REVIEW_DIMS
) -> dict[str, float]:
    """Extract scores from the LLM's raw text.

    Tolerates:
    - markdown fences (` ```json `)
    - text preamble / postamble
    - missing dimensions (defaults to 0.5)
    - out-of-range floats (clamped to [0, 1])
    - extra dimensions in the response (silently dropped — the LLM
      sometimes adds H/A even when not asked, which we ignore)

    `dimensions` defaults to `PEER_REVIEW_DIMS` (F/L/R only) per spec.
    Pass `REPUTATION_DIMS` to opt into the legacy 5D prompt for
    ablation studies, but expect the aggregator to receive
    spec-inconsistent signal on H/A.

    Raises `ValueError` only if no JSON-shaped block exists anywhere in
    the response — callers should fall back to the heuristic.
    """
    text = raw.strip()
    # Strip common markdown fence.
    if text.startswith("```"):
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text[3:]
        if text.startswith("json"):
            text = text[4:]
    # Find the first plausible JSON object.
    m = _JSON_BLOCK_RE.search(text)
    if not m:
        raise ValueError(f"no JSON object found in scorer response: {raw[:120]!r}")
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(f"scorer response not valid JSON: {exc}") from exc

    out: dict[str, float] = {}
    for dim in dimensions:
        v = obj.get(dim, 0.5)
        try:
            f = float(v)
        except (TypeError, ValueError):
            f = 0.5
        out[dim] = max(0.0, min(1.0, f))
    return out


__ablation_5d_dims = REPUTATION_DIMS  # keep available for opt-in ablation tests
_ = __ablation_5d_dims, Any  # silence unused-import warnings


async def score_response_with_llm(
    *,
    request_text: str,
    response_text: str,
    scorer: SubstrateBackend,
) -> dict[str, float]:
    """One-shot 5D LLM scoring. Returns 5 floats in [0,1].

    Raises `ValueError` if the scorer's response can't be parsed.
    Callers (typically `peer_review_tick` via `LLMScorer.score`) wrap
    this in their own try/except + fallback path — keeping the
    success/failure distinction visible at the call site lets the
    review's `substrate` field truthfully label which path actually
    produced the score.
    """
    req = SubstrateRequest(
        system_prompt=SCORER_SYSTEM_PROMPT,
        user_prompt=build_scorer_prompt(question=request_text, answer=response_text),
        metadata={"role": "5d-scorer"},
    )
    resp = await scorer.infer(req)
    return parse_scorer_response(resp.text)


@dataclass
class LLMScorer:
    """Stateful adapter so callers can pass `scorer` once and forget.

    Wraps a `SubstrateBackend` plus a label that ends up on the review
    record's `substrate` field (so the aggregator can downweight
    "alice-self-scored" reviews differently from "claude-judged" ones).
    """

    backend: SubstrateBackend
    label: str = "llm-5d-scorer"

    async def score(self, *, request_text: str, response_text: str) -> dict[str, float]:
        """Score a (question, answer) pair with the configured backend."""
        return await score_response_with_llm(
            request_text=request_text,
            response_text=response_text,
            scorer=self.backend,
        )

    @property
    def substrate_tag(self) -> str:
        """The string written into the review record's `substrate` field.

        Format: `<label>:<backend.name>` so downstream aggregators can
        bucket reviews by scorer flavor without parsing.
        """
        return f"{self.label}:{self.backend.name}"


# Kept for opt-in ablation tests that need the full 5D contract.
# See `test_parse_opt_in_5dim_for_ablation` in tests/unit/test_llm_scorer.py.
_ABLATION_5D_DIMS: tuple[str, ...] = REPUTATION_DIMS
_KEEP_ANY: Any = None  # silence unused-import for `Any` in older type-checkers
del _KEEP_ANY
