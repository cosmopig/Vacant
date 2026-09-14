# anchor_kind: goal
# anchor: Some of their values contain an equals sign.
# derivation: only the first equals sign separates the key from the value, so the
# rest of the line arrives intact.


def run(solution):
    defaults = {"dsn": ""}
    file_text = "dsn = postgres://u:p@h/db?sslmode=require&x=1\n"
    got = solution.load(defaults, file_text, {}).get("dsn")
    want = "postgres://u:p@h/db?sslmode=require&x=1"
    assert got == want, "args=%r got=%r want=%r" % (file_text, got, want)
