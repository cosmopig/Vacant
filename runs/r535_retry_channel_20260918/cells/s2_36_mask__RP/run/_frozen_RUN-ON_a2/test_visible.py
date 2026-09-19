def mask(s, keep):
    if len(s) <= keep:
        return s
    readable = s[:keep]
    masked_part = s[keep:]
    masked_result = ""
    for i in range(0, len(masked_part), 2):
        if i + 1 < len(masked_part):
            masked_result += "*"
        else:
            masked_result += masked_part[i]
    return readable + masked_result

def test_mask():
    # Test case from the feedback
    args = ('1234567890', 4)
    got = mask(*args)
    want = '******7890'
    assert got == want, "mask args=%r got=%r want=%r" % (args, got, want)

if __name__ == "__main__":
    test_mask()
