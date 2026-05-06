"""P5 composite error hierarchy."""

from __future__ import annotations

from vacant.core.errors import CoreError


class CompositeError(CoreError):
    """Base class for `vacant.composite` errors."""


class ManifestError(CompositeError):
    """A `ChildManifest` is malformed or its dual signature is invalid."""


class TreeOnlyViolationError(CompositeError):
    """A closed child attempted an outbound call to a non-tree target
    (P5 §2 D2 / CLAUDE.md §Closed children)."""


class GraduationError(CompositeError):
    """Graduation precondition failed: missing parent consent, rate limit
    exceeded, or collusion signal too high."""


class GraduationRateLimitError(GraduationError):
    """Graduation rejected because the per-parent 24h rate limit was hit
    (D012 §A)."""


class GraduationConsentError(GraduationError):
    """Graduation rejected because the parent's consent was missing,
    malformed, or did not verify."""


class GraduationCollusionError(GraduationError):
    """Graduation rejected because a `same_*` signal between parent
    and child exceeded `GRADUATION_COLLUSION_THRESHOLD` (D012 §B)."""
