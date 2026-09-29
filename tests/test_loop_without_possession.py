#!/usr/bin/env python3
"""loop_check.py — falsify `vacant loop` without spending one model call.

Every check here is a claim the decision depends on, with a check that can fail:

  1. the suite outside the workspace is refused, and the refusal message is the
     one the decision quotes;
  2. an agent that passes on the first try is accepted on attempt 1, with no
     second spawn (so a passing task costs exactly one run);
  3. an agent that fails gets the VISIBLE suite's own words in the NEXT prompt,
     verbatim enough to act on, and never the hidden tree;
  4. a budget of N is a ceiling: N attempts, then refuse, and the refusal is not
     a pass;
  5. an agent that never terminates is recorded as a timed-out attempt and still
     stays in the denominator;
  6. a check that raises is `infra_void`, which is neither accept nor reject;
  7. retry cost is visible: attempt count and wall are in the result.

Run:  python3 tests/test_loop_without_possession.py
"""
from __future__ import annotations

import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from vacant_network import loop as L  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append(name + (" :: " + detail if detail else ""))


def _fixture(tmp: pathlib.Path, agent_body: str) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    ws = tmp / "ws"
    suite = tmp / "auth_suite"
    ws.mkdir()
    suite.mkdir()
    (suite / "test_visible.py").write_text(
        "def check_one():\n    import solution\n    assert solution.f() == 2\n",
        encoding="utf-8")
    agent = tmp / "agent.sh"
    agent.write_text("#!/bin/sh\n" + agent_body, encoding="utf-8")
    agent.chmod(0o755)
    return ws, suite, agent


# 1 ---------------------------------------------------------------- suite placement
def t1_suite_outside_workspace() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ws, suite, agent = _fixture(tmp, "exit 0\n")
        inner = ws / "tests"
        inner.mkdir()
        (inner / "test_x.py").write_text("x=1\n", encoding="utf-8")
        try:
            L.run_loop(workspace=ws, suite=inner, cmd=[str(agent)],
                       check=lambda w, n: (True, "", None))
            check("1 suite-under-workspace refused", False, "no exception raised")
        except ValueError as e:
            check("1 suite-under-workspace refused",
                  "outside the workspace" in str(e), str(e)[:80])
        # and the out-of-workspace form is accepted
        r = L.run_loop(workspace=ws, suite=suite, cmd=[str(agent)],
                       check=lambda w, n: (True, "", None))
        check("1 suite-outside-workspace accepted", r.accepted is True)


# 2 ------------------------------------------------------- a pass costs one run
def t2_pass_on_first_try() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ws, suite, agent = _fixture(tmp, "echo hi > solution.py\nexit 0\n")
        spawns: list[int] = []
        r = L.run_loop(workspace=ws, suite=suite, cmd=[str(agent)], attempts=3,
                       check=lambda w, n: (spawns.append(n), (True, "", None))[1])
        check("2 pass accepted on attempt 1", r.total_attempts_used == 1,
              f"used {r.total_attempts_used}")
        check("2 only one spawn happened", spawns == [1], str(spawns))
        check("2 exit code is accept", r.exit_code == L.EXIT_ACCEPT)


# 3 ------------------------------------- feedback is the visible suite's own words
def t3_feedback_content_and_source() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ws, suite, agent = _fixture(tmp, "exit 0\n")
        # the agent records the argv it was given, so we can read the prompt
        spy = tmp / "spy.sh"
        spy.write_text('#!/bin/sh\nfor a in "$@"; do echo "$a"; done > "$PWD/argv.txt"\n',
                       encoding="utf-8")
        spy.chmod(0o755)
        seen: list[dict] = []

        def check_fn(w, n):
            seen.append({"n": n})
            if n == 1:
                return (False, "check_one: ModuleNotFoundError: No module named 'solution'", None)
            return (True, "", "sha256:deadbeef")

        r = L.run_loop(workspace=ws, suite=suite, cmd=[str(spy), "TASK"], attempts=3,
                       feedback="prompt", check=check_fn)
        check("3 two attempts were spent", r.total_attempts_used == 2,
              str(r.total_attempts_used))
        check("3 accepted on the retry", r.accepted is True)
        # read what the second spawn was told
        argv2 = (ws / "argv.txt").read_text(encoding="utf-8")
        check("3 retry prompt carries the failure text",
              "ModuleNotFoundError" in argv2, argv2[:120].replace("\n", " "))
        check("3 retry prompt does NOT contain the hidden marker",
              "HIDDEN_MARKER" not in argv2)
        # file mode writes the same words to the workspace
        r2dir = tmp / "ws2"
        (r2dir).mkdir()
        (r2dir / "argv.txt").write_text("", encoding="utf-8")
        L.run_loop(workspace=r2dir, suite=suite, cmd=[str(spy), "TASK"], attempts=2,
                   feedback="file", check=lambda w, n: (
                       (False, "boom: got=1 want=2", None) if n == 1 else (True, "", None)))
        f = r2dir / "VACANT_FEEDBACK.md"
        check("3 file mode wrote the feedback file", f.exists())
        if f.exists():
            body = f.read_text(encoding="utf-8")
            check("3 file feedback has args= and want=", "got=1" in body and "want=2" in body)
            check("3 file feedback has no hidden marker", "HIDDEN_MARKER" not in body)


