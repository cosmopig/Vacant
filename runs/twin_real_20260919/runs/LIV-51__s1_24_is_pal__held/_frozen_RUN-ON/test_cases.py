def is_palindrome(text):
    filtered_chars = [char.lower() for char in text if char.isalnum()]
    return filtered_chars == filtered_chars[::-1]

test_cases = [
    ("A man, a plan, a canal: Panama", True),
    ("race a car", False),
    (" ", True),
    ("No 'x' in Nixon", True),
    ("Was it a car or a cat I saw?", True),
    ("12321", True),
    ("123456", False),
    ("!@#$%^&*()", True),
    ("Never odd or even", True),
    ("Hello World", False)
]

for text, expected in test_cases:
    result = is_palindrome(text)
    assert result == expected, f"Failed for '{text}': expected {expected}, got {result}"

print("All tests passed!")
