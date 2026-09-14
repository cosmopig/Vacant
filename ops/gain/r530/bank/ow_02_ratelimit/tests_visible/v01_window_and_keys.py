"""Visible check 1: the window slides, and callers are counted apart."""


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock()
    limiter = solution.RateLimiter(10.0, 2, clock)
    seen = []
    for moment in (0.0, 1.0, 2.0):
        clock.t = moment
        seen.append(limiter.allow("alice"))
    want = [True, True, False]
    assert seen == want, "args=%r got=%r want=%r" % ("allow('alice') at 0,1,2", seen, want)

    clock.t = 2.0
    got = limiter.allow("bob")
    assert got is True, "args=%r got=%r want=%r" % ("allow('bob') at 2.0", got, True)

    clock.t = 11.0
    got = limiter.allow("alice")
    assert got is True, "args=%r got=%r want=%r" % ("allow('alice') at 11.0", got, True)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_window_and_keys")
