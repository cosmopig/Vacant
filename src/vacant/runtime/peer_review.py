"""Idle peer review tick (Pfix8 P8.5).

technical.html §02 ("Peer Review") + §03 ("five-dimensional reputation"):
when this vacant is idle, it picks a sibling peer with low signal,
sends a signed A2A probe envelope to that peer's HTTP endpoint, scores
the response along the five canonical dimensions, signs the review,
and appends a JSONL row to the peer's
``~/.vacant/<peer>/reviews_received.jsonl``. The review is keyed by
the reviewer's vacant_id so an aggregator can later filter out
same-source reviews per technical.html §03 ("same-LLM down-weight").

This module is deliberately a plain function — not a long-running
asyncio loop. ``vacant serve`` schedules a wakeup against it on a
configurable interval; tests call it directly. Skipping the loop
machinery here keeps the tick pure-data-in / pure-effects-out, which
matters because the tick is also the smallest unit a P8.7 verification
on the VM has to exercise.

Heuristic scoring is intentionally simple. The thesis claim doesn't
hinge on reviewers being smart — it hinges on reviewers being many,
diverse, and signed. The aggregator (P8.4 + P3) handles signal
quality. Replace the heuristic with an LLM-driven scorer when
``--substrate=ollama`` is wired into the loop (P8.5 follow-up).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vacant.cli import local_store as ls
from vacant.core.crypto import SigningKey, hash_blake2b
from vacant.core.types import EMPTY_PREV_HASH, ResidentForm, VacantId
from vacant.protocol.envelope import (
    A2AMessage,
    A2APart,
    VacantEnvelope,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)

__all__ = [
    "PROBE_PROMPT",
    "PeerReviewTickResult",
    "peer_review_tick",
    "score_response_heuristic",
    "select_peer",
]


PROBE_PROMPT = "self_describe"
"""A2A payload text used as the probe content. Peer's behavior receives
this as the user prompt; under the default echo behavior the response
is "echo from <peer>: self_describe" — heuristic scorer extracts
length / non-empty signal from that."""


class PeerReviewTickResult:
    """Outcome of a single peer-review tick."""

    __slots__ = (
        "delivered_to",
        "dimensions",
        "error",
        "probe_envelope_id_hex",
        "reviewer_vacant_id_hex",
        "skipped_reason",
        "target_vacant_id_hex",
    )

    def __init__(
        self,
        *,
        reviewer_vacant_id_hex: str,
        target_vacant_id_hex: str | None = None,
        delivered_to: str | None = None,
        probe_envelope_id_hex: str | None = None,
        dimensions: dict[str, float] | None = None,
        error: str | None = None,
        skipped_reason: str | None = None,
    ):
        self.reviewer_vacant_id_hex = reviewer_vacant_id_hex
        self.target_vacant_id_hex = target_vacant_id_hex
        self.delivered_to = delivered_to
        self.probe_envelope_id_hex = probe_envelope_id_hex
        self.dimensions = dimensions
        self.error = error
        self.skipped_reason = skipped_reason


def select_peer(
    *,
    self_vacant_id_hex: str,
    home: Path,
    review_count_max: int = 5,
) -> tuple[str, ls.LocalMeta] | None:
    """Pick a peer to review.

    Criteria:
    - Not this vacant.
    - Lives under the same VACANT_HOME directory.
    - meta.endpoint is set (the peer is serving).
    - The peer's reviews_received.jsonl has < `review_count_max` rows
      (low-signal vacants get priority).

    Returns ``(name, meta)`` or ``None`` when no eligible peer exists.
    """
    if not home.exists():
        return None
    candidates: list[tuple[int, str, ls.LocalMeta]] = []
    for entry in sorted(home.iterdir()):
        if not entry.is_dir() or not (entry / "meta.json").exists():
            continue
        try:
            meta = ls.load_meta(entry.name)
        except (ls.LocalVacantError, OSError, ValueError):  # pragma: no cover
            continue
        if meta.vacant_id_hex == self_vacant_id_hex:
            continue
        if not meta.endpoint:
            continue
        reviews_path = entry / "reviews_received.jsonl"
        count = 0
        if reviews_path.exists():
            try:
                with reviews_path.open(encoding="utf-8") as f:
                    count = sum(1 for line in f if line.strip())
            except OSError:  # pragma: no cover
                continue
        if count >= review_count_max:
            continue
        candidates.append((count, entry.name, meta))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], t[1]))
    _, name, meta = candidates[0]
    return name, meta


def score_response_heuristic(response_text: str, *, request_text: str = "") -> dict[str, float]:
    """Heuristic 5D scorer.

    Real reviewers would use an LLM to judge each dimension; this
    placeholder uses cheap signals (length, non-empty, refusal markers)
    so the peer-review loop can run without any LLM dependency.
    """
    text = response_text.strip()
    n = len(text)
    refusal = any(
        marker in text.lower()
        for marker in ("i cannot", "i can't", "refuse", "unable to", "not allowed")
    )
    # Echo-like response (default child behavior) — still useful as a
    # baseline live signal but should NOT score top marks.
    is_echo = "echo from" in text.lower() or (request_text and request_text in text)

    if not text:
        return {
            "factual": 0.1,
            "logical": 0.1,
            "relevance": 0.1,
            "honesty": 0.5,
            "adoption": 0.1,
        }
    if refusal:
        return {
            "factual": 0.4,
            "logical": 0.5,
            "relevance": 0.3,
            "honesty": 0.8,
            "adoption": 0.2,
        }
    base = min(0.9, 0.4 + n / 400.0)
    if is_echo:
        base = min(base, 0.55)
    return {
        "factual": round(base, 3),
        "logical": round(base * 0.95, 3),
        "relevance": round(base, 3),
        "honesty": 0.7,
        "adoption": 0.4,
    }


def _sign_review_record(
    *,
    reviewer: VacantId,
    target: VacantId,
    dimensions: dict[str, float],
    substrate: str,
    call_envelope_id_hex: str,
    claim: str,
    issued_at_iso: str,
    signing_key: SigningKey,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "reviewer": reviewer.hex(),
        "target": target.hex(),
        "dimensions": dimensions,
        "substrate": substrate,
        "call_envelope_id_hex": call_envelope_id_hex,
        "claim": claim,
        "issued_at": issued_at_iso,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = hash_blake2b(canonical.encode("utf-8"))
    signature = signing_key.sign(payload_hash).signature
    return {
        **payload,
        "payload_hash_hex": payload_hash.hex(),
        "signature_hex": signature.hex(),
    }


async def peer_review_tick(
    *,
    self_form: ResidentForm,
    self_signing_key: SigningKey,
    home: Path | None = None,
    review_count_max: int = 5,
    http_post: Any | None = None,
) -> PeerReviewTickResult:
    """One peer-review pass. Pure-data-in / persisted-effects-out.

    Effects (when a peer is selected):
    - Signed A2A probe envelope sent to ``peer.meta.endpoint`` via
      ``http_post`` (injectable for tests; defaults to ``httpx.AsyncClient.post``).
    - Signed review record appended to
      ``~/.vacant/<peer>/reviews_received.jsonl``.

    Returns a ``PeerReviewTickResult`` describing what happened so
    callers can log / aggregate. ``error`` is non-None when the
    network probe failed; ``skipped_reason`` is non-None when no peer
    was eligible.
    """
    home = home or ls.vacant_home()
    self_hex = self_form.identity.hex()

    chosen = select_peer(
        self_vacant_id_hex=self_hex,
        home=home,
        review_count_max=review_count_max,
    )
    if chosen is None:
        return PeerReviewTickResult(
            reviewer_vacant_id_hex=self_hex,
            skipped_reason="no_eligible_peer",
        )
    peer_name, peer_meta = chosen
    peer_vid = VacantId(pubkey_bytes=bytes.fromhex(peer_meta.vacant_id_hex))

    probe_env = VacantEnvelope(
        from_vacant_id=self_form.identity,
        to_vacant_id=peer_vid,
        sequence_no=1,
        timestamp=datetime.now(UTC),
        prev_envelope_hash=EMPTY_PREV_HASH,
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text=PROBE_PROMPT)]),
        idempotency_key=f"peer-review-probe-{int(datetime.now(UTC).timestamp() * 1000)}",
    ).signed(self_signing_key)
    wire = to_a2a_jsonrpc(probe_env)
    probe_id_hex = probe_env.compute_hash().hex()

    if http_post is None:  # pragma: no cover -- live httpx exercised by integration tests
        import httpx as _httpx

        async def _default_post(url: str, json_body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            async with _httpx.AsyncClient(timeout=30.0) as cli:
                r = await cli.post(url, json=json_body)
                return r.status_code, r.json()

        http_post = _default_post

    assert peer_meta.endpoint is not None  # narrowed by select_peer
    url = f"{peer_meta.endpoint.rstrip('/')}/a2a/message/send"
    try:
        status, body = await http_post(url, wire)
    except Exception as exc:
        return PeerReviewTickResult(
            reviewer_vacant_id_hex=self_hex,
            target_vacant_id_hex=peer_vid.hex(),
            probe_envelope_id_hex=probe_id_hex,
            error=f"probe_http_failed: {exc}",
        )
    if status != 200 or "result" not in body or "message" not in body.get("result", {}):
        return PeerReviewTickResult(
            reviewer_vacant_id_hex=self_hex,
            target_vacant_id_hex=peer_vid.hex(),
            probe_envelope_id_hex=probe_id_hex,
            error=f"probe_bad_response: status={status}",
        )

    try:
        response_env = from_a2a_jsonrpc(
            {
                "jsonrpc": "2.0",
                "id": body.get("id", "rsp"),
                "method": "message/send",
                "params": {"message": body["result"]["message"]},
            }
        )
        response_env.verify_or_raise(peer_vid.verify_key())
    except Exception as exc:
        return PeerReviewTickResult(
            reviewer_vacant_id_hex=self_hex,
            target_vacant_id_hex=peer_vid.hex(),
            probe_envelope_id_hex=probe_id_hex,
            error=f"probe_signature: {exc}",
        )

    response_text = " ".join(p.text for p in response_env.payload.parts)
    dimensions = score_response_heuristic(response_text, request_text=PROBE_PROMPT)
    issued_at_iso = datetime.now(UTC).isoformat()
    signed_record = _sign_review_record(
        reviewer=self_form.identity,
        target=peer_vid,
        dimensions=dimensions,
        substrate="peer-review:heuristic",
        call_envelope_id_hex=probe_id_hex,
        claim="idle peer-review probe; heuristic scorer",
        issued_at_iso=issued_at_iso,
        signing_key=self_signing_key,
    )

    peer_dir = home / peer_name
    with (peer_dir / "reviews_received.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(signed_record, sort_keys=True) + "\n")

    return PeerReviewTickResult(
        reviewer_vacant_id_hex=self_hex,
        target_vacant_id_hex=peer_vid.hex(),
        delivered_to=str(peer_dir / "reviews_received.jsonl"),
        probe_envelope_id_hex=probe_id_hex,
        dimensions=dimensions,
    )
