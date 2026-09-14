# anchor_kind: contract
# anchor: `get` and `source` raise `KeyError` for a key that is not in `defaults`.
# derivation: asking about a setting that does not exist is a mistake worth
# reporting, not a None.


def run(solution):
    config = solution.load({"a": 1}, None, {})
    for method in ("get", "source"):
        try:
            getattr(config, method)("nope")
        except KeyError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (method + "('nope')", "no error", "KeyError"))
