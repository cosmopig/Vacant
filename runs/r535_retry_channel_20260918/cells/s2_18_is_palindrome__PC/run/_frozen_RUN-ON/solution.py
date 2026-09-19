def is_palindrome(s):
    # Filter out non-alphanumeric characters and convert to lowercase
    filtered_chars = [char.lower() for char in s if char.isalnum()]
    
    # Check if the filtered list of characters is equal to its reverse
    return filtered_chars == filtered_chars[::-1]

if __name__ == "__main__":
    # Examples and testing
    test_cases = [
        ("A man, a plan, a canal: Panama", True),
        ("race a car", False),
        ("Was it a car or a cat I saw?", True),
        ("No 'x' in Nixon", True),
        ("12321", True),
        ("123456", False),
        (" ", True) # Empty string/only spaces are technically palindromes
    ]

    for text, expected in test_cases:
        result = is_palindrome(text)
        print(f"'{text}': {result} (Expected: {expected})")
