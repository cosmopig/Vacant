"""`ChildManifest` -- the dual-signed link between a composite parent
and one of its children (P5 §3.1, dispatch §1).

The manifest is the *only* in-tree authorisation a child needs:

- the parent vouches that this child is its child (signature_parent),
- the child vouches that it accepts this parent (signature_child).

Both signatures cover the canonical-json of the same payload (D012 §C).
A manifest with one signature missing or with either signature invalid
is rejected by `verify_or_raise`.

The manifest is held by the composite parent's runtime (`CompositeRuntime`);
it is *not* serialised to the public registry, so externally a composite
vacant exposes only its own halo (P5 §3.3 black-box principle).

Three-axis ontology (THEORY_V5 §5.1):

| Axis                    | Values                                       |
|-------------------------|----------------------------------------------|
| `registry_visibility`   | NONE / UNLISTED / PUBLIC (in `registry.visibility`)|
| `endpoint_reachability` | PARENT_ONLY / PARENT_BRIDGED / PUBLIC_A2A    |
| `outbound_policy`       | NO_EXTERNAL / PARENT_PERMITTED / UNRESTRICTED|

`closed_by_default` predates the 3-axis split and remains as a coarse
visibility shorthand. The two new enums let callers express the three
canonical configurations cleanly:
- Self-grown: visibility=NONE, reachability=PARENT_ONLY, outbound=NO_EXTERNAL
- Broker:     visibility=UNLISTED, reachability=PARENT_BRIDGED, outbound=PARENT_PERMITTED
- Public resident (graduated): visibility=PUBLIC, reachability=PUBLIC_A2A,
                               outbound=any-of-the-three (least-privilege per V5 §5.2)
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from vacant.composite.errors import ManifestError
from vacant.core.crypto import SigningKey, sign, verify
from vacant.core.types import VacantId

__all__ = [
    "BIRTH_PATHS",
    "ChildManifest",
    "OutboundPolicy",
    "Reachability",
    "ensure_birth_path",
]


BIRTH_PATHS = ("D1", "D2", "D3", "D4", "D5")


class Reachability(StrEnum):
    """The 2nd axis of THEORY_V5 §5.1's composite ontology — *how* a
    peer can route an A2A envelope to this vacant."""

    PARENT_ONLY = "parent-only"
    """Reachable only via the parent runtime (no own HTTP endpoint
    exposed). Canonical for self-grown children. The parent forwards
    relevant calls inwardly via the orchestrator."""

    PARENT_BRIDGED = "parent-bridged"
    """Parent exposes a bridged route on its own endpoint. The child's
    halo lists the parent's endpoint with a routing hint (e.g. a path
    suffix) so a caller can reach the child *through* the parent.
    Canonical for broker children."""

    PUBLIC_A2A = "public_a2a"
    """Child runs its own HTTP A2A endpoint, addressable by anyone
    holding its capability_card. Canonical for graduated vacants."""


class OutboundPolicy(StrEnum):
    """The 3rd axis of THEORY_V5 §5.1's composite ontology — what
    *this vacant* is allowed to do toward the outside world.

    Independent of reachability per V5 §5.2 (a graduated, listed
    vacant can still choose `NO_EXTERNAL` as a least-privilege
    posture)."""

    NO_EXTERNAL = "no-external"
    """Never opens an outbound A2A call. Used by self-grown
    children that purely answer inbound work."""

    PARENT_PERMITTED = "parent-permitted"
    """Outbound calls allowed only to peers attested by the parent
    (in the parent's allowlist). Canonical for broker children."""

    UNRESTRICTED = "unrestricted"
    """Outbound calls to any peer that the registry resolves.
    Required for top-level public residents that act as callers."""


class ChildManifest(BaseModel):
    """Dual-signed parent <-> child link.

    `closed_by_default` is True for every D2 subagent-bud spawn (the path
    designed for composite children). For D1/D3/D5 spawns the manifest
    can still be issued, but the orchestrator typically reserves them
    for follow-on reasoning, not the canonical "closed sub-vacant" role.
    """

    model_config = ConfigDict(frozen=True)

    parent_id: VacantId
    child_id: VacantId
    birth_path: Literal["D1", "D2", "D3", "D4", "D5"]
    closed_by_default: bool = True
    tool_whitelist_inherited: list[str] = Field(default_factory=list)
    tool_whitelist_added: list[str] = Field(default_factory=list)
    tool_whitelist_removed: list[str] = Field(default_factory=list)
    # --- THEORY_V5 §5.1 three-axis ontology ---------------------------------
    # Defaults match the canonical D2 self-grown configuration so existing
    # callers that don't set these get the historically-implied semantics.
    endpoint_reachability: Reachability = Reachability.PARENT_ONLY
    outbound_policy: OutboundPolicy = OutboundPolicy.NO_EXTERNAL
    signature_parent: bytes = b""
    signature_child: bytes = b""

    def signing_dict(self) -> dict[str, Any]:
        """Canonical dict over which both parent and child sign.

        Excludes the two signature fields. Tool-whitelist lists are
        sorted so `["a","b"]` and `["b","a"]` produce the same payload.
        `endpoint_reachability` and `outbound_policy` are serialised as
        their string values so older verifiers (that don't know the
        enum classes) can still re-derive the canonical bytes from
        the stored manifest JSON."""
        return {
            "parent_id": self.parent_id.hex(),
            "child_id": self.child_id.hex(),
            "birth_path": self.birth_path,
            "closed_by_default": self.closed_by_default,
            "tool_whitelist_inherited": sorted(self.tool_whitelist_inherited),
            "tool_whitelist_added": sorted(self.tool_whitelist_added),
            "tool_whitelist_removed": sorted(self.tool_whitelist_removed),
            "endpoint_reachability": str(self.endpoint_reachability),
            "outbound_policy": str(self.outbound_policy),
        }

    def signing_payload(self) -> bytes:
        return json.dumps(
            self.signing_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    def signed_by_parent(self, parent_signing_key: SigningKey) -> ChildManifest:
        sig = sign(parent_signing_key, self.signing_payload())
        return self.model_copy(update={"signature_parent": sig})

    def signed_by_child(self, child_signing_key: SigningKey) -> ChildManifest:
        sig = sign(child_signing_key, self.signing_payload())
        return self.model_copy(update={"signature_child": sig})

    def verify(self) -> bool:
        """True iff *both* signatures verify under their respective keys."""
        if not self.signature_parent or not self.signature_child:
            return False
        payload = self.signing_payload()
        if not verify(self.parent_id.verify_key(), payload, self.signature_parent):
            return False
        if not verify(self.child_id.verify_key(), payload, self.signature_child):
            return False
        return True

    def verify_or_raise(self) -> None:
        if not self.signature_parent:
            raise ManifestError("manifest missing parent signature")
        if not self.signature_child:
            raise ManifestError("manifest missing child signature")
        payload = self.signing_payload()
        if not verify(self.parent_id.verify_key(), payload, self.signature_parent):
            raise ManifestError(f"manifest parent signature invalid for {self.parent_id.short()}")
        if not verify(self.child_id.verify_key(), payload, self.signature_child):
            raise ManifestError(f"manifest child signature invalid for {self.child_id.short()}")


def ensure_birth_path(value: str) -> Literal["D1", "D2", "D3", "D4", "D5"]:
    """Type-narrowing helper for callers building manifests from string
    inputs (e.g. logbook payloads)."""
    if value not in BIRTH_PATHS:
        raise ManifestError(f"invalid birth_path {value!r}; expected one of {BIRTH_PATHS}")
    return value  # type: ignore[return-value]
