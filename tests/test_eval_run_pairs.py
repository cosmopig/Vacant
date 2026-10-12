"""ops/eval/local/run_pairs.py：共用佇列的排程——配對同一台、先做已接下的、續跑回原來那台、過了時間上限不拿新的但接下的做完。"""
import collections
import pathlib
import sys
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ops" / "eval" / "local"))
from run_pairs import Queue, units  # noqa: E402


def _drain(q, machines):
    got, lock = [], threading.Lock()

    def worker(m):
        while True:
            c = q.take(m)
            if c is None:
                if q.pending(m):
                    continue
                return
            with lock:
                got.append(c)

    ts = [threading.Thread(target=worker, args=(m,)) for m in machines for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return got


def test_units_order_is_seeded_and_sample_major():
    a = units([str(i) for i in range(10)], ["A", "C"], [1, 2], 3)
    assert a == units([str(i) for i in range(10)], ["A", "C"], [1, 2], 3)
    assert [s for _, s, _ in a] == [1] * 10 + [2] * 10
    assert all(sorted(g) == ["A", "C"] for _, _, g in a)


def test_pairs_stay_on_one_machine_and_every_cell_runs_once():
    us = units([str(i) for i in range(30)], ["A", "C"], [1], 5)
    q = Queue(us, ["w", "x"], lambda a, t, s: False, lambda a, t, s: None, None)
    got = _drain(q, ["w", "x"])
    assert len(got) == 60 and len(set(got)) == 60
    per = collections.defaultdict(set)
    for t, _, s, m in got:
        per[(t, s)].add(m)
    assert all(len(v) == 1 for v in per.values())


def test_own_accepted_cell_comes_before_a_new_unit():
    us = units(["1", "2"], ["A", "C"], [1], 1)
    q = Queue(us, ["w"], lambda a, t, s: False, lambda a, t, s: None, None)
    first, second = q.take("w"), q.take("w")
    assert first[0] == second[0] and {first[1], second[1]} == {"A", "C"}


def test_resumed_half_pair_goes_back_to_the_machine_that_ran_the_other_half():
    us = units(["1"], ["A", "C"], [1], 1)
    q = Queue(us, ["w", "x"], lambda a, t, s: a == "A", lambda a, t, s: "x" if a == "A" else None, None)
    assert q.take("w") is None
    assert q.pending("x") and q.take("x") == ("1", "C", 1, "x")


def test_deadline_stops_new_units_but_finishes_an_accepted_pair():
    now = [0.0]
    us = units(["1", "2", "3"], ["A", "C"], [1], 1)
    q = Queue(us, ["w"], lambda a, t, s: False, lambda a, t, s: None, deadline=10.0, clock=lambda: now[0])
    first = q.take("w")
    now[0] = 11.0
    second = q.take("w")
    assert second is not None and second[0] == first[0]
    assert q.take("w") is None


def test_after_deadline_only_units_started_before_are_taken():
    now = [11.0]
    us = units(["1", "2", "3"], ["A", "C"], [1], 1)
    first_task = us[0][0]
    q = Queue(us, ["w"], lambda a, t, s: False, lambda a, t, s: None, deadline=10.0, clock=lambda: now[0],
              started={(us[1][0], 1)})
    got = [q.take("w"), q.take("w"), q.take("w")]
    assert {c[0] for c in got[:2]} == {us[1][0]} and got[2] is None
    assert first_task not in {c[0] for c in got[:2]}
