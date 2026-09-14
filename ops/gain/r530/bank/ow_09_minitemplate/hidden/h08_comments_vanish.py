# anchor_kind: goal
# anchor: leave a note in the template that does not appear in the output
# derivation: the comment contributes nothing, including when it sits inside a
# repeated block or contains words that look like a placeholder name.


def run(solution):
    template = "a{{! remember to ask about count }}b{{#each rows}}{{! inner }}{{.}}{{/each}}"
    data = {"rows": [1, 2]}
    got = solution.render(template, data)
    want = "ab12"
    assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
