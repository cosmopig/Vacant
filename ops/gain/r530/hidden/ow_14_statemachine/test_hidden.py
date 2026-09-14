"""ow_14_statemachine — hidden checks, 12. **Never enters a workspace.**

Generated from bank/ow_14_statemachine/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_history_starts_at_the_beginning():
    # anchor_kind: goal
    # anchor: starting from where it began
    # derivation: before anything has happened the path already holds the starting
    # state, so support staff can see where the order came from.

    SPEC = {"queued": {"start": "running"}, "running": {}}


    def _bank_entry(solution):
        machine = solution.Machine(SPEC, "queued")
        got = machine.history()
        assert got == ["queued"], "args=%r got=%r want=%r" % ("a fresh machine", got, ["queued"])
    _bank_entry(solution)


def check_h02_refusal_names_both_halves():
    # anchor_kind: contract
    # anchor: it raises `ValueError` naming the state and the event
    # derivation: the message has to carry the state the order is in and the event that
    # was asked for, so a support ticket can be answered from the log alone.

    SPEC = {"paid": {"ship": "shipped"}, "shipped": {}}


    def _bank_entry(solution):
        machine = solution.Machine(SPEC, "paid")
        try:
            machine.fire("cancel")
        except ValueError as exc:
            text = str(exc)
            assert "paid" in text and "cancel" in text, (
                "args=%r got=%r want=%r" % ("fire('cancel') in paid", text, "a message naming paid and cancel"))
            return
        raise AssertionError("args=%r got=%r want=%r" % ("fire('cancel') in paid", "moved", "ValueError"))
    _bank_entry(solution)


def check_h03_refusal_leaves_no_trace():
    # anchor_kind: goal
    # anchor: has to leave the order exactly where it was, in state and in record
    # derivation: after several refused events the state and the path are exactly what
    # they were before them.

    SPEC = {"one": {"next": "two"}, "two": {}}


    def _bank_entry(solution):
        machine = solution.Machine(SPEC, "one")
        machine.fire("next")
        before_state, before_history = machine.state, machine.history()
        for event in ("next", "back", "explode"):
            try:
                machine.fire(event)
            except ValueError:
                pass
        assert machine.state == before_state, (
            "args=%r got=%r want=%r" % ("three refusals", machine.state, before_state))
        assert machine.history() == before_history, (
            "args=%r got=%r want=%r" % ("three refusals", machine.history(), before_history))
    _bank_entry(solution)


def check_h04_can_matches_fire():
    # anchor_kind: contract
    # anchor: `.can(event)` is True exactly when the current state's mapping has that
    # event.
    # derivation: for every state and every event name in play, can() and whether fire()
    # succeeds must agree.

    SPEC = {"a": {"x": "b", "y": "a"}, "b": {"x": "a"}}


    def _bank_entry(solution):
        for state in ("a", "b"):
            for event in ("x", "y", "z"):
                machine = solution.Machine(SPEC, state)
                allowed = machine.can(event)
                try:
                    machine.fire(event)
                    happened = True
                except ValueError:
                    happened = False
                assert allowed is happened, (
                    "args=%r got=%r want=%r" % ((state, event), (allowed, happened), "they agree"))
    _bank_entry(solution)


def check_h05_self_transition_is_recorded():
    # anchor_kind: goal
    # anchor: Something that puts an order back into the state it was already in still
    # happened and belongs in that path.
    # derivation: an event whose target is the state it started from still appends to
    # the path, so the path grows by one each time.

    SPEC = {"idle": {"poke": "idle", "go": "busy"}, "busy": {}}


    def _bank_entry(solution):
        machine = solution.Machine(SPEC, "idle")
        for _ in range(3):
            got = machine.fire("poke")
            assert got == "idle", "args=%r got=%r want=%r" % ("fire('poke')", got, "idle")
        want = ["idle", "idle", "idle", "idle"]
        assert machine.history() == want, (
            "args=%r got=%r want=%r" % ("three pokes", machine.history(), want))
    _bank_entry(solution)


def check_h06_history_is_a_copy():
    # anchor_kind: contract
    # anchor: `.history()` hands back a copy: changing the returned list does not change
    # the machine.
    # derivation: a caller who clears or appends to what they were given must not be
    # able to rewrite the order's past.

    SPEC = {"a": {"go": "b"}, "b": {}}


    def _bank_entry(solution):
        machine = solution.Machine(SPEC, "a")
        machine.fire("go")
        borrowed = machine.history()
        borrowed.append("forged")
        borrowed.clear()
        got = machine.history()
        assert got == ["a", "b"], "args=%r got=%r want=%r" % ("after mangling the copy", got, ["a", "b"])
    _bank_entry(solution)


def check_h07_reset_starts_over():
    # anchor_kind: goal
    # anchor: there has to be a way to start over
    # derivation: after reset the machine is in the starting state and its path is just
    # that state, and it still works afterwards.

    SPEC = {"new": {"pay": "paid"}, "paid": {"ship": "done"}, "done": {}}


    def _bank_entry(solution):
        machine = solution.Machine(SPEC, "new")
        machine.fire("pay")
        machine.fire("ship")
        machine.reset()
        assert machine.state == "new", "args=%r got=%r want=%r" % ("after reset", machine.state, "new")
        assert machine.history() == ["new"], (
            "args=%r got=%r want=%r" % ("after reset", machine.history(), ["new"]))
        got = machine.fire("pay")
        assert got == "paid", "args=%r got=%r want=%r" % ("fire after reset", got, "paid")
    _bank_entry(solution)


def check_h08_unknown_start_state():
    # anchor_kind: goal
    # anchor: a starting state that is not on the whiteboard at all
    # derivation: the mistake is reported when the rules are handed over, so building
    # the machine raises rather than the first event failing.

    SPEC = {"a": {"go": "b"}, "b": {}}


    def _bank_entry(solution):
        for start in ("c", "", "A"):
            try:
                solution.Machine(SPEC, start)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (start, "constructed", "ValueError"))
    _bank_entry(solution)


def check_h09_target_state_must_exist():
    # anchor_kind: goal
    # anchor: Rules that point at a state nobody defined
    # derivation: an event leading somewhere that is not a state is caught at hand-over,
    # even when no order would ever reach it.


    def _bank_entry(solution):
        spec = {"a": {"go": "b"}, "b": {"onward": "nowhere"}}
        try:
            solution.Machine(spec, "a")
        except ValueError:
            return
        raise AssertionError("args=%r got=%r want=%r" % (spec, "constructed", "ValueError"))
    _bank_entry(solution)


def check_h10_dead_end_states_are_fine():
    # anchor_kind: contract
    # anchor: Every state the machine can be in appears as a key of `spec`, even when it
    # has no events of its own.
    # derivation: a state with an empty mapping is a legitimate end of the line: it
    # builds, it can be reached, and everything is refused from there.


    def _bank_entry(solution):
        spec = {"open": {"close": "closed"}, "closed": {}}
        machine = solution.Machine(spec, "open")
        machine.fire("close")
        assert machine.can("close") is False, (
            "args=%r got=%r want=%r" % ("can('close') in closed", machine.can("close"), False))
        try:
            machine.fire("close")
        except ValueError:
            assert machine.state == "closed", (
                "args=%r got=%r want=%r" % ("state after refusal", machine.state, "closed"))
            return
        raise AssertionError("args=%r got=%r want=%r" % ("fire('close') in closed", "moved", "ValueError"))
    _bank_entry(solution)


def check_h11_two_machines_do_not_share():
    # anchor_kind: goal
    # anchor: They run the same rules for the next order
    # derivation: two machines built from the same rules keep their own state and their
    # own path, so moving one does not move the other.

    SPEC = {"a": {"go": "b"}, "b": {"go": "c"}, "c": {}}


    def _bank_entry(solution):
        first = solution.Machine(SPEC, "a")
        second = solution.Machine(SPEC, "a")
        first.fire("go")
        first.fire("go")
        assert second.state == "a", "args=%r got=%r want=%r" % ("the second machine", second.state, "a")
        assert second.history() == ["a"], (
            "args=%r got=%r want=%r" % ("the second machine", second.history(), ["a"]))
    _bank_entry(solution)


def check_h12_long_path_in_order():
    # anchor_kind: goal
    # anchor: They want the path an order took, in order
    # derivation: over a longer run through a cycle the path holds every state in the
    # order it was entered, with repeats kept.

    SPEC = {"a": {"go": "b"}, "b": {"go": "c", "back": "a"}, "c": {"back": "b"}}


    def _bank_entry(solution):
        machine = solution.Machine(SPEC, "a")
        for event in ("go", "go", "back", "back", "go"):
            machine.fire(event)
        want = ["a", "b", "c", "b", "a", "b"]
        assert machine.history() == want, (
            "args=%r got=%r want=%r" % ("go,go,back,back,go", machine.history(), want))
    _bank_entry(solution)
