"""Composite orchestrator (P5 §3, dispatch §2).

`CompositeRuntime` holds a composite parent's `ResidentForm` plus the
`ChildManifest` list for every direct child, and exposes:

- `delegate(subtask, child_id)` -- dispatch a subtask to a sub-vacant
  through the Tree-Only protocol.
- `aggregate(child_responses)` -- combine sub-results into the
  composite's response.
- `outbound_call(caller_child_id, callee_id)` -- the gate every
  outgoing socket from a closed-child runtime passes through.

Every dispatch writes to **both** logbooks: the parent's logbook
records the delegation, the child's logbook records the inbound task.
That dual-write is the audit trail used by graduation + by the
internal mini_rep tracker (P5 §3.6).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass
from typing import Any

from vacant.composite.errors import CompositeError, ManifestError
from vacant.composite.manifest import ChildManifest
from vacant.composite.tree_only import siblings_of, tree_only_filter
from vacant.core.crypto import SigningKey
from vacant.core.types import ResidentForm, VacantId

__all__ = [
    "ChildHandler",
    "ChildRecord",
    "CompositeRuntime",
    "DelegationResult",
]


ChildHandler = Callable[[Any], Coroutine[Any, Any, Any]]
"""Async callable invoked when the orchestrator delegates to a child.
The orchestrator hands the subtask in; the child returns its result.
Real implementations would route via P6 envelopes; tests pass a lambda."""


@dataclass(frozen=True)
class ChildRecord:
    """A child registered with the composite parent.

    Combines the dual-signed manifest with the runtime hooks the
    orchestrator needs to dispatch to it.
    """

    manifest: ChildManifest
    child_form: ResidentForm
    child_signing_key: SigningKey
    handler: ChildHandler


@dataclass(frozen=True)
class DelegationResult[T]:
    """Output of `CompositeRuntime.delegate`."""

    child_id: VacantId
    subtask: Any
    response: T


# Logbook event kinds (P5 §3.1, dispatch §2 dual-write).
DELEGATE_KIND = "COMPOSITE_DELEGATE"
EXECUTE_KIND = "COMPOSITE_EXECUTE"
AGGREGATE_KIND = "COMPOSITE_AGGREGATE"


class CompositeRuntime:
    """In-process composite parent. Holds the parent form + child registry.

    Construction does not perform any I/O. Use `register_child` to add
    a fully-spawned child + its dual-signed manifest. `delegate`
    dispatches a single subtask; `aggregate` combines a list of
    `DelegationResult`s into one output.

    Concurrency: delegation acquires `self._lock` per dispatch so that
    parent-logbook writes stay strictly ordered (BLAKE2b chain
    integrity). Children are dispatched sequentially in `delegate_many`
    by default; callers who want parallelism inject their own
    `asyncio.gather` through `delegate`.
    """

    def __init__(
        self,
        *,
        parent_form: ResidentForm,
        parent_signing_key: SigningKey,
    ) -> None:
        self._parent_form = parent_form
        self._parent_signing_key = parent_signing_key
        self._children: dict[VacantId, ChildRecord] = {}
        self._lock = asyncio.Lock()

    # --- registration ------------------------------------------------------

    def register_child(self, record: ChildRecord) -> None:
        """Validate the manifest's dual signatures and add the child.

        Raises `ManifestError` if the manifest is unsigned or the parent
        id does not match this composite's identity. Re-registering the
        same child id raises `CompositeError`."""
        if record.manifest.parent_id != self._parent_form.identity:
            raise ManifestError(
                f"manifest parent_id {record.manifest.parent_id.short()} does not "
                f"match this composite {self._parent_form.identity.short()}"
            )
        if record.manifest.child_id != record.child_form.identity:
            raise ManifestError(
                f"manifest child_id {record.manifest.child_id.short()} does not "
                f"match the registered child form's identity {record.child_form.identity.short()}"
            )
        record.manifest.verify_or_raise()
        if record.child_form.identity in self._children:
            raise CompositeError(f"child {record.child_form.identity.short()} already registered")
        self._children[record.child_form.identity] = record

    # --- read-only views ---------------------------------------------------

    @property
    def parent_form(self) -> ResidentForm:
        return self._parent_form

    @property
    def child_ids(self) -> tuple[VacantId, ...]:
        return tuple(self._children.keys())

    @property
    def manifests(self) -> tuple[ChildManifest, ...]:
        return tuple(rec.manifest for rec in self._children.values())

    def manifest_for(self, child_id: VacantId) -> ChildManifest:
        rec = self._children.get(child_id)
        if rec is None:
            raise CompositeError(f"unknown child {child_id.short()}")
        return rec.manifest

    def get_child(self, child_id: VacantId) -> ChildRecord:
        rec = self._children.get(child_id)
        if rec is None:
            raise CompositeError(f"unknown child {child_id.short()}")
        return rec

    # --- delegation --------------------------------------------------------

    async def delegate(
        self,
        *,
        child_id: VacantId,
        subtask: Any,
    ) -> DelegationResult[Any]:
        """Send `subtask` to the named child and write to both logbooks."""
        record = self.get_child(child_id)
        async with self._lock:
            self._parent_form.logbook.append(
                DELEGATE_KIND,
                {
                    "child_id": child_id.hex(),
                    "subtask_kind": _subtask_kind(subtask),
                },
                self._parent_signing_key,
            )
        record.child_form.logbook.append(
            EXECUTE_KIND,
            {
                "parent_id": self._parent_form.identity.hex(),
                "subtask_kind": _subtask_kind(subtask),
            },
            record.child_signing_key,
        )
        response = await record.handler(subtask)
        return DelegationResult(child_id=child_id, subtask=subtask, response=response)

    async def delegate_many(
        self,
        plan: Iterable[tuple[VacantId, Any]],
    ) -> list[DelegationResult[Any]]:
        """Sequential delegation of a list of (child_id, subtask) pairs."""
        results: list[DelegationResult[Any]] = []
        for child_id, subtask in plan:
            results.append(await self.delegate(child_id=child_id, subtask=subtask))
        return results

    def aggregate(
        self,
        results: Iterable[DelegationResult[Any]],
        *,
        combiner: Callable[[list[Any]], Any] = list,
    ) -> Any:
        """Combine sub-results. Default combiner returns the list of
        responses; callers pass a custom combiner for domain shaping."""
        materialised = list(results)
        responses = [r.response for r in materialised]
        combined = combiner(responses)
        self._parent_form.logbook.append(
            AGGREGATE_KIND,
            {
                "n_results": len(materialised),
                "child_ids": [r.child_id.hex() for r in materialised],
            },
            self._parent_signing_key,
        )
        return combined

    # --- outbound gate -----------------------------------------------------

    def outbound_call(
        self,
        *,
        caller_child_id: VacantId,
        callee_id: VacantId,
    ) -> None:
        """Gate every outbound network call from a closed child.

        Raises `TreeOnlyViolationError` for cross-tree / external calls.
        A graduated child (closed_by_default=False) bypasses the gate."""
        manifest = self.manifest_for(caller_child_id)
        sibling_set = siblings_of(caller_child_id, self.manifests)
        tree_only_filter(
            caller_manifest=manifest,
            callee_id=callee_id,
            siblings=sibling_set,
        )

    # --- post-graduation flip ---------------------------------------------

    def mark_graduated(self, child_id: VacantId, new_manifest: ChildManifest) -> None:
        """Replace a child's manifest after graduation.

        The new manifest must (a) be dual-signed, (b) have the same
        parent_id and child_id, and (c) have `closed_by_default=False`.
        Raises `ManifestError` otherwise.
        """
        record = self.get_child(child_id)
        if new_manifest.parent_id != record.manifest.parent_id:
            raise ManifestError("graduated manifest parent_id mismatch")
        if new_manifest.child_id != record.manifest.child_id:
            raise ManifestError("graduated manifest child_id mismatch")
        if new_manifest.closed_by_default:
            raise ManifestError("graduated manifest must have closed_by_default=False")
        new_manifest.verify_or_raise()
        self._children[child_id] = ChildRecord(
            manifest=new_manifest,
            child_form=record.child_form,
            child_signing_key=record.child_signing_key,
            handler=record.handler,
        )


def _subtask_kind(subtask: Any) -> str:
    """Best-effort label for the subtask, written into both logbooks."""
    if isinstance(subtask, dict) and "kind" in subtask:
        return str(subtask["kind"])
    return type(subtask).__name__
