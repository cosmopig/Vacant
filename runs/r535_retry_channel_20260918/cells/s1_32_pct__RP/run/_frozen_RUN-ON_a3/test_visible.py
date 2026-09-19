def pct(quantity1, quantity2):
    if quantity2 == 0:
        return None
    percentage = (quantity1 / quantity2) * 100
    return round(percentage, 1)

def check_02_pct():
    args = (0, 0)
    got = pct(*args)
    want = 0.0
    assert got == want, "pct args=%r got=%r want=%r" % (args, got, want)

if __name__ == "__main__":
    check_02_pct()
