"""DHT-style registry backend (technical.html §Roadmap: "Future: Federated
→ Distributed (IPFS-like)").

The federated backend (`federated.py`) does M-of-N quorum *reads* over a
fixed set of N peer registries. The DHT pattern goes one step further:
the peer set is **dynamic** and each piece of registry data lives on the
peers whose `node_id` is XOR-closest to the data's `record_key` (the
Kademlia routing model used by IPFS / BitTorrent DHT).

This module implements an **in-memory Kademlia-lite** so the codebase
has a *real* DHT shape (deterministic XOR distance, k-bucket fan-out,
replication factor) that an operator can later swap for a network-bound
implementation without touching `RegistryBackend` callers.

What this module gives you:

- `KademliaDHT(nodes=[...], k=20, replication=3)` — routing table +
  storage map. Each `node_id` is a 32-byte BLAKE2b hash (matches our
  `VacantId` width).
- `record_key(...)` — deterministic 32-byte key for a registry record
  (e.g. `vacant.vacant_id` for halos, `epoch.epoch_id` for epoch
  records). Same data → same key → same N closest nodes.
- `DHTBackend(dht=...)` — a thin `RegistryBackend`-shaped read surface
  that resolves each query to its closest `replication` nodes and
  returns the value held by ≥ ceil(replication/2) of them.

What this module does NOT give you:

- A real network. `KademliaDHT` is in-memory; "remote" nodes are local
  Python objects. The shape is wire-correct; the transport is a stub.
- BFT writes. Like `FederatedRegistryBackend`, writes go to the
  closest nodes but no consensus runs between them — operators handle
  divergence with `record_hash` quorum on reads.

The win: the existing `RegistryBackend.Protocol` extends to a fully
content-addressed, dynamic-membership topology without touching callers.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from vacant.core.crypto import hash_blake2b
from vacant.registry.errors import RegistryError
from vacant.registry.federated import record_hash

__all__ = [
    "DEFAULT_K",
    "DEFAULT_REPLICATION",
    "DHTBackend",
    "DHTError",
    "DHTNode",
    "KademliaDHT",
    "record_key",
    "xor_distance",
]


DEFAULT_K = 20
"""Standard Kademlia k-bucket size. Operators rarely need to tune this."""

DEFAULT_REPLICATION = 3
"""Number of closest nodes that store/serve each record. Quorum is
`ceil(replication / 2)` distinct agreeing copies."""


class DHTError(RegistryError):
    """Raised when a DHT operation fails (no closest nodes available,
    quorum unreachable, key length mismatch)."""


# --- node id + distance -----------------------------------------------------


def _node_id_bytes(seed: bytes) -> bytes:
    """Deterministically derive a 32-byte node id from an operator seed.

    Real DHT nodes use Ed25519 pubkeys or hashed peer ids; for the
    in-memory variant we accept any byte seed and BLAKE2b it. Same seed
    → same node id (load-bearing for tests + scenarios)."""
    return hash_blake2b(b"vacant:dht:node:" + seed)


def xor_distance(a: bytes, b: bytes) -> int:
    """Kademlia distance: bitwise XOR interpreted as a big-endian int.

    Two equal ids have distance 0; complementary ids have distance
    `2**(8*len(a)) - 1`. The total order on distance is what lets
    "closest N nodes" be well-defined.

    Raises `DHTError` on length mismatch — silently truncating would
    quietly degrade routing.
    """
    if len(a) != len(b):
        raise DHTError(f"xor_distance: key lengths differ ({len(a)} vs {len(b)})")
    return int.from_bytes(bytes(x ^ y for x, y in zip(a, b, strict=True)), "big")


def record_key(*parts: bytes | str | int) -> bytes:
    """Stable 32-byte DHT key for a logical registry record.

    Args:
        parts: Components that uniquely identify the record (e.g.
            (`"vacant"`, vacant_id_hex)). Strings are utf-8 encoded;
            ints are converted to decimal text. The function is a
            BLAKE2b hash over `0x1f`-joined components.

    Returns:
        32-byte key, suitable for `xor_distance` against a node id.
    """
    if not parts:
        raise DHTError("record_key requires at least one component")
    blob_parts: list[bytes] = []
    for p in parts:
        if isinstance(p, bytes):
            blob_parts.append(p)
        elif isinstance(p, str):
            blob_parts.append(p.encode("utf-8"))
        elif isinstance(p, int):
            blob_parts.append(str(int(p)).encode("utf-8"))
        else:
            raise DHTError(f"record_key: unsupported part type {type(p).__name__}")
    return hash_blake2b(b"vacant:dht:key:" + b"\x1f".join(blob_parts))


# --- node + DHT --------------------------------------------------------------


@dataclass
class DHTNode:
    """One in-memory DHT node.

    Each node has a deterministic `node_id` (32 bytes), an optional
    operator-supplied label (for debugging / dashboards), and a local
    `store` dict mapping `record_key → value`. The DHT puts copies of
    a value into the closest `replication` nodes; lookups consult those
    same nodes.
    """

    node_id: bytes
    label: str = ""
    store: dict[bytes, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.node_id) != 32:
            raise DHTError(f"DHTNode.node_id must be 32 bytes; got {len(self.node_id)}")

    @classmethod
    def from_seed(cls, seed: str | bytes, *, label: str = "") -> DHTNode:
        """Build a node whose id is a BLAKE2b hash of `seed`."""
        seed_b = seed.encode("utf-8") if isinstance(seed, str) else seed
        return cls(
            node_id=_node_id_bytes(seed_b),
            label=label or seed.decode("utf-8") if isinstance(seed, bytes) else (label or seed),
        )


@dataclass
class KademliaDHT:
    """In-memory Kademlia-lite DHT.

    Provides the routing primitive (`closest_nodes`) and a content-
    addressed put/get (`put` / `get_quorum`). The `RegistryBackend`-
    shaped adapter is `DHTBackend(dht=this)`.

    Attributes:
        nodes: All live nodes in the DHT. The "k-bucket" structure of
            real Kademlia is collapsed into a flat list — fine for
            in-memory; a network impl would split by XOR-prefix bucket
            for log(N) routing.
        k: k-bucket size. Default 20.
        replication: Number of closest nodes that store each value.
            Quorum on reads is `ceil(replication / 2)`.
    """

    nodes: list[DHTNode]
    k: int = DEFAULT_K
    replication: int = DEFAULT_REPLICATION

    def __post_init__(self) -> None:
        if self.k < 1:
            raise DHTError(f"k must be >= 1; got {self.k}")
        if self.replication < 1:
            raise DHTError(f"replication must be >= 1; got {self.replication}")
        if not self.nodes:
            raise DHTError("KademliaDHT requires at least one node")
        if self.replication > len(self.nodes):
            raise DHTError(
                f"replication ({self.replication}) must be <= len(nodes) ({len(self.nodes)})"
            )
        seen: set[bytes] = set()
        for n in self.nodes:
            if n.node_id in seen:
                raise DHTError(f"duplicate node id in KademliaDHT: {n.node_id.hex()[:8]}…")
            seen.add(n.node_id)

    @property
    def quorum_threshold(self) -> int:
        """ceil(replication / 2) — minimum distinct agreeing copies for
        a read to succeed."""
        return (self.replication + 1) // 2

    def closest_nodes(self, key: bytes, *, n: int | None = None) -> list[DHTNode]:
        """Return the `n` closest nodes to `key` (defaults to `replication`).

        Sorted by ascending `xor_distance(node_id, key)`. A real Kademlia
        would walk k-buckets; we just sort the full list — fine when the
        DHT lives in-process for testing.
        """
        n = n if n is not None else self.replication
        return sorted(self.nodes, key=lambda node: xor_distance(node.node_id, key))[:n]

    def put(self, key: bytes, value: Any) -> list[bytes]:
        """Store `value` at the `replication` closest nodes.

        Returns the node ids that received the write. A real
        implementation would also propagate via gossip after the
        initial replication put; we leave that to the operator-driven
        `GossipReplicator` (`gossip.py`) which is content-agnostic.
        """
        closest = self.closest_nodes(key)
        for node in closest:
            node.store[key] = value
        return [n.node_id for n in closest]

    def get_quorum(self, key: bytes) -> Any:
        """Read with `quorum_threshold` agreement across the `replication`
        closest nodes.

        Returns the value held by the most nodes (provided it crosses
        the threshold); raises `DHTError` otherwise. Same content-hash
        primitive as `FederatedRegistryBackend`.
        """
        closest = self.closest_nodes(key)
        counts: Counter[bytes] = Counter()
        by_hash: dict[bytes, Any] = {}
        for node in closest:
            v = node.store.get(key)
            h = record_hash(v) if v is not None else b"\x00" * 32
            counts[h] += 1
            by_hash.setdefault(h, v)
        if not counts:
            raise DHTError("no closest nodes")
        top_hash, top_count = counts.most_common(1)[0]
        if top_count < self.quorum_threshold:
            raise DHTError(
                f"DHT quorum not reached: top group has {top_count} of "
                f"{self.replication}; need {self.quorum_threshold}"
            )
        # If the agreed value is None, surface as "not found".
        return by_hash.get(top_hash)

    def iter_keys(self) -> Iterable[bytes]:
        """Union of every node's local key set (deduped). Used by tests
        + admin tools; not part of the canonical Kademlia API."""
        seen: set[bytes] = set()
        for node in self.nodes:
            for k in node.store:
                if k in seen:
                    continue
                seen.add(k)
                yield k


# --- backend adapter --------------------------------------------------------


class DHTBackend:
    """`RegistryBackend`-shaped read surface backed by a `KademliaDHT`.

    Write methods accept structured values and replicate them to the
    closest nodes — there is no canonical write authority in a DHT, so
    the "primary" concept that `RegistryStore` has doesn't apply. This
    is fine for the kinds of records the DHT layer holds (immutable
    halo announcements, sealed epoch roots); mutable per-vacant state
    should still live on a primary `RegistryStore`.
    """

    def __init__(self, dht: KademliaDHT) -> None:
        self._dht = dht

    @property
    def dht(self) -> KademliaDHT:
        return self._dht

    # --- mutators -----------------------------------------------------------

    async def put_vacant_record(self, vacant_id: str, record: Any) -> list[bytes]:
        """Store a halo-like record under `record_key("vacant", vid)`.

        Returns the node ids that received the write. The caller is
        free to set `record` to any picklable object; the DHT layer is
        content-agnostic. For type safety in MVP, pass either a
        `Vacant` SQLModel row or a dict matching its schema.
        """
        return await asyncio.to_thread(self._dht.put, record_key("vacant", vacant_id), record)

    async def put_epoch_record(self, epoch_id: int, record: Any) -> list[bytes]:
        return await asyncio.to_thread(self._dht.put, record_key("epoch", int(epoch_id)), record)

    # --- readers ------------------------------------------------------------

    async def get_vacant_record(self, vacant_id: str) -> Any:
        return await asyncio.to_thread(self._dht.get_quorum, record_key("vacant", vacant_id))

    async def get_epoch_record(self, epoch_id: int) -> Any:
        return await asyncio.to_thread(self._dht.get_quorum, record_key("epoch", int(epoch_id)))

    # --- diagnostics --------------------------------------------------------

    def closest_node_labels(self, *, kind: str, key_part: str | int) -> list[str]:
        """Return labels of the `replication` closest nodes for a key.

        Used by dashboards / debugging to visualise routing. Not part
        of the public Protocol.
        """
        return [
            n.label or n.node_id.hex()[:12]
            for n in self._dht.closest_nodes(record_key(kind, key_part))
        ]


def build_dht_from_seeds(
    seeds: Sequence[str],
    *,
    k: int = DEFAULT_K,
    replication: int = DEFAULT_REPLICATION,
) -> KademliaDHT:
    """Convenience: build a `KademliaDHT` from a list of human seeds.

    `seeds` is a list of operator-friendly strings (e.g. region names).
    Each becomes one `DHTNode`. Order doesn't matter — the topology is
    fixed by the XOR-distance metric, not insertion order.
    """
    nodes = [DHTNode.from_seed(s) for s in seeds]
    return KademliaDHT(nodes=nodes, k=k, replication=replication)
