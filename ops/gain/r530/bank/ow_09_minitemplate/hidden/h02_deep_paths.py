# anchor_kind: goal
# anchor: placeholders that can reach into nested data
# derivation: a dotted name walks down several levels of dictionaries, and
# whitespace inside the braces is not part of the name.


def run(solution):
    template = "{{ a.b.c.d }}"
    data = {"a": {"b": {"c": {"d": "deep"}}}}
    got = solution.render(template, data)
    assert got == "deep", "args=%r got=%r want=%r" % ((template, data), got, "deep")
