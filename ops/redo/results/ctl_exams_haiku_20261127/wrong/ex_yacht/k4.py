from collections import Counter

YACHT = 0
ONES = 1
TWOS = 2
THREES = 3
FOURS = 4
FIVES = 5
SIXES = 6
FULL_HOUSE = 7
FOUR_OF_A_KIND = 8
LITTLE_STRAIGHT = 9
BIG_STRAIGHT = 10
CHOICE = 11


def score(dice, category):
    counts = Counter(dice)

    if category in (ONES, TWOS, THREES, FOURS, FIVES, SIXES):
        face = category
        return face * counts[face]

    if category == FULL_HOUSE:
        if len(counts) == 2:
            return sum(dice)
        return 0

    if category == FOUR_OF_A_KIND:
        face, n = counts.most_common(1)[0]
        if n >= 4:
            return 4 * face
        return 0

    if category == LITTLE_STRAIGHT:
        return 30 if sorted(dice) == [1, 2, 3, 4, 5] else 0

    if category == BIG_STRAIGHT:
        return 30 if sorted(dice) == [2, 3, 4, 5, 6] else 0

    if category == CHOICE:
        return sum(dice)

    if category == YACHT:
        return 50 if len(counts) == 1 else 0

    return 0
