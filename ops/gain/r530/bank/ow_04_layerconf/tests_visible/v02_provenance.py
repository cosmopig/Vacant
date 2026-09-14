"""Visible check 2: for any one setting, say where the value came from."""


def run(solution):
    defaults = {"port": 8080, "host": "localhost", "retries": 3}
    file_text = "host = example.com\n"
    env = {"APP_PORT": "7000"}
    config = solution.load(defaults, file_text, env)
    got = (config.source("port"), config.source("host"), config.source("retries"))
    want = ("env", "file", "default")
    assert got == want, "args=%r got=%r want=%r" % ((defaults, file_text, env), got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_provenance")
