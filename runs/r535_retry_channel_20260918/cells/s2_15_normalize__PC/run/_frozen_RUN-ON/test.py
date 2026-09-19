from solution import normalize

def test_normalize():
    assert normalize("") == ""
    assert normalize("/") == "/"
    assert normalize("//") == "/"
    assert normalize("///") == "/"
    assert normalize("/a//b/") == "/a/b"
    assert normalize("/a/b//c") == "/a/b/c"
    assert normalize("a//b") == "a/b"
    assert normalize("//a//b//") == "/a/b"
    assert normalize("///a///b///") == "/a/b"
    assert normalize("a/") == "a"
    assert normalize("a//") == "a"

if __name__ == "__main__":
    test_normalize()
    print("All tests passed!")
