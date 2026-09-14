"""Visible check 3: wiping one caller, and wiping everybody."""


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock(100.0)
    limiter = solution.RateLimiter(60.0, 1, clock)
    limiter.allow("x")
    limiter.allow("y")
    limiter.reset("x")
    got = limiter.allow("x")
    assert got is True, "args=%r got=%r want=%r" % ("allow('x') after reset('x')", got, True)
    got = limiter.allow("y")
    assert got is False, "args=%r got=%r want=%r" % ("allow('y') after reset('x')", got, False)

    limiter.reset()
    got = [limiter.allow("x"), limiter.allow("y")]
    assert got == [True, True], "args=%r got=%r want=%r" % ("allow after reset()", got, [True, True])

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_reset")
