# anchor_kind: contract
# anchor: raises `KeyError` whose single argument is the placeholder's name exactly
# as it was written
# derivation: when the walk stops half way down, the error names the whole dotted
# path and not just the segment that was missing.


def run(solution):
    template = "{{user.address.city}}"
    data = {"user": {"address": {"street": "Main"}}}
    try:
        solution.render(template, data)
    except KeyError as exc:
        assert exc.args[0] == "user.address.city", (
            "args=%r got=%r want=%r" % (template, exc.args[0], "user.address.city"))
        return
    raise AssertionError("args=%r got=%r want=%r" % (template, "rendered", "KeyError"))
