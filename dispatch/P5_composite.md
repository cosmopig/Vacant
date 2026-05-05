# P5 — Composite

## Goal

Implement P5 Composite — composite vacants (a vacant whose capability is fulfilled by orchestrating sub-vacants), with **closed-by-default children** that may **graduate** to public via parent consent + rate limit + 3-layer collusion detection.

## Read first (in order)

1. `/CLAUDE.md`
2. `architecture/components/P5_composite.md`
3. `architecture/THEORY_V5.md` §3 (composite mention), §4 (lineage), §6 (collusion defense framing)
4. P1 spawn paths (D2 subagent-bud especially) — composite children are typically D2-spawned

## Repo state at start

- P0, P1, P2, P4 merged. (P3 and P6 may or may not be merged — independent of this work.)
- `src/vacant/composite/` has only `__init__.py` and `errors.py`.

## Scope

### 1. Child manifest — `src/vacant/composite/manifest.py`

`ChildManifest(BaseModel)`:

- `parent_id: VacantId`
- `child_id: VacantId`
- `birth_path: Literal['D1','D2','D3','D4','D5']`
- `closed_by_default: bool` (defaults `True`)
- `tool_whitelist_inherited: list[str]`
- `tool_whitelist_added: list[str]`
- `tool_whitelist_removed: list[str]`
- `signature_parent: bytes`
- `signature_child: bytes`

Both parent and child sign — neither party can fabricate a manifest unilaterally.

### 2. Composite orchestrator — `src/vacant/composite/orchestrator.py`

`CompositeRuntime`:

- Holds a `ResidentForm` for the composite parent + a list of `ChildManifest`s
- `delegate(subtask, child_id)` — call a sub-vacant per Tree-Only protocol (see §3)
- `aggregate(child_responses)` — combine sub-results into the composite's response
- All sub-calls write to BOTH parent's logbook AND child's logbook

### 3. Tree-Only protocol — `src/vacant/composite/tree_only.py`

Closed children **cannot make outbound calls except to their parent or siblings within the same composite tree**:

- `is_call_allowed(caller_manifest, callee_id) -> bool`
- Outbound HTTP from a closed-child runtime is gated through `tree_only_filter` middleware that rejects non-tree calls

### 4. Graduation — `src/vacant/composite/graduation.py`

A closed child can graduate to public (registry_visibility ACTIVE) when ALL of the following hold:

1. **Parent consent** — signed `GraduationRequest` from parent
2. **Rate limit** — graduations per parent per time window (spec gives the values)
3. **3-layer collusion check passes** — same-controller, same-substrate, same-stylo signals (from P3) all below threshold for the parent-child pair

```python
async def graduate(child_id: VacantId, parent: ResidentForm, ...) -> GraduationOutcome:
    # checks 1-3, on success: emits GRADUATION entries to both logbooks,
    # changes child's registry_visibility from NONE → PUBLIC,
    # publishes child's halo
```

**Same keypair, same logbook through graduation.** It is a visibility flag flip, not an entity upgrade. No new identity.

### 5. Collusion detection adapter — `src/vacant/composite/collusion.py`

Thin wrapper around P3's `same_detect` for the graduation path. If P3 isn't merged yet, define a `CollusionProtocol` and use a stub.

## Tests

- `tests/unit/test_manifest.py` — both signatures required; manifest with one missing is rejected
- `tests/unit/test_tree_only.py` — closed child calling outside tree is blocked at the filter; calling parent/sibling allowed
- `tests/unit/test_graduation.py`:
  - All 3 conditions met → graduates, halo published
  - Parent consent missing → rejected
  - Rate limit exceeded → rejected
  - Same-* signal high → rejected
  - **Identity preserved**: post-graduation `child.identity == pre.identity`, `child.logbook` is an extension of pre's, no fork
- `tests/property/test_tree_only_invariant.py` — hypothesis: random call graphs from a closed child only succeed if target is in the same tree
- `tests/integration/test_composite_e2e.py` (`@pytest.mark.slow`) — parent + 3 D2 children handle a composite query end-to-end; one child graduates; post-graduation it answers a direct external call

Coverage target on `src/vacant/composite/`: ≥90%.

## Acceptance

- Tree-Only invariant holds under fuzz (property test)
- Graduation preserves identity and logbook continuity
- All previous criteria hold

## Output

PR titled **"P5: composite — child manifest, Tree-Only, graduation"**.

## Out of scope

- Multi-parent (D4 lineage-merge) graduation flows — handle in a follow-up if needed
- Cross-tree migration (a child re-parented to a different composite)
