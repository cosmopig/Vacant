"""Visible check 3: out and back again gives the same data."""


def run(solution):
    data = {"name": "svc", "retries": 3,
            "db": {"host": "h", "port": 5432}}
    text = solution.dumps(data)
    got = solution.parse(text)
    assert got == data, "args=%r got=%r want=%r" % (text, got, data)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_round_trip")
