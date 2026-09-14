# anchor_kind: goal
# anchor: Their settings file is grouped into sections
# derivation: a key under [db] is the setting db.something, and a key written
# before any section header stays at the top level.


def run(solution):
    defaults = {"name": "svc", "db.host": "127.0.0.1", "db.port": 5432, "log.path": "/tmp/l"}
    file_text = "name = billing\n[db]\nhost = db.internal\nport = 6000\n[log]\npath = /var/log/b\n"
    config = solution.load(defaults, file_text, {})
    got = config.as_dict()
    want = {"name": "billing", "db.host": "db.internal", "db.port": 6000, "log.path": "/var/log/b"}
    assert got == want, "args=%r got=%r want=%r" % (file_text, got, want)
