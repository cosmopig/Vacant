def flip_words(sentence: str) -> str:
    """
    Takes a sentence and returns it with its words in the opposite order.
    Words are separated by whitespace on the way in, and by a single space on the way out.
    """
    words = sentence.split()
    return " ".join(reversed(words))
