from solution import column

def test_column():
    rows = [{'a': 1}, {'b': 2}]
    field = 'a'
    expected = [1, None]
    got = column(rows, field)
    assert got == expected, f"Expected {expected}, but got {got}"
    print("Test passed!")

if __name__ == "__main__":
    test_column()
