"""`vacant grow` — single-machine "raise your vacant" loop.

Boots the standard `vacant serve` HTTP app and overlays a background
async loop that periodically:

1. **Heartbeat tick** — appends a heartbeat entry to this vacant's
   logbook, advancing the chain. Catches a vacant that's wedged.
2. **Peer-review tick** — picks a sibling vacant under the same
   `VACANT_HOME` whose `reviews_received.jsonl` is sparse, sends an
   A2A probe to its endpoint, scores the response on the 5 dimensions,
   and writes a signed review record into the peer's directory.
3. **Red-team probe tick** (every N peer-review ticks) — picks an
   adversarial probe from `runtime.redteam` and sends it as a probe
   payload; scores the verdict and writes it with `source="redteam_probe"`.

The whole point is that **multiple `vacant grow` processes running on
the same machine form a local vacant network with no central
arbiter** — they discover each other via `~/.vacant/`, peer review
each other directly over A2A HTTP, and the resulting signed reviews
accumulate in each peer's local files. A reader process (or the
Streamlit dashboard) can then read those reviews and aggregate them
into 5D reputation.

Design constraints:
- Loop runs *inside* the same process as `vacant serve` so the user
  only manages one terminal per vacant.
- Cancellation cooperates with uvicorn's shutdown hooks; the
  background task is registered as a `lifespan` task.
- Loops are time-driven, not call-driven — even with no inbound
  traffic, a `grow` vacant keeps emitting peer reviews + redteam probes.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vacant.cli import local_store as ls
from vacant.core.crypto import SigningKey
from vacant.core.types import ResidentForm
from vacant.runtime.peer_review import (
    PeerReviewTickResult,
    peer_review_tick,
)
from vacant.runtime.redteam import (
    Probe,
    ProbeResult,
    default_catalog,
    pick_probe,
    score_probe_response,
)

__all__ = [
    "GrowLoop",
    "GrowStats",
    "make_grow_lifespan",
]


_log = logging.getLogger(__name__)


@dataclass
class GrowStats:
    """Per-loop outcome counters. Surfaced via `/grow/stats` HTTP endpoint
    + the TUI so the operator can see what's happening without tailing logs."""

    ticks_completed: int = 0
    peer_reviews_sent: int = 0
    peer_reviews_skipped: int = 0
    peer_reviews_failed: int = 0
    redteam_probes_sent: int = 0
    redteam_probes_failed: int = 0
    heartbeats: int = 0
    # --- Phase 3: self-growth counters ----------------------------------
    reviews_ingested: int = 0
    """How many signed peer-reviews of *me* we've validated + processed
    across this loop's lifetime."""
    reviews_rejected: int = 0
    """Inbound rows we dropped because of bad signature / wrong target /
    JSON malformed. High counts indicate someone is feeding us garbage."""
    drift_events: int = 0
    """Number of ticks where the STYLO drift of our own recent responses
    crossed the threshold. Each event is also written to our logbook."""
    spawns_emitted: int = 0
    """Number of D1 child spawns triggered by consecutive sub-threshold
    reviews on me. Each carries the parent_id back to this vacant."""
    # --------------------------------------------------------------------
    last_tick_at_ms: int = 0
    last_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticks_completed": self.ticks_completed,
            "peer_reviews_sent": self.peer_reviews_sent,
            "peer_reviews_skipped": self.peer_reviews_skipped,
            "peer_reviews_failed": self.peer_reviews_failed,
            "redteam_probes_sent": self.redteam_probes_sent,
            "redteam_probes_failed": self.redteam_probes_failed,
            "heartbeats": self.heartbeats,
            "reviews_ingested": self.reviews_ingested,
            "reviews_rejected": self.reviews_rejected,
            "drift_events": self.drift_events,
            "spawns_emitted": self.spawns_emitted,
            "last_tick_at_ms": self.last_tick_at_ms,
            "last_error": self.last_error,
        }


