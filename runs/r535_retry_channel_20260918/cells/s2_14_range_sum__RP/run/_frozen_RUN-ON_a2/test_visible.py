def range_sum(a, b):
    pass

def check_02_range_sum():
    args = (5, 1)
    got = range_sum(*args)
    want = 0
    assert got == want, "range_sum args=%r got=%r want=%r" % (args, got, want)

if __name__ == "__main__":
    check_02_range_sum()
