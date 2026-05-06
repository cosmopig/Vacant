"""Graduation -- flip a closed child's `registry_visibility` from
NONE to PUBLIC (P5 §3.7, dispatch §4).

Three preconditions, all must hold:

1. **Parent consent** -- a `GraduationRequest` signed by both parent and
   child (mirrors `ChildManifest`'s dual-signature design).
2. **Rate limit** -- per-parent 24h sliding window, defaults to
   `GRADUATION_RATE_LIMIT_PER_PARENT_24H` (D012 §A).
3. **Collusion check** -- max signal strength on (parent, child) below
   `GRADUATION_COLLUSION_THRESHOLD` (D012 §B). Uses the
   `CollusionDetector` injected at construction time; a default
   `CompositeStubDetector` returning zeroes is used when P3 is not
   wired.

Identity preservation is load-bearing (CLAUDE.md §Closed children +
graduation): the same keypair, the same logbook, just a visibility
flag flip. The graduated child gets a new dual-signed manifest with
`closed_by_default=False` and fresh `GRADUATED` log entries appended
to both logbooks; nothing else changes.

A successful `graduate()` call returns a `GraduationOutcome` carrying
the new manifest plus the `CapabilityCard` ready for `publish_halo`
in P4. The caller is responsible for the actual halo publish (P5 does
not import P4 directly to keep the layering clean).
"""

from __future__ import annotations

import json
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from vacant.composite.collusion import (
    CollusionDetector,
    CollusionSignals,
    default_detector,
    max_signal_strength,
)
from vacant.composite.errors import (
    GraduationCollusionError,
    GraduationConsentError,
    GraduationRateLimitError,
)
from vacant.composite.manifest import ChildManifest
from vacant.composite.orchestrator import CompositeRuntime
from vacant.core.constants import (
    GRADUATION_COLLUSION_THRESHOLD,
    GRADUATION_RATE_LIMIT_PER_PARENT_24H,
)
from vacant.core.crypto import SigningKey, sign, verify
from vacant.core.types import (
    BehaviorBundle,
    CapabilityCard,
    ResidentForm,
    SubstrateSpec,
    VacantId,
)

__all__ = [
    "GRADUATED_KIND",
    "GraduationOutcome",
    "GraduationRequest",
    "GraduationService",
    "make_graduation_request",
]


GRADUATED_KIND = "COMPOSITE_GRADUATED"
"""Logbook entry kind written to both parent and child on success."""


_GRADUATION_INTENT = "vacant:graduation:v1"


