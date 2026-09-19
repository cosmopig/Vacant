def is_palindrome(text: str) -> bool:
    filtered_chars = [char.lower() for char in text if char.isalnum()]
    return filtered_chars == filtered_chars[::-1]

if __name__ == "__main__":
    import sys
    input_data = sys.stdin.read()
    print(is_palindrome(input_data))
