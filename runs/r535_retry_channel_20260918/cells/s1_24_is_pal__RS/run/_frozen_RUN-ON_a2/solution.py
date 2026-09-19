import re

def is_palindrome(text: str) -> bool:
    # Keep only letters and digits, convert to lowercase
    cleaned = "".join(char.lower() for char in text if char.isalnum())
    
    # Check if the cleaned string reads the same forwards and backwards
    return cleaned == cleaned[::-1]

if __name__ == "__main__":
    import sys
    # Read input from stdin (optional, but good for testing)
    # If the task implies a function only, we can just leave it.
    # However, usually these tasks expect some way to run or test.
    # Let's check if there are any specific requirements on how to call it.
    # The prompt says "Write the code in a file called solution.py".
    pass
