# anchor_kind: contract
# anchor: `select` checks every pattern it is given, whether or not anything matches
# it.
# derivation: a malformed pattern raises even when the file list is empty, and even
# when it sits behind an exclamation mark.


def run(solution):
    for patterns in (["*.py", "src/[abc.py"], ["!src/[].py"], ["[!].py"]):
        try:
            solution.select(patterns, [])
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (patterns, "answered", "ValueError"))
