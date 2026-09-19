from solution import is_palindrome

def test():
    assert is_palindrome("A man, a plan, a canal: Panama") == True
    assert is_palindrome("race a car") == False
    assert is_palindrome(" ") == True
    assert is_palindrome("No 'x' in Nixon") == True
    assert is_palindrome("Was it a car or a cat I saw?") == True
    assert is_palindrome("12321") == True
    assert is_palindrome("123456") == False
    assert is_palindrome("0P") == False
    print("All tests passed!")

if __name__ == "__main__":
    test()
