# anchor_kind: contract
# anchor: A value that cannot be converted raises `ValueError`.
# derivation: a word where an integer is expected is a ValueError, from the file
# layer and from the environment layer alike.


def run(solution):
    defaults = {"port": 80}
    try:
        solution.load(defaults, "port = eighty\n", {})
    except ValueError:
        pass
    else:
        raise AssertionError("args=%r got=%r want=%r" % ("port = eighty", "no error", "ValueError"))

    try:
        solution.load(defaults, None, {"APP_PORT": "eighty"})
    except ValueError:
        return
    raise AssertionError("args=%r got=%r want=%r" % ({"APP_PORT": "eighty"}, "no error", "ValueError"))
