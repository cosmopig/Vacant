"""Self-growth helpers for `GrowLoop` (Pfix9 Phase 3).

Three independent capabilities that the grow loop composes:

1. **Reputation ingest** — every tick, read newly-appended rows from
   `~/.vacant/<self>/reviews_received.jsonl`, verify each row's
   signature against the claimed `reviewer` pubkey, and feed valid
   ones into a local 5D Beta aggregator. The result is "my own
   evolving picture of how peers see me".

2. **Drift detection** — every tick, compute the STYLO-Vec16
   embedding of the responses we've recently emitted and compare them
   to a slowly-updating anchor distribution. A Mahalanobis distance
   above `STYLO_DRIFT_THRESHOLD` (3.5) is logged as a drift event
   into our logbook so an auditor can see the moment behaviour
   shifted.

3. **Auto-spawn on consecutive bad reviews** — if the most recent N
   reviews of this vacant on its primary substrate are all below a
   threshold on `factual+logical+relevance`, run D1
   (`spawn_clone_with_mutation`) to create a successor with a tiny
   policy patch. Both vacants then coexist; the network's UCB
   exploration decides which wins.

These three are deliberately *additive*: a grow loop can opt into any
combination. Tests exercise each in isolation, plus one combined
scenario.

Design constraints:
- Reputation ingest is **cheap** — only newly-added lines are processed
  (offset cursor + `seek()` rather than re-reading the whole file).
- Drift compute is also cheap — fixed 16-dim vector per response.
- Spawn is **destructive in spirit** but additive in fact — the parent
  remains, just gets a child. So if the spawn was misjudged the
  parent doesn't disappear.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vacant.core.crypto import VerifyKey, hash_blake2b, pubkey_from_bytes, verify
from vacant.runtime.shadow_self import (
    AnchorDistribution,
    compute_drift,
    compute_embedding,
    is_drifting,
)

__all__ = [
    "ReceivedReviewIngest",
    "SelfDriftMonitor",
    "SelfReputationSnapshot",
    "consecutive_low_review_window",
    "verify_review_signature",
]


_log = logging.getLogger(__name__)


# --- A. Received-review ingest ---------------------------------------------


@dataclass
class SelfReputationSnapshot:
    """Aggregated 5D view of how peers have scored this vacant.

    Built by `ReceivedReviewIngest.compute_snapshot()`. Each dim is the
    mean of all valid review scores for that dim; `n_reviews` counts
    the unique reviews that contributed (signed + non-self).

    Cold start handling: with `n_reviews < min_n` the dim values are
    intentionally `None` so dashboards show "data insufficient" rather
    than misleading 0.5 priors.
    """

    n_reviews: int
    factual: float | None
    logical: float | None
    relevance: float | None
    honesty: float | None
    adoption: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_reviews": self.n_reviews,
            "factual": self.factual,
            "logical": self.logical,
            "relevance": self.relevance,
            "honesty": self.honesty,
            "adoption": self.adoption,
        }


def verify_review_signature(record: dict[str, Any]) -> bool:
    """Verify a row from `reviews_received.jsonl` was signed by the
    claimed reviewer.

    The row layout is what `_sign_review_record` in `peer_review.py`
    writes: `{reviewer, target, dimensions, ..., payload_hash_hex,
    signature_hex}`. We rebuild the canonical bytes from every field
    EXCEPT `payload_hash_hex` and `signature_hex`, verify the BLAKE2b
    matches the claimed hash, then Ed25519-verify against the
    reviewer's pubkey.

    Returns True iff both checks pass. False on any malformed row,
    missing field, or signature mismatch — the loop drops invalid
    rows silently rather than crashing.
    """
    try:
        reviewer_hex = record["reviewer"]
        sig_hex = record["signature_hex"]
        claimed_hash_hex = record["payload_hash_hex"]
    except KeyError:
        return False

    # Reconstruct canonical bytes from the fields the signer included.
    # `_sign_review_record` builds its payload dict and JSON-encodes
    # with sort_keys + tight separators; we mirror that exactly.
    payload = {k: v for k, v in record.items() if k not in ("payload_hash_hex", "signature_hex")}
    try:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        recomputed = hash_blake2b(canonical.encode("utf-8")).hex()
    except (TypeError, ValueError):
        return False
    if recomputed != claimed_hash_hex:
        return False

    try:
        pubkey = bytes.fromhex(reviewer_hex)
        signature = bytes.fromhex(sig_hex)
        payload_hash = bytes.fromhex(claimed_hash_hex)
    except ValueError:
        return False
    try:
        vk: VerifyKey = pubkey_from_bytes(pubkey)
    except Exception:
        return False
    return verify(vk, payload_hash, signature)


@dataclass
class ReceivedReviewIngest:
    """Tracks the byte offset in `reviews_received.jsonl` so each tick
    only processes newly-appended rows.

    Per-vacant; one instance per `GrowLoop`.
    """

    review_file: Path
    self_pubkey_hex: str
    _offset: int = 0
    _accepted_rows: list[dict[str, Any]] = field(default_factory=list)
    _rejected_count: int = 0

    @property
    def total_accepted(self) -> int:
        return len(self._accepted_rows)

    @property
    def total_rejected(self) -> int:
        return self._rejected_count

    def ingest_new(self) -> int:
        """Read newly-appended rows from `review_file`. Returns the
        number of valid rows accepted in this call.

        Rejected rows (bad signature, self-review, malformed JSON) are
        silently counted into `total_rejected`. A self-review is
        defined as `reviewer == target == self`; we ignore those
        because we don't grade ourselves through the same channel as
        peers (the self/peer eval gap goes through a separate
        aggregator path).
        """
        if not self.review_file.exists():
            return 0
        try:
            with self.review_file.open("rb") as f:
                f.seek(self._offset)
                new_bytes = f.read()
                self._offset = f.tell()
        except OSError:
            return 0
        if not new_bytes:
            return 0
        accepted = 0
        for raw_line in new_bytes.splitlines():
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                self._rejected_count += 1
                continue
            if not isinstance(record, dict):
                self._rejected_count += 1
                continue
            # Drop self-reviews — they're a separate channel
            # (`Aggregator.record_self_eval_gap`).
            if record.get("reviewer") == record.get("target") == self.self_pubkey_hex:
                self._rejected_count += 1
                continue
            # Only accept rows where the target IS us.
            if record.get("target") != self.self_pubkey_hex:
                self._rejected_count += 1
                continue
            if not verify_review_signature(record):
                self._rejected_count += 1
                continue
            self._accepted_rows.append(record)
            accepted += 1
        return accepted

    def compute_snapshot(self, *, min_n: int = 2) -> SelfReputationSnapshot:
        """Build a 5D snapshot from accepted reviews. Cold start when
        `n < min_n` returns `None` per-dim (dashboards display
        "insufficient")."""
        n = len(self._accepted_rows)
        if n < min_n:
            return SelfReputationSnapshot(
                n_reviews=n,
                factual=None,
                logical=None,
                relevance=None,
                honesty=None,
                adoption=None,
            )
        sums: dict[str, float] = {
            "factual": 0,
            "logical": 0,
            "relevance": 0,
            "honesty": 0,
            "adoption": 0,
        }
        counts: dict[str, int] = {k: 0 for k in sums}
        for row in self._accepted_rows:
            dims = row.get("dimensions", {})
            if not isinstance(dims, dict):
                continue
            for k in sums:
                v = dims.get(k)
                if isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0:
                    sums[k] += float(v)
                    counts[k] += 1
        means: dict[str, float | None] = {
            k: (sums[k] / counts[k]) if counts[k] > 0 else None for k in sums
        }
        return SelfReputationSnapshot(
            n_reviews=n,
            factual=means["factual"],
            logical=means["logical"],
            relevance=means["relevance"],
            honesty=means["honesty"],
            adoption=means["adoption"],
        )

    def recent_objective_score(self, *, window: int = 5) -> list[float]:
        """Combined (factual+logical+relevance)/3 for the most recent N
        accepted reviews. Used by `consecutive_low_review_window`."""
        out: list[float] = []
        for row in self._accepted_rows[-window:]:
            d = row.get("dimensions", {})
            if not isinstance(d, dict):
                continue
            vals = [d.get(k) for k in ("factual", "logical", "relevance")]
            nums = [float(v) for v in vals if isinstance(v, (int, float))]
            if not nums:
                continue
            out.append(sum(nums) / len(nums))
        return out


def consecutive_low_review_window(
    scores: list[float],
    *,
    threshold: float = 0.3,
    required_streak: int = 3,
) -> bool:
    """True iff the most-recent `required_streak` scores are ALL strictly
    below `threshold`.

    Matches the Pfix8 P8.6 rule lifted into the grow loop: 3 consecutive
    sub-0.3 reviews → time to spawn a successor.
    """
    if len(scores) < required_streak:
        return False
    tail = scores[-required_streak:]
    return all(s < threshold for s in tail)


# --- B. Self drift monitor --------------------------------------------------


@dataclass
class SelfDriftMonitor:
    """Tracks recent self-responses and detects STYLO drift.

    The anchor distribution is built from the first `anchor_window`
    responses; subsequent responses are compared via `compute_drift`.
    When `is_drifting(distance, threshold)` flips True, the monitor
    flags it and the GrowLoop emits a logbook entry — auditable trail
    of "this vacant's behaviour shifted at this moment".
    """

    anchor_window: int = 8
    _recent_responses: list[str] = field(default_factory=list)
    _anchor: AnchorDistribution | None = None
    _last_drift_value: float = 0.0

    @property
    def has_anchor(self) -> bool:
        return self._anchor is not None

    @property
    def last_drift(self) -> float:
        return self._last_drift_value

    def observe(self, response_text: str) -> bool:
        """Record a response; return True iff drift was just detected.

        The first `anchor_window` calls accumulate into the anchor (no
        drift can be detected until then). After that every call
        computes Mahalanobis-style distance vs the anchor.

        `compute_embedding` takes `Sequence[bytes]` (windows for the
        STYLO sketch); we chunk on whitespace so an embedding of "hello
        world foo" treats each token as a separate window. Empty
        responses are skipped — no point feeding silence into the
        anchor.
        """
        text = response_text.strip()
        if text:
            self._recent_responses.append(text)
        # Lazily build the anchor once we have enough data.
        if self._anchor is None:
            if len(self._recent_responses) < self.anchor_window:
                return False
            embeddings = [
                compute_embedding(self._as_windows(t))
                for t in self._recent_responses[: self.anchor_window]
            ]
            self._anchor = AnchorDistribution.from_history(embeddings)
            return False
        # Compute drift on the latest embedding.
        latest_embed = compute_embedding(self._as_windows(self._recent_responses[-1]))
        self._last_drift_value = compute_drift(latest_embed, self._anchor)
        return is_drifting(self._last_drift_value)

    @staticmethod
    def _as_windows(text: str) -> list[bytes]:
        """Split `text` into UTF-8 windows on whitespace.

        Each token becomes one window. Empty fallback uses a single
        zero-byte window so the embedding is well-defined.
        """
        tokens = text.split()
        if not tokens:
            return [b"\x00"]
        return [tok.encode("utf-8") for tok in tokens]
