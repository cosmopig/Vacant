def is_palindrome(s):
    # Remove non-alphanumeric characters and convert to lowercase
    cleaned = "".join(char.lower() for char in s if char.isalnum())
    # Check if the cleaned string is equal to its reverse
    return cleaned == cleaned[::-1]

if __name__ == "__main__":
    # Example usage:
    test_cases = [
        ("A man, a plan, a canal: Panama", True),
        ("race a car", False),
        ("Was it a car or a cat I saw?", True),
        ("No 'x' in Nixon", True),
        ("Hello World", False)
    ]

    for text, expected in test_cases:
        result = is_palindrome(text)
        print(f"'{text}': {result} (Expected: {expected})")
