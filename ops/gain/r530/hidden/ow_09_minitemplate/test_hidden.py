"""ow_09_minitemplate — hidden checks, 13. **Never enters a workspace.**

Generated from bank/ow_09_minitemplate/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_values_become_text():
    # anchor_kind: contract
    # anchor: converted with `str()`
    # derivation: numbers, booleans and None all arrive as their str() form rather
    # than being rejected or formatted some other way.


    def _bank_entry(solution):
        template = "{{n}}|{{f}}|{{b}}|{{z}}"
        data = {"n": 42, "f": 1.5, "b": True, "z": None}
        got = solution.render(template, data)
        want = "42|1.5|True|None"
        assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
    _bank_entry(solution)


def check_h02_deep_paths():
    # anchor_kind: goal
    # anchor: placeholders that can reach into nested data
    # derivation: a dotted name walks down several levels of dictionaries, and
    # whitespace inside the braces is not part of the name.


    def _bank_entry(solution):
        template = "{{ a.b.c.d }}"
        data = {"a": {"b": {"c": {"d": "deep"}}}}
        got = solution.render(template, data)
        assert got == "deep", "args=%r got=%r want=%r" % ((template, data), got, "deep")
    _bank_entry(solution)


def check_h03_missing_path_names_itself():
    # anchor_kind: contract
    # anchor: raises `KeyError` whose single argument is the placeholder's name exactly
    # as it was written
    # derivation: when the walk stops half way down, the error names the whole dotted
    # path and not just the segment that was missing.


    def _bank_entry(solution):
        template = "{{user.address.city}}"
        data = {"user": {"address": {"street": "Main"}}}
        try:
            solution.render(template, data)
        except KeyError as exc:
            assert exc.args[0] == "user.address.city", (
                "args=%r got=%r want=%r" % (template, exc.args[0], "user.address.city"))
            return
        raise AssertionError("args=%r got=%r want=%r" % (template, "rendered", "KeyError"))
    _bank_entry(solution)


def check_h04_never_an_empty_string():
    # anchor_kind: goal
    # anchor: silently producing an empty string is what bit them last time
    # derivation: every way of missing a value -- a top-level name, a path through a
    # non-dictionary, a field of an item -- raises rather than rendering nothing.


    def _bank_entry(solution):
        cases = [("{{nope}}", {}), ("{{a.b}}", {"a": 5}),
                 ("{{#each xs}}{{.q}}{{/each}}", {"xs": [{"p": 1}]})]
        for template, data in cases:
            try:
                solution.render(template, data)
            except KeyError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % ((template, data), "rendered", "KeyError"))
    _bank_entry(solution)


def check_h05_item_itself():
    # anchor_kind: goal
    # anchor: they need both the item itself and its fields
    # derivation: a list of plain values is reached through the lone dot, with the
    # block text repeated around each one.


    def _bank_entry(solution):
        template = "{{#each words}}[{{.}}]{{/each}}"
        data = {"words": ["a", "bb", 3]}
        got = solution.render(template, data)
        want = "[a][bb][3]"
        assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
    _bank_entry(solution)


def check_h06_outer_names_inside_a_block():
    # anchor_kind: goal
    # anchor: they still need to reach the values that live outside the block
    # derivation: a name without a leading dot is looked up in the outer data even
    # while a block is being repeated.


    def _bank_entry(solution):
        template = "{{#each rows}}{{title}}:{{.n}} {{/each}}"
        data = {"title": "T", "rows": [{"n": 1}, {"n": 2}]}
        got = solution.render(template, data)
        want = "T:1 T:2 "
        assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
    _bank_entry(solution)


def check_h07_empty_list_leaves_nothing():
    # anchor_kind: goal
    # anchor: An empty list should leave nothing behind.
    # derivation: the block contributes no output at all, while the text around it is
    # still rendered.


    def _bank_entry(solution):
        template = "start|{{#each rows}}x{{.}}x{{/each}}|end"
        data = {"rows": []}
        got = solution.render(template, data)
        want = "start||end"
        assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
    _bank_entry(solution)


def check_h08_comments_vanish():
    # anchor_kind: goal
    # anchor: leave a note in the template that does not appear in the output
    # derivation: the comment contributes nothing, including when it sits inside a
    # repeated block or contains words that look like a placeholder name.


    def _bank_entry(solution):
        template = "a{{! remember to ask about count }}b{{#each rows}}{{! inner }}{{.}}{{/each}}"
        data = {"rows": [1, 2]}
        got = solution.render(template, data)
        want = "ab12"
        assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
    _bank_entry(solution)


def check_h09_literal_braces():
    # anchor_kind: goal
    # anchor: their templates sometimes have to print two literal braces
    # derivation: the escaped form renders as the braces themselves, the backslash
    # disappears, and what follows is ordinary text rather than a placeholder.


    def _bank_entry(solution):
        template = "\\{{name}} is how you write {{name}}"
        data = {"name": "Ann"}
        got = solution.render(template, data)
        want = "{{name}} is how you write Ann"
        assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
    _bank_entry(solution)


def check_h10_unclosed_placeholder():
    # anchor_kind: goal
    # anchor: a placeholder that is never closed
    # derivation: an opening brace pair with no closing one is a broken template and is
    # reported, not copied through.


    def _bank_entry(solution):
        for template in ("hello {{name", "{{a}} and {{b", "{{#each xs}}{{.}}"):
            try:
                solution.render(template, {"name": "x", "a": 1, "b": 2, "xs": [1]})
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (template, "rendered", "ValueError"))
    _bank_entry(solution)


def check_h11_no_repeat_inside_a_repeat():
    # anchor_kind: goal
    # anchor: a repeat inside a repeat
    # derivation: nesting the blocks is outside the language and is reported rather
    # than half-rendered.


    def _bank_entry(solution):
        template = "{{#each rows}}{{#each inner}}{{.}}{{/each}}{{/each}}"
        data = {"rows": [{"inner": [1]}], "inner": [1]}
        try:
            solution.render(template, data)
        except ValueError:
            return
        raise AssertionError("args=%r got=%r want=%r" % (template, "rendered", "ValueError"))
    _bank_entry(solution)


def check_h12_repeat_over_a_non_list():
    # anchor_kind: goal
    # anchor: a repeat over something that is not a list
    # derivation: a string or a dictionary is not a list, so repeating over one is a
    # template mistake rather than an iteration over characters or keys.


    def _bank_entry(solution):
        for value in ("abc", {"a": 1}, 7):
            template = "{{#each thing}}{{.}}{{/each}}"
            try:
                solution.render(template, {"thing": value})
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (value, "rendered", "ValueError"))
    _bank_entry(solution)


def check_h13_stray_closing_tag():
    # anchor_kind: goal
    # anchor: a closing repeat with nothing to close
    # derivation: a closing tag on its own, and an item reference outside any block,
    # are both template mistakes.


    def _bank_entry(solution):
        for template in ("text {{/each}} more", "{{.}}", "{{.field}}"):
            try:
                solution.render(template, {"field": 1})
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (template, "rendered", "ValueError"))
    _bank_entry(solution)
