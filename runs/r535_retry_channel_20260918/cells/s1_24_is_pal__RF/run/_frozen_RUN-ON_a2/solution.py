import re

def is_palindrome(text):
    # Remove all characters that are not letters or digits
    cleaned_text = "".join(char.lower() for char in text if char.isalnum())
    
    # Check if the cleaned text reads the same forwards and backwards
    return cleaned_text == cleaned_text[::-1]

if __name__ == "__main__":
    import sys
    input_text = sys.stdin.read()
    print(is_palindrome(input_text))
