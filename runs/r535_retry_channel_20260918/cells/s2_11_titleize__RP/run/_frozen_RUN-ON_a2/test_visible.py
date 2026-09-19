def titleize(s):
    words = s.split(' ')
    return ' '.join(word.capitalize() for word in words)

def check_01_titleize():
    args = ('the NASA report',)
    got = titleize(*args)
    want = 'The NASA Report'
    assert got == want, "titleize args=%r got=%r want=%r" % (args, got, want)

if __name__ == "__main__":
    check_01_titleize()
