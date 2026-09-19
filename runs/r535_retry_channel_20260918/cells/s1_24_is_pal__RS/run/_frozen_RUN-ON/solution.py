import re

def is_palindrome(text):
    # Keep only letters and digits, convert to lowercase
    cleaned = "".join(char.lower() for char in text if char.isalnum())
    
    # Check if the cleaned string reads the same forwards and backwards
    return cleaned == cleaned[::-1]

if __name__ == "__main__":
    import sys
    # Read input from stdin (optional, but good practice)
    # For this task, we just need to provide the function.
    # However, since I'm writing a solution file, 
    # I'll make it take an argument or read from stdin if needed.
    # The prompt doesn't specify input method, so I'll assume 
    # a simple script that reads from standard input.
    input_text = sys.stdin.read()
    if input_text:
        print(is_palindrome(input_text))
