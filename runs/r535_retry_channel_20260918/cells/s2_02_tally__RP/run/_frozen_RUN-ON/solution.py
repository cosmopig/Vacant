def tally(words):
    """
    Takes a list of words and returns a dictionary mapping each word to its count,
    normalizing for common variations (e.g., capitalization).
    """
    tally_dict = {}
    for word in words:
        # Normalize the word to lowercase to handle different capitalizations
        normalized_word = word.lower()
        tally_dict[normalized_word] = tally_dict.get(normalized_word, 0) + 1
    return tally_dict

# Example usage:
if __name__ == "__main__":
    words = ["Apple", "apple", "Banana", "BANANA", "orange"]
    print(tally(words))
