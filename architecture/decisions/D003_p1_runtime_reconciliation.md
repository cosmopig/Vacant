# D003 — P1 Runtime Spec Reconciliation

**Date:** 2026-05-05
**Author:** P1 implementation session
**Affected components:** P1 Runtime / `core/types.py` / `core/constants.py` / `architecture/CONSTANTS.md`

---

## Background

Three spec ambiguities surfaced while implementing `dispatch/P1_runtime.md`. Each is pinned here so downstream sessions and reviewers can see the resolution and reverse it if needed.

### Issue A — `can_review(state)` for STALE

`dispatch/P1_runtime.md` §1 says only:

> `can_review(state) -> bool` — returns False for SUNK and ARCHIVED (§4.1).

But `architecture/THEORY_V5.md` §4.1 (the cited section) explicitly lists STALE as also unable to issue new reviews ("Stale / Warmup ❌（凍結直到復活）"). The dispatch's wording undersells what §4.1 actually requires.

### Issue B — SUNK heartbeat cadence

`architecture/CONSTANTS.md` §Lifecycle exposes two cadence constants that look overlapping:

| Constant | Value | Comment |
|---|---|---|
| `HEARTBEAT_DECAYED_PERIOD_S` | `86400` (24h) | cited as "P1 §D5, line 59" with the **(Sunk)** label |
| `HEARTBEAT_SUNK_LIVENESS_PERIOD_S` | `600` (10 min) | cited as "THEORY_V5 §3, line 340" |

Reading the underlying sources:

- `architecture/THEORY_V5.md` §4.2 (and the §3 line CONSTANTS.md cites): "Sunk vacant 的 10-min 殘響心跳" — i.e. **SUNK = 10 min**, with the explicit semantic note that this is *identity custody attestation, not liveness*.
- `architecture/components/P1_runtime.md` §D6 line 73: "進 hibernation … 仍跑最低限度 heartbeat（每 24h 一次空 attestation）" — i.e. **HIBERNATING = 24h**.

The CONSTANTS.md row that labels `HEARTBEAT_DECAYED_PERIOD_S = 86400` as "(Sunk)" is the artefact of an earlier pass where SUNK and HIBERNATING shared the "decayed" mode. THEORY V5 §4.2 (codex R5 fix) split them apart.

### Issue C — `parent_id` field on `ResidentForm`

`dispatch/P1_runtime.md` §4 says spawn "returns a child `ResidentForm` with `parent_id` set", but P0's `ResidentForm` has no `parent_id` field. P0 is also marked "extend, do not modify" in the dispatch's read-first list.

## Decision

### A. `can_review` returns False for STALE, SUNK, and ARCHIVED

```python
def can_review(state: VacantState) -> bool:
    return state in {VacantState.LOCAL, VacantState.ACTIVE, VacantState.HIBERNATING}
```

This matches THEORY_V5 §4.1 verbatim. The dispatch's narrower wording is treated as informative; the canonical spec wins (per CLAUDE.md).

The dispatch acceptance line `can_review(SUNK) is False and can_review(ARCHIVED) is False` is satisfied a fortiori.

### B. HIBERNATING and SUNK use distinct cadences

`core/constants.py` exports both, with disambiguated names and explicit citations:

```python
HEARTBEAT_HIBERNATING_PERIOD_S: Final[int] = 86_400   # P1 §D6
HEARTBEAT_SUNK_LIVENESS_PERIOD_S: Final[int] = 600    # THEORY_V5 §4.2
```

`HEARTBEAT_DECAYED_PERIOD_S = 86_400` (already exported in P0) is preserved as an alias for HIBERNATING — its original value is unchanged, but the docstring is updated to reflect the spec-correct meaning. SUNK heartbeats use `HEARTBEAT_SUNK_LIVENESS_PERIOD_S`.

`architecture/CONSTANTS.md` is updated in the same PR to:
- Re-label `HEARTBEAT_DECAYED_PERIOD_S` as the HIBERNATING cadence (citing P1 §D6 line 73).
- Add `HEARTBEAT_HIBERNATING_PERIOD_S` as the canonical name.
- Keep `HEARTBEAT_SUNK_LIVENESS_PERIOD_S` unchanged.

### C. `ResidentForm` gains an additive `parent_id`

`core/types.py` adds:

```python
class ResidentForm(BaseModel):
    ...
    parent_id: VacantId | None = None
    """Lineage anchor: VacantId of the parent that spawned this vacant
    (None for root / Path-Zero vacants). THEORY_V5 §4.3."""
```

Default is `None`, so all P0 callers and tests are unaffected. Spawn paths set `parent_id` to the parent vacant's id; secondary parents (D4 lineage-merge) are recorded inside the BIRTH log entry payload, not on `ResidentForm`, to keep the field shape stable.

This is treated as an *extension* (purely additive, default-valued field), not a *modification* of P0 semantics.

## Consequences

- Downstream P3 (reputation) gets a clean `can_review` predicate it can call without re-deriving §4.1 logic.
- `HeartbeatScheduler` selects cadence by state via a small dispatch table (see `runtime/heartbeat.py`), eliminating the HIBERNATING/SUNK confusion at every call site.
- Lineage-aware code in P3/P4 can read `ResidentForm.parent_id` directly; D4 secondary-parent attestations live in the BIRTH log entry payload and are read from there.
