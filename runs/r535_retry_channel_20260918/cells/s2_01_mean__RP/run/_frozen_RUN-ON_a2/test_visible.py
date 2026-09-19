def mean(xs):
    if not xs:
        return 0
    return sum(xs) / len(xs)

def check_01_mean():
    args = ([1, 2, 4],)
    got = mean(*args)
    want = 2.333
    assert got == want, "mean args=%r got=%r want=%r" % (args, got, want)

if __name__ == "__main__":
    check_01_mean()
