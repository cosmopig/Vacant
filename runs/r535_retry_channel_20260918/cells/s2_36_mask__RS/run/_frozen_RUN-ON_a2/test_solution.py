from solution import mask

def test():
    assert mask("12345678", 2) == "12***"
    assert mask("ABCDE", 1) == "A**"
    assert mask("ABCDE", 5) == "ABCDE"
    assert mask("ABCDE", 6) == "ABCDE"
    print("All tests passed!")

if __name__ == "__main__":
    test()
