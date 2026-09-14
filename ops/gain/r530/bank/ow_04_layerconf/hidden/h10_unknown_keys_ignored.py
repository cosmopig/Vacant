# anchor_kind: goal
# anchor: A typo in a setting name should be ignored rather than quietly adding a
# setting nobody reads
# derivation: a misspelled key in the file or the environment changes nothing and
# never appears in the returned settings.


def run(solution):
    defaults = {"retries": 3}
    file_text = "retires = 9\nretries = 4\n"
    env = {"APP_RETRYS": "77"}
    config = solution.load(defaults, file_text, env)
    got = config.as_dict()
    want = {"retries": 4}
    assert got == want, "args=%r got=%r want=%r" % ((file_text, env), got, want)
