from service import Queue

def test_ready():
    q = Queue()
    q.push("a", {}, 1)
    assert [job["id"] for job in q.ready(1)] == ["a"]
