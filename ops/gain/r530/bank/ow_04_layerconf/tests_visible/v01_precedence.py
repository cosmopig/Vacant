"""Visible check 1: env beats file beats default."""


def run(solution):
    defaults = {"port": 8080, "host": "localhost", "retries": 3}
    file_text = "port = 9090\nhost = example.com\n"
    env = {"APP_PORT": "7000"}
    config = solution.load(defaults, file_text, env)
    got = (config.get("port"), config.get("host"), config.get("retries"))
    want = (7000, "example.com", 3)
    assert got == want, "args=%r got=%r want=%r" % ((defaults, file_text, env), got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_precedence")
