def flip_words(s: str) -> str:
    """
    Takes a sentence and returns it with its words in the opposite order.
    Words are separated by whitespace on the way in, and by a single space 
    on the way out.
    """
    # Split the string into words based on any whitespace
    words = s.split()
    # Reverse the list of words
    reversed_words = words[::-1]
    # Join the reversed words with a single space
    return " ".join(reversed_words)

if __name__ == "__main__":
    # Example usage:
    print(flip_words("Hello world"))  # Expected output: "world Hello"
    print(flip_words("  This   is  a test  "))  # Expected output: "test a is This"
