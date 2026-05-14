"""P3 -- reputation: 5-dim Beta posterior, UCB, STYLO discount, cold start."""

from vacant.reputation.adoption import (
    AdoptionEvent,
    AdoptionLedger,
    AdoptionLedgerError,
)
from vacant.reputation.aggregator import (
    Aggregator,
    ReviewRecord,
    VacantContext,
)
from vacant.reputation.cold_start import (
    BirthPath,
    ColdStartCaveats,
    InsufficientDataLabel,
    birth_path_bonus,
    initial_prior,
    is_eligible_for_low_stakes_probe,
    niche_bonus,
    should_idle_review_target,
    show_label,
)
from vacant.reputation.discount import (
    CumulativeDriftTracker,
    apply_discount,
    apply_discount_5d,
    compute_discount,
    dimension_imbalance_alert,
)
from vacant.reputation.errors import (
    ChainTamperError,
    IneligibleReviewerError,
    InvalidDimensionError,
    InvalidSignalError,
    MissingAuditKeyError,
    ReputationError,
    ReviewRateLimitError,
)
from vacant.reputation.portability import compute_portability
from vacant.reputation.posterior import (
    Beta,
    Beta5D,
    Dim,
    decay_factor,
    five_d_with_priors,
)
from vacant.reputation.same_detect import (
    SameDetectSignal,
    cosine_similarity,
    cross_correlation,
    discount_from_signals,
    same_controller,
    same_stylo,
    same_substrate,
)
from vacant.reputation.ucb import (
    call_score,
    cold_start_floor,
    exploration_boost,
    lineage_prior_alpha,
    ucb_score,
    ucb_with_lineage_prior,
)

__all__ = [
    "AdoptionEvent",
    "AdoptionLedger",
    "AdoptionLedgerError",
    "Aggregator",
    "Beta",
    "Beta5D",
    "BirthPath",
    "ChainTamperError",
    "ColdStartCaveats",
    "CumulativeDriftTracker",
    "Dim",
    "IneligibleReviewerError",
    "InsufficientDataLabel",
    "InvalidDimensionError",
    "InvalidSignalError",
    "MissingAuditKeyError",
    "ReputationError",
    "ReviewRateLimitError",
    "ReviewRecord",
    "SameDetectSignal",
    "VacantContext",
    "apply_discount",
    "apply_discount_5d",
    "birth_path_bonus",
    "call_score",
    "cold_start_floor",
    "compute_discount",
    "compute_portability",
    "cosine_similarity",
    "cross_correlation",
    "decay_factor",
    "dimension_imbalance_alert",
    "discount_from_signals",
    "exploration_boost",
    "five_d_with_priors",
    "initial_prior",
    "is_eligible_for_low_stakes_probe",
    "lineage_prior_alpha",
    "niche_bonus",
    "same_controller",
    "same_stylo",
    "same_substrate",
    "should_idle_review_target",
    "show_label",
    "ucb_score",
    "ucb_with_lineage_prior",
]
