from solution import is_palindrome

def check_a():
    assert is_palindrome('A man, a plan, a canal: Panama')

def check_b():
    assert not is_palindrome('abc')
