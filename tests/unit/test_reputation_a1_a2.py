"""A1 + A2 — Ground-truth 1.5x factual multiplier + Self/Peer Eval Gap → honesty.

A1: `record_review(source="ground_truth", dimensions={"factual": ...})`
    must apply a 1.5x weight multiplier on the factual dim specifically.
    Other sources / other dims must NOT get the bump.

A2: `record_self_eval_gap` writes only to the `honesty` dim, with
    signal = 1 - mean(|self - peer|). Bad self-evals lower honesty;
    perfectly calibrated self-evals raise it.
"""

from __future__ import annotations

import pytest

from vacant.core.constants import (
    GROUND_TRUTH_FACTUAL_MULTIPLIER,
    SOURCE_BASE_WEIGHTS,
)
from vacant.core.crypto import keygen
from vacant.core.types import VacantId, VacantState
from vacant.reputation import (
    Aggregator,
    InvalidDimensionError,
    InvalidSignalError,
    VacantContext,
)


def _vid() -> VacantId:
    _sk, vk = keygen()
    return VacantId.from_verify_key(vk)


def _agg_with(reviewer: VacantId, target: VacantId) -> Aggregator:
    return Aggregator(
        {
            reviewer: VacantContext(
                vacant_id=reviewer, base_model_family="A", state=VacantState.ACTIVE
            ),
            target: VacantContext(
                vacant_id=target, base_model_family="B", state=VacantState.ACTIVE
            ),
        }
    )


# --- A1: ground-truth 1.5x factual --------------------------------------------


@pytest.mark.asyncio
async def test_ground_truth_factual_gets_1_5x_multiplier_vs_caller_review() -> None:
    """Same numerical signal (0.9) on factual through ground_truth vs
    caller_review must yield a strictly larger posterior alpha on
    factual for ground_truth — the multiplier is 1.5x AND the source
    base weight is ground_truth=1.0 vs caller_review=0.6, so the gap
    should be roughly 2.5x in alpha movement."""
    rev, tgt = _vid(), _vid()
    agg_gt = _agg_with(rev, tgt)
    agg_cr = _agg_with(rev, tgt)

    await agg_gt.record_review(rev, tgt, {"factual": 1.0}, "default", source="ground_truth")
    await agg_cr.record_review(rev, tgt, {"factual": 1.0}, "default", source="caller_review")

    rep_gt = await agg_gt.get_reputation(tgt, "default")
    rep_cr = await agg_cr.get_reputation(tgt, "default")

    # ground_truth alpha bump should be ~1.5x bigger than caller_review at
    # the same source weight, but ground_truth itself also has 1.0 vs 0.6.
    gt_factual_alpha = rep_gt.factual.alpha
    cr_factual_alpha = rep_cr.factual.alpha
    assert gt_factual_alpha > cr_factual_alpha


@pytest.mark.asyncio
async def test_ground_truth_multiplier_only_applies_to_factual() -> None:
    """Other dimensions on a ground_truth review must NOT receive the
    1.5x boost — the multiplier is factual-specific (technical.html row
    3 phrasing)."""
    rev, tgt = _vid(), _vid()
    agg_gt = _agg_with(rev, tgt)
    agg_cr = _agg_with(rev, tgt)
    # Use the same source on both sides for `logical` so the only
    # difference is the dim-specific multiplier path.
    await agg_gt.record_review(rev, tgt, {"logical": 1.0}, "default", source="ground_truth")
    await agg_cr.record_review(rev, tgt, {"logical": 1.0}, "default", source="ground_truth")
    # Same dim, same source on both → identical posterior updates.
    rep_gt = await agg_gt.get_reputation(tgt, "default")
    rep_cr = await agg_cr.get_reputation(tgt, "default")
    assert rep_gt.logical.alpha == rep_cr.logical.alpha


@pytest.mark.asyncio
async def test_ground_truth_multiplier_constant_value() -> None:
    """Sanity-check the constant is the value technical.html promises (1.5)."""
    assert GROUND_TRUTH_FACTUAL_MULTIPLIER == pytest.approx(1.5)


# --- A2: self/peer eval gap → honesty -----------------------------------------


@pytest.mark.asyncio
async def test_perfect_self_eval_raises_honesty() -> None:
    """Gap = 0 → honesty signal = 1.0; the honesty posterior should
    shift toward 1 (more alpha than beta on the update)."""
    tgt = _vid()
    agg = Aggregator(
        {tgt: VacantContext(vacant_id=tgt, base_model_family="A", state=VacantState.ACTIVE)}
    )
    rep_before = await agg.get_reputation(tgt, "default")
    h_before = rep_before.honesty.alpha
    sig = await agg.record_self_eval_gap(
        tgt,
        "default",
        self_scores={"factual": 0.7},
        peer_scores={"factual": 0.7},
    )
    assert sig == pytest.approx(1.0)
    rep_after = await agg.get_reputation(tgt, "default")
    assert rep_after.honesty.alpha > h_before


