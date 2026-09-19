from solution import initials

def check_01_initials():
    args = ('ada lovelace',)
    got = initials(*args)
    want = ['A', 'L']
    assert got == want, "initials args=%r got=%r want=%r" % (args, got, want)

def check_02_initials():
    args = ('Grace Brewster Hopper',)
    got = initials(*args)
    want = ['G', 'B', 'H']
    assert got == want, "initials args=%r got=%r want=%r" % (args, got, want)

if __name__ == "__main__":
    check_01_initials()
    check_02_initials()
