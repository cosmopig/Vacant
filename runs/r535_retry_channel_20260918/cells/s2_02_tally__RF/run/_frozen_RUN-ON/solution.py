def tally(words):
    """
    Takes a list of words and returns a dictionary mapping each word to its count,
    normalizing the words by converting them to lowercase.
    """
    tally_dict = {}
    for word in words:
        # Normalize to lowercase as per "the same word turns up written in more than one way"
        normalized_word = word.lower()
        tally_dict[normalized_word] = tally_dict.get(normalized_word, 0) + 1
    return tally_dict

if __name__ == "__main__":
    # Example usage:
    words = ["Apple", "apple", "Banana", "BANANA", "orange"]
    print(tally(words))
