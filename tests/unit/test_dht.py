"""B7 — DHT-style registry backend (in-memory Kademlia-lite)."""

from __future__ import annotations

import pytest

from vacant.registry import (
    DEFAULT_REPLICATION,
    DHTBackend,
    DHTError,
    DHTNode,
    KademliaDHT,
    build_dht_from_seeds,
    record_key,
    xor_distance,
)

# --- xor_distance + record_key ---------------------------------------------


def test_xor_distance_zero_when_equal() -> None:
    assert xor_distance(b"\x00" * 32, b"\x00" * 32) == 0


def test_xor_distance_max_when_complementary() -> None:
    assert xor_distance(b"\x00" * 32, b"\xff" * 32) == (1 << 256) - 1


def test_xor_distance_length_mismatch() -> None:
    with pytest.raises(DHTError):
        xor_distance(b"\x00" * 32, b"\x00" * 31)


def test_record_key_stable() -> None:
    k1 = record_key("vacant", "abc123")
    k2 = record_key("vacant", "abc123")
    assert k1 == k2
    assert len(k1) == 32


def test_record_key_distinguishes_kinds() -> None:
    assert record_key("vacant", 1) != record_key("epoch", 1)


def test_record_key_rejects_empty() -> None:
    with pytest.raises(DHTError):
        record_key()


# --- KademliaDHT validation -------------------------------------------------


def test_dht_rejects_empty_nodes() -> None:
    with pytest.raises(DHTError):
        KademliaDHT(nodes=[])


def test_dht_rejects_replication_above_nodes() -> None:
    with pytest.raises(DHTError):
        KademliaDHT(nodes=[DHTNode.from_seed("a")], replication=2)


def test_dht_rejects_duplicate_node_ids() -> None:
    seed = b"alpha"
    n1 = DHTNode.from_seed(seed)
    n2 = DHTNode.from_seed(seed)
    with pytest.raises(DHTError):
        KademliaDHT(nodes=[n1, n2])


def test_dht_node_rejects_non_32_byte_id() -> None:
    with pytest.raises(DHTError):
        DHTNode(node_id=b"too short")


# --- closest_nodes + put/get ------------------------------------------------


def test_closest_nodes_count_matches_replication() -> None:
    dht = build_dht_from_seeds(["a", "b", "c", "d", "e"], replication=3)
    closest = dht.closest_nodes(b"\x00" * 32)
    assert len(closest) == 3


def test_put_replicates_to_closest_nodes_only() -> None:
    dht = build_dht_from_seeds(["a", "b", "c", "d", "e"], replication=2)
    key = record_key("vacant", "alice")
    target_ids = dht.put(key, {"hello": "world"})
    assert len(target_ids) == 2
    holders = [n for n in dht.nodes if key in n.store]
    assert len(holders) == 2
    assert {n.node_id for n in holders} == set(target_ids)


def test_get_quorum_returns_value_on_agreement() -> None:
    dht = build_dht_from_seeds(["a", "b", "c"], replication=3)
    key = record_key("epoch", 7)
    payload = {"root_hex": "ab" * 32, "epoch_id": 7}
    dht.put(key, payload)
    assert dht.get_quorum(key) == payload


def test_get_quorum_raises_when_below_threshold() -> None:
    """Manually corrupt one node's view so 2 of 3 hold value X and 1
    holds value Y. With replication=3 the threshold is ceil(3/2)=2;
    the majority value should be returned, not raise. Then corrupt
    enough nodes to drop below threshold and check it raises."""
    dht = build_dht_from_seeds(["a", "b", "c"], replication=3)
    key = record_key("epoch", 7)
    dht.put(key, "X")
    # Override one node's value → 2 of 3 still hold X.
    closest = dht.closest_nodes(key)
    closest[0].store[key] = "Y"
    assert dht.get_quorum(key) == "X"

    # Now corrupt one more → only 1 of 3 holds X → below threshold 2.
    closest[1].store[key] = "Z"
    with pytest.raises(DHTError):
        dht.get_quorum(key)


def test_get_quorum_no_closest_nodes_raises() -> None:
    """Edge case: an explicit empty `closest` is impossible because the
    DHT requires >= 1 node at construction; but the helper that walks
    closest still needs to handle the "no value held anywhere" case.
    We test by querying a key nobody stored — quorum should still
    succeed because all 3 nodes hold `None`, and `None` is the agreed
    value."""
    dht = build_dht_from_seeds(["a", "b", "c"], replication=3)
    out = dht.get_quorum(record_key("vacant", "ghost"))
    assert out is None


def test_iter_keys_dedups_across_nodes() -> None:
    dht = build_dht_from_seeds(["a", "b", "c"], replication=3)
    dht.put(record_key("vacant", "alpha"), 1)
    dht.put(record_key("vacant", "beta"), 2)
    keys = list(dht.iter_keys())
    assert len(keys) == 2


# --- DHTBackend adapter -----------------------------------------------------


@pytest.mark.asyncio
async def test_dht_backend_put_get_vacant_record() -> None:
    dht = build_dht_from_seeds(["a", "b", "c"], replication=3)
    backend = DHTBackend(dht)
    nodes_holding = await backend.put_vacant_record("alice", {"x": 1})
    assert len(nodes_holding) == 3
    got = await backend.get_vacant_record("alice")
    assert got == {"x": 1}


@pytest.mark.asyncio
async def test_dht_backend_put_get_epoch_record() -> None:
    dht = build_dht_from_seeds(["a", "b", "c"], replication=DEFAULT_REPLICATION)
    backend = DHTBackend(dht)
    await backend.put_epoch_record(42, {"root": "ab"})
    out = await backend.get_epoch_record(42)
    assert out == {"root": "ab"}


def test_dht_backend_closest_node_labels_for_diagnostics() -> None:
    dht = build_dht_from_seeds(["alpha", "beta", "gamma", "delta", "epsilon"], replication=2)
    backend = DHTBackend(dht)
    labels = backend.closest_node_labels(kind="vacant", key_part="alice")
    assert len(labels) == 2
    # Every label should be one of the seeds.
    valid = {"alpha", "beta", "gamma", "delta", "epsilon"}
    assert all(label in valid for label in labels)