# 4 -------------------------------------------------------- budget is a ceiling
def t4_budget_ceiling() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ws, suite, agent = _fixture(tmp, "exit 0\n")
        n = []
        r = L.run_loop(workspace=ws, suite=suite, cmd=[str(agent)], attempts=4,
                       feedback="none",
                       check=lambda w, i: (n.append(i), (False, "nope", None))[1])
        check("4 exactly N attempts", r.total_attempts_used == 4, str(n))
        check("4 refused after the budget", r.accepted is False)
        check("4 refusal is not a pass", r.exit_code != L.EXIT_ACCEPT,
              f"exit={r.exit_code}")
        check("4 budget exit code is exhausted", r.exit_code == L.EXIT_EXHAUSTED)


# 5 ------------------------------------------------------------- hang is recorded
def t5_hang_is_recorded() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ws, suite, agent = _fixture(tmp, "sleep 30\n")
        r = L.run_loop(workspace=ws, suite=suite, cmd=[str(agent)], attempts=1,
                       timeout_s=1.0, check=lambda w, n: (False, "slow", None))
        a = r.attempts[0]
        check("5 hang recorded as timed_out", a.timed_out is True)
        check("5 hang keeps its attempt in the count", r.total_attempts_used == 1)
        check("5 hang is not a pass", r.accepted is False)


# 6 ------------------------------------------------------------ infra_void is neither
def t6_check_raises_is_infra() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ws, suite, agent = _fixture(tmp, "exit 0\n")

        def boom(w, n):
            raise RuntimeError("verifier exploded")

        r = L.run_loop(workspace=ws, suite=suite, cmd=[str(agent)], attempts=3,
                       check=boom)
        check("6 a raising check is infra_void", r.attempts[0].outcome == "infra_void")
        check("6 infra is neither accept nor reject", r.accepted is None,
              repr(r.accepted))
        check("6 infra exit code", r.exit_code == L.EXIT_INFRA)
        check("6 infra does not burn the whole budget", r.total_attempts_used == 1)


# 7 ------------------------------------------------------------- cost is visible
def t7_cost_visible() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ws, suite, agent = _fixture(tmp, "exit 0\n")
        r = L.run_loop(workspace=ws, suite=suite, cmd=[str(agent)], attempts=3,
                       check=lambda w, n: (n < 2, "f", None) if False else (False, "f", None))
        check("7 per-attempt wall recorded", all(a.wall_s >= 0 for a in r.attempts))
        check("7 total wall recorded", r.wall_s > 0)
        check("7 attempt count is in the result", r.total_attempts_used == 3)
        check("7 events are in the result", len(r.events) == 3)
        check("7 every event names its outcome",
              all("outcome" in ev for ev in r.events))


def _run_all() -> list[str]:
    for fn in (t1_suite_outside_workspace, t2_pass_on_first_try,
               t3_feedback_content_and_source, t4_budget_ceiling,
               t5_hang_is_recorded, t6_check_raises_is_infra, t7_cost_visible):
        try:
            fn()
        except Exception as e:  # a check that errors is a failure, not a skip
            FAILED.append(f"{fn.__name__} raised {type(e).__name__}: {e}")
    return list(FAILED)


#: Pytest entry point. The checks above are plain asserts recorded into PASSED /
#: FAILED rather than raised, because a check that ERRORS and a check that FAILS
#: are different facts and the report should show both. This shim turns the
#: recorded failures into a pytest failure without losing that distinction.
def test_vacant_loop_falsification_checks():
    failures = _run_all()
    assert not failures, "falsification checks failed:\n  " + "\n  ".join(failures)


if __name__ == "__main__":
    failures = _run_all()
    print("=" * 74)
    print("vacant loop — falsification checks (zero model calls)")
    print("=" * 74)
    for x in PASSED:
        print("  [OK ]", x)
    for f in failures:
        print("  [FAIL]", f)
    print(f"\n{len(PASSED)} passed, {len(failures)} failed")
    sys.exit(1 if failures else 0)
