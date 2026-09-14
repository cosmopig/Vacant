"""ow_15_tomlsub — hidden checks, 13. **Never enters a workspace.**

Generated from bank/ow_15_tomlsub/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_five_kinds():
    # anchor_kind: goal
    # anchor: The values they use are text, whole numbers, decimals, true and false, and
    # lists of one of those.
    # derivation: each kind arrives as its own Python type, and true is a boolean rather
    # than the word.


    def _bank_entry(solution):
        text = 's = "x"\ni = -12\nf = -0.5\nt = true\nlist = [1, 2, 3]\n'
        got = solution.parse(text)
        kinds = [type(got[name]).__name__ for name in ("s", "i", "f", "t", "list")]
        want = ["str", "int", "float", "bool", "list"]
        assert kinds == want, "args=%r got=%r want=%r" % (text, kinds, want)
        assert got["i"] == -12 and got["f"] == -0.5 and got["t"] is True, (
            "args=%r got=%r want=%r" % (text, (got["i"], got["f"], got["t"]), (-12, -0.5, True)))
    _bank_entry(solution)


def check_h02_escapes_in_text():
    # anchor_kind: goal
    # anchor: Text sometimes has to contain quotes, tabs and line breaks, written with a
    # backslash.
    # derivation: the four escapes turn into the characters they stand for, and nothing
    # else does.


    def _bank_entry(solution):
        text = 'a = "he said \\"no\\""\nb = "one\\ttwo"\nc = "line\\nline"\nd = "a\\\\b"\n'
        got = solution.parse(text)
        want = {"a": 'he said "no"', "b": "one\ttwo", "c": "line\nline", "d": "a\\b"}
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_h03_hash_inside_text():
    # anchor_kind: goal
    # anchor: a `#` inside a piece of text is not a comment
    # derivation: a hash inside quotes belongs to the value, while a hash after the
    # value still ends the line.


    def _bank_entry(solution):
        text = 'colour = "#ff0000"   # the brand red\ntag = "a#b#c"\n'
        got = solution.parse(text)
        want = {"colour": "#ff0000", "tag": "a#b#c"}
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_h04_nested_headings():
    # anchor_kind: goal
    # anchor: headings can be nested with dots
    # derivation: a dotted heading puts the names one level deeper, and the parent group
    # is created on the way.


    def _bank_entry(solution):
        text = '[a]\nx = 1\n\n[a.b]\ny = 2\n\n[a.b.c]\nz = 3\n'
        got = solution.parse(text)
        want = {"a": {"x": 1, "b": {"y": 2, "c": {"z": 3}}}}
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_h05_names_before_the_first_heading():
    # anchor_kind: contract
    # anchor: Names before the first heading live at the top level.
    # derivation: a name written above every heading stays at the top, and the same name
    # inside a group is a different setting.


    def _bank_entry(solution):
        text = 'host = "top"\n\n[db]\nhost = "inner"\n'
        got = solution.parse(text)
        want = {"host": "top", "db": {"host": "inner"}}
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_h06_mixed_list_is_a_mistake():
    # anchor_kind: goal
    # anchor: A list that mixes kinds is a mistake.
    # derivation: a list holding two different kinds raises, and the message says which
    # line it was on.


    def _bank_entry(solution):
        text = 'a = 1\nb = [1, "two"]\n'
        try:
            solution.parse(text)
        except ValueError as exc:
            assert str(exc).startswith("line 2: "), (
                "args=%r got=%r want=%r" % (text, str(exc), "line 2: ..."))
            return
        raise AssertionError("args=%r got=%r want=%r" % (text, "parsed", "ValueError"))
    _bank_entry(solution)


def check_h07_duplicate_name():
    # anchor_kind: goal
    # anchor: The same setting written twice in one group
    # derivation: the second appearance raises on its own line, while the same name in
    # two different groups is fine.


    def _bank_entry(solution):
        text = '[db]\nport = 1\nhost = "h"\nport = 2\n'
        try:
            solution.parse(text)
        except ValueError as exc:
            assert str(exc).startswith("line 4: "), (
                "args=%r got=%r want=%r" % (text, str(exc), "line 4: ..."))
        else:
            raise AssertionError("args=%r got=%r want=%r" % (text, "parsed", "ValueError"))

        fine = '[a]\nport = 1\n\n[b]\nport = 2\n'
        got = solution.parse(fine)
        assert got == {"a": {"port": 1}, "b": {"port": 2}}, (
            "args=%r got=%r want=%r" % (fine, got, {"a": {"port": 1}, "b": {"port": 2}}))
    _bank_entry(solution)


def check_h08_duplicate_heading():
    # anchor_kind: goal
    # anchor: or the same heading opened twice
    # derivation: reopening a group raises on the line that reopened it, even when the
    # names inside do not clash.


    def _bank_entry(solution):
        text = '[db]\nport = 1\n\n[db]\nhost = "h"\n'
        try:
            solution.parse(text)
        except ValueError as exc:
            assert str(exc).startswith("line 4: "), (
                "args=%r got=%r want=%r" % (text, str(exc), "line 4: ..."))
            return
        raise AssertionError("args=%r got=%r want=%r" % (text, "parsed", "ValueError"))
    _bank_entry(solution)


def check_h09_line_numbers_on_every_mistake():
    # anchor_kind: goal
    # anchor: Every mistake has to say which line it is on
    # derivation: several different kinds of malformed line each report the line they
    # are on, counting comments and blank lines.


    def _bank_entry(solution):
        cases = [('# note\n\na = 1\nthis is junk\n', "line 4: "),
                 ('a = 1\nb = \n', "line 2: "),
                 ('a = 1\nb = [1, 2\n', "line 2: "),
                 ('a = 1\n[unclosed\n', "line 2: "),
                 ('a = 1\nb = notaword\n', "line 2: ")]
        for text, prefix in cases:
            try:
                solution.parse(text)
            except ValueError as exc:
                assert str(exc).startswith(prefix), (
                    "args=%r got=%r want=%r" % (text, str(exc), prefix + "..."))
                continue
            raise AssertionError("args=%r got=%r want=%r" % (text, "parsed", "ValueError"))
    _bank_entry(solution)


def check_h10_round_trip_data():
    # anchor_kind: goal
    # anchor: Writing the data out and reading it back has to give the same data
    # derivation: data holding every kind, including text that needs escaping and a
    # nested group, survives a trip through the written form.


    def _bank_entry(solution):
        data = {"title": 'a "quoted"\ttitle', "n": -3, "f": 1.25, "yes": True, "no": False,
                "ports": [1, 2, 3], "words": ["a", "b"], "none": [],
                "outer": {"inner": {"deep": "yes"}, "k": 1}}
        written = solution.dumps(data)
        got = solution.parse(written)
        assert got == data, "args=%r got=%r want=%r" % (written, got, data)
    _bank_entry(solution)


def check_h11_round_trip_text():
    # anchor_kind: goal
    # anchor: writing out what was just read has to give the same text
    # derivation: written form is canonical, so a second pass through parse and dumps
    # changes nothing at all.


    def _bank_entry(solution):
        data = {"z": 1, "a": 2, "m": {"q": "x\"y", "b": [1, 2], "deep": {"k": True}}}
        once = solution.dumps(data)
        twice = solution.dumps(solution.parse(once))
        assert once == twice, "args=%r got=%r want=%r" % (data, twice, once)
        thrice = solution.dumps(solution.parse(twice))
        assert twice == thrice, "args=%r got=%r want=%r" % (data, thrice, twice)
    _bank_entry(solution)


def check_h12_written_order():
    # anchor_kind: contract
    # anchor: `dumps` writes the top-level names first in name order, then each heading
    # in name order with its own names in name order
    # derivation: whatever order the dictionary was built in, the written form is in
    # name order with the plain names above the headings.


    def _bank_entry(solution):
        data = {"zebra": 1, "apple": 2, "mango": {"b": 1, "a": 2}, "banana": {"x": 1}}
        written = solution.dumps(data)
        lines = [line for line in written.splitlines() if line]
        want = ["apple = 2", "zebra = 1", "[banana]", "x = 1", "[mango]", "a = 2", "b = 1"]
        assert lines == want, "args=%r got=%r want=%r" % (data, lines, want)
    _bank_entry(solution)


def check_h13_unwritable_data():
    # anchor_kind: contract
    # anchor: `dumps` raises `ValueError` for data it cannot write
    # derivation: each of the four named cases raises rather than producing text that
    # would not read back.


    def _bank_entry(solution):
        cases = [{"a": None}, {"a": {"b": set()}}, {"a": [1, "two"]}, {"a": [[1], [2]]},
                 {"has space": 1}, {"a": object()}]
        for data in cases:
            try:
                solution.dumps(data)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (data, "written", "ValueError"))
    _bank_entry(solution)
