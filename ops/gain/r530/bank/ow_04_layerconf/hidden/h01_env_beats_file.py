# anchor_kind: contract
# anchor: Precedence is env over file over default.
# derivation: when all three name the same setting the environment value is the one
# that survives.


def run(solution):
    defaults = {"level": "info"}
    file_text = "level = debug\n"
    env = {"APP_LEVEL": "warn"}
    config = solution.load(defaults, file_text, env)
    got = config.get("level")
    assert got == "warn", "args=%r got=%r want=%r" % ((file_text, env), got, "warn")
