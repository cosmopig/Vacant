import pytest
from service import Queue
from codec import loads, dumps

def test_queue_zero_limit_stability_and_detached_payload():
    # SPEC §1
    q = Queue()
    payload = {"items": [1]}
    q.push("z", payload, 1)
    q.push("a", {}, 1)
    payload["items"].append(2)
    assert q.ready(5, 0) == []
    jobs = q.ready(5)
    assert [job["id"] for job in jobs] == ["z", "a"]
    assert jobs[0]["payload"] == {"items":[1]}

def test_queue_retry_roundtrip_claim_and_backoff():
    # SPEC §2
    # SPEC §4
    q = loads('[{"id":"a","payload":{},"due":0}]')
    job = q.ready(0)[0]
    q = loads(dumps(q))
    q.retry(job, 3)
    with pytest.raises(ValueError, match="^job is not claimed$"):
        q.ack(job)
    assert q.ready(4) == []
    job2 = q.ready(5)[0]
    assert job2["attempts"] == 1
    q.retry(job2, 5, cap=3)
    assert q.ready(7) == []
    job3 = q.ready(8)[0]
    q.ack(job3)
    q.push("a", {}, 0)
    assert q.size() == 1
    assert loads(dumps(Queue())).size() == 0

def test_queue_errors_do_not_remove_jobs():
    # SPEC §3
    q = Queue()
    q.push("a", {}, 0)
    with pytest.raises(ValueError, match="^limit must be an integer >= 0$"):
        q.ready(0, True)
    assert q.size() == 1
    q.ready(0)
    with pytest.raises(ValueError, match="^duplicate job$"):
        q.push("a", {}, 0)
