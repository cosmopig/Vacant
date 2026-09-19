def tally(words):
    tally_dict = {}
    for word in words:
        lower_word = word.lower()
        tally_dict[lower_word] = tally_dict.get(lower_word, 0) + 1
    return tally_dict