def _signing_payload(parent_id: VacantId, child_id: VacantId, capability_text: str) -> bytes:
    """Canonical payload over which both parent and child sign a graduation
    request. Includes the capability text the child intends to publish so
    the parent's consent is bound to a specific capability claim, not a
    blank cheque."""
    obj: dict[str, Any] = {
        "intent": _GRADUATION_INTENT,
        "parent_id": parent_id.hex(),
        "child_id": child_id.hex(),
        "capability_text": capability_text,
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


@dataclass(frozen=True)
class GraduationRequest:
    """Dual-signed authorisation for graduation.

    `parent_signature` and `child_signature` are detached Ed25519
    signatures over `_signing_payload(parent_id, child_id,
    capability_text)`. Both must verify under their respective ids."""

    parent_id: VacantId
    child_id: VacantId
    capability_text: str
    parent_signature: bytes
    child_signature: bytes

    def signing_payload(self) -> bytes:
        return _signing_payload(self.parent_id, self.child_id, self.capability_text)

    def verify(self) -> bool:
        if not self.parent_signature or not self.child_signature:
            return False
        payload = self.signing_payload()
        if not verify(self.parent_id.verify_key(), payload, self.parent_signature):
            return False
        if not verify(self.child_id.verify_key(), payload, self.child_signature):
            return False
        return True


def make_graduation_request(
    *,
    parent_id: VacantId,
    parent_signing_key: SigningKey,
    child_id: VacantId,
    child_signing_key: SigningKey,
    capability_text: str,
) -> GraduationRequest:
    """Builder helper: produce a fully signed `GraduationRequest`."""
    payload = _signing_payload(parent_id, child_id, capability_text)
    return GraduationRequest(
        parent_id=parent_id,
        child_id=child_id,
        capability_text=capability_text,
        parent_signature=sign(parent_signing_key, payload),
        child_signature=sign(child_signing_key, payload),
    )


@dataclass(frozen=True)
class GraduationOutcome:
    """Result of a successful `graduate()`.

    `new_manifest` replaces the child's old (closed) manifest in the
    composite runtime. `child_card` is the freshly-signed capability
    card for `publish_halo` (P4); the caller actually publishes."""

    new_manifest: ChildManifest
    child_card: CapabilityCard
    collusion_signals: CollusionSignals


class GraduationService:
    """Stateful graduation gate held by the composite runtime.

    Owns the per-parent rate-limit sliding-window deque + the injected
    collusion detector. The same instance is reused across graduation
    calls so the window persists.

    The service does NOT publish to P4. It returns the
    `CapabilityCard` and the new dual-signed manifest; the caller wires
    up `publish_halo` (P4 §publish_halo) so P5 is not coupled to the
    registry implementation.
    """

    def __init__(
        self,
        *,
        rate_limit_per_24h: int = GRADUATION_RATE_LIMIT_PER_PARENT_24H,
        collusion_threshold: float = GRADUATION_COLLUSION_THRESHOLD,
        detector: CollusionDetector | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if rate_limit_per_24h < 1:
            raise ValueError(f"rate_limit_per_24h must be >= 1; got {rate_limit_per_24h}")
        if not (0.0 <= collusion_threshold <= 1.0):
            raise ValueError(f"collusion_threshold must be in [0, 1]; got {collusion_threshold}")
        self._rate_limit = rate_limit_per_24h
        self._collusion_threshold = collusion_threshold
        self._detector: CollusionDetector = detector or default_detector()
        self._clock = clock
        self._window_per_parent: dict[VacantId, deque[float]] = {}

    # --- main entry point --------------------------------------------------

    async def graduate(
        self,
        *,
        runtime: CompositeRuntime,
        request: GraduationRequest,
        substrate_spec: SubstrateSpec | None = None,
        ts: float | None = None,
    ) -> GraduationOutcome:
        """Run all three checks and, on success, flip the child's
        manifest in `runtime` and return the new outcome.

        Raises `GraduationConsentError`, `GraduationRateLimitError`, or
        `GraduationCollusionError` on the first failing check. The
        runtime is not mutated until all checks pass."""
        record = runtime.get_child(request.child_id)
        old_manifest = record.manifest
        if old_manifest.parent_id != request.parent_id:
            raise GraduationConsentError(
                f"graduation parent_id {request.parent_id.short()} does not match "
                f"child's manifest parent {old_manifest.parent_id.short()}"
            )
        if not request.verify():
            raise GraduationConsentError("graduation request signatures did not verify")

        when = ts if ts is not None else self._clock()
        self._enforce_rate_limit(request.parent_id, when)

        signals = self._detector.signals_for(request.parent_id, request.child_id)
        if max_signal_strength(signals) >= self._collusion_threshold:
            raise GraduationCollusionError(
                f"collusion signals too high for graduation: "
                f"controller={signals.same_controller:.2f}, "
                f"substrate={signals.same_substrate:.2f}, "
                f"stylo={signals.same_stylo:.2f} "
                f"(threshold {self._collusion_threshold})"
            )

        # All checks passed: rebuild manifest with closed_by_default=False,
        # mint capability card, append GRADUATED to both logbooks.
        new_manifest = self._rebuild_manifest(old_manifest)
        new_manifest = new_manifest.signed_by_parent(_parent_signing_key(runtime))
        new_manifest = new_manifest.signed_by_child(record.child_signing_key)

        spec = substrate_spec or record.child_form.substrate_spec
        child_card = CapabilityCard(
            vacant_id=request.child_id,
            capability_text=request.capability_text,
            substrate_spec=spec,
        ).signed(record.child_signing_key)

        runtime.mark_graduated(request.child_id, new_manifest)
        self._record_graduation(request.parent_id, when)
        _append_graduated_entries(
            runtime=runtime,
            request=request,
            child_form=record.child_form,
            child_signing_key=record.child_signing_key,
        )

        return GraduationOutcome(
            new_manifest=new_manifest,
            child_card=child_card,
            collusion_signals=signals,
        )

    # --- internals ---------------------------------------------------------

    def _enforce_rate_limit(self, parent_id: VacantId, when: float) -> None:
        window = self._window_per_parent.setdefault(parent_id, deque())
        cutoff = when - 86_400.0
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= self._rate_limit:
            raise GraduationRateLimitError(
                f"parent {parent_id.short()} hit graduation rate limit "
                f"({len(window)} in last 24h, limit {self._rate_limit})"
            )

    def _record_graduation(self, parent_id: VacantId, when: float) -> None:
        # Called only after all gates passed.
        self._window_per_parent.setdefault(parent_id, deque()).append(when)

    @staticmethod
    def _rebuild_manifest(old: ChildManifest) -> ChildManifest:
        """Strip old signatures + flip closed_by_default."""
        return ChildManifest(
            parent_id=old.parent_id,
            child_id=old.child_id,
            birth_path=old.birth_path,
            closed_by_default=False,
            tool_whitelist_inherited=list(old.tool_whitelist_inherited),
            tool_whitelist_added=list(old.tool_whitelist_added),
            tool_whitelist_removed=list(old.tool_whitelist_removed),
        )


# --- helpers ---------------------------------------------------------------


def _parent_signing_key(runtime: CompositeRuntime) -> SigningKey:
    """Read the parent signing key from the runtime's protected slot.

    `CompositeRuntime` holds the parent key privately so business logic
    elsewhere doesn't accidentally surface it. The graduation flow needs
    it to re-sign the manifest, so we reach in deliberately here. Kept
    as an internal helper to make the cross-module access explicit
    rather than scattering name-mangled references."""
    return runtime._parent_signing_key


def _append_graduated_entries(
    *,
    runtime: CompositeRuntime,
    request: GraduationRequest,
    child_form: ResidentForm,
    child_signing_key: SigningKey,
) -> None:
    """Write the GRADUATED event to both parent and child logbooks."""
    payload: dict[str, Any] = {
        "child_id": request.child_id.hex(),
        "parent_id": request.parent_id.hex(),
        "capability_text": request.capability_text,
    }
    runtime.parent_form.logbook.append(
        GRADUATED_KIND,
        payload,
        _parent_signing_key(runtime),
    )
    child_form.logbook.append(
        GRADUATED_KIND,
        payload,
        child_signing_key,
    )


def _silence_unused() -> None:
    _ = BehaviorBundle  # type re-exported so callers can build SubstrateSpec/BehaviorBundle locally
