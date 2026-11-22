import json
import pytest
import codec
from service import Queue


def test_order_limit_and_copies():
    q = Queue()
    payload = {"x": [1]}
    q.push("b", payload, 2)
    q.push("a", {}, 1)
    q.push("c", {}, 2)
    payload["x"].append(2)
    assert q.ready(5, limit=0) == []
    jobs = q.ready(5, limit=2)
    assert [j["id"] for j in jobs] == ["a", "b"]
    assert jobs[1]["payload"] == {"x": [1]}
    jobs[1]["payload"]["x"].append(9)
    assert q.claimed["b"]["payload"] == {"x": [1]}
    assert [j["id"] for j in q.ready(5)] == ["c"]


def test_retry_backoff_sequence_and_ack():
    q = Queue()
    q.push("a", {}, 0)
    q.push("b", {}, 5)
    (job,) = q.ready(0)
    q.retry(job, 0)
    assert q.pending[-1]["due"] == 2 and q.pending[-1]["attempts"] == 1
    with pytest.raises(ValueError, match="job is not claimed"):
        q.ack(job)
    (job2,) = q.ready(2)
    q.retry(job2, 2, base=0)
    assert q.pending[-1]["due"] == 2
    (job3,) = q.ready(5, limit=1)
    assert job3["id"] == "a" and job3["sequence"] == 0
    with pytest.raises(ValueError, match="duplicate job"):
        q.push("a", {})
    q.ack(job3)
    q.push("a", {})
    (j,) = q.ready(0)
    q.retry(j, 0, base=2, cap=1)
    assert q.pending[-1]["due"] == 1


def test_validation_does_not_mutate():
    q = Queue()
    q.push("a", {}, 0)
    before = q.export()
    for bad in (-1, True):
        with pytest.raises(ValueError, match="limit must be an integer >= 0"):
            q.ready(0, bad)
    (job,) = q.ready(0)
    state = q.export()
    with pytest.raises(ValueError):
        q.retry(job, -1)
    assert q.export() == state
    with pytest.raises(ValueError, match="job is not claimed"):
        q.ack({"id": "zzz"})
    assert before["pending"][0]["id"] == "a"


def test_codec_roundtrip_with_claims():
    q = Queue()
    q.push("a", {"n": 1}, 0)
    q.push("b", {}, 3)
    q.push("c", {}, 1)
    (job,) = q.ready(0)
    r = codec.loads(codec.dumps(q))
    assert r.export() == q.export()
    with pytest.raises(ValueError, match="duplicate job"):
        r.push("a", {})
    r.ack(job)
    assert [j["id"] for j in r.ready(9)] == ["c", "b"]
    e = codec.loads(codec.dumps(Queue()))
    assert e.export() == Queue().export()


def test_legacy_list_and_detached_export():
    raw = json.dumps([{"id": "x", "payload": {}, "due": 1},
                      {"id": "y", "payload": {}, "due": 1}])
    q = codec.loads(raw)
    assert [(j["sequence"], j["attempts"]) for j in q.pending] == [(0, 0), (1, 0)]
    exported = q.export()
    exported["pending"].clear()
    assert q.size() == 2
    assert codec.loads("[]").size() == 0
