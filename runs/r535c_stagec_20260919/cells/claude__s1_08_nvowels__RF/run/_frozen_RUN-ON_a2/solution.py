import sys

def count_vowels(text: str) -> int:
    """Count the number of vowels in a given string."""
    vowels = "aeiouAEIOU"
    count = 0
    for char in text:
        if char in vowels:
            count += 1
    return count

if __name__ == "__main__":
    # Read all input from standard input
    input_text = sys.stdin.read()
    print(count_vowels(input_text))
