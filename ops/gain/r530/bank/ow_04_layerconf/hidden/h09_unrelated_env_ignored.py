# anchor_kind: goal
# anchor: most of which have nothing to do with this program
# derivation: environment variables without the prefix must not touch the settings,
# even when their name after stripping would have matched.


def run(solution):
    defaults = {"port": 80, "home": "/srv"}
    env = {"PORT": "9999", "HOME": "/root", "PATH": "/bin", "APP_PORT": "8081"}
    config = solution.load(defaults, None, env)
    got = config.as_dict()
    want = {"port": 8081, "home": "/srv"}
    assert got == want, "args=%r got=%r want=%r" % (env, got, want)
    assert config.source("home") == "default", (
        "args=%r got=%r want=%r" % (env, config.source("home"), "default"))
