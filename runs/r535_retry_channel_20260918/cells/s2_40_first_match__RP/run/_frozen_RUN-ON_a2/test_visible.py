def first_match(words, prefix):
    for word in words:
        if word.startswith(prefix):
            return word
    return None

def check_01_first_match():
    args = (['Apple', 'ant'], 'a')
    want = 'Apple'
    got = first_match(*args)
    assert got == want, "first_match args=%r got=%r want=%r" % (args, got, want)

if __name__ == "__main__":
    check_01_first_match()
