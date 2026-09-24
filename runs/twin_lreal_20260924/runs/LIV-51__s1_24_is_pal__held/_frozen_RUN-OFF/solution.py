def is_palindrome(s: str) -> bool:
    # Filter out non-alphanumeric characters and convert to lowercase
    filtered_chars = [char.lower() for char in s if char.isalnum()]
    
    # Check if the filtered list of characters reads the same forwards and backwards
    return filtered_chars == filtered_chars[::-1]

if __name__ == "__main__":
    import sys
    input_text = sys.stdin.read()
    print(is_palindrome(input_text))
