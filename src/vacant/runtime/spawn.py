"""Self-replication paths (D1-D5).

Each path:
1. generates a fresh Ed25519 keypair (no key derivation — keypairs are
   independent so a parent compromise does not give the controller the
   child's private key; cf. D003)
2. assembles a new `BehaviorBundle` / `SubstrateSpec` per the path
3. seeds the child's logbook with a `BIRTH` entry that names the parent
4. appends a `SPAWN` entry to the parent's logbook that names the child
5. returns the new `ResidentForm` with `parent_id` set

Path A (human-written vacant) is **deprecated** and intentionally absent
(CLAUDE.md §Things to NOT do).

D4 lineage-merge requires an explicit `ParentConsent` from the secondary
parent — a detached signature over the spawn intent. Without it the call
raises `ConsentError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from vacant.core.crypto import SigningKey, hash_blake2b, keygen, sign, verify
from vacant.core.types import (
    BehaviorBundle,
    Logbook,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.runtime.errors import ConsentError, SpawnError

__all__ = [
    "BIRTH_KIND",
    "SPAWN_KIND",
    "ParentConsent",
    "SpawnResult",
    "consent",
    "spawn_capability_fork",
    "spawn_clone_with_mutation",
    "spawn_cross_substrate_respawn",
    "spawn_lineage_merge",
    "spawn_subagent_bud",
]


SPAWN_KIND: Final[str] = "SPAWN"
BIRTH_KIND: Final[str] = "BIRTH"


@dataclass(frozen=True)
class SpawnResult:
    """Output of every spawn path."""

    child: ResidentForm
    child_signing_key: SigningKey
    path: str
    """One of D1..D5."""


@dataclass(frozen=True)
class ParentConsent:
    """Detached signature attesting that a parent agrees to a spawn.

    `signature` is over `consent_payload(parent_id, intent)` — see
    `consent()`. Verified by `verify_consent()` inside `spawn_lineage_merge`.
    """

    parent_id: VacantId
    intent: str
    signature: bytes


def _consent_payload(parent_id: VacantId, intent: str) -> bytes:
    return hash_blake2b(parent_id.pubkey_bytes + b"\x1f" + intent.encode("utf-8"))


def consent(parent_id: VacantId, parent_signing_key: SigningKey, intent: str) -> ParentConsent:
    """Helper for tests + D4 callers: build a signed consent token."""
    sig = sign(parent_signing_key, _consent_payload(parent_id, intent))
    return ParentConsent(parent_id=parent_id, intent=intent, signature=sig)


def _verify_consent(token: ParentConsent, expected_intent: str) -> None:
    if token.intent != expected_intent:
        raise ConsentError(
            f"consent intent mismatch: got {token.intent!r}, expected {expected_intent!r}"
        )
    ok = verify(
        token.parent_id.verify_key(),
        _consent_payload(token.parent_id, token.intent),
        token.signature,
    )
    if not ok:
        raise ConsentError("consent signature did not verify")


def _seed_birth(
    *,
    child_logbook: Logbook,
    child_signing_key: SigningKey,
    parent_id: VacantId,
    path: str,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "parent_id": parent_id.hex(),
        "path": path,
    }
    if extra:
        payload.update(extra)
    child_logbook.append(BIRTH_KIND, payload, child_signing_key)


def _record_spawn(
    *,
    parent_form: ResidentForm,
    parent_signing_key: SigningKey,
    child_id: VacantId,
    path: str,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "child_id": child_id.hex(),
        "path": path,
    }
    if extra:
        payload.update(extra)
    parent_form.logbook.append(SPAWN_KIND, payload, parent_signing_key)


def _build_child(
    *,
    parent_id: VacantId,
    behavior_bundle: BehaviorBundle,
    substrate_spec: SubstrateSpec,
    initial_state: VacantState,
) -> tuple[ResidentForm, SigningKey]:
    sk, vk = keygen()
    child_id = VacantId.from_verify_key(vk)
    return (
        ResidentForm(
            identity=child_id,
            logbook=Logbook(),
            behavior_bundle=behavior_bundle,
            substrate_spec=substrate_spec,
            runtime_state=initial_state,
            capability_card=None,
            parent_id=parent_id,
        ),
        sk,
    )


def _ensure_parent_runnable(parent: ResidentForm) -> None:
    if parent.runtime_state not in {VacantState.LOCAL, VacantState.ACTIVE}:
        raise SpawnError(f"spawn requires LOCAL or ACTIVE parent, got {parent.runtime_state.value}")


# --- D1: clone-with-mutation -------------------------------------------------


def spawn_clone_with_mutation(
    parent: ResidentForm,
    parent_signing_key: SigningKey,
    *,
    policy_mutation: str,
) -> SpawnResult:
    """D1 — clone the parent's bundle, append `policy_mutation` to its DSL.

    Same `tool_whitelist`, same `system_prompt`. Child starts in `ACTIVE`.
    """
    _ensure_parent_runnable(parent)
    if not policy_mutation.strip():
        raise SpawnError("D1 requires a non-empty policy_mutation")
    new_bundle = BehaviorBundle(
        system_prompt=parent.behavior_bundle.system_prompt,
        policy_dsl=(parent.behavior_bundle.policy_dsl + "\n" + policy_mutation).strip(),
        tool_whitelist=list(parent.behavior_bundle.tool_whitelist),
    )
    child, sk = _build_child(
        parent_id=parent.identity,
        behavior_bundle=new_bundle,
        substrate_spec=parent.substrate_spec,
        initial_state=VacantState.ACTIVE,
    )
    _seed_birth(
        child_logbook=child.logbook,
        child_signing_key=sk,
        parent_id=parent.identity,
        path="D1",
        extra={"policy_mutation": policy_mutation},
    )
    _record_spawn(
        parent_form=parent,
        parent_signing_key=parent_signing_key,
        child_id=child.identity,
        path="D1",
    )
    return SpawnResult(child=child, child_signing_key=sk, path="D1")


# --- D2: subagent-bud --------------------------------------------------------


def spawn_subagent_bud(
    parent: ResidentForm,
    parent_signing_key: SigningKey,
    *,
    narrowed_tools: list[str],
) -> SpawnResult:
    """D2 — spawn a closed subagent (registry_visibility=none → LOCAL).

    `narrowed_tools` must be a (possibly equal) subset of the parent's
    tool whitelist; child starts in LOCAL because composite-parent
    children are closed by default (P5 §5.1, CLAUDE.md §Closed children).
    """
    _ensure_parent_runnable(parent)
    parent_tools = set(parent.behavior_bundle.tool_whitelist)
    extra_tools = set(narrowed_tools) - parent_tools
    if extra_tools:
        raise SpawnError(
            f"D2 narrowed_tools must be a subset of parent tools; extras: {sorted(extra_tools)}"
        )
    new_bundle = BehaviorBundle(
        system_prompt=parent.behavior_bundle.system_prompt,
        policy_dsl=parent.behavior_bundle.policy_dsl,
        tool_whitelist=list(narrowed_tools),
    )
    child, sk = _build_child(
        parent_id=parent.identity,
        behavior_bundle=new_bundle,
        substrate_spec=parent.substrate_spec,
        initial_state=VacantState.LOCAL,
    )
    _seed_birth(
        child_logbook=child.logbook,
        child_signing_key=sk,
        parent_id=parent.identity,
        path="D2",
        extra={"narrowed_tools": list(narrowed_tools)},
    )
    _record_spawn(
        parent_form=parent,
        parent_signing_key=parent_signing_key,
        child_id=child.identity,
        path="D2",
        extra={"closed_child": True},
    )
    return SpawnResult(child=child, child_signing_key=sk, path="D2")


# --- D3: capability-fork -----------------------------------------------------


def spawn_capability_fork(
    parent: ResidentForm,
    parent_signing_key: SigningKey,
    *,
    new_capability_text: str,
    new_system_prompt: str,
) -> SpawnResult:
    """D3 — fork into a different capability with a different system prompt.

    Same substrate spec; child starts ACTIVE. `new_capability_text` is
    persisted on the BIRTH entry so downstream code can later mint a fresh
    `CapabilityCard` from it (P4 owns card publication).
    """
    _ensure_parent_runnable(parent)
    if not new_capability_text.strip():
        raise SpawnError("D3 requires a non-empty new_capability_text")
    if not new_system_prompt.strip():
        raise SpawnError("D3 requires a non-empty new_system_prompt")
    new_bundle = BehaviorBundle(
        system_prompt=new_system_prompt,
        policy_dsl=parent.behavior_bundle.policy_dsl,
        tool_whitelist=list(parent.behavior_bundle.tool_whitelist),
    )
    child, sk = _build_child(
        parent_id=parent.identity,
        behavior_bundle=new_bundle,
        substrate_spec=parent.substrate_spec,
        initial_state=VacantState.ACTIVE,
    )
    _seed_birth(
        child_logbook=child.logbook,
        child_signing_key=sk,
        parent_id=parent.identity,
        path="D3",
        extra={"new_capability_text": new_capability_text},
    )
    _record_spawn(
        parent_form=parent,
        parent_signing_key=parent_signing_key,
        child_id=child.identity,
        path="D3",
    )
    return SpawnResult(child=child, child_signing_key=sk, path="D3")


# --- D4: lineage-merge -------------------------------------------------------


_D4_INTENT = "vacant:spawn:D4:lineage_merge"


def spawn_lineage_merge(
    parent_a: ResidentForm,
    parent_a_signing_key: SigningKey,
    parent_b: ResidentForm,
    parent_b_consent: ParentConsent,
    *,
    merged_system_prompt: str,
) -> SpawnResult:
    """D4 — merge two parents' bundles. Requires `parent_b`'s signed consent.

    `parent_a` is the *primary* parent (the one running the ceremony).
    `parent_b_consent` must be a `ParentConsent` whose `parent_id` matches
    `parent_b.identity` and whose `intent` is `_D4_INTENT`. The secondary
    parent is recorded inside the BIRTH log entry payload (D003 §C); only
    the primary parent appears on `child.parent_id`.
    """
    _ensure_parent_runnable(parent_a)
    _ensure_parent_runnable(parent_b)
    if parent_a.identity == parent_b.identity:
        raise SpawnError("D4 requires two distinct parents")
    if parent_b_consent.parent_id != parent_b.identity:
        raise ConsentError("D4 consent: parent_id does not match parent_b")
    _verify_consent(parent_b_consent, _D4_INTENT)

    merged_tools = sorted(
        set(parent_a.behavior_bundle.tool_whitelist) | set(parent_b.behavior_bundle.tool_whitelist)
    )
    merged_policy = "\n".join(
        s
        for s in (
            parent_a.behavior_bundle.policy_dsl,
            parent_b.behavior_bundle.policy_dsl,
        )
        if s
    )
    new_bundle = BehaviorBundle(
        system_prompt=merged_system_prompt,
        policy_dsl=merged_policy,
        tool_whitelist=merged_tools,
    )
    # Substrates: intersect allowed_substrates so the child can run on either parent's stack
    merged_substrates = sorted(
        set(parent_a.substrate_spec.allowed_substrates)
        & set(parent_b.substrate_spec.allowed_substrates)
    ) or list(parent_a.substrate_spec.allowed_substrates)
    new_substrate_spec = SubstrateSpec(
        allowed_substrates=merged_substrates,
        policy={**parent_a.substrate_spec.policy, **parent_b.substrate_spec.policy},
    )
    child, sk = _build_child(
        parent_id=parent_a.identity,
        behavior_bundle=new_bundle,
        substrate_spec=new_substrate_spec,
        initial_state=VacantState.ACTIVE,
    )
    _seed_birth(
        child_logbook=child.logbook,
        child_signing_key=sk,
        parent_id=parent_a.identity,
        path="D4",
        extra={
            "secondary_parent_id": parent_b.identity.hex(),
            "consent_signature": parent_b_consent.signature.hex(),
        },
    )
    _record_spawn(
        parent_form=parent_a,
        parent_signing_key=parent_a_signing_key,
        child_id=child.identity,
        path="D4",
        extra={"secondary_parent_id": parent_b.identity.hex()},
    )
    return SpawnResult(child=child, child_signing_key=sk, path="D4")


def make_d4_consent(parent_b: ResidentForm, parent_b_signing_key: SigningKey) -> ParentConsent:
    """Convenience: build a ParentConsent for the standard D4 intent."""
    return consent(parent_b.identity, parent_b_signing_key, _D4_INTENT)


# --- D5: cross-substrate respawn --------------------------------------------


def spawn_cross_substrate_respawn(
    parent: ResidentForm,
    parent_signing_key: SigningKey,
    *,
    new_substrate_spec: SubstrateSpec,
) -> SpawnResult:
    """D5 — same bundle, different substrate. Identity (keypair) is fresh,
    but the child carries the parent's prompt + policy + tools verbatim.
    """
    _ensure_parent_runnable(parent)
    if not new_substrate_spec.allowed_substrates:
        raise SpawnError("D5 requires at least one allowed substrate in the new spec")
    if new_substrate_spec.allowed_substrates == parent.substrate_spec.allowed_substrates:
        raise SpawnError(
            "D5 requires a different substrate spec; new spec is identical to parent's"
        )
    new_bundle = BehaviorBundle(
        system_prompt=parent.behavior_bundle.system_prompt,
        policy_dsl=parent.behavior_bundle.policy_dsl,
        tool_whitelist=list(parent.behavior_bundle.tool_whitelist),
    )
    child, sk = _build_child(
        parent_id=parent.identity,
        behavior_bundle=new_bundle,
        substrate_spec=new_substrate_spec,
        initial_state=VacantState.ACTIVE,
    )
    _seed_birth(
        child_logbook=child.logbook,
        child_signing_key=sk,
        parent_id=parent.identity,
        path="D5",
        extra={
            "new_substrates": list(new_substrate_spec.allowed_substrates),
            "old_substrates": list(parent.substrate_spec.allowed_substrates),
        },
    )
    _record_spawn(
        parent_form=parent,
        parent_signing_key=parent_signing_key,
        child_id=child.identity,
        path="D5",
    )
    return SpawnResult(child=child, child_signing_key=sk, path="D5")
