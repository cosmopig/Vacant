import solution

def test():
    args1 = ('aabbb',)
    got1 = solution.longest_run(args1[0])
    want1 = {'ch': 'b', 'n': 3}
    assert got1 == want1, "longest_run args=%r got=%r want=%r" % (args1, got1, want1)

    args2 = ('aabb',)
    got2 = solution.longest_run(args2[0])
    want2 = {'ch': 'a', 'n': 2}
    assert got2 == want2, "longest_run args=%r got=%r want=%r" % (args2, got2, want2)

if __name__ == "__main__":
    test()
