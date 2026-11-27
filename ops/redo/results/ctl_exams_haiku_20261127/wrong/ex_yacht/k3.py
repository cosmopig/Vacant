YACHT = 1
ONES = 2
TWOS = 3
THREES = 4
FOURS = 5
FIVES = 6
SIXES = 7
FULL_HOUSE = 8
FOUR_OF_A_KIND = 9
LITTLE_STRAIGHT = 10
BIG_STRAIGHT = 11
CHOICE = 12


def score(dice, category):
    counts = {face: dice.count(face) for face in range(1, 7)}
    total = sum(dice)

    if category == YACHT:
        return 50 if len(set(dice)) == 1 else 0

    if category in (ONES, TWOS, THREES, FOURS, FIVES, SIXES):
        face = category - ONES + 1
        return face * counts[face]

    if category == FULL_HOUSE:
        if sorted(counts.values()) == [0, 0, 0, 0, 2, 3]:
            return float(total)
        return 0

    if category == FOUR_OF_A_KIND:
        for face, count in counts.items():
            if count >= 4:
                return face * 4
        return 0

    if category == LITTLE_STRAIGHT:
        return 30 if sorted(dice) == [1, 2, 3, 4, 5] else 0

    if category == BIG_STRAIGHT:
        return 30 if sorted(dice) == [2, 3, 4, 5, 6] else 0

    if category == CHOICE:
        return total

    return 0
