LETTER_VALUES = {}
for letters, value in (
    ("AEIOULNRST", 1),
    ("DG", 2),
    ("BCMP", 3),
    ("FHVWY", 4),
    ("K", 5),
    ("JX", 8),
    ("QZ", 10),
):
    for letter in letters:
        LETTER_VALUES[letter] = value


def score(word):
    if len(word) <= 1:
        return 0
    total = 0
    for letter in word.upper():
        total += LETTER_VALUES.get(letter, 0)
    return total