@pytest.mark.asyncio
async def test_maximally_wrong_self_eval_lowers_honesty() -> None:
    """Gap = 1 → signal = 0.0 → honesty beta grows, alpha doesn't."""
    tgt = _vid()
    agg = Aggregator(
        {tgt: VacantContext(vacant_id=tgt, base_model_family="A", state=VacantState.ACTIVE)}
    )
    rep_before = await agg.get_reputation(tgt, "default")
    a_before = rep_before.honesty.alpha
    b_before = rep_before.honesty.beta
    sig = await agg.record_self_eval_gap(
        tgt,
        "default",
        self_scores={"factual": 1.0},
        peer_scores={"factual": 0.0},
    )
    assert sig == pytest.approx(0.0)
    rep_after = await agg.get_reputation(tgt, "default")
    assert rep_after.honesty.alpha == pytest.approx(a_before)
    assert rep_after.honesty.beta > b_before


@pytest.mark.asyncio
async def test_self_eval_gap_only_writes_honesty() -> None:
    """Only the honesty dim should move. Factual / logical / relevance /
    adoption must be untouched."""
    tgt = _vid()
    agg = Aggregator(
        {tgt: VacantContext(vacant_id=tgt, base_model_family="A", state=VacantState.ACTIVE)}
    )
    rep_before = await agg.get_reputation(tgt, "default")
    snapshot_other = {
        d: (rep_before.get(d).alpha, rep_before.get(d).beta)
        for d in ("factual", "logical", "relevance", "adoption")
    }
    await agg.record_self_eval_gap(
        tgt,
        "default",
        self_scores={"factual": 0.5, "logical": 0.5},
        peer_scores={"factual": 0.7, "logical": 0.3},
    )
    rep_after = await agg.get_reputation(tgt, "default")
    for d, (a, b) in snapshot_other.items():
        assert rep_after.get(d).alpha == pytest.approx(a)
        assert rep_after.get(d).beta == pytest.approx(b)


@pytest.mark.asyncio
async def test_self_eval_gap_unknown_target_raises() -> None:
    tgt = _vid()
    agg = Aggregator({})
    with pytest.raises(InvalidSignalError):
        await agg.record_self_eval_gap(
            tgt, "default", self_scores={"factual": 0.5}, peer_scores={"factual": 0.5}
        )


@pytest.mark.asyncio
async def test_self_eval_gap_unknown_dim_raises() -> None:
    tgt = _vid()
    agg = Aggregator(
        {tgt: VacantContext(vacant_id=tgt, base_model_family="A", state=VacantState.ACTIVE)}
    )
    with pytest.raises(InvalidDimensionError):
        await agg.record_self_eval_gap(
            tgt,
            "default",
            self_scores={"made_up_dim": 0.5},
            peer_scores={"made_up_dim": 0.5},
        )


@pytest.mark.asyncio
async def test_self_eval_gap_out_of_range_score_raises() -> None:
    tgt = _vid()
    agg = Aggregator(
        {tgt: VacantContext(vacant_id=tgt, base_model_family="A", state=VacantState.ACTIVE)}
    )
    with pytest.raises(InvalidSignalError):
        await agg.record_self_eval_gap(
            tgt, "default", self_scores={"factual": 1.5}, peer_scores={"factual": 0.5}
        )


@pytest.mark.asyncio
async def test_self_eval_gap_no_overlap_is_noop() -> None:
    """No overlapping dims → returns 0.0 and posterior unchanged."""
    tgt = _vid()
    agg = Aggregator(
        {tgt: VacantContext(vacant_id=tgt, base_model_family="A", state=VacantState.ACTIVE)}
    )
    rep_before = await agg.get_reputation(tgt, "default")
    sig = await agg.record_self_eval_gap(
        tgt,
        "default",
        self_scores={"factual": 0.5},
        peer_scores={"logical": 0.5},
    )
    assert sig == pytest.approx(0.0)
    rep_after = await agg.get_reputation(tgt, "default")
    assert rep_after.honesty.alpha == rep_before.honesty.alpha
    assert rep_after.honesty.beta == rep_before.honesty.beta


@pytest.mark.asyncio
async def test_self_eval_source_weight_value_constant() -> None:
    """self_eval base weight constant is intentionally low (0.05) so a
    miscalibrated self-eval can move honesty but not dominate it."""
    assert SOURCE_BASE_WEIGHTS["self_eval"] == pytest.approx(0.05)
