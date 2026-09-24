def is_palindrome(text: str) -> bool:
    # Filter out non-alphanumeric characters and convert to lowercase
    filtered_chars = [char.lower() for char in text if char.isalnum()]
    
    # Check if the filtered list of characters reads the same forwards and backwards
    return filtered_chars == filtered_chars[::-1]

if __name__ == "__main__":
    import sys
    # Read input from stdin (assuming the input is provided as a single line or multiple lines)
    input_data = sys.stdin.read()
    print(is_palindrome(input_data))
