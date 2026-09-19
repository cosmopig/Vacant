import sys

def is_palindrome(text: str) -> bool:
    # Keep only letters and digits, convert to lowercase
    cleaned = "".join(char.lower() for char in text if char.isalnum())
    
    # Check if the cleaned string reads the same forwards and backwards
    return cleaned == cleaned[::-1]

if __name__ == "__main__":
    input_data = sys.stdin.read().strip()
    print(is_palindrome(input_data))
