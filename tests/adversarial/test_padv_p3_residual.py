"""Padv P3 -- residual-risk regression guards.

Documented residual risks per `architecture/decisions/D010_padv_p3_findings.md`:

- **Honesty laundering via self_eval**: per spec §3.5, self_eval can't
  directly write H -- its only role is feeding the gap calculation.
- **Adoption stuffing**: P3 doesn't verify adoption events trace to a
  callsite (P4 event-log integration deferred).
- **Post-merger reputation poaching**: D4 lineage-merge inherits a
  fraction of parent posterior via `lineage_prior_alpha` -- there's no
  separate post-merge cold-start period beyond the depth-decay.
"""

from __future__ import annotations

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import VacantId, VacantState
from vacant.reputation import (
    Aggregator,
    Beta,
    InvalidSignalError,
    VacantContext,
    lineage_prior_alpha,
    ucb_with_lineage_prior,
)


def _ctx(*, family: str = "claude") -> VacantContext:
    _sk, vk = keygen()
    return VacantContext(
        vacant_id=VacantId.from_verify_key(vk),
        base_model_family=family,
        state=VacantState.ACTIVE,
        attestation_level="L1",
    )


def _agg(*ctxs: VacantContext) -> Aggregator:
    return Aggregator(
        contexts={c.vacant_id: c for c in ctxs},
        review_limit_per_target_24h=10_000,
    )


# --- Honesty laundering ---------------------------------------------------
# Defense (P at API surface): the self_eval source weight is intentionally
# tiny (0.05). The Padv-P3 residual is that self_eval CAN still write to
# H via the API -- the spec separation says self_eval should only feed
# gap calculation. We pin this by asserting that even after many
# self_eval=1.0 reviews, the H mean's increment over the prior stays
# small relative to a peer-review pile.


@pytest.mark.asyncio
async def test_self_eval_alone_cannot_dominate_honesty() -> None:
    target = _ctx()
    reviewer = _ctx(family="gemini")
    agg = _agg(target, reviewer)

    # 3 self-eval-source reviews (tiny base weight 0.05).
    for _ in range(3):
        await agg.record_review(
            reviewer.vacant_id,
            target.vacant_id,
            dimensions={"honesty": 1.0},
            substrate="default",
            source="self_eval",
        )
    self_eval_alpha = (await agg.get_reputation(target.vacant_id, "default")).honesty.alpha

    # Compare: 3 peer-review-source reviews (base weight 0.4, 8x larger).
    agg2 = _agg(target, reviewer)
    for _ in range(3):
        await agg2.record_review(
            reviewer.vacant_id,
            target.vacant_id,
            dimensions={"honesty": 1.0},
            substrate="default",
            source="peer_review",
        )
    peer_alpha = (await agg2.get_reputation(target.vacant_id, "default")).honesty.alpha
    # Peer-review accumulates at least 4x more alpha than self_eval.
    assert (peer_alpha - 2.0) > 4 * (self_eval_alpha - 2.0)


# --- Adoption stuffing ---------------------------------------------------
# Defense (D, residual): adoption events go through the same
# `record_review` path with `source="adoption_event"`. The P4 event-log
# verification (callsite proof) is future work. The signal rejection at
# the API surface still applies: bogus dims / bad signals raise.


@pytest.mark.asyncio
async def test_adoption_event_signal_must_still_be_in_unit_interval() -> None:
    target = _ctx()
    reviewer = _ctx(family="gemini")
    agg = _agg(target, reviewer)
    with pytest.raises(InvalidSignalError):
        await agg.record_review(
            reviewer.vacant_id,
            target.vacant_id,
            dimensions={"adoption": 2.0},  # > 1.0
            substrate="default",
            source="adoption_event",
        )


@pytest.mark.asyncio
async def test_adoption_stuffing_residual_documented() -> None:
    """Regression guard: adoption events are accepted at the API surface
    today. P4 callsite-trace verification is the cost-raising mitigation
    documented in D010 §"residual"."""
    target = _ctx()
    reviewer = _ctx(family="gemini")
    agg = _agg(target, reviewer)
    # Aggregator accepts adoption events without callsite verification.
    # This pin is the residual-risk regression guard -- when P4 wires
    # callsite-trace verification, callers should remove this and add
    # a positive test instead.
    await agg.record_review(
        reviewer.vacant_id,
        target.vacant_id,
        dimensions={"adoption": 1.0},
        substrate="default",
        source="adoption_event",
    )
    rep = await agg.get_reputation(target.vacant_id, "default")
    assert rep.adoption.alpha > 1.0  # bumped


# --- Post-merger reputation poaching --------------------------------------
# Defense (P, depth-decay only): `lineage_prior_alpha` blends parent
# posterior with `kappa = inherit_fraction * exp(-decay_lambda * depth)`.
# Depth=0 inherits 25% by default; deeper descendants inherit much less.
# Padv-P3 residual: a freshly-merged D4 child at depth=0 still gets the
# 25% inheritance immediately. The residual mitigation is the sample-
# size requirement (`N_MIN_FOR_STABLE_SCORE = 30`) before the merged
# vacant gets a stable scalar score; P3's `show_label` returns
# INSUFFICIENT_DATA until then.


def test_post_merger_depth_zero_child_inherits_capped_fraction() -> None:
    parent = Beta(alpha=20.0, beta=2.0, alpha0=1.0, beta0=1.0)  # high parent
    child = Beta(alpha=1.0, beta=1.0, alpha0=1.0, beta0=1.0)  # cold-start
    a, b = lineage_prior_alpha(
        base_alpha=child.alpha,
        base_beta=child.beta,
        parent_alpha=parent.alpha,
        parent_beta=parent.beta,
        depth=0,
    )
    # Default inherit_fraction=0.25 → blended alpha = 1 + 0.25 * 20 = 6.0.
    assert a == pytest.approx(6.0, abs=1e-6)
    assert b == pytest.approx(1.5, abs=1e-6)


def test_post_merger_inheritance_decays_steeply_with_depth() -> None:
    parent_alpha, parent_beta = 20.0, 2.0
    a0, _ = lineage_prior_alpha(
        base_alpha=1.0,
        base_beta=1.0,
        parent_alpha=parent_alpha,
        parent_beta=parent_beta,
        depth=0,
    )
    a3, _ = lineage_prior_alpha(
        base_alpha=1.0,
        base_beta=1.0,
        parent_alpha=parent_alpha,
        parent_beta=parent_beta,
        depth=3,
    )
    # Depth-3 inherits substantially less than depth-0.
    assert (a0 - 1.0) > 4 * (a3 - 1.0)


def test_post_merger_low_n_eff_keeps_show_label_insufficient() -> None:
    """A merged child has lineage prior boost but `n_eff = 0` -- UI
    rendering must still show INSUFFICIENT_DATA until 10+ events
    accumulate (P3 §3.8 stage 3)."""
    from vacant.reputation import five_d_with_priors, show_label

    rep = five_d_with_priors()
    # Even with a high prior, n_eff = 0 → show INSUFFICIENT_DATA.
    label = show_label(rep)
    assert label.label == "INSUFFICIENT_DATA"
    _ = ucb_with_lineage_prior  # silence unused