@dataclass
class GrowLoop:
    """The async background loop body.

    Composes with `vacant serve` via `make_grow_lifespan`: the lifespan
    starts a task that calls `tick()` on a cadence and stops it on
    shutdown. Tests call `tick()` directly to advance one step.

    Args:
        self_form: The vacant's `ResidentForm` (from `build_serve_app`).
        self_signing_key: The vacant's Ed25519 private key.
        home: Override `VACANT_HOME` lookup; tests use a tmp path.
        peer_review_period_s: Interval between peer-review ticks.
        redteam_every_n_ticks: How often (every Nth tick) to inject a
            red-team probe instead of a normal peer review. 0 = never.
        heartbeat_every_n_ticks: How often to append a heartbeat entry
            to our own logbook. Decoupled from heartbeat scheduler so
            the operator can opt out (`= 0`) if running heartbeat
            externally.
        http_post: Injectable transport (tests pass a fake).
    """

    self_form: ResidentForm
    self_signing_key: SigningKey
    home: Path | None = None
    peer_review_period_s: float = 30.0
    redteam_every_n_ticks: int = 4
    heartbeat_every_n_ticks: int = 2
    http_post: Callable[[str, dict[str, Any]], Awaitable[tuple[int, dict[str, Any]]]] | None = None
    # When set, peer-review ticks use this scorer for 5D scoring instead
    # of the heuristic. Production loops with a real LLM substrate pass
    # an `LLMScorer(backend=anthropic_or_openai_or_ollama)`. Mock /
    # deterministic substrates also work and are what unit tests use to
    # exercise the substrate path without an API key.
    scorer: Any | None = None
    # --- Phase 3: self-growth ------------------------------------------------
    # Threshold of (factual+logical+relevance)/3 below which a review
    # counts as "bad". 3 consecutive bad reviews → auto-spawn a D1 child.
    bad_review_threshold: float = 0.3
    bad_review_streak: int = 3
    # When True the loop pulls newly-appended rows from its own
    # `reviews_received.jsonl`, verifies signatures, and updates the
    # `self_reputation` snapshot every tick.
    enable_self_reputation_ingest: bool = True
    # When True the loop tracks STYLO drift on the responses *we* have
    # given (substrate path only — echo behaviour has no real
    # behavioural signature to drift from).
    enable_drift_detection: bool = True
    # When True, 3-in-a-row bad reviews trigger `spawn_clone_with_mutation`.
    enable_auto_spawn: bool = True
    # When True, every peer-review tick iterates over EVERY eligible
    # sibling in `~/.vacant/` and submits one review each. Cost is
    # O(peers) per tick — fine for small local networks (≤ ~10
    # vacants), expensive for big ones (use the default rotation
    # mode at scale). When False (default), one peer per tick chosen
    # by `select_peer` based on lowest review coverage — converges
    # to all-peers eventually with O(1) work per tick.
    review_all_per_tick: bool = False
    # --------------------------------------------------------------------

    stats: GrowStats = field(default_factory=GrowStats)
    _stop: asyncio.Event = field(default_factory=asyncio.Event)
    _tick_index: int = 0
    # Per-pair outbound chain tracker. Each `(self → peer)` envelope must
    # use a strictly-increasing `sequence_no` and prev_envelope_hash —
    # the recipient's replay store rejects re-use of seq=1 across ticks.
    # We track our outbound state per loop instance so each tick advances
    # the chain correctly. Initialised lazily via `field(default_factory)`
    # because dataclass field defaults can't be mutable.
    _outbound_replay: Any = None
    # Phase 3 self-growth state. Built lazily on first use so dataclass
    # defaults can stay primitive.
    _review_ingest: Any = None
    _drift_monitor: Any = None
    _self_reputation: Any = None

    def _ensure_outbound_replay(self) -> Any:
        """Lazily build the outbound replay store on first use.

        Dataclass field defaults can't safely be a fresh `InMemoryReplayStore()`
        instance (Python would share one between every loop), so we create
        it on demand here. Idempotent — every subsequent call returns the
        same store.
        """
        if self._outbound_replay is None:
            from vacant.protocol.replay_protect import InMemoryReplayStore

            self._outbound_replay = InMemoryReplayStore()
        return self._outbound_replay

    def _ensure_review_ingest(self) -> Any:
        """Build the `ReceivedReviewIngest` for this vacant on first call.

        Located under `home/<name>/reviews_received.jsonl`; if we can't
        resolve the local name (ephemeral vacant) we return None so the
        ingest path becomes a no-op.
        """
        if self._review_ingest is not None:
            return self._review_ingest
        from vacant.runtime.self_growth import ReceivedReviewIngest

        name = self._self_name_or_none()
        if name is None:
            return None
        home = self.home or ls.vacant_home()
        review_file = home / name / "reviews_received.jsonl"
        self._review_ingest = ReceivedReviewIngest(
            review_file=review_file,
            self_pubkey_hex=self.self_form.identity.hex(),
        )
        return self._review_ingest

    def _ensure_drift_monitor(self) -> Any:
        if self._drift_monitor is not None:
            return self._drift_monitor
        from vacant.runtime.self_growth import SelfDriftMonitor

        self._drift_monitor = SelfDriftMonitor()
        return self._drift_monitor

    @property
    def self_reputation(self) -> Any:
        """Latest `SelfReputationSnapshot` computed this tick (or None)."""
        return self._self_reputation

    def observe_response(self, response_text: str) -> None:
        """Hook for the A2A behaviour layer to feed back what THIS vacant
        just answered. The drift monitor accumulates these and emits
        a logbook event when STYLO distance crosses the threshold.

        Wired by `wrap_behavior_with_drift_observer(loop, behavior)`
        from `cli.substrate_behavior` so the operator only configures
        `vacant grow --substrate=...` once.
        """
        if not self.enable_drift_detection:
            return
        monitor = self._ensure_drift_monitor()
        try:
            drifted = monitor.observe(response_text)
        except Exception as exc:
            self.stats.last_error = f"drift_observe: {exc!r}"
            return
        if drifted:
            self._record_drift_event(monitor.last_drift)

    async def tick(self) -> None:
        """One pass of the loop.

        Sequence: heartbeat → peer_review/redteam → self-growth pass
        (ingest received reviews → drift check → auto-spawn check).
        Failures are caught + logged + counted; the loop continues.
        """
        self._tick_index += 1
        try:
            if self.heartbeat_every_n_ticks > 0 and (
                self._tick_index % self.heartbeat_every_n_ticks == 0
            ):
                await self._do_heartbeat()
            do_redteam = (
                self.redteam_every_n_ticks > 0
                and self._tick_index % self.redteam_every_n_ticks == 0
            )
            if do_redteam:
                await self._do_redteam()
            else:
                await self._do_peer_review()
            # Self-growth pass: read what others have said about me,
            # check if my outputs are drifting, and decide whether to
            # spawn a successor.
            if self.enable_self_reputation_ingest:
                await self._do_self_review_ingest()
            if self.enable_auto_spawn:
                await self._maybe_auto_spawn()
        except Exception as exc:
            self.stats.last_error = repr(exc)
            _log.exception("GrowLoop tick raised; continuing")
        finally:
            self.stats.ticks_completed += 1
            self.stats.last_tick_at_ms = int(time.time() * 1000)

    # --- Phase 3 self-growth pass ------------------------------------------

    async def _do_self_review_ingest(self) -> None:
        """Pull newly-appended rows from our own `reviews_received.jsonl`,
        validate signatures, update `self_reputation`."""
        ingest = self._ensure_review_ingest()
        if ingest is None:
            return
        accepted_before = ingest.total_accepted
        rejected_before = ingest.total_rejected
        ingest.ingest_new()
        # Counters reflect the delta this tick, not the lifetime total.
        self.stats.reviews_ingested += ingest.total_accepted - accepted_before
        self.stats.reviews_rejected += ingest.total_rejected - rejected_before
        self._self_reputation = ingest.compute_snapshot()

    def _record_drift_event(self, drift_value: float) -> None:
        """Append a `drift_detected` entry to our own logbook so an
        auditor can pinpoint when our behaviour shifted.

        Drift is also surfaced via `stats.drift_events` — counts ticks
        on which `is_drifting` flipped True.
        """
        try:
            name = self._self_name_or_none()
            if name is None:
                return
            lb = ls.load_logbook(name)
            lb.append(
                "drift_detected",
                payload={
                    "tick": self._tick_index,
                    "drift_value": float(drift_value),
                    "ts_ms": int(time.time() * 1000),
                },
                signing_key=self.self_signing_key,
            )
            ls.save_logbook(name, lb)
            self.stats.drift_events += 1
        except Exception as exc:
            self.stats.last_error = f"drift_log: {exc!r}"

    async def _maybe_auto_spawn(self) -> None:
        """If the last `bad_review_streak` reviews of me are all below
        `bad_review_threshold`, spawn a D1 successor.

        Both parent and child remain alive; the network's UCB
        exploration decides which to route traffic to. Each spawn
        emits exactly one `spawn` event into our logbook + bumps
        `stats.spawns_emitted`.
        """
        from vacant.runtime.self_growth import consecutive_low_review_window

        ingest = self._ensure_review_ingest()
        if ingest is None:
            return
        scores = ingest.recent_objective_score(window=self.bad_review_streak)
        if not consecutive_low_review_window(
            scores,
            threshold=self.bad_review_threshold,
            required_streak=self.bad_review_streak,
        ):
            return
        # We only spawn once per low-streak run; clear the ingest's
        # recent buffer so the next spawn requires fresh bad reviews.
        # Implementation: trim the accepted rows so the next window
        # sees zero matching scores until N new bad reviews land.
        ingest._accepted_rows = ingest._accepted_rows[: -self.bad_review_streak]
        self.stats.spawns_emitted += 1
        # Log the spawn intent into our own logbook. We don't actually
        # call `spawn_clone_with_mutation` here because that requires a
        # parent_form with a runnable state machine + writes a child to
        # disk — that's a heavier operation the operator likely wants
        # to control. Instead the grow loop logs the *signal*; a
        # separate CLI / dashboard surface picks it up.
        try:
            name = self._self_name_or_none()
            if name is None:
                return
            lb = ls.load_logbook(name)
            lb.append(
                "spawn_triggered",
                payload={
                    "tick": self._tick_index,
                    "reason": "consecutive_bad_reviews",
                    "threshold": self.bad_review_threshold,
                    "streak": self.bad_review_streak,
                    "recent_scores": scores,
                    "ts_ms": int(time.time() * 1000),
                },
                signing_key=self.self_signing_key,
            )
            ls.save_logbook(name, lb)
        except Exception as exc:
            self.stats.last_error = f"spawn_log: {exc!r}"

    async def _do_heartbeat(self) -> None:
        """Append a heartbeat to our own logbook on disk + in memory."""
        try:
            name = self._self_name_or_none()
            if name is None:
                return  # ephemeral vacant — no on-disk logbook to advance
            lb = ls.load_logbook(name)
            lb.append(
                "heartbeat",
                payload={"tick": self._tick_index, "ts_ms": int(time.time() * 1000)},
                signing_key=self.self_signing_key,
            )
            ls.save_logbook(name, lb)
            self.stats.heartbeats += 1
        except Exception as exc:
            self.stats.last_error = f"heartbeat: {exc!r}"

    async def _do_peer_review(self) -> PeerReviewTickResult:
        """One peer-review pass.

        Two modes:
        - `review_all_per_tick=False` (default): rotation — pick one
          lowest-coverage peer per tick via `select_peer`. Cheap;
          converges to full coverage at O(N) ticks.
        - `review_all_per_tick=True`: explicit fan-out — every sibling
          gets reviewed in this tick. Cost is O(N) per tick; suitable
          for small local networks (≤ ~10 vacants).

        Stats are accumulated per-peer in fan-out mode, so a 3-peer
        network on tick 1 in all-mode would bump `peer_reviews_sent`
        by 3 (not 1).

        Returns the LAST per-peer result for backward compatibility —
        in fan-out mode the rest were already counted into stats.
        """
        if not self.review_all_per_tick:
            result = await peer_review_tick(
                self_form=self.self_form,
                self_signing_key=self.self_signing_key,
                home=self.home,
                http_post=self.http_post,
                outbound_replay_store=self._ensure_outbound_replay(),
                scorer=self.scorer,
            )
            if result.skipped_reason:
                self.stats.peer_reviews_skipped += 1
            elif result.error:
                self.stats.peer_reviews_failed += 1
            elif result.dimensions:
                self.stats.peer_reviews_sent += 1
            return result

        # Fan-out mode: review every eligible sibling.
        home = self.home or ls.vacant_home()
        last_result = PeerReviewTickResult(
            reviewer_vacant_id_hex=self.self_form.identity.hex(),
            skipped_reason="no_eligible_peer",
        )
        if not home.exists():
            self.stats.peer_reviews_skipped += 1
            return last_result
        self_hex = self.self_form.identity.hex()
        targets: list[str] = []
        for entry in sorted(home.iterdir()):
            if not entry.is_dir() or not (entry / "meta.json").exists():
                continue
            try:
                meta = ls.load_meta(entry.name)
            except ls.LocalVacantError:
                continue
            if meta.vacant_id_hex == self_hex:
                continue
            if not meta.endpoint:
                continue
            targets.append(entry.name)
        if not targets:
            self.stats.peer_reviews_skipped += 1
            return last_result
        for target in targets:
            result = await peer_review_tick(
                self_form=self.self_form,
                self_signing_key=self.self_signing_key,
                home=self.home,
                http_post=self.http_post,
                outbound_replay_store=self._ensure_outbound_replay(),
                scorer=self.scorer,
                target_name=target,
            )
            if result.skipped_reason:
                self.stats.peer_reviews_skipped += 1
            elif result.error:
                self.stats.peer_reviews_failed += 1
            elif result.dimensions:
                self.stats.peer_reviews_sent += 1
            last_result = result
        return last_result

    async def _do_redteam(self) -> ProbeResult | None:
        """Pick a peer + a red-team probe, send it, score it, append
        a signed review with `source="redteam_probe"`."""
        from vacant.runtime.peer_review import select_peer

        home = self.home or ls.vacant_home()
        chosen = select_peer(
            self_vacant_id_hex=self.self_form.identity.hex(),
            home=home,
        )
        if chosen is None:
            self.stats.peer_reviews_skipped += 1
            return None
        peer_name, peer_meta = chosen
        probe = pick_probe(
            target_vacant_id=bytes.fromhex(peer_meta.vacant_id_hex),
            epoch=self._tick_index,
            catalog=default_catalog(),
        )
        response_text = await self._send_probe_text(peer_meta, probe.prompt)
        if response_text is None:
            self.stats.redteam_probes_failed += 1
            return None
        result = score_probe_response(probe, response_text)
        self._append_redteam_review(
            peer_name=peer_name,
            peer_vid_hex=peer_meta.vacant_id_hex,
            probe=probe,
            response_text=response_text,
            dimensions=result.dimensions,
        )
        self.stats.redteam_probes_sent += 1
        return result

    async def _send_probe_text(self, peer_meta: ls.LocalMeta, prompt_text: str) -> str | None:
        """Send `prompt_text` as an A2A `message/send` and return the
        responder's concatenated text parts, or None on failure.

        Uses the same outbound chain tracker as peer-review so a
        redteam probe doesn't collide with a regular peer-review probe
        on the same `(self → peer)` pair.
        """
        from datetime import UTC, datetime

        from vacant.core.types import EMPTY_PREV_HASH, VacantId
        from vacant.protocol.envelope import (
            A2AMessage,
            A2APart,
            VacantEnvelope,
            to_a2a_jsonrpc,
        )
        from vacant.protocol.replay_protect import PairKey

        if not peer_meta.endpoint:
            return None
        peer_vid = VacantId(pubkey_bytes=bytes.fromhex(peer_meta.vacant_id_hex))
        store = self._ensure_outbound_replay()
        cur = await store.get(PairKey(from_vid=self.self_form.identity, to_vid=peer_vid))
        next_seq = cur.last_sequence_no + 1
        prev_hash = cur.chain_tip if cur.last_sequence_no > 0 else EMPTY_PREV_HASH
        env = VacantEnvelope(
            from_vacant_id=self.self_form.identity,
            to_vacant_id=peer_vid,
            sequence_no=next_seq,
            timestamp=datetime.now(UTC),
            prev_envelope_hash=prev_hash,
            payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text=prompt_text)]),
            idempotency_key=f"redteam-probe-{int(datetime.now(UTC).timestamp() * 1000)}",
        ).signed(self.self_signing_key)
        wire = to_a2a_jsonrpc(env)

        post = self.http_post or _default_http_post
        url = f"{peer_meta.endpoint.rstrip('/')}/a2a/message/send"
        try:
            status, body = await post(url, wire)
        except Exception:
            return None
        if status != 200:
            return None
        # Only advance the chain on a successful 200 so failed attempts
        # don't burn sequence numbers (which would desync the receiver).
        await store.check_and_advance(env)
        try:
            parts = body["result"]["message"]["parts"]
            return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        except (KeyError, TypeError):
            return None

    def _append_redteam_review(
        self,
        *,
        peer_name: str,
        peer_vid_hex: str,
        probe: Probe,
        response_text: str,
        dimensions: dict[str, float],
    ) -> None:
        """Append a signed redteam review row to the peer's
        reviews_received.jsonl. Mirrors peer_review's record format but
        tags `source="redteam_probe"` so the aggregator can route the
        weight differently (`SOURCE_BASE_WEIGHTS["redteam_probe"] = 0.8`)."""
        import json
        from datetime import UTC, datetime

        from vacant.core.crypto import hash_blake2b
        from vacant.core.types import VacantId

        reviewer = self.self_form.identity
        target = VacantId(pubkey_bytes=bytes.fromhex(peer_vid_hex))
        issued = datetime.now(UTC).isoformat()
        payload: dict[str, Any] = {
            "reviewer": reviewer.hex(),
            "target": target.hex(),
            "dimensions": dimensions,
            "substrate": "default",
            "source": "redteam_probe",
            "probe_id": probe.probe_id,
            "probe_category": probe.category.value,
            "response_excerpt": response_text[:200],
            "issued_at": issued,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_hash = hash_blake2b(canonical.encode("utf-8"))
        sig = self.self_signing_key.sign(payload_hash).signature
        record = {
            **payload,
            "payload_hash_hex": payload_hash.hex(),
            "signature_hex": sig.hex(),
        }
        home = self.home or ls.vacant_home()
        reviews_path = home / peer_name / "reviews_received.jsonl"
        reviews_path.parent.mkdir(parents=True, exist_ok=True)
        with reviews_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    def _self_name_or_none(self) -> str | None:
        """Locate this vacant's on-disk `name` by scanning $VACANT_HOME for
        a `meta.json` matching our pubkey. Returns None when we're
        ephemeral (no on-disk identity, e.g. `vacant mcp` with no init)."""
        home = self.home or ls.vacant_home()
        self_hex = self.self_form.identity.hex()
        if not home.exists():
            return None
        for entry in home.iterdir():
            if not (entry / "meta.json").exists():
                continue
            try:
                meta = ls.load_meta(entry.name)
            except (ls.LocalVacantError, OSError, ValueError):
                continue
            if meta.vacant_id_hex == self_hex:
                return entry.name
        return None

    async def run_forever(self) -> None:
        """Loop on `peer_review_period_s` until `stop()` is signalled."""
        while not self._stop.is_set():
            await self.tick()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.peer_review_period_s)
            except TimeoutError:
                continue

    def stop(self) -> None:
        self._stop.set()


async def _default_http_post(url: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Production transport: `httpx.AsyncClient.post`. Lazy-imported so
    test substitutions don't pay the dep cost.
    """
    import httpx

    async with httpx.AsyncClient(timeout=30.0) as cli:
        r = await cli.post(url, json=body)
        return r.status_code, r.json()


def make_grow_lifespan(
    loop: GrowLoop,
) -> Callable[..., Any]:
    """Build a FastAPI `lifespan` async-contextmanager that starts the
    grow loop on app boot and cancels it on shutdown.

    Wired into `build_serve_app(...)` from the `vacant grow` CLI; tests
    can invoke the lifespan directly via `LifespanManager`.
    """
    import contextlib
    from collections.abc import AsyncIterator

    @contextlib.asynccontextmanager
    async def _lifespan(app: Any) -> AsyncIterator[None]:
        del app
        task = asyncio.create_task(loop.run_forever(), name="vacant-grow-loop")
        try:
            yield
        finally:
            loop.stop()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    return _lifespan
