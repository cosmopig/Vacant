"""ow_10_dedupe — hidden checks, 13. **Never enters a workspace.**

Generated from bank/ow_10_dedupe/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_order_is_first_appearance():
    # anchor_kind: goal
    # anchor: in the order things first appeared
    # derivation: the position of a key in the result is decided by its first
    # occurrence, not by its last one and not by sorting.


    def _bank_entry(solution):
        records = [{"k": "z"}, {"k": "m"}, {"k": "a"}, {"k": "m"}, {"k": "z"}]
        got = [record["k"] for record in solution.dedupe(records, "k")]
        want = ["z", "m", "a"]
        assert got == want, "args=%r got=%r want=%r" % (records, got, want)
    _bank_entry(solution)


def check_h02_first_is_the_default():
    # anchor_kind: contract
    # anchor: The default is `"first"`.
    # derivation: calling without a policy behaves exactly like asking for the first
    # copy.


    def _bank_entry(solution):
        records = [{"k": 1, "v": "early"}, {"k": 1, "v": "late"}]
        implicit = solution.dedupe(records, "k")
        explicit = solution.dedupe(records, "k", "first")
        assert implicit == explicit == [{"k": 1, "v": "early"}], (
            "args=%r got=%r want=%r" % (records, implicit, [{"k": 1, "v": "early"}]))
    _bank_entry(solution)


def check_h03_last_replaces_wholesale():
    # anchor_kind: contract
    # anchor: `"last"` -- the latest copy's values are kept
    # derivation: the later copy replaces the earlier one entirely, so a field only the
    # earlier copy had does not survive.


    def _bank_entry(solution):
        records = [{"k": 1, "a": "keep?", "b": 2}, {"k": 1, "b": 3}]
        got = solution.dedupe(records, "k", "last")
        want = [{"k": 1, "b": 3}]
        assert got == want, "args=%r got=%r want=%r" % (records, got, want)
    _bank_entry(solution)


def check_h04_merge_takes_the_last_filled():
    # anchor_kind: contract
    # anchor: field by field, the value of the last copy that both has the field and
    # whose value is not `None`
    # derivation: across three copies each field independently takes the latest real
    # value it was given.


    def _bank_entry(solution):
        records = [{"k": 1, "a": "a1", "b": "b1"},
                   {"k": 1, "a": "a2"},
                   {"k": 1, "b": "b3"}]
        got = solution.dedupe(records, "k", "merge")
        want = [{"k": 1, "a": "a2", "b": "b3"}]
        assert got == want, "args=%r got=%r want=%r" % (records, got, want)
    _bank_entry(solution)


def check_h05_merge_gains_new_fields():
    # anchor_kind: contract
    # anchor: `"merge"` -- field by field
    # derivation: a field that only the later copy carries is added to the merged
    # record rather than dropped.


    def _bank_entry(solution):
        records = [{"k": "u", "name": "Bo"}, {"k": "u", "phone": "555"}]
        got = solution.dedupe(records, "k", "merge")
        want = [{"k": "u", "name": "Bo", "phone": "555"}]
        assert got == want, "args=%r got=%r want=%r" % (records, got, want)
    _bank_entry(solution)


def check_h06_none_never_overwrites():
    # anchor_kind: goal
    # anchor: A field that is present but empty of meaning counts as not filled in.
    # derivation: a later copy carrying None for a field must leave the real value that
    # came before it alone.


    def _bank_entry(solution):
        records = [{"k": "u", "email": "bo@example.com", "note": None},
                   {"k": "u", "email": None, "note": None}]
        got = solution.dedupe(records, "k", "merge")
        want = [{"k": "u", "email": "bo@example.com", "note": None}]
        assert got == want, "args=%r got=%r want=%r" % (records, got, want)
    _bank_entry(solution)


def check_h07_composite_key_order():
    # anchor_kind: contract
    # anchor: a list of field names making a composite key whose parts are compared in
    # the order given
    # derivation: two records are the same only when every named part agrees, so
    # swapping the values between the two fields makes a different record.


    def _bank_entry(solution):
        records = [{"a": 1, "b": 2, "v": "x"},
                   {"a": 2, "b": 1, "v": "y"},
                   {"a": 1, "b": 2, "v": "z"}]
        got = solution.dedupe(records, ["a", "b"])
        want = [{"a": 1, "b": 2, "v": "x"}, {"a": 2, "b": 1, "v": "y"}]
        assert got == want, "args=%r got=%r want=%r" % (records, got, want)
    _bank_entry(solution)


def check_h08_composite_parts_do_not_run_together():
    # anchor_kind: goal
    # anchor: two records that agree on only one of them are not the same thing
    # derivation: two records whose key parts would glue into the same text are still
    # different records, because the parts are compared separately.


    def _bank_entry(solution):
        records = [{"first": "ab", "second": "c", "v": 1},
                   {"first": "a", "second": "bc", "v": 2}]
        got = solution.dedupe(records, ["first", "second"])
        assert len(got) == 2, "args=%r got=%r want=%r" % (records, len(got), 2)
        assert [record["v"] for record in got] == [1, 2], (
            "args=%r got=%r want=%r" % (records, [record["v"] for record in got], [1, 2]))
    _bank_entry(solution)


def check_h09_missing_key_field():
    # anchor_kind: goal
    # anchor: A record that does not carry the field they are keying on is a data
    # problem they want to hear about, not something to skip quietly.
    # derivation: the missing field raises, and the error names the field, for the
    # single-field and the composite case alike.


    def _bank_entry(solution):
        records = [{"id": 1}, {"other": 2}]
        try:
            solution.dedupe(records, "id")
        except KeyError as exc:
            assert exc.args[0] == "id", "args=%r got=%r want=%r" % (records, exc.args[0], "id")
        else:
            raise AssertionError("args=%r got=%r want=%r" % (records, "returned", "KeyError"))

        records = [{"a": 1, "b": 2}, {"a": 1}]
        try:
            solution.dedupe(records, ["a", "b"])
        except KeyError as exc:
            assert exc.args[0] == "b", "args=%r got=%r want=%r" % (records, exc.args[0], "b")
            return
        raise AssertionError("args=%r got=%r want=%r" % (records, "returned", "KeyError"))
    _bank_entry(solution)


def check_h10_unknown_policy():
    # anchor_kind: goal
    # anchor: Asking for a way of resolving disagreements that does not exist is a
    # programming mistake and should say so.
    # derivation: anything outside the three names raises, including near misses and
    # the empty string.


    def _bank_entry(solution):
        for policy in ("newest", "First", "", "merge ", None):
            try:
                solution.dedupe([{"k": 1}], "k", policy)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (policy, "accepted", "ValueError"))
    _bank_entry(solution)


def check_h11_inputs_are_left_alone():
    # anchor_kind: goal
    # anchor: nothing they handed in may come back changed
    # derivation: after every policy the original dictionaries hold exactly what they
    # held before, and no dictionary in the result is one of them.


    def _bank_entry(solution):
        for policy in ("first", "last", "merge"):
            records = [{"k": "u", "a": 1, "b": None}, {"k": "u", "b": 2, "c": 3}]
            snapshot = [dict(record) for record in records]
            result = solution.dedupe(records, "k", policy)
            assert records == snapshot, "args=%r got=%r want=%r" % (policy, records, snapshot)
            for produced in result:
                for original in records:
                    assert produced is not original, (
                        "args=%r got=%r want=%r" % (policy, "an input dict", "a new dict"))
    _bank_entry(solution)


def check_h12_nothing_to_do():
    # anchor_kind: contract
    # anchor: The result holds one record per distinct key value
    # derivation: an empty list gives an empty list, and a list with no repeats comes
    # back in the same order with the same contents.


    def _bank_entry(solution):
        got = solution.dedupe([], "k")
        assert got == [], "args=%r got=%r want=%r" % ([], got, [])

        records = [{"k": 1, "v": "a"}, {"k": 2, "v": "b"}, {"k": 3, "v": "c"}]
        got = solution.dedupe(records, "k", "merge")
        assert got == records, "args=%r got=%r want=%r" % (records, got, records)
    _bank_entry(solution)


def check_h13_key_values_of_other_types():
    # anchor_kind: contract
    # anchor: `key` is a field name
    # derivation: the key value is whatever the field holds, so numbers and None are
    # key values in their own right and do not collide with their text form.


    def _bank_entry(solution):
        records = [{"k": 1, "v": "int"}, {"k": "1", "v": "str"}, {"k": None, "v": "none"},
                   {"k": 1, "v": "int again"}]
        got = solution.dedupe(records, "k")
        want = [{"k": 1, "v": "int"}, {"k": "1", "v": "str"}, {"k": None, "v": "none"}]
        assert got == want, "args=%r got=%r want=%r" % (records, got, want)
    _bank_entry(solution)
