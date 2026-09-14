# anchor_kind: goal
# anchor: Sometimes there is no settings file at all.
# derivation: passing None for the file must behave exactly like passing an empty
# one, with the environment still applied on top.


def run(solution):
    defaults = {"a": 1, "b": "x"}
    env = {"APP_B": "y"}
    none_config = solution.load(defaults, None, env)
    empty_config = solution.load(defaults, "", env)
    got = (none_config.as_dict(), none_config.source("a"))
    want = ({"a": 1, "b": "y"}, "default")
    assert got == want, "args=%r got=%r want=%r" % (env, got, want)
    assert none_config.as_dict() == empty_config.as_dict(), (
        "args=%r got=%r want=%r" % (env, none_config.as_dict(), empty_config.as_dict()))
