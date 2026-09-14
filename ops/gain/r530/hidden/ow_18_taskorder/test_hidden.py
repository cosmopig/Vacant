"""ow_18_taskorder — hidden checks, 6. **Never enters a workspace.**

Generated from bank/ow_18_taskorder/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_every_job_exactly_once():
    # anchor_kind: goal
    # anchor: every job appears in the order exactly once, and a job that is only ever
    # mentioned as something else's prerequisite is still a job
    # derivation: the order is a permutation of every name that appears anywhere in the
    # table, keys and prerequisites alike.


    def _bank_entry(solution):
        jobs = {"c": ["a", "b"], "d": ["c"], "e": []}
        got = solution.plan(jobs)
        want = ["a", "b", "c", "d", "e"]
        assert sorted(got) == want, "args=%r got=%r want=%r" % (jobs, sorted(got), want)
        assert len(got) == len(set(got)), "args=%r got=%r want=%r" % (jobs, got, "no repeats")
    _bank_entry(solution)


def check_h02_nothing_runs_too_early():
    # anchor_kind: goal
    # anchor: nothing runs before something it waits for
    # derivation: for every job and every one of its prerequisites, the prerequisite
    # stands earlier in the order.


    def _bank_entry(solution):
        jobs = {"app": ["lib", "assets"], "lib": ["proto"], "assets": ["proto"],
                "proto": [], "docs": ["app"], "package": ["app", "docs"]}
        got = solution.plan(jobs)
        position = dict((name, index) for index, name in enumerate(got))
        for name, needs in jobs.items():
            for need in needs:
                assert position[need] < position[name], (
                    "args=%r got=%r want=%r" % (jobs, got, "%s before %s" % (need, name)))
    _bank_entry(solution)


def check_h03_same_table_same_order():
    # anchor_kind: goal
    # anchor: running the planner twice on the same table gives the same order
    # derivation: repeated calls on the same table return exactly the same list, so the
    # build log diffs cleanly.


    def _bank_entry(solution):
        jobs = {"x": [], "y": [], "z": ["x", "y"], "w": []}
        answers = [solution.plan(jobs) for _ in range(5)]
        assert all(answer == answers[0] for answer in answers), (
            "args=%r got=%r want=%r" % (jobs, answers, "five identical orders"))
    _bank_entry(solution)


def check_h04_circles_are_reported():
    # anchor_kind: goal
    # anchor: because some jobs wait on each other in a circle, directly or through
    # others
    # derivation: a two-job circle and a longer one both raise, including when other
    # jobs in the table could have been ordered perfectly well.


    def _bank_entry(solution):
        for jobs in ({"a": ["b"], "b": ["c"], "c": ["a"]},
                     {"ok": [], "a": ["b"], "b": ["a"], "also_ok": ["ok"]},
                     {"a": ["b"], "b": ["c"], "c": ["d"], "d": ["b"]}):
            try:
                solution.plan(jobs)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (jobs, "an order", "ValueError"))
    _bank_entry(solution)


def check_h05_a_job_waiting_on_itself():
    # anchor_kind: goal
    # anchor: or because a job waits on itself
    # derivation: a job listing its own name can never start, so the table is reported
    # rather than ordered.


    def _bank_entry(solution):
        for jobs in ({"a": ["a"]}, {"a": [], "b": ["b"], "c": ["a"]}):
            try:
                solution.plan(jobs)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (jobs, "an order", "ValueError"))
    _bank_entry(solution)


def check_h06_nothing_to_do():
    # anchor_kind: contract
    # anchor: `plan` returns a list of job names.
    # derivation: an empty table gives an empty list, and a table where nothing waits
    # for anything still returns every job once.


    def _bank_entry(solution):
        assert solution.plan({}) == [], "args=%r got=%r want=%r" % ({}, solution.plan({}), [])
        jobs = {"a": [], "b": [], "c": []}
        got = solution.plan(jobs)
        assert sorted(got) == ["a", "b", "c"], (
            "args=%r got=%r want=%r" % (jobs, sorted(got), ["a", "b", "c"]))
    _bank_entry(solution)
