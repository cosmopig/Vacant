from solution import top_n

def test_top_n():
    args = ({'b': 2, 'a': 2, 'c': 1}, 2)
    got = top_n(*args)
    want = ['a', 'b']
    assert got == want, "top_n args=%r got=%r want=%r" % (args, got, want)

if __name__ == "__main__":
    test_top_n()
