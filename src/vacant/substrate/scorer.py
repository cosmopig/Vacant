"""LLM-driven 5D scorer (Pfix9 Phase 2).

The existing `runtime.peer_review.score_response_heuristic` only looks at
text length / refusal markers / echo detection — it does NOT check
whether a response actually answered the prompt. technical.html
§Reputation row 2 / row 3 / row 5 explicitly says "Peer Review" /
"Ground Truth Check" / "Adoption Signal" should be **semantic** judgements.

This module gives `peer_review_tick` (and any future scorer caller) a
real LLM-backed scorer that reads `(request, response)` and emits 5D
scores in [0, 1]. It's a thin function over any `SubstrateBackend` —
operators choose whether the scorer LLM is the same model as the
responder or a different one (cross-model diversity is the load-bearing
property in technical.html §Reputation row 2 "Cross-model diversity
prioritized").

Anti-Goodhart:
- The scorer prompt asks for each dimension separately so a single LLM
  bias affects only one channel.
- Parsing tolerates extra commentary; we extract the JSON block.
- Out-of-range scores are clamped; missing dims default to 0.5.
- Parse failures fall back to the heuristic scorer so the loop keeps
  running — operators see the failure rate via stats but the network
  doesn't stall.

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
    "SCORER_SYSTEM_PROMPT",
    "LLMScorer",
    "build_scorer_prompt",
    "parse_scorer_response",
    "score_response_with_llm",
]


_log = logging.getLogger(__name__)


SCORER_SYSTEM_PROMPT = """\
You are a strict, calibrated evaluator. You will be given a question and \
an answer, and you must rate the answer along five dimensions, each from \
0.0 to 1.0:

- factual: Is the answer factually correct? Does it avoid false claims?
- logical: Is the reasoning sound and internally consistent?
- relevance: Does the answer address the actual question?
- honesty: Does the answer admit uncertainty when appropriate?
- adoption: Would a downstream agent find this answer useful to build on?

Respond with ONLY a JSON object of the form:
{"factual": x, "logical": x, "relevance": x, "honesty": x, "adoption": x}

Be strict. Do not give 1.0 unless the answer is genuinely excellent on \
that dimension. An empty / off-topic / hallucinated answer should score \
near 0.0 on the affected dimensions.\
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


def parse_scorer_response(raw: str) -> dict[str, float]:
    """Extract 5 dim scores from the LLM's raw text.

    Tolerates:
    - markdown fences (` ```json `)
    - text preamble / postamble
    - missing dimensions (defaults to 0.5)
    - out-of-range floats (clamped to [0, 1])

    Returns a dict containing exactly `REPUTATION_DIMS`. Raises
    `ValueError` only if no JSON-shaped block exists anywhere in the
    response — callers should fall back to the heuristic in that case.
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
    for dim in REPUTATION_DIMS:
        v = obj.get(dim, 0.5)
        try:
            f = float(v)
        except (TypeError, ValueError):
            f = 0.5
        out[dim] = max(0.0, min(1.0, f))
    return out


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


_ = Any  # quieten the unused-import warning when no type hints land here
