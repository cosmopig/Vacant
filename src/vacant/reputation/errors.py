"""Error hierarchy for `vacant.reputation`."""

from __future__ import annotations

from vacant.core.errors import CoreError


class ReputationError(CoreError):
    """Base class for `vacant.reputation` errors."""


class IneligibleReviewerError(ReputationError):
    """A reviewer's runtime state forbids new reviews (P1 §4.1)."""


class InvalidDimensionError(ReputationError):
    """An unknown reputation dimension was referenced."""


class InvalidSignalError(ReputationError):
    """A signal is malformed (e.g. score outside [0,1])."""


class ReviewRateLimitError(ReputationError):
    """A target's per-window review rate limit was exceeded
    (Padv-P3 finding D010 §1)."""


class ChainTamperError(ReputationError):
    """A reviewer's logbook failed `verify_chain` during `record_review`
    audit (D015 §D). Posterior update is rolled back and the review is
    rejected — the auditable history of reputation events is the load-
    bearing claim of the thesis (CLAUDE.md §load-bearing decisions)."""


class MissingAuditKeyError(ReputationError):
    """The aggregator was constructed in audit mode but the reviewer's
    signing key / logbook is not registered (D015 §D)."""
