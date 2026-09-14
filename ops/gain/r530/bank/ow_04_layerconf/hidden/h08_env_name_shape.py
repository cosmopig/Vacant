# anchor_kind: contract
# anchor: After the prefix, `__` stands for `.` and the rest is lowercased, so
# `APP_DB__PORT` sets `db.port`.
# derivation: the capitals-and-underscores spelling has to map onto the dotted key,
# and the prefix itself is matched without regard to case.


def run(solution):
    defaults = {"db.port": 5432, "db.pool.size": 4}
    env = {"APP_DB__PORT": "6543", "app_db__pool__size": "16"}
    config = solution.load(defaults, None, env)
    got = config.as_dict()
    want = {"db.port": 6543, "db.pool.size": 16}
    assert got == want, "args=%r got=%r want=%r" % (env, got, want)
